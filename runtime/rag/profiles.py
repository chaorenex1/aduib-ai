from __future__ import annotations

from typing import TYPE_CHECKING

from runtime.rag.indexing.indexing_profile import IndexingProfile
from runtime.rag.rag_type import RagType
from runtime.rag.retrieve.methods import RerankMode, RetrievalMethod
from runtime.rag.retrieve.requests import RetrievalContext
from runtime.rag.transform.context import TransformContext

if TYPE_CHECKING:
    from models import KnowledgeBase


def build_retrieval_context(
    kb: KnowledgeBase,
    *,
    top_k: int | None = None,
    score_threshold: float | None = None,
    retrieval_method: str = RetrievalMethod.VECTOR,
    reranking_mode: str | None = RerankMode.RERANKING_MODEL,
    weights: dict | None = None,
) -> RetrievalContext:
    rule = kb.reranking_rule or {}
    reranking_model = (
        {"reranking_model_name": kb.rerank_model, "reranking_provider_name": kb.rerank_model_provider}
        if kb.rerank_model and kb.rerank_model_provider
        else {}
    )
    reranking_model["reranking_mode"] = rule.get("reranking_mode", RetrievalMethod.VECTOR)
    effective_weights = weights or {
        "keyword_weight": rule.get("keyword_weight", 0.2),
        "vector_weight": rule.get("vector_weight", 0.8),
    }
    return RetrievalContext(
        knowledge_base_id=str(kb.id),
        rag_type=str(kb.rag_type),
        retrieval_method=str(retrieval_method),
        top_k=top_k if top_k is not None else int(rule.get("top_k", 10)),
        score_threshold=score_threshold if score_threshold is not None else float(rule.get("score_threshold", 0.0)),
        reranking_mode=reranking_mode,
        reranking_model=reranking_model,
        weights=effective_weights,
    )


def build_transform_context(
    kb: KnowledgeBase,
    *,
    doc_language: str | None = None,
) -> TransformContext:
    split_rule = kb.data_process_rule
    if not split_rule:
        raise ValueError("no process rule found")
    rules = split_rule.get("rules") or {}
    segmentation = rules.get("segmentation") or {}
    separator = segmentation.get("separator")
    if separator is None:
        delimiter = segmentation.get("delimiter")
        if isinstance(delimiter, list):
            separator = ",".join(delimiter)
        else:
            separator = delimiter or "\n\n,。,., ,"
    return TransformContext(
        split_rule=split_rule,
        process_rule_mode=split_rule.get("mode", "custom"),
        chunk_size=int(segmentation.get("max_tokens", 500)),
        chunk_overlap=int(segmentation.get("chunk_overlap", 0)),
        separator=str(separator),
        doc_language=doc_language,
    )


def build_indexing_profile(
    kb: KnowledgeBase,
    *,
    with_keywords: bool = True,
) -> IndexingProfile:
    full_delete_method = "delete_all" if str(kb.rag_type) == str(RagType.QA) else "delete"
    return IndexingProfile(with_keywords=with_keywords, full_delete_method=full_delete_method)
