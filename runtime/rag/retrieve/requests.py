from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievalContext:
    """Resolved retrieval configuration for one knowledge base."""

    knowledge_base_id: str
    rag_type: str
    retrieval_method: str
    top_k: int
    score_threshold: float
    reranking_mode: str | None = None
    reranking_model: dict[str, Any] = field(default_factory=dict)
    weights: dict[str, Any] | None = None


@dataclass(slots=True)
class RetrieveRequest:
    """Runtime retrieval request that can override parts of the base context."""

    query: str
    top_k: int | None = None
    score_threshold: float | None = None
    retrieval_method: str | None = None
    reranking_mode: str | None = None
    reranking_model: dict[str, Any] | None = None
    weights: dict[str, Any] | None = None
    options: dict[str, Any] = field(default_factory=dict)
