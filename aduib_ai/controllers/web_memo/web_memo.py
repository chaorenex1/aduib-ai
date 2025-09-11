from fastapi import APIRouter
from starlette.requests import Request

from controllers.common.base import BaseResponse, catch_exceptions
from libs.deps import CurrentApiKeyDep
from service.web_memo import WebMemoService

router = APIRouter(tags=['web_memo'])

@router.post('/web_memo')
@catch_exceptions
async def web_memo(request:Request,current_key:CurrentApiKeyDep):
    """
    Web Memo endpoint
    """
    body = await request.json()
    await WebMemoService.handle_web_memo(body)
    return BaseResponse.ok()



@router.post('/web_memo/notify')
@catch_exceptions
async def notify(request:Request):
    """
    Web Memo endpoint
    """
    body = await request.json()
    api_hash_key = request.query_params.get('api_key','')
    await WebMemoService.handle_web_memo_notify(body,api_hash_key)
    return BaseResponse.ok()