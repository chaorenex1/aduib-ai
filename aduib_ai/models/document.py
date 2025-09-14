import datetime

from sqlalchemy import Column, DateTime, Integer, String, text, UUID, Index, func, TEXT
from sqlalchemy.dialects.postgresql import JSONB

from models import Base



class Document(Base):
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"),
                comment="id")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    name = Column(String(255), nullable=False, comment="name")
    file_id = Column(String, index=True, nullable=False, comment="file id")
    rag_type = Column(String, index=True, nullable=False, comment="rag type")
    date_source_type = Column(String, index=True, nullable=False, comment="data source type")
    data_process_rule=Column(JSONB, nullable=True, comment="data process rule")