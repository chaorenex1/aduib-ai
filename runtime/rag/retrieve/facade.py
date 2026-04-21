from __future__ import annotations

from runtime.entities.document_entities import Document
from runtime.rag.retrieve.orchestrator import RetrievalService
from runtime.rag.retrieve.requests import RetrievalContext, RetrieveRequest


class RetrievalFacade:
    """Thin application-facing facade around the lower-level retrieval orchestrator."""

    @classmethod
    def retrieve(
        cls,
        context: RetrievalContext,
        request: RetrieveRequest,
    ) -> list[Document]:
        return RetrievalService.retrieve(
            rerank_method=request.retrieval_method or context.retrieval_method,
            knowledge_base_id=context.knowledge_base_id,
            query=request.query,
            top_k=request.top_k if request.top_k is not None else context.top_k,
            score_threshold=request.score_threshold if request.score_threshold is not None else context.score_threshold,
            reranking_mode=request.reranking_mode if request.reranking_mode is not None else context.reranking_mode,
            reranking_model=(
                request.reranking_model if request.reranking_model is not None else context.reranking_model
            ),
            weights=request.weights if request.weights is not None else context.weights,
            **request.options,
        )
