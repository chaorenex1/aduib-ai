from __future__ import annotations

import logging

from service.memory.base.contracts import (
    ExtractOperationsPhaseResult,
    MemoryWritePipelineContext,
    OrchestratorAction,
    OrchestratorWorkingState,
    PreparedExtractContext,
    ReasoningTraceStep,
)
from service.memory.base.enums import OrchestratorStep

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
                if action.action == "update_state":
                    self._apply_state_action(working_state, action)
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
    def _apply_state_action(
        working_state: OrchestratorWorkingState,
        action: OrchestratorAction,
    ) -> None:
        if action.step is None or action.state_delta is None:
            raise ValueError("update_state action requires step and state_delta")
        working_state.apply_state_delta(step=action.step, state_delta=action.state_delta)

    @staticmethod
    def _build_reasoning_trace(
        working_state: OrchestratorWorkingState,
    ) -> list[ReasoningTraceStep]:
        return [
            ReasoningTraceStep(
                step=OrchestratorStep.CHANGE_PLAN,
                metadata={
                    "identified_memory_count": len(working_state.identified_memories),
                    "planned_change_count": len(working_state.change_plan),
                },
            ),
            ReasoningTraceStep(
                step=OrchestratorStep.OPERATIONS,
                metadata={"operation_count": len(working_state.operations)},
            ),
            ReasoningTraceStep(
                step=OrchestratorStep.SUMMARY,
                metadata={"summary_count": len(working_state.summary_plan)},
            ),
        ]


def run_memory_react_orchestrator(context: MemoryWritePipelineContext) -> ExtractOperationsPhaseResult:
    return ReActOrchestrator(context).run()
