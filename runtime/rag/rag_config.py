from typing import Any

from pydantic import BaseModel

MODES = ["automatic", "custom", "hierarchical"]
PRE_PROCESSING_RULES = ["remove_stopwords", "remove_extra_spaces", "remove_urls_emails"]
AUTOMATIC_RULES: dict[str, Any] = {
    "pre_processing_rules": [
        {"id": "remove_extra_spaces", "enabled": True},
        {"id": "remove_urls_emails", "enabled": False},
    ],
    "segmentation": {"delimiter": "\n", "max_tokens": 500, "chunk_overlap": 50},
}
default_retrieval_model = {
    "reranking_model": {"reranking_provider_name": "Qwen/Qwen3-Reranker-4B", "reranking_model_name": "transformer"},
    "top_k": 5,
    "score_threshold": 0.8,
}


class PreProcessingRule(BaseModel):
    id: str
    enabled: bool


class Segmentation(BaseModel):
    separator: str = "\n"
    max_tokens: int
    chunk_overlap: int = 0


class SplitterRule(BaseModel):
    pre_processing_rules: list[PreProcessingRule] = []
    segmentation: Segmentation


class RerankingRule(BaseModel):
    score_threshold: float = 0.8
    top_k: int = 5


class RagProcessingRule(BaseModel):
    mode: str = "automatic"
    rules: SplitterRule = None
