from bs4 import BeautifulSoup

from runtime.entities.document_entities import Document
from runtime.rag.extractor.extractor_base import BaseExtractor


class HtmlExtractor(BaseExtractor):
    """
    Load html files.


    Args:
        file_path: Path to the file to load.
    """

    def __init__(self, file_path: str):
        """Initialize with file path."""
        self._file_path = file_path
        self._encoding = "utf-8"

    def extract(self) -> list[Document]:
        return [Document(content=self._load_as_text())]

    def _load_as_text(self) -> str:
        text: str = ""
        with open(self._file_path, "rb") as fp:
            soup = BeautifulSoup(fp, "html.parser")
            text = soup.get_text()
            text = text.strip() if text else ""
        return text
