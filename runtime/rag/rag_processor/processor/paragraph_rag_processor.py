
from runtime.entities.document_entities import Document
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.extractor.extractor_runner import ExtractorRunner
from runtime.rag.rag_processor.rag_processor_base import BaseRAGProcessor
from runtime.rag.retrieve.facade import RetrievalFacade
from runtime.rag.retrieve.requests import RetrievalContext, RetrieveRequest


class ParagraphRAGProcessor(BaseRAGProcessor):
    def extract(self, extract_setting: ExtractionSetting, **kwargs) -> list[Document]:
        text_docs = ExtractorRunner.extract(extraction_setting=extract_setting)
        return text_docs

    def retrieve(self, request: RetrieveRequest, context: RetrievalContext) -> list[Document]:
        results = RetrievalFacade.retrieve(context, request)
        docs = []
        score_threshold = request.score_threshold if request.score_threshold is not None else context.score_threshold
        for result in results:
            metadata = result.metadata
            score = result.metadata.get("score")
            if score >= score_threshold:
                doc = Document(content=result.content, metadata=metadata)
                docs.append(doc)
        return docs
