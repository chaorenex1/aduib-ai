import logging
from collections.abc import Generator
from typing import Any, Optional

from starlette.responses import StreamingResponse

from configs import config
from runtime.entities.llm_entities import LLMRequest, LLMResponse
from utils import RateLimit

logger = logging.getLogger(__name__)


class ClaudeCompletionService:
    @classmethod
    async def create_completion(cls, req: LLMRequest) -> Optional[Any]:
        """
        Create a completion based on the request and raw request.
        :param req: The request object containing parameters for completion.
        :param raw_request: The raw request object, typically from FastAPI.
        :return: A response object containing the completion result, or a streaming response if requested.
        """
        rate_limit: RateLimit = RateLimit(config.APP_NAME, config.APP_MAX_REQUESTS)
        request_id = rate_limit.gen_request_key()
        try:
            rate_limit.enter(request_id)
            response = await cls._completion(req)
            return rate_limit.generate(await cls.convert_to_stream(response, req), request_id)
        except Exception:
            rate_limit.exit(request_id)
            raise
        finally:
            if not req.stream:
                rate_limit.exit(request_id)

    @classmethod
    async def _completion(cls, req: LLMRequest):
        """
        Internal method to handle the completion logic.
        :param req: The request object containing parameters for completion.
        :return: A response object containing the completion result.
        """
        from libs import get_current_user_id
        from runtime.callbacks.message_record_callback import MessageRecordCallback
        from runtime.model_manager import ModelManager

        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(model_name=req.model)
        model_instance.model_instance.user_id = get_current_user_id()
        return await model_instance.invoke_llm(
            prompt_messages=req, source="message", callbacks=[MessageRecordCallback()]
        )

    @classmethod
    async def convert_to_stream(
        cls,
        response: LLMResponse,
        req: LLMRequest,
    ) -> Any:
        """
        Convert the response to a streaming response if the request requires it.
        :param response: The response object or generator to be converted.
        :param req: The request object containing parameters for completion.
        :return: A StreamingResponse if the request is a stream, otherwise the response object.
        """
        if req.stream:

            def handle() -> Generator[bytes, None, None]:
                for chunk in response:
                    if chunk.done:
                        yield "data: [DONE]\n\n"
                    else:
                        yield f"event: {chunk.type}\n\n"
                        yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
                        # yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"

            return StreamingResponse(handle(), media_type="text/event-stream")
        else:
            return response
