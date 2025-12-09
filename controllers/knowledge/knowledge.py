from fastapi import APIRouter, UploadFile, File, BackgroundTasks

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import KnowledgeBasePayload, KnowledgeRetrievalPayload, BrowserHistoryPayload
from runtime.generator.generator import LLMGenerator
from service import KnowledgeBaseService

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/bases")
@catch_exceptions
def create_knowledge(payload: KnowledgeBasePayload):
    kb = KnowledgeBaseService.create_knowledge_base(payload.name, payload.rag_type, payload.default_base)
    return kb


@router.get("/knowledge/rag/qa")
@catch_exceptions
async def create_qa_rag():
    await KnowledgeBaseService.qa_rag_from_conversation_message()
    return BaseResponse.ok()


@router.post("/knowledge/rag/paragraph")
@catch_exceptions
async def create_paragraph_rag(file: UploadFile = File(...)):
    await KnowledgeBaseService.paragraph_rag_from_blog_content(await file.read(),file.filename)
    return BaseResponse.ok()


@router.get("/knowledge/rag/paragraph/retry")
@catch_exceptions
async def retry_paragraph_rag():
    await KnowledgeBaseService.retry_failed_paragraph_rag_embeddings()
    return BaseResponse.ok()


@router.get("/knowledge/rag/paragraph/clean")
@catch_exceptions
async def clean_paragraph_rag():
    await KnowledgeBaseService.clean_knowledge_documents()
    return BaseResponse.ok()


@router.post("/knowledge/rag/paragraph/background")
@catch_exceptions
async def create_paragraph_rag_background(background_tasks: BackgroundTasks,file: UploadFile = File(...)):
    background_tasks.add_task(KnowledgeBaseService.paragraph_rag_from_blog_content,await file.read())
    return BaseResponse.ok()


@router.post("/knowledge/retrieval")
@catch_exceptions
async def knowledge_retrieval(payload: KnowledgeRetrievalPayload):
    result = await KnowledgeBaseService.retrieve_from_knowledge_base(payload.rag_type, payload.query)
    return result

@router.post("/knowledge/retrieval/answer")
@catch_exceptions
async def knowledge_retrieval(payload: KnowledgeRetrievalPayload):
    result = await KnowledgeBaseService.retrieve_from_knowledge_base(payload.rag_type, payload.query)
    return LLMGenerator.generate_retrieval_content(payload.query,result,payload.rag_type)


@router.post("/knowledge/retrieval/browser_history")
@catch_exceptions
async def knowledge_retrieval_browser_history(payload: BrowserHistoryPayload):
    result = await KnowledgeBaseService.retrieval_from_browser_history(payload.query,payload.start_time,payload.end_time)
    return result
