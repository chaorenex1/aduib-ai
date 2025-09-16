from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import CreateModelRequest, CreateProviderRequest
from libs.deps import CurrentApiKeyDep
from service.model_service import ModelService
from service.provider_service import ProviderService

router = APIRouter(tags=["models"])


@router.post("/models/add")
@catch_exceptions
def create_model(req: CreateModelRequest) -> BaseResponse:
    """
    创建一个新的模型
    """
    model = ModelService.create_model(req)
    if not model:
        return BaseResponse(code=500, msg="模型创建失败")
    return BaseResponse(code=200, msg="模型创建成功")


@router.post("/providers/add")
@catch_exceptions
def create_model(req: CreateProviderRequest) -> BaseResponse:
    """
    创建一个新的模型提供者
    """
    provider = ProviderService.create_provider(
        req.provider_name, req.supported_model_types, req.provider_type, req.provider_config
    )
    if not provider:
        return BaseResponse(code=500, msg="模型提供者创建失败")
    return BaseResponse(code=200, msg="模型提供者创建成功")


@router.get("/models")
@catch_exceptions
def get_models(current_key: CurrentApiKeyDep):
    """
    获取模型信息
    """
    models = ModelService.get_models()
    if not models:
        return BaseResponse(code=404, msg="模型未找到")
    return models
