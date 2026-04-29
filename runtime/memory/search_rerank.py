from __future__ import annotations

import logging

from configs import config
from runtime.entities.model_entities import ModelType
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.model_manager import ModelManager
from runtime.rag.retrieve.methods import RerankMode
from service.document_service import DocumentService

from .search_types import SearchCandidate

logger = logging.getLogger(__name__)


class MemorySearchReranker:
    @classmethod
    def rerank(cls, query: str, candidates: list[SearchCandidate], top_k: int) -> list[SearchCandidate]:
        if not candidates:
            return []

        pool = cls._fallback_sort(candidates)[: config.MEMORY_SEARCH_RERANK_TOP_N]
        try:
            rerank_request = cls._to_rerank_request(query=query, candidates=pool, top_k=top_k)
            rerank_response = DocumentService.rerank(rerank_request)
        except Exception:
            logger.exception("memory search rerank failed; falling back to candidate order")
            return cls._fallback_sort(pool)
        return cls._apply_rerank_scores(pool, rerank_response)

    @classmethod
    def _to_rerank_request(cls, query: str, candidates: list[SearchCandidate], top_k: int) -> RerankRequest:
        model_name = None
        if config.rerank_method != RerankMode.WEIGHTED_SCORE:
            model_instance = ModelManager().get_default_model_instance(ModelType.RERANKER.to_model_type())
            model_name = model_instance.model if model_instance else None
        return RerankRequest(
            model=model_name,
            query=query,
            documents=[item.abstract or item.content for item in candidates],
            top_n=min(len(candidates), max(top_k, config.MEMORY_SEARCH_RERANK_TOP_N)),
        )

    @classmethod
    def _apply_rerank_scores(
        cls,
        candidates: list[SearchCandidate],
        rerank_response: RerankResponse,
    ) -> list[SearchCandidate]:
        updated = [item.model_copy(deep=True) for item in candidates]
        for candidate in updated:
            candidate.final_score = candidate.vector_score if candidate.vector_score is not None else 0.0

        for result in rerank_response.results:
            if result.index < 0 or result.index >= len(updated):
                continue
            candidate = updated[result.index]
            candidate.rerank_score = result.relevance_score
            candidate.final_score = result.relevance_score

        updated.sort(
            key=lambda item: (-(item.final_score or item.vector_score or 0.0), item.branch_path, item.file_path),
        )
        return updated

    @classmethod
    def _fallback_sort(cls, candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        ordered = [item.model_copy(deep=True) for item in candidates]
        for candidate in ordered:
            base_score = candidate.vector_score if candidate.vector_score is not None else 0.0
            candidate.rerank_score = base_score
            candidate.final_score = base_score
        ordered.sort(
            key=lambda item: (-(item.final_score or item.vector_score or 0.0), item.branch_path, item.file_path)
        )
        return ordered
