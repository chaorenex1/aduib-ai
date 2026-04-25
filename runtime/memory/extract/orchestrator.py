from __future__ import annotations

import logging

from runtime.memory.base.contracts import (
    ExtractOperationsPhaseResult,
    OrchestratorAction,
    OrchestratorWorkingState,
    PreparedExtractContext,
    ReasoningTraceStep,
)
from runtime.memory.base.enums import OrchestratorStep

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

    def run(self) -> ExtractOperationsPhaseResult:
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
