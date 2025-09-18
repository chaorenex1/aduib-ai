import tempfile
from pathlib import Path
from typing import Optional

from component.storage.base_storage import storage_manager
from models import FileResource
from runtime.entities.document_entities import Document
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.extractor.entity.extraction_source_type import ExtractionSourceType
from runtime.rag.extractor.extractor_base import BaseExtractor
from runtime.rag.extractor.html_extractor import HtmlExtractor
from runtime.rag.extractor.markdown_extractor import MarkdownExtractor
from runtime.rag.extractor.text_extractor import TextExtractor


class ExtractorRunner:
    @classmethod
    def extract(cls, extraction_setting: ExtractionSetting) -> list[Document]:
        if extraction_setting.extraction_source == ExtractionSourceType.FILE:
            with tempfile.TemporaryDirectory() as tmpdir:
                file: FileResource = extraction_setting.extraction_file
                suffix = Path(file.access_url).suffix
                file_path = f"{tmpdir}/{next(tempfile._get_candidate_names())}{suffix}"  # type: ignore
                storage_manager.download(file.access_url, file_path)
            input_file = Path(file_path)
            file_type = input_file.suffix.lower()
            extractor: Optional[BaseExtractor] = None
            if file_type == ".pdf":
                ...
            elif file_type in [".doc", ".docx"]:
                ...
            elif file_type in [".xls", ".xlsx"]:
                ...
            elif file_type == ".csv":
                ...
            elif file_type in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif"]:
                ...
            elif file_type in [".md", ".markdown", ".mdx"]:
                extractor = MarkdownExtractor(file_path, encoding="utf-8")
            elif file_type in [".html", ".htm", ".xml"]:
                extractor = HtmlExtractor(file_path)
            else:
                extractor = TextExtractor(file_path)
            return extractor.extract()
        elif extraction_setting.extraction_source == ExtractionSourceType.DB_TABLE:
            extractor: Optional[BaseExtractor] = None
            if extraction_setting.extraction_db == "conversation_message":
                from runtime.rag.extractor.conversation_message_extractor import (
                    ConversationMessageExtractor,
                )
                extractor = ConversationMessageExtractor()

            return extractor.extract()
        else:
            raise ValueError(f"Unsupported extraction source: {extraction_setting.extraction_source}")
