from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.base.contracts import (
    MemoryReadEvidence,
    MemoryTargetProgress,
    OrchestratorAction,
    OrchestratorWorkingState,
    PlannerToolRequest,
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
        step, current_target = self._select_next_step(working_state=working_state)
        if step is None:
            if not working_state.targets:
                return OrchestratorAction(action="stop_noop")
            return OrchestratorAction(action="finalize")
        if (
            step == OrchestratorStep.OPERATIONS
            and current_target is not None
            and current_target.status == "awaiting_read"
        ):
            if not current_target.required_read_path:
                raise ValueError(f"awaiting_read target missing required_read_path: {current_target.target_key}")
            return OrchestratorAction(
                action="request_tools",
                step=OrchestratorStep.OPERATIONS,
                tool_requests=[
                    PlannerToolRequest(
                        tool="read",
                        args={"path": current_target.required_read_path, "max_chars": 8000},
                    )
                ],
            )
        return self._request_step_action(
            step=step,
            working_state=working_state,
            current_target=current_target,
        )

    def _select_next_step(
        self,
        *,
        working_state: OrchestratorWorkingState,
    ) -> tuple[OrchestratorStep | None, MemoryTargetProgress | None]:
        current_target = working_state.next_target_awaiting_read()
        if current_target is not None:
            return OrchestratorStep.OPERATIONS, current_target
        current_target = working_state.next_target_ready_for_operation()
        if current_target is not None:
            return OrchestratorStep.OPERATIONS, current_target
        if not working_state.planning_complete:
            return OrchestratorStep.CHANGE_PLAN, None
        return None, None

    def _request_step_action(
        self,
        *,
        step: OrchestratorStep,
        working_state: OrchestratorWorkingState,
        current_target: MemoryTargetProgress | None = None,
    ) -> OrchestratorAction:
        current_target_read_evidence = (
            self._current_target_read_evidence(working_state, current_target) if current_target is not None else None
        )
        scoped_tool_results = (
            self._tool_results_for_target(working_state, current_target)
            if current_target is not None
            else working_state.tool_results
        )
        raw = self._invoke(
            messages=self.prompt_composer.build_step_messages(
                step=step,
                working_state=working_state,
                current_target=current_target,
                current_target_read_evidence=current_target_read_evidence,
                tool_results=scoped_tool_results,
            )
        )
        return parse_step_action(
            step=step,
            raw_text=raw,
        )

    def _current_target_read_evidence(
        self,
        working_state: OrchestratorWorkingState,
        current_target: MemoryTargetProgress,
    ) -> MemoryReadEvidence | None:
        required_path = current_target.required_read_path
        if not required_path:
            return None
        tool_results = list(reversed(self._tool_results_for_target(working_state, current_target)))
        for item in tool_results:
            if item.tool != "read":
                continue
            result_path = str((item.result or {}).get("path") or "").strip()
            args_path = str((item.args or {}).get("path") or "").strip()
            if required_path not in {result_path, args_path}:
                continue
            return MemoryReadEvidence(
                path=result_path or args_path,
                content=str((item.result or {}).get("content") or ""),
                source="tool_read",
            )
        for item in self.prepared.prefetched_context.get("file_reads") or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if path != required_path:
                continue
            return MemoryReadEvidence(
                path=path,
                content=str(item.get("content") or ""),
                source="prefetch",
            )
        return None

    @staticmethod
    def _tool_results_for_target(
        working_state: OrchestratorWorkingState,
        current_target: MemoryTargetProgress,
    ) -> list:
        target_path = f"{current_target.change_plan_item.target_branch}/{current_target.change_plan_item.filename}"
        scoped_results = []
        for item in working_state.tool_results:
            args_path = str((item.args or {}).get("path") or "").strip()
            result_path = str((item.result or {}).get("path") or "").strip()
            if item.tool == "read" and target_path in {args_path, result_path}:
                scoped_results.append(item)
                continue
            if item.tool in {"ls", "find"} and args_path and (
                args_path == current_target.change_plan_item.target_branch
                or target_path.startswith(args_path.rstrip("/"))
            ):
                scoped_results.append(item)
        return scoped_results

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
