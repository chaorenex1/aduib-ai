from __future__ import annotations

from pydantic import Field

from runtime.memory.base.contracts import MemoryContract, PlannerToolUseResult
from runtime.memory.project.contracts import ProjectDocumentPlan, ProjectMemoryScope


class ProjectPlanningState(MemoryContract):
    scope: ProjectMemoryScope
    source_payload: dict = Field(default_factory=dict)
    document_plans: list[ProjectDocumentPlan] = Field(default_factory=list)
    tool_results: list[PlannerToolUseResult] = Field(default_factory=list)

    def apply_tool_result(self, tool_result: PlannerToolUseResult) -> None:
        self.tool_results.append(tool_result)

    def apply_document_plans(self, document_plans: list[ProjectDocumentPlan]) -> None:
        self.document_plans = [item.model_copy(deep=True) for item in document_plans]

    def snapshot(self) -> dict:
        return {
            "scope": self.scope.model_dump(mode="python", exclude_none=True),
            "source_payload": self.source_payload,
            "document_plans": [item.model_dump(mode="python", exclude_none=True) for item in self.document_plans],
            "tool_results": [item.model_dump(mode="python", exclude_none=True) for item in self.tool_results],
        }
