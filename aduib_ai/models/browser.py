import datetime

from sqlalchemy import Column, DateTime, Integer, String, text, UUID, BOOLEAN, Index, func, TEXT

from models import Base


class BrowserHistory(Base):
    __tablename__ = "browser_history"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"),comment="browser history id")
    url = Column(String, comment="browsed url",index=True)
    ua = Column(String, comment="user agent")
    title = Column(String, comment="page title")
    crawl_task_id = Column(String, comment="crawl task id")
    crawl_content = Column(TEXT, comment="crawl content")
    crawl_screenshot = Column(String, comment="crawl screenshot url")
    crawl_time = Column(DateTime, comment="crawl time")
    crawl_status = Column(BOOLEAN, comment="crawl status", default=False)
    visit_time = Column(DateTime, default=datetime.datetime.now(), comment="visit time")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="history create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="history update time")
    deleted = Column(Integer, default=0, comment="history delete flag")
    # jieba_cfg
    __table_args__ = (
        Index("ix_content",
              func.to_tsvector(text("'jieba_cfg'"), crawl_content),
              postgresql_using="gin"),
    )