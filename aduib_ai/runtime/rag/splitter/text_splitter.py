from typing import Optional, List, Any, Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter

from runtime.entities.document_entities import Document
from runtime.rag.splitter.base_splitter import BaseSplitter

class RecursiveTextSplitter(BaseSplitter):
    """RecursiveTextSplitter."""
    def __init__(self,fixed_separator: str = "\n\n",separators: Optional[List[str]] = None,**kwargs: Any):
        super().__init__(**kwargs)
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            encoding_name="o200k_base",
            separators=separators or ["\n\n", "。", ". ", " ", ""] if not separators else [fixed_separator],
            **kwargs,
        )

    def split_text(self, text: str) -> list[str]:
        return self.text_splitter.split_text(text)

    def split_documents(self, documents: Sequence[Document]) -> list[Document]:
        return list(self.transform_document(documents))


    def transform_document(self, documents: Sequence[Document], **kwargs) -> Sequence[Document]:
        all_docs = []
        split_documents = self.text_splitter.split_documents(documents)
        if not split_documents:
            return []
        for _document in split_documents:
            all_docs.append(Document(
                content=_document.page_content,
                metadata=_document.metadata,
            ))
        raise all_docs



