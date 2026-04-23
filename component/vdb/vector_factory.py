from __future__ import annotations

import logging
import time
from abc import ABC
from typing import Any, Optional

from component.cache.redis_cache import redis_client
from component.vdb.base_vector import BaseVector
from component.vdb.contracts import EmbeddingProvider
from component.vdb.specs import VectorStoreSpec
from component.vdb.vector_store_factory import AbstractVectorStoreFactory, get_vector_store_factory
from configs import config
from runtime.entities.document_entities import Document

logger = logging.getLogger(__name__)


class AbstractVectorFactory(AbstractVectorStoreFactory, ABC):
    """Backward-compatible alias kept for callers that still import this symbol."""


class Vector:
    def __init__(self, *, spec: VectorStoreSpec, embedding_provider: EmbeddingProvider):
        self._spec = spec
        self._embedding_provider = embedding_provider
        self._vector_processor = self._init_vector()

    def _init_vector(self) -> BaseVector:
        vector_factory_cls = self.get_vector_factory(config.VECTOR_STORE)
        return vector_factory_cls().create_store(
            spec=self._spec,
            embedding_provider=self._embedding_provider,
        )

    @staticmethod
    def get_vector_factory(vector_type: str) -> type[AbstractVectorStoreFactory]:
        return get_vector_store_factory(vector_type)

    def create(self, texts: Optional[list] = None, **kwargs):
        if texts:
            start = time.time()
            logger.info("start embedding %s texts %s", len(texts), start)
            batch_size = 10
            total_batches = len(texts) + batch_size - 1
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_start = time.time()
                logger.info("Processing batch %s/%s (%s texts)", i // batch_size + 1, total_batches, len(batch))
                batch_embeddings = self._embedding_provider.embed_documents([document.content for document in batch])
                logger.info(
                    "Embedding batch %s/%s took %s s", i // batch_size + 1, total_batches, time.time() - batch_start
                )
                self._vector_processor.save(texts=batch, embeddings=batch_embeddings, **kwargs)
            logger.info("Embedding %s texts took %s s", len(texts), time.time() - start)

    def add_texts(self, documents: list[Document], **kwargs):
        if kwargs.get("duplicate_check", False):
            documents = self._filter_duplicate_texts(documents)

        embeddings = self._embedding_provider.embed_documents([document.content for document in documents])
        self._vector_processor.save(texts=documents, embeddings=embeddings, **kwargs)

    def text_exists(self, id: str) -> bool:
        return self._vector_processor.exists(id)

    def delete_by_ids(self, ids: list[str]):
        self._vector_processor.delete_by_ids(ids)

    def delete_by_metadata_field(self, key: str, value: str):
        self._vector_processor.delete_by_metadata_field(key, value)

    def search_by_vector(self, query: str, **kwargs: Any) -> list[Document]:
        query_vector = self._embedding_provider.embed_query(query)
        return self._vector_processor.search_by_vector(query_vector, **kwargs)

    def search_by_full_text(self, query: str, **kwargs: Any) -> list[Document]:
        return self._vector_processor.search_by_full_text(query, **kwargs)

    def delete(self):
        self._vector_processor.delete_all()
        if self._vector_processor.collection_name:
            collection_exist_cache_key = f"vector_indexing_{self._vector_processor.collection_name}"
            redis_client.delete(collection_exist_cache_key)

    def _filter_duplicate_texts(self, texts: list[Document]) -> list[Document]:
        for text in texts.copy():
            if text.metadata is None:
                continue
            doc_id = text.metadata["doc_id"]
            if doc_id:
                exists_duplicate_node = self.text_exists(doc_id)
                if exists_duplicate_node:
                    texts.remove(text)

        return texts

    def __getattr__(self, name):
        if self._vector_processor is not None:
            method = getattr(self._vector_processor, name)
            if callable(method):
                return method

        raise AttributeError(f"'vector_processor' object has no attribute '{name}'")
