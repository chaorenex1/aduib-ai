from __future__ import annotations

import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.project.contracts import ProjectPlannerAction
from runtime.memory.project.errors import ProjectPlannerError
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
            raise ProjectPlannerError("project planner model unavailable") from exc
        if model_instance is None:
            raise ProjectPlannerError("project planner model unavailable")

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
            raise ProjectPlannerError("project planner invocation failed") from exc
        return str(response.message.content or "").strip()
