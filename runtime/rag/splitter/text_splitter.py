import os
from typing import Optional, List, Any, Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from runtime.entities.document_entities import Document
from runtime.rag.splitter.base_splitter import BaseTextSplitter


class RecursiveTextSplitter(BaseTextSplitter):
    """RecursiveTextSplitter."""

    def __init__(self,separators: Optional[List[str]] = None, **kwargs: Any):
        super().__init__(**kwargs)
        if "TIKTOKEN_CACHE_DIR" not in os.environ:
            os.environ["TIKTOKEN_CACHE_DIR"] = os.path.expanduser("~/.cache/tiktoken")

        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            separators=separators or ["\n\n", "。", ". ", " ", ""],
            **kwargs,
        )

    def split_text(self, text: str) -> list[str]:
        return self.text_splitter.split_text(text)

    def split_documents(self, documents: Sequence[Document]) -> list[Document]:
        return list(self.transform_document(documents))

    def transform_document(self, documents: Sequence[Document], **kwargs) -> Sequence[Document]:
        all_docs = []
        from langchain_core.documents import Document as LCDocument
        split_documents = self.text_splitter.split_documents([LCDocument(page_content=doc.content, metadata=doc.metadata) for doc in documents])
        if not split_documents:
            return []
        for _document in split_documents:
            all_docs.append(
                Document(
                    content=_document.page_content,
                    metadata=_document.metadata,
                )
            )
        return all_docs


class FixedRecursiveTextSplitter(BaseTextSplitter):
    """FixedRecursiveTextSplitter."""

    def __init__(self, fixed_separator: str = "\n\n", **kwargs: Any):
        super().__init__(**kwargs)
        if "TIKTOKEN_CACHE_DIR" not in os.environ:
            os.environ["TIKTOKEN_CACHE_DIR"] = os.path.expanduser("~/.cache/tiktoken")
        separators=[separator for separator in fixed_separator.split(",") if separator]
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            separators=separators or ["\n\n", "。", ". ", " ", ""],
            **kwargs,
        )

    def split_text(self, text: str) -> list[str]:
        return self.text_splitter.split_text(text)

    def split_documents(self, documents: Sequence[Document]) -> list[Document]:
        return list(self.transform_document(documents))

    def transform_document(self, documents: Sequence[Document], **kwargs) -> Sequence[Document]:
        all_docs = []
        from langchain_core.documents import Document as LCDocument
        split_documents = self.text_splitter.split_documents(
            [LCDocument(page_content=doc.content, metadata=doc.metadata) for doc in documents])
        if not split_documents:
            return []
        for _document in split_documents:
            all_docs.append(
                Document(
                    content=_document.page_content,
                    metadata=_document.metadata,
                )
            )
        return all_docs