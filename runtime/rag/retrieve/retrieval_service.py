import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from component.vdb.vector_factory import Vector
from models import get_db, KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.rag.keyword.keyword import Keyword
from runtime.rag.retrieve.rerank_model import RankerModelRunner

default_retrieval_model = {
    "reranking_enable": False,
    "reranking_model": {"reranking_provider_name": "", "reranking_model_name": ""},
    "top_k": 10,
    "score_threshold_enabled": False,
}


class RetrievalService:
    # Cache precompiled regular expressions to avoid repeated compilation
    @classmethod
    def retrieve(
        cls,
        knowledge_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float] = 0.0,
        reranking_model: Optional[dict] = None,
        reranking_mode: str = "reranking_model",
        weights: Optional[dict] = None,
        knowledge_ids_filter: Optional[list[str]] = None,
    ):
        if not query:
            return []
        knowledge = cls._get_knowledge(knowledge_id)
        if not knowledge:
            return []

        all_documents: list[Document] = []
        exceptions: list[str] = []

        # Optimize multithreading with thread pools
        with ThreadPoolExecutor(max_workers=dify_config.RETRIEVAL_SERVICE_EXECUTORS) as executor:  # type: ignore
            futures = [
                executor.submit(
                    cls.keyword_search,
                    knowledge_id=knowledge_id,
                    query=query,
                    top_k=top_k,
                    all_documents=all_documents,
                    exceptions=exceptions,
                    knowledge_ids_filter=knowledge_ids_filter,
                ),
                executor.submit(
                    cls.embedding_search,
                    knowledge_id=knowledge_id,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    reranking_model=reranking_model,
                    all_documents=all_documents,
                    exceptions=exceptions,
                    knowledge_ids_filter=knowledge_ids_filter,
                ),
                executor.submit(
                    cls.full_text_index_search,
                    knowledge_id=knowledge_id,
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
    def _get_knowledge(cls, knowledge_id: str) -> Optional[KnowledgeBase]:
        with get_db() as session:
            return session.query(KnowledgeBase).where(KnowledgeBase.id == knowledge_id).first()

    @classmethod
    def keyword_search(
        cls,
        knowledge_id: str,
        query: str,
        top_k: int,
        all_documents: list,
        exceptions: list,
        knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            knowledge = cls._get_knowledge(knowledge_id)
            if not knowledge:
                raise ValueError("knowledge not found")

            keyword = Keyword(knowledge=knowledge)

            documents = keyword.search(
                cls.escape_query_for_search(query), top_k=top_k, knowledge_ids_filter=knowledge_ids_filter
            )
            all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def embedding_search(
        cls,
        knowledge_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            knowledge = cls._get_knowledge(knowledge_id)
            if not knowledge:
                raise ValueError("knowledge not found")

            vector = Vector(knowledge=knowledge)
            documents = vector.search_by_vector(
                query,
                search_type="similarity_score_threshold",
                top_k=top_k,
                score_threshold=score_threshold,
                filter={"group_id": [knowledge.id]},
                knowledge_ids_filter=knowledge_ids_filter,
            )

            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def full_text_index_search(
        cls,
        knowledge_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        knowledge_ids_filter: Optional[list[str]] = None,
    ):
        try:
            knowledge_base = cls._get_knowledge(knowledge_id)
            if not knowledge_base:
                raise ValueError("knowledge_base not found")

            vector_processor = Vector(knowledge=knowledge_base)

            documents = vector_processor.search_by_full_text(
                cls.escape_query_for_search(query), top_k=top_k, knowledge_ids_filter=knowledge_ids_filter
            )
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        return query.replace('"', '\\"')
