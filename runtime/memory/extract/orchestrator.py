from __future__ import annotations

import json
import logging

from runtime.memory.apply.memory_updater import MemoryUpdater
from runtime.memory.apply.patch_handler import PatchHandler
from runtime.memory.base.contracts import (
    ExtractOperationsPhaseResult,
    MemoryCommittedResult,
    MemorySourceRef,
    MemoryUpdateContext,
    NavigationPlanningPreview,
    NavigationRefreshResult,
    OrchestratorAction,
    OrchestratorWorkingState,
    PatchPlanResult,
    PreparedExtractContext,
    ReasoningTraceStep,
)
from runtime.memory.base.enums import MemoryTaskPhase, OrchestratorStep
from runtime.memory.navigation.navigation_manager import NavigationManager
from runtime.memory.project.manager import ProjectMemoryManager

from ..schema.registry import MemorySchemaRegistry
from .planner import LLMPlanner
from .tools import SUPPORTED_PLANNER_TOOLS, PlannerToolExecutor

logger = logging.getLogger(__name__)


class ReActOrchestrator:
    MAX_TURNS = 8

    def __init__(self, prepared: PreparedExtractContext) -> None:
        self.prepared = prepared
        self.registry = MemorySchemaRegistry.load()
        self.planner = LLMPlanner(prepared=self.prepared, registry=self.registry)
        self.tool_executor = PlannerToolExecutor()
        self.navigation_manager = NavigationManager()
        self.patch_handler = PatchHandler()
        self.project_memory_manager = ProjectMemoryManager()

    def run(self) -> ExtractOperationsPhaseResult:
        return self.run_extract_phase()

    def run_extract_phase(self) -> ExtractOperationsPhaseResult:
        if str(self.prepared.source_ref.type or "").strip() == "project_memory_import":
            return ExtractOperationsPhaseResult(
                task_id=self.prepared.task_id,
                planner_status="noop",
                tools_available=list(SUPPORTED_PLANNER_TOOLS),
                tools_used=[],
            )

        working_state = OrchestratorWorkingState(
            prefetched_read_paths=sorted(self.prepared.prefetched_read_paths()),
        )

        try:
            for _turn in range(self.MAX_TURNS):
                action = self.planner.next_action(working_state=working_state)
                if action.action == "request_tools":
                    for request in action.tool_requests:
                        tool_result = self.tool_executor.execute_sync(request)
                        working_state.apply_tool_result(tool_result)
                    continue
                if action.action == "update_state":
                    self._apply_state_action(working_state, action)
                    continue
                if action.action == "stop_noop":
                    self._validate_noop_ready(working_state)
                    return self._build_phase_result(
                        planner_status="noop",
                        working_state=working_state,
                    )
                if action.action == "finalize":
                    self._validate_finalize_ready(working_state)
                    return self._build_phase_result(
                        planner_status="planned",
                        working_state=working_state,
                    )
            raise ValueError("react orchestrator exceeded maximum turns")
        except Exception as exc:
            logger.warning("memory_react_orchestrator failed: %s", exc)
            return ExtractOperationsPhaseResult(
                task_id=self.prepared.task_id,
                planner_status="planner_failed",
                tools_available=list(SUPPORTED_PLANNER_TOOLS),
                tools_used=working_state.tool_results,
                planner_error=str(exc),
            )

    def run_apply_coordination_phase(
        self,
        *,
        update_ctx: MemoryUpdateContext,
    ) -> MemoryCommittedResult:
        updater = MemoryUpdater(update_ctx, patch_handler=self.patch_handler)
        project_memory_plan = self._build_project_memory_plan(update_ctx=update_ctx)
        preview_resolve_result = updater.resolve_document_operations(project_memory_plan=project_memory_plan)
        preview_patch_plan_result = self.patch_handler.build_staged_write_set(
            update_ctx=update_ctx,
            resolve_result=preview_resolve_result,
        )
        patch_apply_result = None
        try:
            navigation_preview = self._build_navigation_preview(
                update_ctx=update_ctx,
                patch_plan=preview_patch_plan_result,
            )
            navigation_summary_result = self.navigation_manager.generate_navigation_summary(
                update_ctx=update_ctx,
                planning_preview=navigation_preview,
            )
            unified_resolve_result = updater.resolve_document_operations(
                navigation_summary_result=navigation_summary_result,
                project_memory_plan=project_memory_plan,
            )
            unified_patch_plan_result = self.patch_handler.build_staged_write_set(
                update_ctx=update_ctx,
                resolve_result=unified_resolve_result,
            )
            patch_apply_result = self.patch_handler.apply_files(
                update_ctx=update_ctx,
                patch_plan=unified_patch_plan_result,
            )
            navigation_refresh_result = NavigationRefreshResult(
                task_id=update_ctx.task_id,
                navigation_files=[
                    item.target_path
                    for item in unified_patch_plan_result.document_mutations
                    if item.document_family == "navigation"
                ],
            )
            metadata_result = self.navigation_manager.refresh_metadata(
                update_ctx=update_ctx,
                patch_plan=unified_patch_plan_result,
            )
        except Exception as exc:
            raise RuntimeError(
                json.dumps(
                    {
                        "phase": str(MemoryTaskPhase.MEMORY_UPDATER),
                        "journal_ref": None if patch_apply_result is None else patch_apply_result.journal_ref,
                        "rollback_metadata": {} if patch_apply_result is None else patch_apply_result.rollback_metadata,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            ) from exc
        return updater.commit(
            resolve_result=unified_resolve_result,
            patch_plan_result=unified_patch_plan_result,
            patch_apply_result=patch_apply_result,
            navigation_summary_result=navigation_summary_result,
            navigation_refresh_result=navigation_refresh_result,
            metadata_result=metadata_result,
        )

    @staticmethod
    def _build_navigation_planning_preview(
        *,
        task_id: str,
        patch_plan: PatchPlanResult,
    ) -> NavigationPlanningPreview:
        return NavigationPlanningPreview(
            task_id=task_id,
            navigation_targets=[item.model_copy(deep=True) for item in patch_plan.navigation_targets],
            memory_document_previews=[
                item.model_copy(deep=True)
                for item in patch_plan.document_mutations
                if item.document_family == "memory"
            ],
        )

    def _build_navigation_preview(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
    ) -> NavigationPlanningPreview:
        source_ref = update_ctx.source_ref
        if str(source_ref.type or "").strip() != "project_memory_import":
            return self._build_navigation_planning_preview(
                task_id=update_ctx.task_id,
                patch_plan=patch_plan,
            )

        plan = self._build_project_memory_plan(update_ctx=update_ctx)
        return self.project_memory_manager. build_navigation_preview_from_plan(
            task_id=update_ctx.task_id,
            plan=plan,
        )

    def _build_project_memory_plan(self, *, update_ctx: MemoryUpdateContext):
        source_ref = MemorySourceRef.model_validate(update_ctx.source_ref.model_dump(mode="python", exclude_none=True))
        if str(source_ref.type or "").strip() != "project_memory_import":
            return None
        scope = self.project_memory_manager.build_scope(
            user_id=str(update_ctx.user_id or "").strip(),
            project_id=str(update_ctx.project_id or source_ref.project_id or "").strip(),
        )
        return self.project_memory_manager.plan_import(
            scope=scope,
            source_ref=source_ref,
        )

    def _build_phase_result(
        self,
        *,
        planner_status: str,
        working_state: OrchestratorWorkingState,
    ) -> ExtractOperationsPhaseResult:
        return ExtractOperationsPhaseResult(
            task_id=self.prepared.task_id,
            planner_status=planner_status,
            change_plan=working_state.finalized_change_plan(),
            structured_operations=working_state.finalized_operations(),
            tools_available=list(SUPPORTED_PLANNER_TOOLS),
            tools_used=working_state.tool_results,
            reasoning_trace=self._build_reasoning_trace(working_state),
        )

    @staticmethod
    def _apply_state_action(
        working_state: OrchestratorWorkingState,
        action: OrchestratorAction,
    ) -> None:
        if action.step is None or action.state_delta is None:
            raise ValueError("update_state action requires step and state_delta")
        working_state.apply_state_delta(step=action.step, state_delta=action.state_delta)

    @staticmethod
    def _validate_noop_ready(working_state: OrchestratorWorkingState) -> None:
        if working_state.targets or working_state.planning_complete:
            raise ValueError("react orchestrator cannot stop_noop after planning state exists")

    @staticmethod
    def _validate_finalize_ready(working_state: OrchestratorWorkingState) -> None:
        if not working_state.planning_complete:
            raise ValueError("react orchestrator cannot finalize before planning_complete")
        awaiting_read = working_state.next_target_awaiting_read()
        if awaiting_read is not None:
            raise ValueError(
                "react orchestrator cannot finalize with pending read target: " + awaiting_read.target_key
            )
        ready_for_operation = working_state.next_target_ready_for_operation()
        if ready_for_operation is not None:
            raise ValueError(
                "react orchestrator cannot finalize with pending operation target: " + ready_for_operation.target_key
            )

    @staticmethod
    def _build_reasoning_trace(
        working_state: OrchestratorWorkingState,
    ) -> list[ReasoningTraceStep]:
        return [
            ReasoningTraceStep(
                step=OrchestratorStep.CHANGE_PLAN,
                metadata={
                    "target_count": len(working_state.targets),
                    "planning_complete": working_state.planning_complete,
                },
            ),
            ReasoningTraceStep(
                step=OrchestratorStep.OPERATIONS,
                metadata={
                    "operation_count": len(working_state.finalized_operations()),
                    "awaiting_read_count": len(
                        [item for item in working_state.targets if item.status == "awaiting_read"]
                    ),
                    "ready_for_operation_count": len(
                        [item for item in working_state.targets if item.status == "ready_for_operation"]
                    ),
                    "operated_count": len([item for item in working_state.targets if item.status == "operated"]),
                },
            ),
        ]
