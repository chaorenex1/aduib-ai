import datetime

from sqlalchemy import Column, Integer, String, JSON, DateTime

from . import Base


class Provider(Base):
    __tablename__ = 'provider'
    id = Column(Integer, primary_key=True,index=True,comment="Provider ID")
    name = Column(String, nullable=False, unique=True, comment="Provider Name")
    support_model_type = Column(JSON, nullable=False, comment="Supported Model")
    provider_type = Column(String, nullable=False, comment="Provider Type")
    provider_config = Column(JSON, nullable=False, comment="Provider Config")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="api key create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="api key update time")
    deleted = Column(Integer, default=0, comment="api key delete flag")
