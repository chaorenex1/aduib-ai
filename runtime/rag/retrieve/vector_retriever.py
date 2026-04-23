from __future__ import annotations

from typing import TYPE_CHECKING, Any

from component.vdb.vector_store_factory import get_vector_store_factory
from configs import config
from runtime.rag.retrieve.embedding import DefaultEmbeddingProvider
from runtime.rag.vector_specs import build_vector_store_spec

if TYPE_CHECKING:
    from models import KnowledgeBase


class KnowledgeVectorRetriever:
    """Small retrieval adapter that assembles embedding + vector store for a knowledge base."""

    def __init__(self, knowledge: KnowledgeBase):
        self._knowledge = knowledge
        self._embedding_provider = DefaultEmbeddingProvider.from_knowledge(knowledge)
        self._spec = build_vector_store_spec(knowledge)
        vector_store_factory_cls = get_vector_store_factory(config.VECTOR_STORE)
        self._vector_store = vector_store_factory_cls().create_store(
            spec=self._spec,
            embedding_provider=self._embedding_provider,
        )

    def search_by_vector(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float | None = 0.0,
        **kwargs: Any,
    ):
        query_vector = self._embedding_provider.embed_query(query)
        return self._vector_store.search_by_vector(
            query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            **kwargs,
        )

    def search_by_full_text(
        self,
        query: str,
        *,
        top_k: int,
        score_threshold: float | None = 0.0,
        **kwargs: Any,
    ):
        return self._vector_store.search_by_full_text(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            **kwargs,
        )
