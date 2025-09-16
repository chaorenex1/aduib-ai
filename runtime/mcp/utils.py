import json
from typing import Union, Mapping, Generator

from sse_starlette import EventSourceResponse
from starlette.responses import JSONResponse, Response

from runtime.mcp.types import ErrorData, JSONRPCError
from utils import jsonable_encoder
from utils.rate_limit import RateLimitGenerator


def create_mcp_error_response(request_id: int | str | None, code: int, message: str, data=None):
    """Create MCP error response"""
    error_data = ErrorData(code=code, message=message, data=data)
    json_response = JSONRPCError(
        jsonrpc="2.0",
        id=request_id or 1,
        error=error_data,
    )
    json_data = json.dumps(jsonable_encoder(json_response))
    sse_content = f"event: message\ndata: {json_data}\n\n".encode()
    yield sse_content


def compact_generate_response(response: Union[Mapping, Generator, RateLimitGenerator]) -> Response:
    if isinstance(response, dict):
        return JSONResponse(response)
    else:

        def generate() -> Generator:
            yield from response

        return EventSourceResponse(generate())