from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from component.vdb.base_vector import BaseVector
from component.vdb.vector_type import VectorType
from runtime.rag.retrieve.interfaces import EmbeddingProvider

if TYPE_CHECKING:
    from models import KnowledgeBase


class AbstractVectorStoreFactory(ABC):
    """Factory port for constructing concrete vector stores."""

    @abstractmethod
    def create_store(
        self,
        *,
        knowledge: KnowledgeBase | None = None,
        attributes: list | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> BaseVector:
        raise NotImplementedError


def get_vector_store_factory(vector_type: str) -> type[AbstractVectorStoreFactory]:
    match vector_type:
        case VectorType.MILVUS:
            from component.vdb.milvus import MilvusVectorFactory

            return MilvusVectorFactory
        case VectorType.PGVECTO_RS:
            from component.vdb.pgvecto_rs import PGVectoRSFactory

            return PGVectoRSFactory
        case _:
            raise ValueError(f"Vector store {vector_type} is not supported.")
