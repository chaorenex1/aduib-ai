from typing import Optional

from pydantic import BaseModel

from models import KnowledgeEmbeddings


class RetrievalChildDocuments(BaseModel):
    """Retrieval segments."""

    id: str
    content: str
    score: float
    position: int


class RetrievalDocuments(BaseModel):
    """Retrieval segments."""

    model_config = {"arbitrary_types_allowed": True}
    segment: KnowledgeEmbeddings
    child_chunks: Optional[list[RetrievalChildDocuments]] = None
    score: Optional[float] = None
