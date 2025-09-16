from abc import ABC, abstractmethod

from runtime.entities.document_entities import Document


class BaseExtractor(ABC):
    """
    Base class for extractors. Extractors are used to extract information from documents.
    """

    @abstractmethod
    def extract(self) -> list[Document]:
        """
        Extract information from a document.
        :return: The extracted information.
        """
        raise NotImplementedError("Extract method not implemented.")