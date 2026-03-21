import datetime

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class StoredResponse(Base):
    """
    Stores OpenAI Responses API responses for server-side conversation state management.
    Supports previous_response_id chaining and store=False opt-out.
    """

    __tablename__ = "stored_responses"

    id = Column(String(255), primary_key=True, comment="Response ID, e.g. resp_xxx")
    model = Column(String(255), nullable=False, index=True, comment="Model name used for this response")
    previous_response_id = Column(
        String(255), nullable=True, index=True, comment="ID of the preceding response in this conversation chain"
    )
    input_items = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Full effective input sent to the model (includes all prior context)",
    )
    output_items = Column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Output items returned by the model"
    )
    usage = Column(JSONB, nullable=True, comment="Token usage statistics")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Creation timestamp")
