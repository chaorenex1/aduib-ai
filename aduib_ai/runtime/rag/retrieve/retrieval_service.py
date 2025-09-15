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
        dataset_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float] = 0.0,
        reranking_model: Optional[dict] = None,
        reranking_mode: str = "reranking_model",
        weights: Optional[dict] = None,
        document_ids_filter: Optional[list[str]] = None,
    ):
        if not query:
            return []
        dataset = cls._get_dataset(dataset_id)
        if not dataset:
            return []

        all_documents: list[Document] = []
        exceptions: list[str] = []

        # Optimize multithreading with thread pools
        with ThreadPoolExecutor(max_workers=dify_config.RETRIEVAL_SERVICE_EXECUTORS) as executor:  # type: ignore
            futures = [executor.submit(
                cls.keyword_search,
                dataset_id=dataset_id,
                query=query,
                top_k=top_k,
                all_documents=all_documents,
                exceptions=exceptions,
                document_ids_filter=document_ids_filter,
            ), executor.submit(
                cls.embedding_search,
                dataset_id=dataset_id,
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                reranking_model=reranking_model,
                all_documents=all_documents,
                exceptions=exceptions,
                document_ids_filter=document_ids_filter,
            ), executor.submit(
                cls.full_text_index_search,
                dataset_id=dataset_id,
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                reranking_model=reranking_model,
                all_documents=all_documents,
                exceptions=exceptions,
                document_ids_filter=document_ids_filter,
            )]
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
    def _get_dataset(cls, dataset_id: str) -> Optional[KnowledgeBase]:
        with get_db() as session:
            return session.query(KnowledgeBase).where(KnowledgeBase.id == dataset_id).first()

    @classmethod
    def keyword_search(
        cls,
        dataset_id: str,
        query: str,
        top_k: int,
        all_documents: list,
        exceptions: list,
        document_ids_filter: Optional[list[str]] = None,
    ):
        try:
            dataset = cls._get_dataset(dataset_id)
            if not dataset:
                raise ValueError("dataset not found")

            keyword = Keyword(dataset=dataset)

            documents = keyword.search(
                cls.escape_query_for_search(query), top_k=top_k, document_ids_filter=document_ids_filter
            )
            all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def embedding_search(
        cls,
        dataset_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        document_ids_filter: Optional[list[str]] = None,
    ):
        try:
            dataset = cls._get_dataset(dataset_id)
            if not dataset:
                raise ValueError("dataset not found")

            vector = Vector(dataset=dataset)
            documents = vector.search_by_vector(
                query,
                search_type="similarity_score_threshold",
                top_k=top_k,
                score_threshold=score_threshold,
                filter={"group_id": [dataset.id]},
                document_ids_filter=document_ids_filter,
            )

            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @classmethod
    def full_text_index_search(
        cls,
        dataset_id: str,
        query: str,
        top_k: int,
        score_threshold: Optional[float],
        reranking_model: Optional[dict],
        all_documents: list,
        exceptions: list,
        document_ids_filter: Optional[list[str]] = None,
    ):
        try:
            dataset = cls._get_dataset(dataset_id)
            if not dataset:
                raise ValueError("dataset not found")

            vector_processor = Vector(dataset=dataset)

            documents = vector_processor.search_by_full_text(
                cls.escape_query_for_search(query), top_k=top_k, document_ids_filter=document_ids_filter
            )
            if documents:
                all_documents.extend(documents)
        except Exception as e:
            exceptions.append(str(e))

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        return query.replace('"', '\\"')
