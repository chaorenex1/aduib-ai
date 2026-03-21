import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class ApiKey(Base):
    __tablename__ = "api_key_info"
    __table_args__ = {
        "comment": "api key table",
    }
    id = Column(Integer, primary_key=True, index=True, comment="api key id")
    name = Column(String, comment="api key name")
    api_key = Column(String, unique=True, comment="api key")
    hash_key = Column(String, unique=True, comment="api key hash")
    salt = Column(String, comment="api key salt")
    description = Column(String, comment="api key description")
    source = Column(String, comment="api key source")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True, comment="bound user id")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="api key create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="api key update time")
    deleted = Column(Integer, default=0, comment="api key delete flag")

    user=relationship("User")
