from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.base.contracts import (
    MemoryChangePlanItem,
    OrchestratorAction,
    OrchestratorWorkingState,
    PreparedExtractContext,
)
from runtime.memory.base.enums import OrchestratorStep
from runtime.model_manager import ModelManager

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
        step, branch_path, current_change_plan_item = self._select_next_step(working_state=working_state)
        if step is None:
            return OrchestratorAction(action="finalize")
        return self._request_step_action(
            step=step,
            working_state=working_state,
            branch_path=branch_path,
            current_change_plan_item=current_change_plan_item,
        )

    def _select_next_step(
        self,
        *,
        working_state: OrchestratorWorkingState,
    ) -> tuple[OrchestratorStep | None, str | None, MemoryChangePlanItem | None]:
        if not working_state.change_plan:
            return OrchestratorStep.CHANGE_PLAN, None, None
        current_change_plan_item = self._select_next_change_plan_item_for_operations(working_state)
        if current_change_plan_item is not None:
            return OrchestratorStep.OPERATIONS, None, current_change_plan_item

        pending_summary_branches = working_state.pending_summary_branches()
        if pending_summary_branches and working_state.operations_ready_for_summary():
            return OrchestratorStep.SUMMARY, pending_summary_branches[0], None
        return None, None, None

    @staticmethod
    def _select_next_change_plan_item_for_operations(
        working_state: OrchestratorWorkingState,
    ) -> MemoryChangePlanItem | None:
        pending_targets = set(working_state.pending_operation_targets())
        for item in working_state.change_plan:
            target_key = OrchestratorWorkingState.operation_target_key(
                memory_type=item.memory_type,
                target_branch=item.target_branch,
                filename=item.filename,
            )
            if target_key in pending_targets:
                return item
        return None

    def _request_step_action(
        self,
        *,
        step: OrchestratorStep,
        working_state: OrchestratorWorkingState,
        branch_path: str | None = None,
        current_change_plan_item: MemoryChangePlanItem | None = None,
    ) -> OrchestratorAction:
        current_target_tool_results = (
            self._tool_results_for_target(working_state, current_change_plan_item)
            if current_change_plan_item is not None
            else None
        )
        current_operation = (
            self._current_operation_for_target(working_state, current_change_plan_item)
            if current_change_plan_item is not None
            else None
        )
        raw = self._invoke(
            messages=self.prompt_composer.build_step_messages(
                step=step,
                working_state=working_state,
                branch_path=branch_path,
                current_change_plan_item=current_change_plan_item,
                current_target_tool_results=current_target_tool_results,
                current_operation=current_operation,
                tool_results=working_state.tool_results,
            )
        )
        return parse_step_action(
            step=step,
            raw_text=raw,
        )

    @staticmethod
    def _tool_results_for_target(
        working_state: OrchestratorWorkingState,
        current_change_plan_item: MemoryChangePlanItem,
    ) -> list:
        target_path = f"{current_change_plan_item.target_branch}/{current_change_plan_item.filename}"
        scoped_results = []
        for item in working_state.tool_results:
            args_path = str((item.args or {}).get("path") or "").strip()
            result_path = str((item.result or {}).get("path") or "").strip()
            if item.tool == "read" and target_path in {args_path, result_path}:
                scoped_results.append(item)
                continue
            if item.tool in {"ls", "find"} and args_path and (
                args_path == current_change_plan_item.target_branch
                or target_path.startswith(args_path.rstrip("/"))
            ):
                scoped_results.append(item)
        return scoped_results

    @staticmethod
    def _current_operation_for_target(
        working_state: OrchestratorWorkingState,
        current_change_plan_item: MemoryChangePlanItem,
    ):
        for item in working_state.operations:
            if (
                item.memory_type == current_change_plan_item.memory_type
                and item.target_branch == current_change_plan_item.target_branch
                and item.filename == current_change_plan_item.filename
            ):
                return item
        return None

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
