from __future__ import annotations

from models import Agent
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from runtime.model_manager import ModelManager


class AgentModelFacade:
    @classmethod
    async def invoke_non_streaming(
        cls,
        request: AnthropicMessageRequest,
        *,
        agent: Agent,
        session_id: int,
        user_id: str | None,
    ):
        manager = ModelManager()
        model_instance = manager.get_model_instance(model_name=request.model)
        cls._apply_agent_parameters(agent, request, model_instance)
        return await model_instance.invoke_llm(
            prompt_messages=request,
            user=user_id,
            agent_id=agent.id,
            agent_session_id=session_id,
        )

    @staticmethod
    def _apply_agent_parameters(agent: Agent, request: AnthropicMessageRequest, model_instance) -> None:
        parameters = getattr(agent, "agent_parameters", {}) or {}
        if parameters.get("temperature") is not None and request.temperature is None:
            request.temperature = parameters["temperature"]
        if parameters.get("top_p") is not None and request.top_p is None:
            request.top_p = parameters["top_p"]
        if parameters.get("max_tokens") is not None and request.max_tokens == 4096:
            request.max_tokens = int(parameters["max_tokens"])
        if parameters.get("api_base"):
            model_instance.provider.provider_credential.credentials["api_base"] = parameters["api_base"]
        if parameters.get("api_key"):
            model_instance.provider.provider_credential.credentials["api_key"] = parameters["api_key"]
