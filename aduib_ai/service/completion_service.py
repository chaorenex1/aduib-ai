import logging
from typing import Optional, Any, Union, Generator

from fastapi import Request
from starlette.responses import StreamingResponse

from configs import config
from models.model import Model
from models.provider import Provider
from runtime.entities import ChatCompletionResponse, ToolPromptMessage
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest
from runtime.entities.model_entities import AIModelEntity
from runtime.tool.entities import ToolInvokeResult
from utils import RateLimit

logger = logging.getLogger(__name__)


class CompletionService:

    @classmethod
    def create_completion(cls,req:Union[ChatCompletionRequest, CompletionRequest],raw_request: Request) -> Optional[Any]:
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
            return rate_limit.generate(cls.convert_to_stream(
                cls._completion(raw_request, req)
                ,req)
                , request_id)
        except Exception:
            rate_limit.exit(request_id)
            raise
        finally:
            if not req.stream:
                rate_limit.exit(request_id)

    @classmethod
    def _completion(cls,raw_request, req):
        """
        Internal method to handle the completion logic.
        :param raw_request: The raw request object, typically from FastAPI.
        :param req: The request object containing parameters for completion.
        :return: A response object containing the completion result.
        """

        from runtime.model_manager import ModelManager
        from . import ModelService, ProviderService
        from runtime.callbacks.message_record_callback import MessageRecordCallback

        model: Model = ModelService.get_model(req.model)
        provider: Provider = ProviderService.get_provider(model.provider_name)
        model_list: list[AIModelEntity] = ModelService.get_ai_models(provider.name)
        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(provider, model, model_list)

        from utils.concurrent import get_completion_service_executor
        with get_completion_service_executor() as executor:
            future = executor.submit(model_instance.invoke_llm, prompt_messages=req,raw_request=raw_request,callbacks=[MessageRecordCallback()])
            llm_result = future.result()
        return llm_result

    @classmethod
    def convert_to_stream(cls,response:Union[ChatCompletionResponse, Generator],req:Union[ChatCompletionRequest, CompletionRequest]):
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
