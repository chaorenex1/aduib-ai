import hashlib
import logging
import re
import threading
import uuid
from typing import Optional

from component.vdb.vector_factory import Vector
from models.document import KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.generator.generator import LLMGenerator
from runtime.rag.clean.clean_processor import CleanProcessor
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.extractor.extractor_runner import ExtractorRunner
from runtime.rag.keyword.keyword import Keyword
from runtime.rag.rag_config import SplitterRule, AUTOMATIC_RULES
from runtime.rag.rag_processor.rag_processor_base import BaseRAGProcessor
from runtime.rag.retrieve.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class QARAGProcessor(BaseRAGProcessor):
    """Question Answering RAG processor."""

    def extract(self, extract_setting: ExtractionSetting, **kwargs) -> list[Document]:
        text_docs = ExtractorRunner.extract(extraction_setting=extract_setting)
        return text_docs

    def transform(self, documents: list[Document], **kwargs) -> list[Document]:
        splitter_rule_dict = kwargs.get("split_rule")
        if not splitter_rule_dict:
            raise ValueError("No splitter rule found.")
        if splitter_rule_dict.get("mode") == "automatic":
            rule = SplitterRule(**AUTOMATIC_RULES)
        else:
            if not splitter_rule_dict.get("rules"):
                raise ValueError("No rules found in splitter rule.")
            rule = SplitterRule(**splitter_rule_dict.get("rules"))
        if not rule.segmentation:
            raise ValueError("No segmentation rule found in splitter rule.")
        splitter = self.get_splitter(
            process_rule_mode=splitter_rule_dict.get("mode"),
            chunk_size=rule.segmentation.max_tokens,
            chunk_overlap=rule.segmentation.chunk_overlap,
            separator=rule.segmentation.separator,
        )
        all_documents = []
        for document in documents:
            # document clean
            document_text = CleanProcessor.clean(document.content, kwargs.get("split_rule", {}))
            document.content = document_text
            # parse document to nodes
            document_nodes = splitter.split_documents([document])
            split_documents = []
            for document_node in document_nodes:
                if document_node.content.strip():
                    doc_id = str(uuid.uuid4())
                    hash = hashlib.sha256(document_node.content.encode("utf-8")).hexdigest()
                    if document_node.metadata is not None:
                        document_node.metadata["doc_id"] = doc_id
                        document_node.metadata["doc_hash"] = hash
                    # delete Splitter character
                    content = self.remove_leading_symbols(document_node.content).strip()
                    if len(content) > 0:
                        document_node.content = content
                        split_documents.append(document_node)
            all_documents.extend(split_documents)
        all_qa_documents = []
        for i in range(0, len(all_documents), 10):
            threads = []
            sub_documents = all_documents[i : i + 10]
            for doc in sub_documents:
                document_format_thread = threading.Thread(
                    target=self._format_qa_document,
                    kwargs={
                        "document_node": doc,
                        "all_qa_documents": all_qa_documents,
                        "document_language": kwargs.get("doc_language", "English"),
                    },
                )
                threads.append(document_format_thread)
                document_format_thread.start()
            for thread in threads:
                thread.join()
        return all_qa_documents

    def load(self, knowledge: KnowledgeBase, documents: list[Document], with_keywords: bool = True, **kwargs):
        vector = Vector(knowledge)
        vector.create(documents)

        if with_keywords:
            keywords_list = kwargs.get("keywords_list")
            keyword = Keyword(knowledge)
            if keywords_list and len(keywords_list) > 0:
                keyword.add_texts(documents, keywords_list=keywords_list)
            else:
                keyword.add_texts(documents)

    def clean(self, knowledge: KnowledgeBase, node_ids: Optional[list[str]], with_keywords: bool = True, **kwargs):
        vector = Vector(knowledge)
        if node_ids and len(node_ids) > 0:
            vector.delete_by_ids(node_ids)
        else:
            vector.delete_all()
        if with_keywords:
            keyword = Keyword(knowledge)
            if node_ids and len(node_ids) > 0:
                keyword.delete_by_ids(node_ids)
            else:
                keyword.delete()

    def retrieve(
        self,
        retrieval_method: str,
        query: str,
        knowledge: KnowledgeBase,
        top_k: int,
        score_threshold: float,
        reranking_model: dict,
    ) -> list[Document]:
        # Set search parameters.
        results = RetrievalService.retrieve(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            reranking_model=reranking_model,
        )
        # Organize results.
        docs = []
        for result in results:
            metadata = result.metadata
            metadata["score"] = result.score
            if result.score >= score_threshold:
                doc = Document(content=result.content, metadata=metadata)
                docs.append(doc)
        return docs

    def _format_qa_document(self, document_node, all_qa_documents, document_language):
        format_documents = []
        if document_node.content is None or not document_node.content.strip():
            return
        try:
            # qa model document
            response = LLMGenerator.generate_qa_document(document_node.content,document_language)
            document_qa_list = self._format_split_text(response)
            qa_documents = []
            for result in document_qa_list:
                qa_document = Document(content=result["question"], metadata=document_node.metadata.copy())
                if qa_document.metadata is not None:
                    doc_id = str(uuid.uuid4())
                    hash = hashlib.sha256(result["question"].encode('utf-8')).hexdigest()
                    qa_document.metadata["answer"] = result["answer"]
                    qa_document.metadata["doc_id"] = doc_id
                    qa_document.metadata["doc_hash"] = hash
                qa_documents.append(qa_document)
            format_documents.extend(qa_documents)
        except Exception:
            logger.exception("Failed to format qa document")

        all_qa_documents.extend(format_documents)

    def _format_split_text(self, text):
        regex = r"Q\d+:\s*(.*?)\s*A\d+:\s*([\s\S]*?)(?=Q\d+:|$)"
        matches = re.findall(regex, text, re.UNICODE)

        return [{"question": q, "answer": re.sub(r"\n\s*", "\n", a.strip())} for q, a in matches if q and a]
