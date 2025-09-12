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
    score_threshold: Optional[float] = None,
    truncate_prompt_tokens: Optional[Annotated[int, Field(ge=-1)]] = None

    # --8<-- [start:rerank-extra-params]

    mm_processor_kwargs: Optional[dict[str, Any]] = Field(
        default=None,
        description=("Additional kwargs to pass to the HF processor."),
    )

    priority: int = Field(
        default=0,
        description=(
            "The priority of the request (lower means earlier handling; "
            "default: 0). Any priority other than 0 will raise an error "
            "if the served model does not use priority scheduling."),
    )

    activation: Optional[bool] = None