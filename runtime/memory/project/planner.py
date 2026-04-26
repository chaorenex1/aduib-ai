from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.project.contracts import ProjectPlannerAction
from runtime.memory.project.prompts import build_project_planner_messages
from runtime.memory.project.structured_output import load_json_payload, normalize_project_planner_action
from runtime.memory.project.working_state import ProjectPlanningState
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class ProjectPlanner:
    def next_action(
        self,
        *,
        working_state: ProjectPlanningState,
    ) -> ProjectPlannerAction:
        raw = self._invoke_project_model(messages=build_project_planner_messages(context=working_state.snapshot()))
        if not raw:
            if working_state.document_plans:
                return ProjectPlannerAction(
                    action="finalize",
                    reasoning="project planner model unavailable; finalize current document plans",
                    document_plans=[item.model_copy(deep=True) for item in working_state.document_plans],
                    navigation_targets=[item.model_copy(deep=True) for item in working_state.navigation_targets],
                )
            return ProjectPlannerAction(
                action="stop_noop",
                reasoning="project planner model unavailable and no document plans exist",
            )
        return normalize_project_planner_action(load_json_payload(raw))

    @staticmethod
    def _invoke_project_model(*, messages: list) -> str:
        try:
            model_manager = ModelManager()
            model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance(
                "llm"
            )
        except Exception as exc:
            logger.warning("project planner model unavailable: %s", exc)
            return ""
        if model_instance is None:
            return ""

        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response = model_instance.invoke_llm_sync(prompt_messages=request, user=None)
        except Exception as exc:
            logger.warning("project planner invocation failed: %s", exc)
            return ""
        return str(response.message.content or "").strip()
