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


class RagProcessingRule(BaseModel):
    mode: str = "automatic"
    rules: SplitterRule = None

