import datetime

from sqlalchemy import Column, String, UUID, text, DateTime, Integer, Text, Index, func

from models import Base


class ConversationMessage(Base):
    """
    Conversation message model.
    """
    __tablename__ = "conversation_message"
    # uuid primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    message_id = Column(String, nullable=False, comment="conversation id")
    model_name= Column(String, nullable=False, comment="model name used for this message",index=True)
    provider_name = Column(String, nullable=False, comment="provider name used for this message", index=True)
    system_prompt: str = Column(Text, nullable=True, comment="system prompt for the conversation",server_default=text("''"))
    content: str = Column(Text, nullable=False, comment="message content",server_default=text("''"))
    role: str = Column(String, nullable=False, comment="message role (user/assistant)")
    usage: str = Column(Text, nullable=True, comment="message usage information")
    state: str = Column(String, nullable=False, comment="message state",default="success")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    #jieba_cfg
    __table_args__ = (
        Index("ix_content",
              func.to_tsvector(text("'jieba_cfg'"), content),
              postgresql_using="gin"),
        Index("ix_system_prompt",
              func.to_tsvector(text("'jieba_cfg'"), system_prompt),
              postgresql_using="gin"),
    )
