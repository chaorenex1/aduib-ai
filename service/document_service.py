import os

from runtime.entities.rerank_entities import RerankRequest, RerankResponse, RerankResult, RerankDocument, RerankUsage
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult


class DocumentService:
    def __init__(self):
        self.documents = {}

    def add_document(self, doc_id, content):
        self.documents[doc_id] = content

    def get_document(self, doc_id):
        return self.documents.get(doc_id, None)

    def delete_document(self, doc_id):
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False

    def list_documents(self):
        return list(self.documents.keys())

    @classmethod
    def embeddings(cls, req: EmbeddingRequest) -> TextEmbeddingResult:
        """Generate embeddings based on the request."""

        from runtime.model_manager import ModelManager

        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(model_name=req.model)
        return model_instance.invoke_text_embedding(texts=req)

    @classmethod
    def rerank(cls, query: RerankRequest) -> RerankResponse:
        """Rerank documents based on the request."""
        from configs import config
        from runtime.rag.retrieve.retrieve import RerankMode
        if config.rerank_method == RerankMode.WEIGHTED_SCORE:
            from runtime.rag.retrieve.cosine_rerank import CosineWeightRerankRunner

            from runtime.rag.retrieve.retrieve import CosineWeight
            weights = CosineWeight(
                vector_weight=config.vector_weight,
                keyword_weight=config.keyword_weight,
                embedding_model_name=config.embedding_model_name,
                embedding_provider_name=config.embedding_provider_name,
            )
            rerank_runner = CosineWeightRerankRunner(weights=weights)
            from runtime.entities.document_entities import Document
            documents:list[Document] = [Document(content=doc,metadata={"doc_id":i}) for i,doc in enumerate(query.documents)]
            _docs = rerank_runner.run(query=query.query, documents=documents, score_threshold=config.score_threshold,
                                    top_n=config.top_n)
            results = []
            for i, doc in enumerate(_docs):
                # Find original document index
                results.append(
                    RerankResult(index=i, document=RerankDocument(text=doc.content), relevance_score=doc.metadata["score"])
                )
            return RerankResponse(
                id="rerank-" + os.urandom(8).hex(),
                model=query.model,
                results=results,
                usage=RerankUsage(total_tokens=0),
            )
        else:
            from runtime.model_manager import ModelManager

            model_manager = ModelManager()
            model_instance = model_manager.get_model_instance(model_name=query.model)
            return model_instance.invoke_rerank(query=query)
