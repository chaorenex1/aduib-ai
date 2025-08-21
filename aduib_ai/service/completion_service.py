from typing import Optional, Any, Union

from controllers.params import CompletionRequest, ChatCompletionRequest
from models.model import Model
from models.provider import Provider
from runtime.callbacks.message_record_callback import MessageRecordCallback
from runtime.entities.model_entities import AIModelEntity
from runtime.model_manager import ModelManager
from .model_service import ModelService
from .provider_service import ProviderService
from fastapi import Request


class CompletionService:

    @staticmethod
    def create_completion(req:Union[ChatCompletionRequest, CompletionRequest],raw_request: Request) -> Optional[Any]:
        model: Model = ModelService.get_model(req.model)
        provider: Provider = ProviderService.get_provider(model.provider_name)
        model_list:list[AIModelEntity]= ModelService.get_ai_models(provider.name)
        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(provider,model, model_list)
        llm_result = model_instance.invoke_llm(prompt_messages=req,
                                               raw_request=raw_request,
                                               callbacks=[MessageRecordCallback()]
                                               )
        return llm_result
