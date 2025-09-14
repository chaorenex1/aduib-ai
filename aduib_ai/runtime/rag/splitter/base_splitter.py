import logging
from abc import abstractmethod, ABC
from typing import Sequence, Iterable, Optional, Callable

from runtime.entities.document_entities import BaseDocumentTransformer, Document

logger=logging.getLogger(__name__)

class BaseSplitter(BaseDocumentTransformer, ABC):
    """Base class for splitter."""
    def __init__(self,chunk_size: int = 500, chunk_overlap: int = 50):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = Callable[[list[str]], list[int]] = lambda x: [len(x) for x in x],


    @abstractmethod
    def split_text(self, text: str) -> list[str]:
        """Split text into chunks."""
        pass

    @abstractmethod
    def split_documents(self, documents: Sequence[Document]) -> list[Document]:
        """Split documents into chunks."""
        pass

    def transform_document(self, documents: Sequence[Document], **kwargs) -> Sequence[Document]:
        """Transform a document list before storing it in a vector database."""
        return self.split_documents(list(documents))