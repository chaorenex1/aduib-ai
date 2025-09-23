from runtime.entities.rerank_entities import RerankRequest, RerankResponse
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

        from runtime.model_manager import ModelManager

        model_manager = ModelManager()
        model_instance = model_manager.get_model_instance(model_name=query.model)
        return model_instance.invoke_rerank(query=query)
