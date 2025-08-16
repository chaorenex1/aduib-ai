import datetime

from sqlalchemy import Column, Integer, String, DECIMAL, JSON, DateTime, UniqueConstraint, ForeignKeyConstraint

from . import Base


class Model(Base):
    """
    Model class for model.
    """
    __tablename__ = 'model'
    id = Column(Integer, primary_key=True,index=True,comment="Model ID")
    name = Column(String, index=True, comment="Model Name")
    type = Column(String, index=True, comment="Model Type")
    provider_name = Column(String, index=True, comment="Model Provider")
    provider_id = Column(Integer, index=True, comment="Model Provider ID")
    max_tokens = Column(Integer, index=True, comment="Max Tokens")
    input_price = Column(DECIMAL(10,2), comment="Input Price",default=0.00)
    output_price = Column(DECIMAL(10,2), comment="Output Price",default=0.00)
    feature=Column(JSON, comment="Model Feature")
    model_params=Column(JSON, comment="Model Params")
    description = Column(String, comment="Model Description")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="api key create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="api key update time")
    deleted = Column(Integer, default=0, comment="api key delete flag")
    UniqueConstraint('name', 'provider', name='uq_model_name_provider')
    ForeignKeyConstraint(['name','provider_id'], ['name','provider_id'])