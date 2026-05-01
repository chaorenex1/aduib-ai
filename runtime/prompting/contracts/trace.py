from __future__ import annotations

from pydantic import BaseModel, Field

from runtime.prompting.contracts.base import PromptMode, PromptPhase


class PromptTrace(BaseModel):
    trace_id: str
    mode: PromptMode
    phase: PromptPhase
    section_ids: list[str] = Field(default_factory=list)
    attachment_ids: list[str] = Field(default_factory=list)
    cache_hits: list[str] = Field(default_factory=list)
    cache_misses: list[str] = Field(default_factory=list)
    skipped_sections: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
