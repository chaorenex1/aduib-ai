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
)

logger = logging.getLogger(__name__)


class LLMPlanner:
    def __init__(self, *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> None:
        self.prepared = prepared
        self.registry = registry
        self.prompt_composer = ExtractPromptComposer(prepared=prepared, registry=registry)

    def request_change_plan(self, *, tool_results: list | None = None) -> ChangePlanStepResult:
        raw = self._invoke(
            messages=self.prompt_composer.build_change_plan_messages(tool_results=tool_results),
        )
        return parse_memory_change_plan_step_output(raw)

    def next_action(self, *, working_state: OrchestratorWorkingState) -> OrchestratorAction:
        if "change_plan" not in working_state.completed_steps:
            step_result = self.request_change_plan(tool_results=working_state.tool_results)
            if step_result.tool_requests:
                return OrchestratorAction(action="request_tools", tool_requests=step_result.tool_requests)
            change_plan = step_result.change_plan or MemoryChangePlanResult()
            if not change_plan.identified_memories and not change_plan.change_plan:
                return OrchestratorAction(action="stop_noop")
            return OrchestratorAction(action="update_change_plan", change_plan=change_plan)

        if "operations" not in working_state.completed_steps:
            operations = self.generate_operations(
                change_plan=MemoryChangePlanResult(
                    identified_memories=working_state.identified_memories,
                    change_plan=working_state.change_plan,
                )
            )
            return OrchestratorAction(action="update_operations", operations=operations)

        pending_summary_branches = working_state.pending_summary_branches()
        if pending_summary_branches:
            summary = self.generate_l0_l1_summary(
                change_plan=MemoryChangePlanResult(
                    identified_memories=working_state.identified_memories,
                    change_plan=working_state.change_plan,
                ),
                operations=MemoryOperationGenerationResult(operations=working_state.operations),
                branch_path=pending_summary_branches[0],
            )
            return OrchestratorAction(action="update_summary", summary=summary)

        return OrchestratorAction(action="finalize")

    def generate_operations(self, *, change_plan: MemoryChangePlanResult) -> MemoryOperationGenerationResult:
        raw = self._invoke(
            messages=self.prompt_composer.build_operation_generation_messages(change_plan=change_plan),
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
                change_plan=change_plan,
                operations=operations,
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
