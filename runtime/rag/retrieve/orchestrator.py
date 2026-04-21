from __future__ import annotations

import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Optional

from runtime.entities.document_entities import Document
from runtime.rag.retrieve.methods import RetrievalMethod
from runtime.rag.retrieve.rerank_processor import RerankProcessor
from runtime.rag.retrieve.vector_retriever import KnowledgeVectorRetriever

if TYPE_CHECKING:
    from models import KnowledgeBase

logger = logging.getLogger(__name__)


class RetrievalService:
    # Cache precompiled regular expressions to avoid repeated compilation
    @classmethod
    def retrieve(
        cls,
        rerank_method: str,
        knowledge_base_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float] = 0.0,
        reranking_mode: Optional[str] = None,
        reranking_model: Optional[dict] = None,
        weights: Optional[dict] = None,
        **kwargs
    ):
        if not query:
            return []

        knowledge_base = cls._get_knowledge_base(knowledge_base_id) if knowledge_base_id else None
        if knowledge_base_id and not knowledge_base:
            return []

        all_documents: list[Document] = []
        exceptions: list[str] = []

        # Optimize multithreading with thread pools
        with ThreadPoolExecutor(thread_name_prefix="Retrieval") as executor:  # type: ignore
            futures = []
            futures.append(
                executor.submit(
                    cls.keyword_search,
                    knowledge_base=knowledge_base,
                    query=query,
                    top_k=top_k,
                    all_documents=all_documents,
                    exceptions=exceptions,
                )),
            if rerank_method == RetrievalMethod.SEMANTICS.value:
                futures.append(executor.submit(
                    cls.embedding_search,
                    knowledge_base=knowledge_base,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    reranking_model=reranking_model,
                    all_documents=all_documents,
                    exceptions=exceptions,
                    **kwargs,
                )),
            if rerank_method == RetrievalMethod.FULL_TEXT.value:
                futures.append(executor.submit(
                    cls.full_text_index_search,
                    knowledge_base=knowledge_base,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    reranking_model=reranking_model,
                    all_documents=all_documents,
                    exceptions=exceptions,
                    **kwargs,
                )),
            concurrent.futures.wait(futures, timeout=30, return_when=concurrent.futures.ALL_COMPLETED)

        if exceptions:
            raise ValueError(";\n".join(exceptions))

        data_post_processor = RerankProcessor(reranking_mode, reranking_model, weights)
        all_documents = data_post_processor.invoke(
            query=query,
            documents=all_documents,
            score_threshold=score_threshold,
            top_n=top_k,
        )

        return all_documents

    @classmethod
    def _get_knowledge_base(cls, knowledge_base_id: str) -> Optional[KnowledgeBase]:
        from models import KnowledgeBase, get_db

        with get_db() as session:
            return session.query(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id).first()

    @staticmethod
    def _build_vector_retriever(knowledge_base: KnowledgeBase) -> KnowledgeVectorRetriever:
        return KnowledgeVectorRetriever(knowledge_base)

    @classmethod
    def keyword_search(
        cls,
        knowledge_base: KnowledgeBase | None,
        query: str,
        top_k: int,
        all_documents: list,
        exceptions: list,
    ):
        try:
            if not knowledge_base:
                raise ValueError("knowledge not found")

            from runtime.rag.keyword.keyword import Keyword

            keyword = Keyword(knowledge=knowledge_base)

            documents = keyword.search(cls.escape_query_for_search(query), max_keywords_per_chunk=top_k)
            all_documents.extend(documents)
            logger.debug("%Keyword search found {len(documents)} documents.")
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def embedding_search(
        cls,
        knowledge_base: KnowledgeBase | None,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        **kwargs
    ):
        try:
            if not knowledge_base:
                raise ValueError("knowledge not found")

            retriever = cls._build_vector_retriever(knowledge_base)
            documents = retriever.search_by_vector(
                query,
                top_k=top_k,
                score_threshold=score_threshold,
                **kwargs,
            )
            logger.debug("%Embedding search found {len(documents)} documents.")
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def full_text_index_search(
        cls,
        knowledge_base: KnowledgeBase | None,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        **kwargs
    ):
        try:
            if not knowledge_base:
                raise ValueError("knowledge not found")

            retriever = cls._build_vector_retriever(knowledge_base)
            documents = retriever.search_by_full_text(
                cls.escape_query_for_search(query),
                top_k=top_k,
                score_threshold=score_threshold,
                **kwargs,
            )
            logger.debug("%Full Text search found {len(documents)} documents.")
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        return query.replace('"', '\\"')
