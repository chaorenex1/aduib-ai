from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from runtime.memory.base.contracts import (
    MemoryContract,
    MemoryLineOperation,
    NavigationPlanningPreview,
    NavigationTarget,
)


class ProjectMemoryScope(MemoryContract):
    user_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    root_path: str = Field(..., min_length=1)
    docs_root_path: str = Field(..., min_length=1)
    project_docs_path: str = Field(..., min_length=1)
    snippets_path: str = Field(..., min_length=1)
    overview_path: str = Field(..., min_length=1)
    summary_path: str = Field(..., min_length=1)


class ProjectDocumentPlan(MemoryContract):
    target_family: Literal["docs", "snippets"]
    op: Literal["write", "edit", "noop"]
    target_path: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    based_on_existing: bool
    topic: str | None = None
    category: str | None = None
    domain: str | None = None
    implementation: str | None = None
    markdown_body: str = ""
    line_operations: list[MemoryLineOperation] = Field(default_factory=list)
    expected_body_sha256: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = Field(..., min_length=1)
    inference_notes: dict[str, Any] = Field(default_factory=dict)


class ProjectMemoryPlan(MemoryContract):
    scope: ProjectMemoryScope
    document_plans: list[ProjectDocumentPlan] = Field(default_factory=list)
    navigation_targets: list[NavigationTarget] = Field(default_factory=list)


class ProjectNavigationPreview(MemoryContract):
    planning_preview: NavigationPlanningPreview
    scope: ProjectMemoryScope
