from fastapi import APIRouter
from starlette.requests import Request

from controllers.common.base import api_endpoint
from service.web_memo import WebMemoService

router = APIRouter(tags=["web_memo"])


@router.post("/web_memo")
@api_endpoint()
async def web_memo(request: Request):
    """
    Web Memo endpoint
    """
    body = await request.json()
    await WebMemoService.handle_web_memo(body)
    return {}


@router.post("/web_memo/notify")
@api_endpoint()
async def notify(request: Request):
    """
    Web Memo endpoint
    """
    body = await request.json()
    api_hash_key = request.query_params.get("api_key", "")
    await WebMemoService.handle_web_memo_notify(body, api_hash_key)
    return {}
