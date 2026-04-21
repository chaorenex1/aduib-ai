from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from runtime.entities.document_entities import Document
from runtime.rag.clean.clean_processor import CleanProcessor
from runtime.rag.retrieve.requests import RetrievalContext, RetrieveRequest
from runtime.rag.splitter.base_splitter import BaseTextSplitter
from runtime.rag.splitter.text_splitter import FixedRecursiveTextSplitter, RecursiveTextSplitter
from runtime.rag.transform.context import TransformContext
from runtime.rag.transform.pipeline import TransformPipeline

if TYPE_CHECKING:
    from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting


class BaseRAGProcessor(ABC):
    """Base class for RAG processors."""

    @abstractmethod
    def extract(self, extract_setting: ExtractionSetting, **kwargs) -> list[Document]:
        raise NotImplementedError

    def transform(self, documents: list[Document], **kwargs) -> list[Document]:
        transform_kwargs = dict(kwargs)
        context = transform_kwargs.pop("context", None)
        if context is None:
            raise ValueError(
                "TransformContext is required; build one via runtime.rag.profiles.build_transform_context()."
            )
        pipeline = TransformPipeline(
            context,
            cleaner=CleanProcessor.clean,
            splitter_factory=self._create_splitter_for_context,
            leading_symbol_remover=self.remove_leading_symbols,
        )
        transformed_documents = pipeline.run(documents)
        return self.post_transform(transformed_documents, context=context, **transform_kwargs)

    @abstractmethod
    def retrieve(
        self,
        request: RetrieveRequest,
        context: RetrievalContext,
    ) -> list[Document]:
        raise NotImplementedError

    def post_transform(
        self,
        documents: list[Document],
        *,
        context: TransformContext,
        **kwargs,
    ) -> list[Document]:
        return documents

    def _create_splitter_for_context(self, context: TransformContext) -> BaseTextSplitter:
        return self.get_splitter(
            process_rule_mode=context.process_rule_mode,
            chunk_size=context.chunk_size,
            chunk_overlap=context.chunk_overlap,
            separator=context.separator,
        )

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
            text_splitter = FixedRecursiveTextSplitter(
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
