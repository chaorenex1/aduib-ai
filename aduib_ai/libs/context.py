import logging
import time
from typing import Callable

from fastapi import Depends
from fastapi.security import APIKeyHeader
from requests import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from controllers.common.error import ApiNotCurrentlyAvailableError
from service.api_key_service import ApiKeyService
from service.error.error import ApiKeyNotFound

API_KEY_HEADER = "X-API-Key"  # 你希望客户端发送的 API Key 的请求头字段名称
api_key_header = APIKeyHeader(name=API_KEY_HEADER)
logger = logging.getLogger(__name__)


def verify_api_key_in_db(api_key: str=Depends(api_key_header)) -> None:
    """从数据库中验证 API Key"""
    try:
        ApiKeyService.validate_api_key(api_key)
    except ApiKeyNotFound:
        raise ApiNotCurrentlyAvailableError()



class LoggingMiddleware(
    BaseHTTPMiddleware
):
    """Middleware to log requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 获取请求体（注意：只能读取一次）
        body = await request.body()
        try:
            body_data = body.decode("utf-8")
        except Exception:
            body_data = str(body)

        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Body: {body_data}")

        # 调用下一个中间件
        response: Response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Process time: {process_time:.2f} ms")

        # 注意：如果要记录响应体，需要先读取再重新构造 Response
        return response