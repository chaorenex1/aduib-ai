from __future__ import annotations

from pydantic import BaseModel, Field


class PromptProfile(BaseModel):
    profile_id: str
    title: str
    description: str = ""
    system_blocks: list[str] = Field(default_factory=list)
    user_meta_blocks: list[str] = Field(default_factory=list)
    default_section_overrides: dict[str, str] = Field(default_factory=dict)
    output_contract_name: str | None = None
    workflow_charter: str | None = None
    examples: list[str] = Field(default_factory=list)
