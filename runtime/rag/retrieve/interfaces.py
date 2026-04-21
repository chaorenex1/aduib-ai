from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Small port that hides the concrete embedding backend from retrieval callers."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError
