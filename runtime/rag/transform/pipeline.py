from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable

from runtime.entities.document_entities import Document
from runtime.rag.transform.context import TransformContext


class TransformPipeline:
    """Shared document preprocessing + chunking pipeline for RAG processors."""

    def __init__(
        self,
        context: TransformContext,
        *,
        cleaner: Callable[[str, dict], str],
        splitter_factory: Callable[[TransformContext], object],
        leading_symbol_remover: Callable[[str], str],
    ):
        self.context = context
        self._cleaner = cleaner
        self._splitter_factory = splitter_factory
        self._leading_symbol_remover = leading_symbol_remover

    def run(self, documents: list[Document]) -> list[Document]:
        splitter = self._splitter_factory(self.context)
        all_documents: list[Document] = []
        for document in documents:
            document_text = self._cleaner(document.content, self.context.split_rule)
            document.content = document_text
            document_nodes = splitter.split_documents([document])
            all_documents.extend(self._prepare_split_documents(document_nodes))
        return all_documents

    def _prepare_split_documents(self, document_nodes: list[Document]) -> list[Document]:
        split_documents: list[Document] = []
        for document_node in document_nodes:
            if not document_node.content.strip():
                continue
            if document_node.metadata is not None:
                document_node.metadata["doc_id"] = str(uuid.uuid4())
                document_node.metadata["doc_hash"] = hashlib.sha256(document_node.content.encode("utf-8")).hexdigest()
            content = document_node.content
            if self.context.normalize_leading_symbols:
                content = self._leading_symbol_remover(content).strip()
            if content:
                document_node.content = content
                split_documents.append(document_node)
        return split_documents
