from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import KnowledgeBasePayload
from service import KnowledgeBaseService

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/bases")
@catch_exceptions
def create_knowledge(payload: KnowledgeBasePayload):
    kb=KnowledgeBaseService.create_knowledge_base(payload.name,payload.rag_type,payload.default_base)
    return BaseResponse.ok(kb)


@router.get("/knowledge/rag/qa")
@catch_exceptions
async def create_qa_rag():
    await KnowledgeBaseService.qa_rag_from_conversation_message()
    return BaseResponse.ok()