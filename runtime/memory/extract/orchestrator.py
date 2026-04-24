from __future__ import annotations

import logging

from service.memory.base.contracts import (
    ExtractOperationsPhaseResult,
    L0L1SummaryResult,
    MemoryChangePlanResult,
    MemoryWritePipelineContext,
    OrchestratorWorkingState,
    PreparedExtractContext,
    ReasoningTraceStep,
)

from ..schema.registry import MemorySchemaRegistry
from .planner import LLMPlanner
from .tools import SUPPORTED_PLANNER_TOOLS, PlannerToolExecutor

logger = logging.getLogger(__name__)


class ReActOrchestrator:
    MAX_TURNS = 8

    def __init__(self, context: MemoryWritePipelineContext) -> None:
        self.context = context
        self.prepared = PreparedExtractContext.model_validate(
            context.phase_results.get("prepare_extract_context") or {}
        )
        self.registry = MemorySchemaRegistry.load()
        self.planner = LLMPlanner(prepared=self.prepared, registry=self.registry)
        self.tool_executor = PlannerToolExecutor()

    def run(self) -> ExtractOperationsPhaseResult:
        working_state = OrchestratorWorkingState()

        try:
            for _turn in range(self.MAX_TURNS):
                action = self.planner.next_action(working_state=working_state)
                if action.action == "request_tools":
                    for request in action.tool_requests:
                        tool_result = self.tool_executor.execute_sync(request)
                        working_state.tool_results.append(tool_result)
                    continue
                if action.action == "update_change_plan":
                    change_plan = action.change_plan or MemoryChangePlanResult()
                    working_state.identified_memories = list(change_plan.identified_memories)
                    working_state.change_plan = list(change_plan.change_plan)
                    self._mark_completed(working_state, "change_plan")
                    continue
                if action.action == "update_operations":
                    working_state.operations = list((action.operations or []).operations)
                    self._mark_completed(working_state, "operations")
                    continue
                if action.action == "update_summary":
                    self._upsert_summary(working_state, action.summary)
                    if not working_state.pending_summary_branches():
                        self._mark_completed(working_state, "summary")
                    continue
                if action.action == "stop_noop":
                    return self._build_phase_result(
                        planner_status="noop",
                        working_state=working_state,
                    )
                if action.action == "finalize":
                    return self._build_phase_result(
                        planner_status="planned",
                        working_state=working_state,
                    )
            raise ValueError("react orchestrator exceeded maximum turns")
        except Exception as exc:
            logger.warning("memory_react_orchestrator failed: %s", exc)
            return ExtractOperationsPhaseResult(
                task_id=self.context.task_id,
                planner_status="planner_failed",
                tools_available=list(SUPPORTED_PLANNER_TOOLS),
                tools_used=working_state.tool_results,
                planner_error=str(exc),
            )

    def _build_phase_result(
        self,
        *,
        planner_status: str,
        working_state: OrchestratorWorkingState,
    ) -> ExtractOperationsPhaseResult:
        return ExtractOperationsPhaseResult(
            task_id=self.context.task_id,
            planner_status=planner_status,
            identified_memories=working_state.identified_memories,
            change_plan=working_state.change_plan,
            structured_operations=working_state.operations,
            summary_plan=working_state.summary_plan,
            tools_available=list(SUPPORTED_PLANNER_TOOLS),
            tools_used=working_state.tool_results,
            reasoning_trace=self._build_reasoning_trace(working_state),
        )

    @staticmethod
    def _upsert_summary(
        working_state: OrchestratorWorkingState,
        summary: L0L1SummaryResult | None,
    ) -> None:
        if summary is None:
            return
        working_state.summary_plan = [
            item for item in working_state.summary_plan if item.branch_path != summary.branch_path
        ] + [summary]

    @staticmethod
    def _mark_completed(working_state: OrchestratorWorkingState, step: str) -> None:
        if step not in working_state.completed_steps:
            working_state.completed_steps.append(step)

    @staticmethod
    def _build_reasoning_trace(
        working_state: OrchestratorWorkingState,
    ) -> list[ReasoningTraceStep]:
        return [
            ReasoningTraceStep(
                step="change_plan",
                metadata={
                    "identified_memory_count": len(working_state.identified_memories),
                    "planned_change_count": len(working_state.change_plan),
                },
            ),
            ReasoningTraceStep(
                step="operation_generation",
                metadata={"operation_count": len(working_state.operations)},
            ),
            ReasoningTraceStep(
                step="summary_generation",
                metadata={"summary_count": len(working_state.summary_plan)},
            ),
        ]


def run_memory_react_orchestrator(context: MemoryWritePipelineContext) -> ExtractOperationsPhaseResult:
    return ReActOrchestrator(context).run()
