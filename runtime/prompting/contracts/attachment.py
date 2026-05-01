from __future__ import annotations

from pydantic import BaseModel, Field


class PromptAttachment(BaseModel):
    attachment_id: str
    attachment_type: str
    content: str
    source: str
    priority: int = 0
    dedupe_key: str | None = None
    activation_reason: str | None = None
    dynamic_variables: dict[str, object] = Field(default_factory=dict)
