import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DECIMAL,
    DateTime,
    UniqueConstraint,
    ForeignKeyConstraint,
    Text,
    UUID,
    text,
)

from . import Base


class Model(Base):
    """
    Model class for model.
    """

    __tablename__ = "model"
    id = Column(Integer, primary_key=True, index=True, comment="Model ID")
    name = Column(String, index=True, comment="Model Name")
    type = Column(String, index=True, comment="Model Type")
    provider_name = Column(String, index=True, comment="Model Provider")
    provider_id = Column(Integer, index=True, comment="Model Provider ID")
    max_tokens = Column(Integer, index=True, comment="Max Tokens")
    input_price = Column(DECIMAL(10, 7), comment="Input Price", server_default=text("'0.0000000'"))
    output_price = Column(DECIMAL(10, 7), comment="Output Price", server_default=text("'0.0000000'"))
    currency = Column(String, default="USD", comment="Model currency")
    feature = Column(Text, comment="Model Feature")
    model_params = Column(Text, comment="Model Params")
    default = Column(Integer, server_default="0", comment="Is Default Model")
    description = Column(String, comment="Model Description")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    __table_args__ = (
        UniqueConstraint("name", "provider_name", name="uq_model_name_provider"),
        ForeignKeyConstraint(["provider_id"], ["provider.id"], name="fk_model_provider_id"),
    )
