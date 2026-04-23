from __future__ import annotations

from typing import TYPE_CHECKING

from component.vdb.specs import VectorStoreSpec

if TYPE_CHECKING:
    from models import KnowledgeBase


DEFAULT_VECTOR_ATTRIBUTES = ["knowledge_id", "doc_id", "doc_hash"]


def build_vector_store_spec(knowledge: KnowledgeBase) -> VectorStoreSpec:
    return VectorStoreSpec(
        collection_name=f"kb_{knowledge.rag_type}_vector",
        attributes=list(DEFAULT_VECTOR_ATTRIBUTES),
    )
