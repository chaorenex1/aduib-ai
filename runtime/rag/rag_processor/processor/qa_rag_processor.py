import hashlib
import logging
import re
import threading
import uuid

from runtime.entities.document_entities import Document
from runtime.generator.generator import LLMGenerator
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.extractor.extractor_runner import ExtractorRunner
from runtime.rag.rag_processor.rag_processor_base import BaseRAGProcessor
from runtime.rag.retrieve.facade import RetrievalFacade
from runtime.rag.retrieve.requests import RetrievalContext, RetrieveRequest
from runtime.rag.transform.context import TransformContext

logger = logging.getLogger(__name__)


class QARAGProcessor(BaseRAGProcessor):
    """Question Answering RAG processor."""

    def extract(self, extract_setting: ExtractionSetting, **kwargs) -> list[Document]:
        text_docs = ExtractorRunner.extract(extraction_setting=extract_setting)
        return text_docs

    def post_transform(self, documents: list[Document], *, context: TransformContext, **kwargs) -> list[Document]:
        all_qa_documents = []
        for i in range(0, len(documents), 10):
            threads = []
            sub_documents = documents[i : i + 10]
            for doc in sub_documents:
                document_format_thread = threading.Thread(
                    target=self._format_qa_document,
                    kwargs={
                        "document_node": doc,
                        "all_qa_documents": all_qa_documents,
                        "document_language": context.doc_language or "English",
                    },
                )
                threads.append(document_format_thread)
                document_format_thread.start()
            for thread in threads:
                thread.join()
        return all_qa_documents

    def retrieve(self, request: RetrieveRequest, context: RetrievalContext) -> list[Document]:
        results = RetrievalFacade.retrieve(context, request)
        docs = []
        score_threshold = request.score_threshold if request.score_threshold is not None else context.score_threshold
        for result in results:
            metadata = result.metadata
            score = metadata["score"]
            if score >= score_threshold:
                doc = Document(content=result.content, metadata=metadata)
                docs.append(doc)
        return docs

    def _format_qa_document(self, document_node, all_qa_documents, document_language):
        format_documents = []
        if document_node.content is None or not document_node.content.strip():
            return
        try:
            # qa model document
            response = LLMGenerator.generate_qa_document(document_node.content, document_language)
            document_qa_list = self._format_split_text(response)
            qa_documents = []
            for result in document_qa_list:
                qa_document = Document(content=result["question"], metadata=document_node.metadata.copy())
                if qa_document.metadata is not None:
                    doc_id = str(uuid.uuid4())
                    hash = hashlib.sha256(result["question"].encode("utf-8")).hexdigest()
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
