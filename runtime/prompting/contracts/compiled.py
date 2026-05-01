from __future__ import annotations

from pydantic import BaseModel, Field

from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.section import PromptSection


class RenderedMessage(BaseModel):
    role: str
    content: str
    is_meta: bool = False
    source: str | None = None


class CacheSegments(BaseModel):
    stable_system_sections: list[str] = Field(default_factory=list)
    session_system_sections: list[str] = Field(default_factory=list)
    volatile_system_sections: list[str] = Field(default_factory=list)


class CompiledPrompt(BaseModel):
    system_sections: list[PromptSection] = Field(default_factory=list)
    user_meta_sections: list[PromptSection] = Field(default_factory=list)
    attachments: list[PromptAttachment] = Field(default_factory=list)
    system_text: str = ""
    user_meta_messages: list[RenderedMessage] = Field(default_factory=list)
    attachment_messages: list[RenderedMessage] = Field(default_factory=list)
    cache_segments: CacheSegments = Field(default_factory=CacheSegments)
    trace_id: str
