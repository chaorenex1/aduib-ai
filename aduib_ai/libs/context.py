# 创建依赖项来验证 API Key
from fastapi import Depends
from fastapi.security import APIKeyHeader

from controllers.common.error import ApiNotCurrentlyAvailableError
from service.api_key_service import ApiKeyService
from service.error.error import ApiKeyNotFound

API_KEY_HEADER = "X-API-Key"  # 你希望客户端发送的 API Key 的请求头字段名称
api_key_header = APIKeyHeader(name=API_KEY_HEADER)


def verify_api_key_in_db(api_key: str=Depends(api_key_header)) -> None:
    """从数据库中验证 API Key"""
    try:
        ApiKeyService.validate_api_key(api_key)
    except ApiKeyNotFound:
        raise ApiNotCurrentlyAvailableError()