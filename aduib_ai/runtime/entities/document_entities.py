from abc import ABC, abstractmethod
from typing import Optional, Any, Sequence

from pydantic import BaseModel


class Document(BaseModel):
    content: str
    vector: Optional[list[float]] = None
    metadata: Optional[dict[str, Any]] = {}
    provider: Optional[str] = "default"
    children: Optional[list["Document"]] = None


class BaseDocumentTransformer(ABC):
    """
    Base class for document transformers. Document transformers are used to transform documents before they are stored in a vector database.
    """

    @abstractmethod
    def transform_document(self, documents: Sequence[Document],**kwargs) -> Sequence[Document]:
        """
        Transform a document list before storing it in a vector database.
        :param documents:
        :return:
        """