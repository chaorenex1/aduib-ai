from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel

from ..entities.model_entities import ModelUsage


class EmbeddingRequest(BaseModel):
    prompt: str = None
    model: str
    input: list[str] | str
    dimensions: int = None
    encoding_format: Optional[str] = "float"  # base64


class EmbeddingsResponse(BaseModel):
    embedding: Optional[List[float]] | Optional[str] | Optional[List[str]] = None
    index: int = 0
    object: str = "embedding"
    encoding_format: Optional[str] = "float"  # base64


class EmbeddingUsage(ModelUsage):
    """
    Model class for embedding usage.
    """

    tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0
    unit_price: Decimal = 0.00
    price_unit: Decimal = 0.00
    total_price: Decimal = 0.00
    currency: str = "USD"
    latency: float = 0.00


class TextEmbeddingResult(BaseModel):
    """
    Model class for text embedding result.
    """

    model: str = ""
    embeddings: list[list[float]] = []
    usage: EmbeddingUsage = None
    object: str = ""
    data: List[EmbeddingsResponse] = []
