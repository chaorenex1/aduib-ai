from typing import Optional, Any, Union, Generator

from starlette.responses import StreamingResponse

from controllers.params import CompletionRequest, ChatCompletionRequest
from models.model import Model
from models.provider import Provider
from runtime.callbacks.message_record_callback import MessageRecordCallback
from runtime.entities import ChatCompletionResponse
from runtime.entities.model_entities import AIModelEntity
from runtime.model_manager import ModelManager
from utils.rate_limit import RateLimit
from .model_service import ModelService
from .provider_service import ProviderService
from fastapi import Request
from configs import config


class CompletionService:

    @staticmethod
    def create_completion(req:Union[ChatCompletionRequest, CompletionRequest],raw_request: Request) -> Optional[Any]:
        """
        Create a completion based on the request and raw request.
        :param req: The request object containing parameters for completion.
        :param raw_request: The raw request object, typically from FastAPI.
        :return: A response object containing the completion result, or a streaming response if requested.
        """
        rate_limit:RateLimit = RateLimit(config.APP_NAME,config.APP_MAX_REQUESTS)
        request_id = rate_limit.gen_request_key()
        try:
            rate_limit.enter(request_id)
            return rate_limit.generate(CompletionService.convert_to_stream(
                CompletionService._completion(raw_request, req)
                ,req)
                , request_id)
        except Exception:
            rate_limit.exit(request_id)
            raise
        finally:
            if not req.stream:
                rate_limit.exit(request_id)

    @staticmethod
    def _completion(raw_request, req):
        """
        Internal method to handle the completion logic.
        :param raw_request: The raw request object, typically from FastAPI.
        :param req: The request object containing parameters for completion.
        :return: A response object containing the completion result.
        """
        model: Model = ModelService.get_model(req.model)
        provider: Provider = ProviderService.get_provider(model.provider_name)
        model_list: list[AIModelEntity] = ModelService.get_ai_models(provider.name)
        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(provider, model, model_list)
        llm_result = model_instance.invoke_llm(prompt_messages=req,
                                               raw_request=raw_request,
                                               callbacks=[MessageRecordCallback()]
                                               )
        return llm_result

    @staticmethod
    def convert_to_stream(response:Union[ChatCompletionResponse, Generator],req:Union[ChatCompletionRequest, CompletionRequest]):
        """
        Convert the response to a streaming response if the request requires it.
        :param response: The response object or generator to be converted.
        :param req: The request object containing parameters for completion.
        :return: A StreamingResponse if the request is a stream, otherwise the response object.
        """
        if req.stream:
            def handle() -> Generator[bytes, None, None]:
                for chunk in response:
                    yield f'data: {chunk.model_dump_json(exclude_none=True)}\n\n'
                    if chunk.done:
                        break

            return StreamingResponse(handle(), media_type="text/event-stream")
        else:
            return response
