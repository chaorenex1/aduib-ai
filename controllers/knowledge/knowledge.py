from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from controllers.common.base import api_endpoint
from controllers.params import BrowserHistoryPayload, KnowledgeBasePayload, KnowledgeRetrievalPayload
from runtime.generator.generator import LLMGenerator
from service import KnowledgeBaseService

router = APIRouter(tags=["knowledge"])
UPLOAD_FILE = File(...)


@router.post("/knowledge/bases")
@api_endpoint()
def create_knowledge(payload: KnowledgeBasePayload):
    kb = KnowledgeBaseService.create_knowledge_base(payload.name, payload.rag_type, payload.default_base)
    return kb


@router.get("/knowledge/rag/qa")
@api_endpoint()
async def create_qa_rag():
    await KnowledgeBaseService.qa_rag_from_conversation_message()
    return {}


@router.post("/knowledge/rag/paragraph")
@api_endpoint()
async def create_paragraph_rag(file: UploadFile = UPLOAD_FILE):
    await KnowledgeBaseService.paragraph_rag_from_blog_content(await file.read(), file.filename)
    return {}


@router.get("/knowledge/rag/paragraph/retry")
@api_endpoint()
async def retry_paragraph_rag():
    await KnowledgeBaseService.retry_failed_paragraph_rag_embeddings()
    return {}


@router.get("/knowledge/rag/paragraph/clean")
@api_endpoint()
async def clean_paragraph_rag():
    await KnowledgeBaseService.clean_knowledge_documents()
    return {}


@router.post("/knowledge/rag/paragraph/background")
@api_endpoint()
async def create_paragraph_rag_background(background_tasks: BackgroundTasks, file: UploadFile = UPLOAD_FILE):
    background_tasks.add_task(KnowledgeBaseService.paragraph_rag_from_blog_content, await file.read())
    return {}


@router.post("/knowledge/retrieval")
@api_endpoint()
async def knowledge_retrieval(payload: KnowledgeRetrievalPayload):
    result = await KnowledgeBaseService.retrieve_from_knowledge_base(payload.rag_type, payload.query)
    return result


@router.post("/knowledge/retrieval/answer")
@api_endpoint()
async def knowledge_retrieval_answer(payload: KnowledgeRetrievalPayload):
    result = await KnowledgeBaseService.retrieve_from_knowledge_base(payload.rag_type, payload.query)
    return LLMGenerator.generate_retrieval_content(payload.query, result, payload.rag_type)


@router.post("/knowledge/retrieval/browser_history")
@api_endpoint()
async def knowledge_retrieval_browser_history(payload: BrowserHistoryPayload):
    result = await KnowledgeBaseService.retrieval_from_browser_history(
        payload.query, payload.start_time, payload.end_time
    )
    return result
