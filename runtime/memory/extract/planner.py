from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.model_manager import ModelManager
from service.memory.base.contracts import (
    ChangePlanStepResult,
    L0L1SummaryResult,
    MemoryChangePlanResult,
    MemoryOperationGenerationResult,
    OrchestratorAction,
    OrchestratorWorkingState,
    PreparedExtractContext,
)

from ..schema.registry import MemorySchemaRegistry
from .prompts import ExtractPromptComposer
from .structured_output import (
    parse_l0_l1_summary_output,
    parse_memory_change_plan_step_output,
    parse_memory_operation_generation_output,
    parse_memory_operation_step_output,
    parse_summary_step_output,
)

logger = logging.getLogger(__name__)


class LLMPlanner:
    def __init__(self, *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> None:
        self.prepared = prepared
        self.registry = registry
        self.prompt_composer = ExtractPromptComposer(prepared=prepared, registry=registry)

    def request_change_plan(self, *, working_state: OrchestratorWorkingState) -> ChangePlanStepResult:
        raw = self._invoke(
            messages=self.prompt_composer.build_change_plan_messages(
                working_state=working_state,
                tool_results=working_state.tool_results,
            ),
        )
        return parse_memory_change_plan_step_output(raw)

    def next_action(self, *, working_state: OrchestratorWorkingState) -> OrchestratorAction:
        if "change_plan" not in working_state.completed_steps:
            step_result = self.request_change_plan(working_state=working_state)
            if step_result.tool_requests:
                return OrchestratorAction(action="request_tools", tool_requests=step_result.tool_requests)
            change_plan = step_result.change_plan or MemoryChangePlanResult()
            if not change_plan.identified_memories and not change_plan.change_plan:
                return OrchestratorAction(action="stop_noop")
            return OrchestratorAction(action="update_change_plan", change_plan=change_plan)

        if "operations" not in working_state.completed_steps:
            return self.request_operation_step(working_state=working_state)

        pending_summary_branches = working_state.pending_summary_branches()
        if pending_summary_branches:
            return self.request_summary_step(
                working_state=working_state,
                branch_path=pending_summary_branches[0],
            )

        return OrchestratorAction(action="finalize")

    def request_operation_step(self, *, working_state: OrchestratorWorkingState) -> OrchestratorAction:
        raw = self._invoke(
            messages=self.prompt_composer.build_operation_generation_messages(
                working_state=working_state,
                tool_results=working_state.tool_results,
            ),
        )
        tool_requests, operations = parse_memory_operation_step_output(raw)
        if tool_requests:
            return OrchestratorAction(action="request_tools", tool_requests=tool_requests)
        return OrchestratorAction(action="update_operations", operations=operations)

    def request_summary_step(
        self,
        *,
        working_state: OrchestratorWorkingState,
        branch_path: str,
    ) -> OrchestratorAction:
        raw = self._invoke(
            messages=self.prompt_composer.build_l0_l1_summary_messages(
                working_state=working_state,
                branch_path=branch_path,
                tool_results=working_state.tool_results,
            )
        )
        tool_requests, summary = parse_summary_step_output(raw)
        if tool_requests:
            return OrchestratorAction(action="request_tools", tool_requests=tool_requests)
        return OrchestratorAction(action="update_summary", summary=summary)

    def generate_operations(self, *, change_plan: MemoryChangePlanResult) -> MemoryOperationGenerationResult:
        raw = self._invoke(
            messages=self.prompt_composer.build_operation_generation_messages(
                working_state=OrchestratorWorkingState(
                    identified_memories=change_plan.identified_memories,
                    change_plan=change_plan.change_plan,
                ),
            ),
        )
        return parse_memory_operation_generation_output(raw)

    def generate_l0_l1_summary(
        self,
        *,
        change_plan: MemoryChangePlanResult,
        operations: MemoryOperationGenerationResult,
        branch_path: str,
    ) -> L0L1SummaryResult:
        raw = self._invoke(
            messages=self.prompt_composer.build_l0_l1_summary_messages(
                working_state=OrchestratorWorkingState(
                    identified_memories=change_plan.identified_memories,
                    change_plan=change_plan.change_plan,
                    operations=operations.operations,
                ),
                branch_path=branch_path,
            )
        )
        return parse_l0_l1_summary_output(raw)

    def _invoke(self, *, messages: list) -> str:
        try:
            model_manager = ModelManager()
            model_instance = (
                model_manager.get_planner_model_instance() or model_manager.get_default_model_instance("llm")
            )
        except Exception as exc:
            logger.warning("memory planner model unavailable: %s", exc)
            return ""
        if model_instance is None:
            return ""

        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        response = model_instance.invoke_llm_sync(
            prompt_messages=request,
            user=self.prepared.user_id,
        )
        return str(response.message.content or "").strip()


def extract_operations(context):
    from .orchestrator import run_memory_react_orchestrator

    return run_memory_react_orchestrator(context)
