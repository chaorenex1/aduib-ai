from __future__ import annotations

from pydantic import BaseModel, Field

from runtime.prompting.contracts.base import PromptCachePolicy, PromptChannel


class PromptSection(BaseModel):
    section_id: str
    title: str
    channel: PromptChannel
    cache_policy: PromptCachePolicy
    content: str
    source: str
    activation_reason: str | None = None
    dynamic_variables: dict[str, object] = Field(default_factory=dict)
