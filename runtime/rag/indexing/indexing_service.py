from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from runtime.entities.document_entities import Document
from runtime.rag.indexing.indexing_profile import IndexingProfile

if TYPE_CHECKING:
    from models.document import KnowledgeBase


class IndexingService:
    """Shared index write/cleanup orchestration for RAG processors."""

    @staticmethod
    def _build_vector(knowledge: KnowledgeBase):
        from component.vdb.vector_factory import Vector

        return Vector(knowledge)

    @staticmethod
    def _build_keyword(knowledge: KnowledgeBase):
        from runtime.rag.keyword.keyword import Keyword

        return Keyword(knowledge)

    @classmethod
    def index_documents(
        cls,
        knowledge: KnowledgeBase,
        documents: list[Document],
        *,
        profile: IndexingProfile | None = None,
        with_keywords: bool | None = None,
        keywords_list: list[str] | None = None,
    ) -> None:
        vector = cls._build_vector(knowledge)
        vector.create(documents)

        if with_keywords is None:
            with_keywords = profile.with_keywords if profile else True
        if not with_keywords:
            return

        cls.index_keywords(knowledge, documents, keywords_list=keywords_list)

    @classmethod
    def index_keywords(
        cls,
        knowledge: KnowledgeBase,
        documents: list[Document],
        *,
        keywords_list: list[str] | None = None,
    ) -> None:
        keyword = cls._build_keyword(knowledge)
        if keywords_list:
            keyword.add_texts(documents, keywords_list=keywords_list)
        else:
            keyword.add_texts(documents)

    @classmethod
    def clean_documents(
        cls,
        knowledge: KnowledgeBase,
        node_ids: list[str] | None,
        *,
        profile: IndexingProfile | None = None,
        with_keywords: bool | None = None,
        full_delete_method: Literal["delete", "delete_all"] | None = None,
    ) -> None:
        vector = cls._build_vector(knowledge)
        if full_delete_method is None:
            full_delete_method = profile.full_delete_method if profile else "delete"
        if node_ids:
            vector.delete_by_ids(node_ids)
        else:
            getattr(vector, full_delete_method)()

        if with_keywords is None:
            with_keywords = profile.with_keywords if profile else True
        if not with_keywords:
            return

        cls.clean_keywords(knowledge, node_ids)

    @classmethod
    def clean_keywords(cls, knowledge: KnowledgeBase, node_ids: list[str] | None) -> None:
        keyword = cls._build_keyword(knowledge)
        if node_ids:
            keyword.delete_by_ids(node_ids)
        else:
            keyword.delete()
