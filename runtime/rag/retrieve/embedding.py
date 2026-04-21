from __future__ import annotations

from typing import TYPE_CHECKING, Any

from runtime.entities.model_entities import ModelType
from runtime.rag.retrieve.interfaces import EmbeddingProvider

if TYPE_CHECKING:
    from models import KnowledgeBase


class DefaultEmbeddingProvider(EmbeddingProvider):
    """Compatibility wrapper around the existing cached embedding implementation."""

    model_manager_cls: Any = None
    cache_embeddings_cls: Any = None

    def __init__(self, model_name: str | None = None):
        model_manager = self._get_model_manager_cls()()
        if model_name:
            embedding_model = model_manager.get_model_instance(model_name=model_name)
        else:
            embedding_model = model_manager.get_default_model_instance(model_type=ModelType.EMBEDDING.to_model_type())
        self._embeddings = self._get_cache_embeddings_cls()(embedding_model)

    @classmethod
    def from_knowledge(cls, knowledge: KnowledgeBase | None) -> DefaultEmbeddingProvider:
        if knowledge:
            model_name = f"{knowledge.embedding_model_provider}/{knowledge.embedding_model}"
            return cls(model_name=model_name)
        return cls()

    @classmethod
    def _get_model_manager_cls(cls):
        if cls.model_manager_cls is None:
            from runtime.model_manager import ModelManager

            cls.model_manager_cls = ModelManager
        return cls.model_manager_cls

    @classmethod
    def _get_cache_embeddings_cls(cls):
        if cls.cache_embeddings_cls is None:
            from runtime.rag.embeddings.cache_embeddings import CacheEmbeddings

            cls.cache_embeddings_cls = CacheEmbeddings
        return cls.cache_embeddings_cls

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)
