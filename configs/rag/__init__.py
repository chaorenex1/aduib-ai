from pydantic import Field
from pydantic_settings import BaseSettings


class RagConfig(BaseSettings):
    """Configuration for Retrieval-Augmented Generation (RAG) models."""
    rerank_method: str = Field(description="rerank method",default="weighted_score")
    top_n: int = Field(description="top n documents to retrieve",default=10)
    score_threshold: float = Field(description="score threshold for filtering documents",default=0.5)
    keyword_weight: float = Field(description="weight for keyword matching",default=0.2)
    vector_weight: float = Field(description="weight for vector similarity",default=0.8)
    embedding_provider_name: str = Field(description="embedding provider name",default="ollama")
    embedding_model_name: str = Field(description="embedding model name",default="modelscope.cn/Qwen/Qwen3-Embedding-8B-GGUF:Q8_0")