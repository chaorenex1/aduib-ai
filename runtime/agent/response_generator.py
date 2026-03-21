import logging
from collections.abc import Callable
from typing import Any

from models import Agent
from runtime.agent.agent_type import AgentExecutionContext
from runtime.callbacks.base_callback import Callback
from runtime.entities.llm_entities import ChatCompletionRequest, LLMRequest
from runtime.model_manager import ModelInstance, ModelManager

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates responses for agent requests"""

    def __init__(
        self,
        model_manager: ModelManager,
        callback_factory: Callable[[Agent], list[Callback]],
    ):
        self.model_manager = model_manager
        self.callback_factory = callback_factory

    async def generate_response(
        self,
        agent: Agent,
        ctx: AgentExecutionContext,
        request: LLMRequest,
    ) -> Any:
        try:
            model_instance = self.model_manager.get_model_instance(model_name=request.model)
            self._apply_agent_parameters(agent, request, model_instance)
            return await model_instance.invoke_llm(
                prompt_messages=request,
                callbacks=self.callback_factory(agent),
                user=ctx.user_id,
                agent_id=ctx.agent_id,
                agent_session_id=ctx.session_id,
            )
        except Exception as ex:
            logger.error("Error generating response: %s", ex)
            raise

    def _apply_agent_parameters(
        self,
        agent: Agent,
        request: ChatCompletionRequest,
        model_instance: ModelInstance,
    ) -> None:
        if not agent.agent_parameters:
            return

        parameters = agent.agent_parameters
        parameter_mapping = {
            "temperature": "temperature",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "max_tokens": "max_completion_tokens",
        }

        for param_key, request_key in parameter_mapping.items():
            if param_key in parameters:
                setattr(request, request_key, parameters[param_key])

        if "api_base" in parameters:
            model_instance.provider.provider_credential.credentials["api_base"] = parameters["api_base"]

        if "api_key" in parameters:
            model_instance.provider.provider_credential.credentials["api_key"] = parameters["api_key"]
