import logging
import time
from contextvars import ContextVar
from typing import Callable

from fastapi import Depends
from fastapi.security import APIKeyHeader
from requests import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from constants.api_key_source import ApikeySource
from controllers.common.error import ApiNotCurrentlyAvailableError
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
from models import ApiKey
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


def verify_api_key_in_db(
    api_key: str = Depends(api_key_header), authorization_token: str = Depends(authorization_header)
) -> None:
    """从数据库中验证 API Key"""
    try:
        if not api_key or len(api_key.strip()) == 0:
            authorization_token = authorization_token.replace("Bearer ", "")
            ApiKeyService.validate_api_key(authorization_token)
        else:
            ApiKeyService.validate_api_key(api_key)
    except ApiKeyNotFound:
        raise ApiNotCurrentlyAvailableError()


def validate_api_key_in_internal() -> bool:
    """验证内部请求的 API Key"""
    api_key = api_key_context.get_or_none()
    logger.debug(f"Validating internal API Key: {api_key}")
    if not api_key:
        return False
    try:
        return api_key.source == ApikeySource.INTERNAL.value
    except ApiKeyNotFound:
        return False


def validate_api_key_in_external() -> bool:
    """验证外部请求的 API Key"""
    api_key = api_key_context.get_or_none()
    logger.debug(f"Validating external API Key: {api_key}")
    if not api_key:
        return False
    try:
        return api_key.source == ApikeySource.EXTERNAL.value
    except ApiKeyNotFound:
        return False


class ApiKeyContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store API Key in request context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        auth_key = request.headers.get(AUTHORIZATION_HEADER) or ""
        if auth_key.startswith("Bearer "):
            api_key_value = auth_key.replace("Bearer ", "")
        else:
            api_key_value = request.headers.get(API_KEY_HEADER) or ""

        try:
            ApiKeyService.validate_api_key(api_key_value)
            api_key = ApiKeyService.get_by_hash_key(api_key_value)
            logger.info(f"Using API Key: {api_key}")

            # Use temporary_set for automatic cleanup
            with api_key_context.temporary_set(api_key):
                return await call_next(request)

        except Exception as e:
            logger.error(f"Invalid API Key: {api_key_value}")
            raise ApiNotCurrentlyAvailableError()


class TraceIdContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store Trace ID in request context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = trace_uuid()
        logger.info(f"Using Trace ID: {trace_id}")

        # Use temporary_set for automatic cleanup
        with trace_id_context.temporary_set(trace_id):
            return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")

        # 调用下一个中间件
        response: Response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Process time: {process_time:.2f} ms")

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
            f"TaskCache API: {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {duration_ms:.2f}ms | "
            f"Request Size: {content_length} bytes"
        )

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "N/A")

        # Warn on slow requests (> 1 second)
        if duration_ms > 1000:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms"
            )

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
