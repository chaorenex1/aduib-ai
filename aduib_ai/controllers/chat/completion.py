from typing import Any, Generator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from ..params import CompletionRequest, ChatCompletionRequest
from service.completion_service import CompletionService

router = APIRouter(tags=['completion'])



@router.post('/completions')
def completion(req:CompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    response = CompletionService.create_completion(req, raw_request)
    if isinstance(response, Generator):
        return StreamingResponse(response, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
    else:
        return response



@router.post('/chat/completions')
def completion(req:ChatCompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    response = CompletionService.create_completion(req, raw_request)
    if isinstance(response, Generator) and req.stream:
        def handle() -> Generator[bytes, None, None]:
            for chunk in response:
                yield f'data: {chunk.model_dump_json(exclude_none=True)}\n\n'
                if chunk.done:
                    break
        return StreamingResponse(handle(), media_type="text/event-stream")
    else :
        return response