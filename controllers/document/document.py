from fastapi import APIRouter

from controllers.common.base import catch_exceptions
from runtime.entities.rerank_entities import RerankRequest
from runtime.entities.text_embedding_entities import EmbeddingRequest
from service.document_service import DocumentService

router = APIRouter(tags=["embeddings"])


@router.post("/embeddings")
@catch_exceptions
def embeddings(req: EmbeddingRequest):
    """
    Embeddings endpoint
    """
    return DocumentService.embeddings(req)


@router.post("/rerank")
@catch_exceptions
def rerank(req: RerankRequest):
    """
    rerank endpoint
    """
    return DocumentService.rerank(req)
