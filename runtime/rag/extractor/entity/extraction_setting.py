from typing import Optional

from pydantic import BaseModel, ConfigDict

from models import FileResource


class ExtractionSetting(BaseModel):
    """Settings for entity extraction."""

    extraction_source: str
    extraction_file: Optional[FileResource] = None
    extraction_db: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
