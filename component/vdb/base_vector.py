from abc import ABC, abstractmethod

from runtime.entities.document_entities import Document


class BaseVector(ABC):
    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    @abstractmethod
    def get_type(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def save(self, texts: list[Document], embeddings: list[list[float]], **kwargs):
        raise NotImplementedError()

    @abstractmethod
    def exists(self, id: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def delete_by_ids(self, ids: list[str]):
        raise NotImplementedError()

    @abstractmethod
    def delete_all(self):
        raise NotImplementedError()

    def get_metadata(self, id: str) -> dict:
        raise NotImplementedError()

    @abstractmethod
    def search_by_vector(self, vector: list[float], **kwargs) -> list[Document]:
        raise NotImplementedError()

    @abstractmethod
    def search_by_full_text(self, text: str, **kwargs) -> list[Document]:
        raise NotImplementedError()

    def delete_by_metadata_field(self, key, value):
        raise NotImplementedError()
