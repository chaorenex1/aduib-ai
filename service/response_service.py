import logging
from collections.abc import Generator
from typing import Any, Union
from uuid import uuid4

from starlette.responses import StreamingResponse

from configs import config
from models import get_db
from models.stored_response import StoredResponse
from runtime.entities.response_entities import ResponseInputItem, ResponseOutput, ResponseOutputItem, ResponseRequest
from utils import RateLimit

logger = logging.getLogger(__name__)


class ResponseService:
    @classmethod
    async def create_response(cls, req: ResponseRequest) -> Any:
        """
        Create a response using the OpenAI Response API format.
        Supports store=True (default) for persistent conversation state and
        previous_response_id for multi-turn context reconstruction.
        """
        rate_limit = RateLimit(config.APP_NAME, config.APP_MAX_REQUESTS)
        request_id = rate_limit.gen_request_key()
        try:
            rate_limit.enter(request_id)

            # 1. Pre-generate stable response ID
            response_id = f"resp_{uuid4().hex[:20]}"

            # 2. Build full input (prepend previous context if needed)
            full_input = cls._build_full_input(req)
            req.input = full_input

            # 3. Invoke model
            response = await cls._response(req)

            # 4. Non-streaming: set ID, store, return
            if not req.stream:
                response.id = response_id
                cls._store_response(req, response_id, full_input, response)
                return rate_limit.generate(
                    await cls.convert_to_stream(response, req, request_id, full_input), request_id
                )

            # 5. Streaming: pass response_id into stream handler for deferred storage
            return rate_limit.generate(
                await cls.convert_to_stream(response, req, response_id, full_input),
                request_id,
            )
        except Exception:
            rate_limit.exit(request_id)
            raise
        finally:
            if not req.stream:
                rate_limit.exit(request_id)

    @classmethod
    def _build_full_input(cls, req: ResponseRequest) -> list[ResponseInputItem]:
        """
        Reconstruct full conversation context from previous_response_id chain.
        Returns a flat list of ResponseInputItem ready to send to the model.
        """
        # Normalize current input to list
        if isinstance(req.input, str):
            current_input = [ResponseInputItem(role="user", content=req.input)]
        else:
            current_input = list(req.input)

        if not req.previous_response_id:
            return current_input

        with get_db() as session:
            prev = session.query(StoredResponse).filter(StoredResponse.id == req.previous_response_id).first()

        if prev is None:
            raise ValueError(
                f"previous_response_id '{req.previous_response_id}' not found. "
                "The response may not have been stored (store=false) or the ID is invalid."
            )

        # Reconstruct: previous full input + previous output as assistant turn + current input
        prev_input = [ResponseInputItem(**item) for item in (prev.input_items or [])]
        prev_output = [
            ResponseInputItem(role="assistant", content=item.get("content") or "")
            for item in (prev.output_items or [])
            if item.get("role") == "assistant" or item.get("content")
        ]
        return prev_input + prev_output + current_input

    @classmethod
    def _store_response(
        cls,
        req: ResponseRequest,
        response_id: str,
        full_input: list[ResponseInputItem],
        response: ResponseOutput,
    ) -> None:
        """Persist the response to stored_responses table if store is not False."""
        if req.store is False:
            return
        try:
            stored = StoredResponse(
                id=response_id,
                model=response.model or req.model,
                previous_response_id=req.previous_response_id,
                input_items=[item.model_dump() for item in full_input],
                output_items=[item.model_dump() for item in (response.output or [])],
                usage=response.usage.model_dump() if response.usage else None,
            )
            with get_db() as session:
                session.add(stored)
                session.commit()
        except Exception:
            logger.exception("Failed to store response id=%s", response_id)

    @classmethod
    def _store_streaming_response(
        cls,
        req: ResponseRequest,
        response_id: str,
        full_input: list[ResponseInputItem],
        accumulated_text: str,
        model: str,
    ) -> None:
        """Persist a streaming response after all chunks have been yielded."""
        if req.store is False:
            return
        try:
            output_item = ResponseOutputItem(role="assistant", content=accumulated_text)
            stored = StoredResponse(
                id=response_id,
                model=model or req.model,
                previous_response_id=req.previous_response_id,
                input_items=[item.model_dump() for item in full_input],
                output_items=[output_item.model_dump()],
                usage=None,
            )
            with get_db() as session:
                session.add(stored)
                session.commit()
        except Exception:
            logger.exception("Failed to store streaming response id=%s", response_id)

    @classmethod
    async def _response(cls, req: ResponseRequest):
        """
        Internal method to handle the response logic.
        """
        from libs import get_current_user_id
        from runtime.callbacks.message_record_callback import MessageRecordCallback
        from runtime.model_manager import ModelManager

        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(model_name=req.model)
        model_instance.model_instance.user_id = get_current_user_id()
        result = await model_instance.invoke_llm(
            prompt_messages=req, source="response", callbacks=[MessageRecordCallback()]
        )
        return result

    @classmethod
    async def convert_to_stream(
        cls,
        response: Union[ResponseOutput, Generator],
        req: ResponseRequest,
        response_id: str = None,
        full_input: list[ResponseInputItem] = None,
    ) -> Any:
        """
        Convert the response to a streaming response if the request requires it.
        Accumulates output text and persists to DB after stream completes.
        """
        if req.stream:

            def handle() -> Generator[bytes, None, None]:
                accumulated_text = ""
                last_model = req.model
                for chunk in response:
                    if chunk.done:
                        if response_id and full_input is not None:
                            cls._store_streaming_response(req, response_id, full_input, accumulated_text, last_model)
                        yield "data: [DONE]\n\n"
                    else:
                        if hasattr(chunk, "model") and chunk.model:
                            last_model = chunk.model
                        if hasattr(chunk, "delta") and chunk.delta:
                            delta_content = getattr(chunk.delta.message, "content", "") or ""
                            accumulated_text += delta_content or ""
                        yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"

            return StreamingResponse(handle(), media_type="text/event-stream")
        else:
            return response
