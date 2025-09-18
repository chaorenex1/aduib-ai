import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import select

from component.cache.redis_cache import redis_client
from component.vdb.base_vector import BaseVector
from component.vdb.vector_type import VectorType
from configs import config
from models import KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.entities.model_entities import ModelType
from runtime.model_manager import ModelManager
from runtime.rag.embeddings.cache_embeddings import CacheEmbeddings
from runtime.rag.embeddings.embeddings import Embeddings

logger = logging.getLogger(__name__)


class AbstractVectorFactory(ABC):
    @abstractmethod
    def init_vector(self, knowledge: KnowledgeBase, attributes: list, embeddings: Embeddings) -> BaseVector:
        raise NotImplementedError

    @staticmethod
    def gen_index_struct_dict(vector_type: VectorType, collection_name: str):
        index_struct_dict = {"type": vector_type, "vector_store": {"class_prefix": collection_name}}
        return index_struct_dict


class Vector:
    def __init__(self, knowledge: KnowledgeBase, attributes: Optional[list] = None):
        if attributes is None:
            attributes = ["knowledge_id", "doc_id", "doc_hash"]
        self._knowledge = knowledge
        self._embeddings = self._get_embeddings()
        self._attributes = attributes
        self._vector_processor = self._init_vector()

    def _init_vector(self) -> BaseVector:
        vector_type = config.VECTOR_STORE
        vector_factory_cls = self.get_vector_factory(vector_type)
        return vector_factory_cls().init_vector(self._knowledge, self._attributes, self._embeddings)

    @staticmethod
    def get_vector_factory(vector_type: str) -> type[AbstractVectorFactory]:
        match vector_type:
            case VectorType.MILVUS:
                from component.vdb.milvus import MilvusVectorFactory

                return MilvusVectorFactory
            case VectorType.PGVECTO_RS:
                from component.vdb.pgvecto_rs import PGVectoRSFactory

                return PGVectoRSFactory
            case _:
                raise ValueError(f"Vector store {vector_type} is not supported.")

    def create(self, texts: Optional[list] = None, **kwargs):
        if texts:
            start = time.time()
            logger.info("start embedding %s texts %s", len(texts), start)
            batch_size = 1000
            total_batches = len(texts) + batch_size - 1
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_start = time.time()
                logger.info("Processing batch %s/%s (%s texts)", i // batch_size + 1, total_batches, len(batch))
                batch_embeddings = self._embeddings.embed_documents([document.page_content for document in batch])
                logger.info(
                    "Embedding batch %s/%s took %s s", i // batch_size + 1, total_batches, time.time() - batch_start
                )
                self._vector_processor.save(texts=batch, embeddings=batch_embeddings, **kwargs)
            logger.info("Embedding %s texts took %s s", len(texts), time.time() - start)

    def add_texts(self, documents: list[Document], **kwargs):
        if kwargs.get("duplicate_check", False):
            documents = self._filter_duplicate_texts(documents)

        embeddings = self._embeddings.embed_documents([document.content for document in documents])
        self._vector_processor.save(texts=documents, embeddings=embeddings, **kwargs)

    def text_exists(self, id: str) -> bool:
        return self._vector_processor.exists(id)

    def delete_by_ids(self, ids: list[str]):
        self._vector_processor.delete_by_ids(ids)

    def delete_by_metadata_field(self, key: str, value: str):
        self._vector_processor.delete_by_metadata_field(key, value)

    def search_by_vector(self, query: str, **kwargs: Any) -> list[Document]:
        query_vector = self._embeddings.embed_query(query)
        return self._vector_processor.search_by_vector(query_vector, **kwargs)

    def search_by_full_text(self, query: str, **kwargs: Any) -> list[Document]:
        return self._vector_processor.search_by_full_text(query, **kwargs)

    def delete(self):
        self._vector_processor.delete_all()
        # delete collection redis cache
        if self._vector_processor.collection_name:
            collection_exist_cache_key = f"vector_indexing_{self._vector_processor.collection_name}"
            redis_client.delete(collection_exist_cache_key)

    def _get_embeddings(self) -> Embeddings:
        model_manager = ModelManager()

        if self._knowledge:
            embedding_model = model_manager.get_model_instance(
                model_name=self._knowledge.embedding_model,
                provider_name=self._knowledge.embedding_model_provider,
            )
        else:
            embedding_model = model_manager.get_default_model_instance(
                model_type=ModelType.EMBEDDING
            )
        return CacheEmbeddings(embedding_model)

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
