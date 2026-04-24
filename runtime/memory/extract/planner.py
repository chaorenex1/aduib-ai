from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.model_manager import ModelManager
from service.memory.base.contracts import OrchestratorAction, OrchestratorWorkingState, PreparedExtractContext
from service.memory.base.enums import OrchestratorStep

from ..schema.registry import MemorySchemaRegistry
from .prompts import ExtractPromptComposer
from .structured_output import parse_step_action

logger = logging.getLogger(__name__)


class LLMPlanner:
    def __init__(self, *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> None:
        self.prepared = prepared
        self.registry = registry
        self.prompt_composer = ExtractPromptComposer(prepared=prepared, registry=registry)

    def next_action(self, *, working_state: OrchestratorWorkingState) -> OrchestratorAction:
        step, branch_path = self._select_next_step(working_state=working_state)
        if step is None:
            return OrchestratorAction(action="finalize")
        return self._request_step_action(
            step=step,
            working_state=working_state,
            branch_path=branch_path,
        )

    def _select_next_step(
        self,
        *,
        working_state: OrchestratorWorkingState,
    ) -> tuple[OrchestratorStep | None, str | None]:
        if not working_state.has_completed(OrchestratorStep.CHANGE_PLAN):
            return OrchestratorStep.CHANGE_PLAN, None
        if not working_state.has_completed(OrchestratorStep.OPERATIONS):
            return OrchestratorStep.OPERATIONS, None

        pending_summary_branches = working_state.pending_summary_branches()
        if pending_summary_branches:
            return OrchestratorStep.SUMMARY, pending_summary_branches[0]
        return None, None

    def _request_step_action(
        self,
        *,
        step: OrchestratorStep,
        working_state: OrchestratorWorkingState,
        branch_path: str | None = None,
    ) -> OrchestratorAction:
        raw = self._invoke(
            messages=self.prompt_composer.build_step_messages(
                step=step,
                working_state=working_state,
                branch_path=branch_path,
                tool_results=working_state.tool_results,
            )
        )
        return parse_step_action(
            step=step,
            raw_text=raw,
        )

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
