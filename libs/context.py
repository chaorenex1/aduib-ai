import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import APIKeyHeader
from requests import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from libs.contextVar_wrapper_enhanced import ContextVarWrapper, DictContextVar
from service.api_key_service import ApiKeyService
from service.error.error import ApiKeyNotFound
from utils import trace_uuid

API_KEY_HEADER = "X-Api-key"  # 你希望客户端发送的 API Key 的请求头字段名称
AUTHORIZATION_HEADER = "Authorization"
api_key_header = APIKeyHeader(name=API_KEY_HEADER)
authorization_header = APIKeyHeader(name=AUTHORIZATION_HEADER)
logger = logging.getLogger(__name__)

api_key_context = ContextVarWrapper.create("api_key")
trace_id_context = ContextVarWrapper.create("trace_id")
user_context = DictContextVar.create("current_user")
request_meta_context = DictContextVar.create("request_meta")
app_context = ContextVarWrapper.create("app")


def get_current_user_id():
    return getattr(user_context, "user_id", None)


def get_app():
    return getattr(app_context, "app", None)


def get_app_home():
    return getattr(app_context, "app_home", None)


def get_request_audit_metadata() -> dict[str, str | None]:
    request_meta = request_meta_context.get(default={}) or {}
    return {
        "trace_id": trace_id_context.get(default=None),
        "request_ip": request_meta.get("request_ip"),
        "user_agent": request_meta.get("user_agent"),
    }


def verify_api_key_in_db(
    api_key: str = Depends(api_key_header), authorization_token: str = Depends(authorization_header)
) -> None:
    """从数据库中验证 API Key"""
    from controllers.common.error import ApiNotCurrentlyAvailableError

    try:
        if not api_key or len(api_key.strip()) == 0:
            authorization_token = authorization_token.replace("Bearer ", "")
            ApiKeyService.validate_api_key(authorization_token)
        else:
            ApiKeyService.validate_api_key(api_key)
    except ApiKeyNotFound:
        raise ApiNotCurrentlyAvailableError()


# Paths that don't require API Key authentication
SKIP_PATHS = {"/v1/auth/login", "/v1/auth/register", "/v1/auth/refresh", "/docs", "/openapi.json", "/health"}


async def verify_jwt_in_request(request: Request) -> dict:
    """FastAPI dependency to verify JWT token from Authorization header."""
    from controllers.common.error import UnauthorizedError
    from utils.auth import decode_token

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired access token")

    return {
        "user_id": int(payload["sub"]),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }


class ApiKeyContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store API Key in request context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from controllers.common.error import UnauthorizedError
        from utils.auth import decode_token

        # Skip auth for certain paths
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        auth_key = request.headers.get(AUTHORIZATION_HEADER) or ""
        if auth_key.startswith("Bearer "):
            api_key_value = auth_key.replace("Bearer ", "")

            try:
                payload = decode_token(api_key_value)
                if not payload or payload.get("type") != "access":
                    raise UnauthorizedError("Invalid or expired access token")
                user_info: dict[str, Any] = {
                    "user_id": int(payload["sub"]),
                    "username": payload.get("username"),
                    "role": payload.get("role"),
                }
                with user_context.temporary_set(user_info):
                    return await call_next(request)
            except Exception:
                raise UnauthorizedError("Invalid or expired access token")
        else:
            api_key_value = request.headers.get(API_KEY_HEADER) or ""
            if not api_key_value or len(api_key_value.strip()) == 0:
                raise UnauthorizedError("Missing API Key")
            try:
                user_info: dict[str, Any] = ApiKeyService.validate_api_key(api_key_value)
                with user_context.temporary_set(user_info):
                    return await call_next(request)
            except Exception:
                raise UnauthorizedError("Invalid API Key")


class TraceIdContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store Trace ID in request context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = trace_uuid()
        request_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        logger.info("%Using Trace ID: {trace_id}")

        # Use temporary_set for automatic cleanup
        with trace_id_context.temporary_set(trace_id):
            with request_meta_context.temporary_set(
                {
                    "request_ip": request_ip,
                    "user_agent": user_agent,
                }
            ):
                return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        logger.info("%Request: {request.method} {request.url}")
        logger.info("%Headers: {dict(request.headers)}")

        # 调用下一个中间件
        response: Response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        logger.info("%Response status: {response.status_code}")
        logger.info("%Process time: {process_time:.2f} ms")

        # 注意：如果要记录响应体，需要先读取再重新构造 Response
        return response


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API performance metrics

    Logs:
    - Request path and method
    - Response time
    - Response status code
    - Request size
    """

    async def dispatch(self, request: Request, call_next):
        # Only track task cache endpoints
        if not request.url.path.startswith(("/v1/api/cache", "/v1/api/tasks", "/v1/api/stats")):
            return await call_next(request)

        # Start timer
        start_time = time.time()

        # Get request size
        content_length = request.headers.get("content-length", 0)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log metrics
        logger.info(
            "TaskCache API: %s %s | Status: %s | Duration: %.2fms | Request Size: %s bytes",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            content_length,
        )

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "N/A")

        # Warn on slow requests (> 1 second)
        if duration_ms > 1000:
            logger.warning("%Slow request detected: {request.method} {request.url.path} took {duration_ms:.2f}ms")

        return response


def add_performance_headers(response: Response, start_time: float) -> Response:
    """
    Helper function to add performance headers to response

    Args:
        response: FastAPI Response object
        start_time: Request start timestamp

    Returns:
        Response with added headers
    """
    duration_ms = (time.time() - start_time) * 1000
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
    return response
