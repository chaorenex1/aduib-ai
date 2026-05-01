from __future__ import annotations

from pydantic import BaseModel, Field

from runtime.prompting.contracts.base import PromptMode


class CapabilityPolicy(BaseModel):
    allow_tools: bool
    allow_skills: bool
    allow_mcp: bool
    allow_subagents: bool
    allow_team_mailbox: bool
    allow_plan_artifacts: bool


class ModeDefinition(BaseModel):
    mode: PromptMode
    capability_policy: CapabilityPolicy
    system_section_ids: list[str] = Field(default_factory=list)
    user_meta_section_ids: list[str] = Field(default_factory=list)
    attachment_types: list[str] = Field(default_factory=list)
