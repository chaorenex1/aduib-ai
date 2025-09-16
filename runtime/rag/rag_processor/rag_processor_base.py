import re
from abc import abstractmethod, ABC
from typing import Optional

from models.document import KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.splitter.base_splitter import BaseTextSplitter
from runtime.rag.splitter.text_splitter import RecursiveTextSplitter


class BaseRAGProcessor(ABC):
    """Base class for RAG processors."""

    @abstractmethod
    def extract(self, extract_setting: ExtractionSetting, **kwargs) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def transform(self, documents: list[Document], **kwargs) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def load(self, knowledge: KnowledgeBase, documents: list[Document], with_keywords: bool = True, **kwargs):
        raise NotImplementedError

    def clean(self, knowledge: KnowledgeBase, node_ids: Optional[list[str]], with_keywords: bool = True, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def retrieve(
        self,
        retrieval_method: str,
        query: str,
        knowledge: KnowledgeBase,
        top_k: int,
        score_threshold: float,
        reranking_model: dict,
    ) -> list[Document]:
        raise NotImplementedError

    def get_splitter(
        self, process_rule_mode: str, chunk_size: int, chunk_overlap: int, separator: str, **kwargs
    ) -> BaseTextSplitter:
        """
        Get the splitter object according to the processing rule.
        """
        if separator:
            separator = separator.replace("\\n", "\n")

        if process_rule_mode in ["custom", "hierarchical"]:
            # The user-defined segmentation rule
            text_splitter = RecursiveTextSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, fixed_separator=separator, **kwargs
            )
        else:
            text_splitter = RecursiveTextSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator=separator, **kwargs
            )
        return text_splitter

    def remove_leading_symbols(self, text: str) -> str:
        """
        Remove leading punctuation or symbols from the given text.

        Args:
            text (str): The input text to process.

        Returns:
            str: The text with leading punctuation or symbols removed.
        """
        # Match Unicode ranges for punctuation and symbols
        # FIXME this pattern is confused quick fix for #11868 maybe refactor it later
        pattern = r"^[\u2000-\u206F\u2E00-\u2E7F\u3000-\u303F!\"#$%&'()*+,./:;<=>?@^_`~]+"
        return re.sub(pattern, "", text)
