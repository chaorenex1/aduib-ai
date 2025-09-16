import datetime

from sqlalchemy import Column, DateTime, Integer, String, text, UUID, Index, func, TEXT
from sqlalchemy.dialects.postgresql import JSONB

from models import Base


class BrowserHistory(Base):
    __tablename__ = "browser_history"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"),comment="browser history id")
    url = Column(String, comment="browsed url",index=True)
    ua = Column(String, comment="user agent")
    crawl_content = Column(TEXT, comment="crawl content",server_default=text("''"))
    crawl_type = Column(String, comment="crawl type")
    crawl_media = Column(JSONB, comment="crawl media json",server_default=text("{}"))
    crawl_metadata = Column(JSONB, comment="additional metadata json",server_default=text("{}"))
    crawl_screenshot = Column(String, comment="crawl screenshot url")
    crawl_time = Column(DateTime, comment="crawl time")
    visit_time = Column(DateTime, default=datetime.datetime.now(), comment="visit time")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="history create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="history update time")
    deleted = Column(Integer, default=0, comment="history delete flag")
    # jieba_cfg
    __table_args__ = (
        Index("ix_crawl_content",
              func.to_tsvector(text("'jieba_cfg'"), crawl_content),
              postgresql_using="gin"),
        Index("crawl_metadata",
              text("crawl_metadata"),
              postgresql_using="gin"),
    )