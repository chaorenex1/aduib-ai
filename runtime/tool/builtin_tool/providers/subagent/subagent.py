from __future__ import annotations

import logging
from typing import Any

from models import Agent
from runtime.entities import ChatCompletionRequest, PromptMessageRole, UserPromptMessage
from runtime.entities.message_entities import ThinkingOptions
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult

logger = logging.getLogger(__name__)


class SubagentTool(BuiltinTool):
    """
    A tool to delegate tasks to subagents.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            task = self._require_non_empty_string(tool_parameters.get("task"), field_name="task")
            context = self._optional_string(tool_parameters.get("context"))
            agent_name = self._require_non_empty_string(tool_parameters.get("agent_name"), field_name="agent_name")
            tool_parameters = dict(tool_parameters)
            tool_parameters["agent_name"] = agent_name
            target_agent = self._resolve_target_agent(tool_parameters)
            parent_agent_id = self._normalize_parent_agent_id(tool_parameters.get("agent_id"))
            if parent_agent_id is not None and target_agent.id == parent_agent_id:
                return ToolInvokeResult(
                    name=self.entity.name,
                    success=False,
                    error="subagent delegation cannot target the current agent itself",
                )

            response_text = await self._invoke_subagent(target_agent, task=task, context=context)
            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "agent_id": target_agent.id,
                    "agent_name": target_agent.name,
                    "task": task,
                    "result": response_text,
                },
                meta={
                    "message_id": message_id,
                    "target_agent_id": target_agent.id,
                    "target_agent_name": target_agent.name,
                    "delegated_by_agent_id": parent_agent_id,
                },
            )
        except ValueError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
        except Exception as exc:
            logger.exception("Subagent invocation failed")
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    async def _invoke_subagent(self, target_agent: Agent, *, task: str, context: str | None = None) -> str:
        from runtime.agent.adapters import ResponseTextExtractor
        from runtime.agent_manager import AgentManager

        request = self._build_subagent_request(target_agent, task=task, context=context)
        response = await AgentManager(agent=target_agent).arun_response(request)
        response_text = ResponseTextExtractor.from_response(response)
        return response_text.strip()

    def _build_subagent_request(
        self,
        target_agent: Agent,
        *,
        task: str,
        context: str | None = None,
    ) -> ChatCompletionRequest:
        user_prompt = task.strip()
        if context:
            user_prompt = f"Context:\n{context.strip()}\n\nTask:\n{user_prompt}"

        messages: list = [
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=user_prompt,
            )
        ]
        agent_parameters = getattr(target_agent, "agent_parameters", {}) or {}
        return ChatCompletionRequest(
            model=str(target_agent.model_id or ""),
            messages=messages,
            stream=True,
            include_reasoning=agent_parameters.get("enable_thinking", False),
            enable_thinking=agent_parameters.get("enable_thinking", False),
            thinking=ThinkingOptions(type="enabled") if agent_parameters.get("thinking", False) else None,
        )

    def _resolve_target_agent(self, tool_parameters: dict[str, Any]) -> Agent:
        from libs.context import get_current_user_id
        from models import get_db

        agent_name = self._optional_string(tool_parameters.get("agent_name"))
        current_user_id = self._optional_string(tool_parameters.get("user_id")) or self._optional_string(
            get_current_user_id()
        )

        with get_db() as session:
            candidates = (
                session.query(Agent)
                .filter(
                    Agent.deleted == 0,
                    Agent.name == agent_name,
                )
                .all()
            )

        visible_candidates = [agent for agent in candidates if self._is_visible_to_user(agent, current_user_id)]
        if not visible_candidates:
            raise ValueError(f"subagent not found or not accessible: name='{agent_name}'")

        visible_candidates.sort(
            key=lambda agent: (
                0 if self._owner_matches(agent, current_user_id) else 1,
                0 if int(getattr(agent, "builtin", 0) or 0) == 1 else 1,
                str(getattr(agent, "name", "") or ""),
            )
        )
        return visible_candidates[0]

    @staticmethod
    def _require_non_empty_string(value: object, *, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"'{field_name}' must be a non-empty string")
        return value.strip()

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_parent_agent_id(value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_visible_to_user(cls, agent: Agent, current_user_id: str | None) -> bool:
        if int(getattr(agent, "builtin", 0) or 0) == 1:
            return True
        if current_user_id is None:
            return not cls._optional_string(getattr(agent, "user_id", None))
        return cls._owner_matches(agent, current_user_id)

    @classmethod
    def _owner_matches(cls, agent: Agent, current_user_id: str | None) -> bool:
        owner = cls._optional_string(getattr(agent, "user_id", None))
        if current_user_id is None:
            return owner is None
        return owner == current_user_id
