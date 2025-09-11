import datetime

from sqlalchemy import Column, DateTime, Integer, String, text, UUID, Index, func, TEXT
from sqlalchemy.dialects.postgresql import JSONB

from models import Base


class FileResource(Base):
    __tablename__ = "file_resources"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"),
                comment="browser history id")
    access_url = Column(String, comment="access_url", index=True,server_default=text("''"))
    file_name = Column(String, comment="file name", index=True,server_default=text("''"))
    file_abs_path = Column(String, comment="file absolute path", index=True,server_default=text("''"))
    file_type = Column(String, comment="file type",server_default=text("''"))
    file_size = Column(Integer, comment="file size", default=0)
    file_metadata = Column(JSONB, comment="file metadata",server_default=text("{}"))
    file_hash = Column(String, comment="file hash", index=True,server_default=text("''"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="history create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="history update time")
    deleted = Column(Integer, default=0, comment="history delete flag")