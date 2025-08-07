from typing import Optional, Any

from .model_service import ModelService
from .provider_service import ProviderService
from ..controllers.params import CompletionRequest
from ..models.model import Model
from ..models.provider import Provider
from ..runtime.entities.model_entities import ModelType
from ..runtime.model_manager import ModelManager


class CompletionService:

    @staticmethod
    def generate_completion(req:CompletionRequest) -> Optional[Any]:
        """
        Generate completion
        :param req: CompletionRequest
        :return: bool
        """
        model:Model = ModelService.get_model(req.model)
        provider:Provider = ProviderService.get_provider(model.provider_name)
        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(provider.name, ModelType.value_of(model.type), model.name)
        model_parameters={
            "model": model.name,
            "max_tokens": model.max_tokens,
            "temperature": req.temperature,
            "top_p": req.top_p,
            "frequency_penalty": req.frequency_penalty,
            "presence_penalty": req.presence_penalty,
            "response_format": req.response_format,
        }
        llm_result = model_instance.invoke_llm(prompt_messages=req.messages, model_parameters=model_parameters,
                                        tools=req.tools, stop=req.stop, stream=req.stream, callbacks=None)
        return llm_result
