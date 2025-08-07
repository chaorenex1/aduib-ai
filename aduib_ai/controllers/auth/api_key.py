from fastapi import APIRouter

from ...libs.deps import CurrentApiKeyDep
from ...models.api_key import ApiKey
from ...service.api_key_service import ApiKeyService

router = APIRouter(tags=['auth'],prefix='/api_key')

@router.post('/get_api_key',response_model=None)
def get_api_key(api_key:str,current_key:CurrentApiKeyDep)->ApiKey:
    return ApiKeyService.get_by_api_key(api_key)