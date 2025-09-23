import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from component.vdb.vector_factory import Vector
from models import get_db, KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.rag.keyword.keyword import Keyword
from runtime.rag.retrieve.rerank_model import RankerModelRunner

logger = logging.getLogger(__name__)


class RetrievalService:
    # Cache precompiled regular expressions to avoid repeated compilation
    @classmethod
    def retrieve(
            cls,
            knowledge_base_id: str,
            query: str,
            top_k: int,
            score_threshold: Optional[float] = 0.0,
            reranking_model: Optional[dict] = None,
            knowledge_ids_filter: Optional[list[str]] = None,
    ):
        if not query:
            return []

        if knowledge_base_id:
            knowledge = cls._get_knowledge_base(knowledge_base_id)
            if not knowledge:
                return []

        all_documents: list[Document] = []
        exceptions: list[str] = []

        # Optimize multithreading with thread pools
        with ThreadPoolExecutor(thread_name_prefix="Retrieval") as executor:  # type: ignore
            futures = [
                # executor.submit(
                #     cls.keyword_search,
                #     knowledge_base_id=knowledge_base_id,
                #     query=query,
                #     top_k=top_k,
                #     all_documents=all_documents,
                #     exceptions=exceptions,
                #     knowledge_ids_filter=knowledge_ids_filter,
                # ),
                # executor.submit(
                #     cls.embedding_search,
                #     knowledge_base_id=knowledge_base_id,
                #     query=query,
                #     top_k=top_k,
                #     score_threshold=score_threshold,
                #     reranking_model=reranking_model,
                #     all_documents=all_documents,
                #     exceptions=exceptions,
                #     knowledge_ids_filter=knowledge_ids_filter,
                # ),
                executor.submit(
                    cls.full_text_index_search,
                    knowledge_base_id=knowledge_base_id,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    reranking_model=reranking_model,
                    all_documents=all_documents,
                    exceptions=exceptions,
                    knowledge_ids_filter=knowledge_ids_filter,
                ),
            ]
            concurrent.futures.wait(futures, timeout=30, return_when=concurrent.futures.ALL_COMPLETED)

        if exceptions:
            raise ValueError(";\n".join(exceptions))

        data_post_processor = RankerModelRunner(reranking_model)
        all_documents = data_post_processor.invoke(
            query=query,
            documents=all_documents,
            score_threshold=score_threshold,
            top_n=top_k,
        )

        return all_documents

    @classmethod
    def _get_knowledge_base(cls, knowledge_base_id: str) -> Optional[KnowledgeBase]:
        with get_db() as session:
            return session.query(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id).first()

    @classmethod
    def keyword_search(
            cls,
            knowledge_base_id: str,
            query: str,
            top_k: int,
            all_documents: list,
            exceptions: list,
            knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            if knowledge_base_id:
                knowledge_base = cls._get_knowledge_base(knowledge_base_id)
                if not knowledge_base:
                    raise ValueError("knowledge not found")

            keyword = Keyword(knowledge=knowledge_base)

            documents = keyword.search(cls.escape_query_for_search(query), max_keywords_per_chunk=top_k)
            all_documents.extend(documents)
            logger.debug(f"Keyword search found {len(documents)} documents.")
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def embedding_search(
            cls,
            knowledge_base_id: str,
            query: str,
            top_k: int,
            score_threshold: Optional[float],
            reranking_model: Optional[dict],
            all_documents: list,
            exceptions: list,
            knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            if knowledge_base_id:
                knowledge_base = cls._get_knowledge_base(knowledge_base_id)
                if not knowledge_base:
                    raise ValueError("knowledge not found")

            vector = Vector(knowledge=knowledge_base)
            documents = vector.search_by_vector(
                query,
                search_type="similarity_score_threshold",
                top_k=top_k,
                score_threshold=score_threshold,
                filter={"group_id": [knowledge_base.id]},
                knowledge_ids_filter=knowledge_ids_filter,
            )
            logger.debug(f"Embedding search found {len(documents)} documents.")
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def full_text_index_search(
            cls,
            knowledge_base_id: str,
            query: str,
            top_k: int,
            score_threshold: Optional[float],
            reranking_model: Optional[dict],
            all_documents: list,
            exceptions: list,
            knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            if knowledge_base_id:
                knowledge_base = cls._get_knowledge_base(knowledge_base_id)
                if not knowledge_base:
                    raise ValueError("knowledge not found")

            vector_processor = Vector(knowledge=knowledge_base)

            documents = vector_processor.search_by_full_text(
                cls.escape_query_for_search(query), top_k=top_k, knowledge_ids_filter=knowledge_ids_filter
            )
            logger.debug(f"Full Text search found {len(documents)} documents.")
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        return query.replace('"', '\\"')
