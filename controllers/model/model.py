from fastapi import APIRouter

from controllers.common.base import ApiHttpException, api_endpoint
from controllers.params import CreateModelRequest, CreateProviderRequest
from service.model_service import ModelService
from service.provider_service import ProviderService

router = APIRouter(tags=["models"])


@router.post("/models/add")
@api_endpoint()
def create_model(req: CreateModelRequest):
    """
    创建一个新的模型
    """
    model = ModelService.create_model(req)
    if not model:
        raise ApiHttpException(status_code=500, code="model_create_failed", message="模型创建失败")
    return {"message": "模型创建成功", "model": model}


@router.post("/providers/add")
@api_endpoint()
def create_provider(req: CreateProviderRequest):
    """
    创建一个新的模型提供者
    """
    provider = ProviderService.create_provider(
        req.provider_name, req.supported_model_types, req.provider_type, req.provider_config
    )
    if not provider:
        raise ApiHttpException(status_code=500, code="provider_create_failed", message="模型提供者创建失败")
    return {"message": "模型提供者创建成功", "provider": provider}


@router.get("/models")
@api_endpoint()
def get_models():
    """
    获取模型信息
    """
    models = ModelService.get_models()
    if not models:
        raise ApiHttpException(status_code=404, code="models_not_found", message="模型未找到")
    return models
