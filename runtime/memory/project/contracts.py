from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from runtime.memory.base.contracts import (
    MemoryContract,
    MemoryLineOperation,
    PlannerToolRequest,
    PlannerToolUseResult,
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

    @model_validator(mode="after")
    def validate_operation_shape(self) -> ProjectDocumentPlan:
        if self.target_family == "snippets" and not str(self.implementation or "").strip():
            raise ValueError("snippets project document plan requires implementation")

        if self.op == "write":
            if self.based_on_existing:
                raise ValueError("write project document plan cannot be based_on_existing")
            if not self.markdown_body.strip():
                raise ValueError("write project document plan requires markdown_body")
            if self.line_operations:
                raise ValueError("write project document plan must not include line_operations")
            return self

        if self.op == "edit":
            if not self.based_on_existing:
                raise ValueError("edit project document plan must be based_on_existing")
            if self.markdown_body.strip():
                raise ValueError("edit project document plan must not include markdown_body")
            if not self.line_operations:
                raise ValueError("edit project document plan requires line_operations")
            if not str(self.expected_body_sha256 or "").strip():
                raise ValueError("edit project document plan requires expected_body_sha256")
            return self

        if self.markdown_body.strip():
            raise ValueError("noop project document plan must not include markdown_body")
        if self.line_operations:
            raise ValueError("noop project document plan must not include line_operations")
        return self


class ProjectMemoryPlan(MemoryContract):
    scope: ProjectMemoryScope
    document_plans: list[ProjectDocumentPlan] = Field(default_factory=list)


class ProjectPlannerAction(MemoryContract):
    action: Literal["request_tools", "update_plan", "finalize", "stop_noop"]
    reasoning: str = Field(..., min_length=1)
    tool_requests: list[PlannerToolRequest] = Field(default_factory=list)
    document_plans: list[ProjectDocumentPlan] = Field(default_factory=list)


class ProjectOperationPlanResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    planner_status: str = Field(..., min_length=1)
    document_plans: list[ProjectDocumentPlan] = Field(default_factory=list)
    tools_used: list[PlannerToolUseResult] = Field(default_factory=list)
    planner_error: str | None = None
