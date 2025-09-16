from typing import Optional, Union, Annotated, Any

from pydantic import BaseModel, Field


class RerankDocument(BaseModel):
    text: Optional[str] = None


class RerankResult(BaseModel):
    index: int
    document: RerankDocument
    relevance_score: float


class RerankUsage(BaseModel):
    total_tokens: int


class RerankResponse(BaseModel):
    id: str
    model: str
    usage: RerankUsage
    results: list[RerankResult]



class RerankRequest(BaseModel):
    model: Optional[str] = None
    query: Union[str, list[str]]
    documents: Union[list[str], str]
    top_n: int = Field(default_factory=lambda: 0)