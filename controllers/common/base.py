import inspect
import logging
import traceback
from functools import wraps
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from starlette.responses import Response

from configs import config
from libs.context import trace_id_context
from service.error.base import BaseServiceError
from utils import jsonable_encoder

logger = logging.getLogger(__name__)


class ApiError(BaseModel):
    """Structured error payload for all JSON APIs."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    """Unified response envelope for all JSON APIs."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    success: bool
    data: Any | None = None
    error: ApiError | None = None

    _status_code: int = PrivateAttr(default=200)

    def with_status(self, status_code: int) -> "ApiResponse":
        self._status_code = status_code
        return self


class ApiHttpException(HTTPException):
    """HTTP exception carrying stable API error metadata."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


def current_request_id() -> str | None:
    """Return the current trace id when middleware has set one."""

    return trace_id_context.get(default=None)


def api_payload(*, success: bool, data: Any | None = None, error: ApiError | None = None) -> ApiResponse:
    payload = ApiResponse(
        request_id=current_request_id(),
        success=success,
        data=jsonable_encoder(obj=data, exclude_none=True) if data is not None else None,
        error=error,
    )
    return payload


def api_ok(data: Any | None = None, status_code: int = 200) -> ApiResponse:
    """Build a success payload."""

    return api_payload(success=True, data=data, error=None).with_status(status_code)


def api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ApiResponse:
    """Build an error payload."""

    return api_payload(
        success=False,
        data=None,
        error=ApiError(code=code, message=message, details=details or {}),
    ).with_status(status_code)


def _to_json_response(payload: ApiResponse, status_code: int | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code if status_code is not None else payload._status_code,
        content=payload.model_dump(mode="json"),
    )


def api_endpoint(success_status: int = 200):
    """Unified controller decorator for JSON endpoints."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)

                if isinstance(result, Response):
                    return result
                if isinstance(result, ApiResponse):
                    return _to_json_response(result)
                return _to_json_response(api_ok(result, status_code=success_status))

            except ApiHttpException as exc:
                logger.exception("ApiHttpException in %s", func.__name__)
                if config.DEBUG:
                    traceback.print_exc()
                return _to_json_response(
                    api_error(
                        status_code=exc.status_code,
                        code=exc.code,
                        message=exc.message,
                        details=exc.details,
                    )
                )
            except BaseServiceError as exc:
                logger.exception("BaseServiceError in %s", func.__name__)
                if config.DEBUG:
                    traceback.print_exc()
                return _to_json_response(
                    api_error(
                        status_code=500,
                        code="service_error",
                        message=exc.description or "service error",
                    )
                )
            except Exception as exc:
                logger.exception("Unhandled exception in %s", func.__name__)
                if config.DEBUG:
                    traceback.print_exc()
                return _to_json_response(
                    api_error(
                        status_code=500,
                        code="internal_error",
                        message=str(exc),
                    )
                )

        return wrapper

    return decorator


def not_implemented(resource_name: str) -> None:
    """Raise a consistent placeholder error for scaffolded endpoints."""

    raise ApiHttpException(
        status_code=501,
        code="not_implemented",
        message=f"{resource_name} is not implemented yet",
    )
