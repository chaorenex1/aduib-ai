from typing import Optional

from runtime.entities.document_entities import Document
from runtime.rag.retrieve.rerank_base import BaseRerankRunner
from runtime.rag.retrieve.rerank_factory import RerankFactory
from runtime.rag.retrieve.retrieve import RerankMode, CosineWeight


class RerankProcessor:
    def __init__(self, rerank_type: str, rerank_model: Optional[dict] = None, weights: Optional[dict] = None):
        self.rerank_type = rerank_type
        self.rerank_model = rerank_model
        self.weights = weights
        self.rerank_runner: Optional[BaseRerankRunner] = self._get_rerank_runner(rerank_type, rerank_model, weights)

    def invoke(self, query: str, documents: list[Document], score_threshold: Optional[float] = None,
            top_n: Optional[int] = None) -> list[Document]:
        if self.rerank_runner:
            documents = self.rerank_runner.run(query, documents, score_threshold, top_n)
        return documents

    def _get_rerank_runner(self, rerank_type: str, rerank_model: Optional[dict],
                           weights: Optional[dict]) -> Optional[BaseRerankRunner]:
        if rerank_type == RerankMode.WEIGHTED_SCORE and weights:
            runner=RerankFactory.get_reranker(reranker_type=rerank_type, weights=CosineWeight(
                vector_weight=weights["vector_weight"],
                keyword_weight=weights["keyword_weight"],
                embedding_model_name=weights["embedding_model_name"],
                embedding_provider_name=weights["embedding_provider_name"],
            ))
            return runner
        elif rerank_type == RerankMode.RERANKING_MODEL and rerank_model:
            runner = RerankFactory.get_reranker(rerank_type=rerank_type, rerank_model=rerank_model)
            return runner
        return None
