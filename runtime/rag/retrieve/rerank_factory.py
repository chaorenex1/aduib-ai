from runtime.rag.retrieve.rerank_base import BaseRerankRunner
from runtime.rag.retrieve.retrieve import RerankMode


class RerankFactory:
    @staticmethod
    def get_reranker(reranker_type: str, *args, **kwargs)-> BaseRerankRunner:
        """
        Factory method to get a reranker instance based on the type.
        """
        match reranker_type:
            case RerankMode.WEIGHTED_SCORE:
                from runtime.rag.retrieve.cosine_rerank import CosineWeightRerankRunner
                return CosineWeightRerankRunner(*args, **kwargs)
            case RerankMode.RERANKING_MODEL:
                from runtime.rag.retrieve.rerank_model import RankerModelRunner
                return RankerModelRunner(*args, **kwargs)
            case _:
                raise ValueError(f"Unknown reranker type: {reranker_type}")