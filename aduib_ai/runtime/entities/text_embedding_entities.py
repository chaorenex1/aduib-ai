from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel

from ..entities.model_entities import ModelUsage


class EmbeddingRequest(BaseModel):
    prompt: str
    model: str

class EmbeddingsResponse(BaseModel):
    embedding: Optional[List[float]] = None

class EmbeddingUsage(ModelUsage):
    """
    Model class for embedding usage.
    """

    tokens: int
    total_tokens: int
    unit_price: Decimal
    price_unit: Decimal
    total_price: Decimal
    currency: str
    latency: float


class TextEmbeddingResult(BaseModel):
    """
    Model class for text embedding result.
    """

    model: str
    embeddings: list[list[float]]
    usage: EmbeddingUsage
