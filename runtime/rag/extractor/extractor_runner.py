import os.path
import shutil
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
            file: FileResource = extraction_setting.extraction_file
            # with tempfile.TemporaryDirectory() as tmpdir:
            #     file_path = f"{tmpdir}/{next(tempfile._get_candidate_names())}"  # type: ignore
            #     Path.mkdir(Path(file_path), parents=True, exist_ok=True)
            suffix = Path(file.file_name).suffix
            file_path = os.path.join(os.path.expanduser("~"), "tmp")
            if not os.path.exists(file_path):
                Path.mkdir(Path(file_path), parents=True, exist_ok=True)
            # download file
            target_file = os.path.join(file_path, file.file_hash + suffix)
            storage_manager.download(file.file_name, target_file)
            input_file = Path(target_file)
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
                extractor = MarkdownExtractor(target_file, encoding="utf-8")
            elif file_type in [".html", ".htm", ".xml"]:
                extractor = HtmlExtractor(target_file)
            else:
                extractor = TextExtractor(target_file)
            result = extractor.extract()
            shutil.rmtree(target_file, ignore_errors=True)
            return result
        elif extraction_setting.extraction_source == ExtractionSourceType.DB_TABLE:
            extractor: Optional[BaseExtractor] = None
            if extraction_setting.extraction_db == "conversation_message":
                from runtime.rag.extractor.conversation_message_extractor import (
                    ConversationMessageExtractor,
                )

                extractor = ConversationMessageExtractor(extraction_setting.extraction_db)

            result = extractor.extract()
            return result
        else:
            raise ValueError(f"Unsupported extraction source: {extraction_setting.extraction_source}")
