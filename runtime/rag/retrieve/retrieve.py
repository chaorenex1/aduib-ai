from enum import StrEnum
from typing import Optional

from pydantic import BaseModel

from models import KnowledgeEmbeddings


class RetrievalChildDocuments(BaseModel):
    """Retrieval segments."""

    id: str
    content: str
    score: float
    position: int


class RetrievalDocuments(BaseModel):
    """Retrieval segments."""

    model_config = {"arbitrary_types_allowed": True}
    segment: KnowledgeEmbeddings
    child_chunks: Optional[list[RetrievalChildDocuments]] = None
    score: Optional[float] = None


class CosineWeight(BaseModel):
    """Cosine weight."""
    vector_weight: float
    keyword_weight: float
    embedding_provider_name: str
    embedding_model_name: str


class RerankMode(StrEnum):
    """Rerank mode."""

    WEIGHTED_SCORE = "weighted_score"
    RERANKING_MODEL = "reranking_model"
