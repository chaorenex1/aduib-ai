from fastapi import APIRouter

from controllers.common.base import api_endpoint
from runtime.entities.rerank_entities import RerankRequest
from runtime.entities.text_embedding_entities import EmbeddingRequest
from service.document_service import DocumentService

router = APIRouter(tags=["embeddings"])


@router.post("/embeddings")
@api_endpoint()
def embeddings(req: EmbeddingRequest):
    """
    Embeddings endpoint
    """
    return DocumentService.embeddings(req)


@router.post("/rerank")
@api_endpoint()
def rerank(req: RerankRequest):
    """
    rerank endpoint
    """
    return DocumentService.rerank(req)
