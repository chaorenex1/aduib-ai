import logging
from typing import Optional

from runtime.entities.document_entities import Document
from runtime.entities.rerank_entities import RerankRequest
from runtime.model_manager import ModelManager, ModelInstance
from runtime.rag.retrieve.rerank_base import BaseRerankRunner

logger = logging.getLogger(__name__)


class RankerModelRunner(BaseRerankRunner):
    """Interface for data post-processing document."""

    def __init__(
        self,
        reranking_model: Optional[dict] = None,
    ):
        self.rerank_model_instance = self._get_rerank_model_instance(reranking_model)

    def invoke(
        self,
        query: str,
        documents: list[Document],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> list[Document]:
        return self.run(query, documents, score_threshold, top_n)

    def run(
        self,
        query: str,
        documents: list[Document],
        score_threshold: Optional[float] = None,
        top_n: Optional[int] = None,
    ) -> list[Document]:
        """
        Run rerank model
        :param query: search query
        :param documents: documents for reranking
        :param score_threshold: score threshold
        :param top_n: top n
        :param user: unique user id if needed
        :return:
        """
        docs = []
        doc_ids = set()
        unique_documents = []
        for document in documents:
            if (
                document.provider == "default"
                and document.metadata is not None
                and document.metadata["doc_id"] not in doc_ids
            ):
                doc_ids.add(document.metadata["doc_id"])
                docs.append(document.content)
                unique_documents.append(document)
            elif document.provider == "external":
                if document not in unique_documents:
                    docs.append(document.content)
                    unique_documents.append(document)

        documents = unique_documents

        rerank_result = self.rerank_model_instance.invoke_rerank(
            query=RerankRequest(model=self.rerank_model_instance.model, query=query, documents=docs, top_n=top_n)
        )

        rerank_documents = []

        for result in rerank_result.results:
            if score_threshold is None or result.relevance_score >= score_threshold:
                # format document
                rerank_document = Document(
                    content=result.document.text,
                    metadata=documents[result.index].metadata,
                    provider=documents[result.index].provider,
                )
                if rerank_document.metadata is not None:
                    rerank_document.metadata["score"] = result.relevance_score
                    rerank_documents.append(rerank_document)

        rerank_documents.sort(key=lambda x: x.metadata.get("score", 0.0), reverse=True)
        return rerank_documents[:top_n] if top_n else rerank_documents

    def _get_rerank_model_instance(self, reranking_model: Optional[dict]) -> ModelInstance | None:
        if reranking_model:
            try:
                model_manager = ModelManager()
                reranking_provider_name = reranking_model.get("reranking_provider_name")
                reranking_model_name = reranking_model.get("reranking_model_name")
                if not reranking_provider_name or not reranking_model_name:
                    return None
                rerank_model_instance = model_manager.get_model_instance(
                    model_name=reranking_model_name,
                    provider_name=reranking_provider_name,
                )
                return rerank_model_instance
            except Exception as e:
                return None
        return None
