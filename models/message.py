import datetime

from sqlalchemy import Column, String, UUID, text, DateTime, Integer, Text, Index, func, Float, DECIMAL

from models import Base


class ConversationMessage(Base):
    """
    Conversation message model.
    """

    __tablename__ = "conversation_message"
    # uuid primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    agent_id = Column(Integer, nullable=True, comment="agent id", index=True)
    agent_session_id = Column(Integer, nullable=True, comment="agent session id", index=True)
    message_id = Column(String, nullable=False, comment="conversation id")
    model_name = Column(String, nullable=False, comment="model name used for this message", index=True)
    provider_name = Column(String, nullable=False, comment="provider name used for this message", index=True)
    system_prompt= Column(
        Text, nullable=True, comment="system prompt for the conversation", server_default=text("''")
    )
    content= Column(Text, nullable=False, comment="message content", server_default=text("''"))
    role= Column(String, nullable=False, comment="message role (user/assistant)")
    usage= Column(Text, nullable=True, comment="message usage information")
    state= Column(String, nullable=False, comment="message state", default="success")
    extracted_state= Column(Integer, nullable=False, comment="message extracted state", server_default=text("0"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    # jieba_cfg
    __table_args__ = (
        Index("ix_content", func.to_tsvector(text("'jieba_cfg'"), content), postgresql_using="gin"),
        Index("ix_system_prompt", func.to_tsvector(text("'jieba_cfg'"), system_prompt), postgresql_using="gin"),
    )


class MessageTokenUsage(Base):
    """
    ModelUsageLog class for model usage log.
    """

    __tablename__ = "message_token_usage"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"), comment="id")
    agent_id = Column(Integer, nullable=True, comment="agent id", index=True)
    agent_session_id = Column(Integer, nullable=True, comment="agent session id", index=True)
    message_id = Column(String, nullable=False, comment="message id", index=True)
    model_name = Column(String, nullable=False, comment="model name", index=True)
    provider_name = Column(String, nullable=False, comment="provider name", index=True)
    prompt_tokens = Column(Integer, nullable=False, server_default=text("'0'"), comment="number of prompt tokens")
    completion_tokens = Column(
        Integer, nullable=False, server_default=text("'0'"), comment="number of completion tokens"
    )
    total_tokens = Column(Integer, nullable=False, server_default=text("'0'"), comment="total number of tokens")
    prompt_unit_price = Column(DECIMAL(10, 7), nullable=False, server_default=text("'0.0000000'"), comment="prompt unit price")
    prompt_price = Column(DECIMAL(10, 7), nullable=False, server_default=text("'0.0000000'"), comment="prompt price")
    completion_unit_price = Column(
        DECIMAL(10, 7), nullable=False, server_default=text("'0.0000000'"), comment="completion unit price"
    )
    completion_price = Column(DECIMAL(10, 7), nullable=False, server_default=text("'0.0000000'"), comment="completion price")
    total_price = Column(DECIMAL(10, 7), nullable=False, server_default=text("'0.0000000'"), comment="total price")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
