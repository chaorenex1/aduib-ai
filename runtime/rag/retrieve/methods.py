from enum import StrEnum

from pydantic import BaseModel


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


class RetrievalMethod(StrEnum):
    """Retrieval method."""

    SEMANTICS = "semantics"
    FULL_TEXT = "full_text"
    VECTOR = "vector"
