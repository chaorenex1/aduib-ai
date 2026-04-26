from __future__ import annotations

from runtime.memory.base.contracts import MemorySourceRef
from runtime.memory.extract.tools import PlannerToolExecutor
from runtime.memory.project.contracts import (
    ProjectMemoryPlan,
    ProjectMemoryScope,
    ProjectOperationPlanResult,
)
from runtime.memory.project.errors import ProjectPayloadError
from runtime.memory.project.planner import ProjectPlanner
from runtime.memory.project.working_state import ProjectPlanningState


class ProjectMemoryManager:
    """Coordinates strict LLM-only planning for project memory imports."""

    def __init__(self) -> None:
        self.planner = ProjectPlanner()
        self.tool_executor = PlannerToolExecutor()

    def build_scope(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectMemoryScope:
        root_path = f"users/{user_id}/project"
        docs_root_path = f"{root_path}/docs"
        project_docs_path = f"{docs_root_path}/{project_id}"
        snippets_path = f"{root_path}/snippets"
        return ProjectMemoryScope(
            user_id=user_id,
            project_id=project_id,
            root_path=root_path,
            docs_root_path=docs_root_path,
            project_docs_path=project_docs_path,
            snippets_path=snippets_path,
            overview_path=f"{root_path}/overview.md",
            summary_path=f"{root_path}/summary.md",
        )

    def plan_import(
        self,
        *,
        scope: ProjectMemoryScope,
        source_ref: MemorySourceRef,
    ) -> ProjectMemoryPlan:
        plan_result = self.run_planning(scope=scope, source_ref=source_ref)
        return ProjectMemoryPlan(
            scope=scope,
            document_plans=[item.model_copy(deep=True) for item in plan_result.document_plans],
        )

    def run_planning(
        self,
        *,
        scope: ProjectMemoryScope,
        source_ref: MemorySourceRef,
    ) -> ProjectOperationPlanResult:
        payload = self._require_project_payload(source_ref)
        working_state = ProjectPlanningState(
            scope=scope,
            source_payload=payload,
            document_plans=[],
        )
        task_id = str(scope.project_id)
        max_turns = 6
        for _ in range(max_turns):
            action = self.planner.next_action(working_state=working_state)
            if action.action == "request_tools":
                for request in action.tool_requests:
                    working_state.apply_tool_result(self.tool_executor.execute_sync(request))
                continue
            if action.action == "update_plan":
                working_state.apply_document_plans([item.model_copy(deep=True) for item in action.document_plans])
                continue
            if action.action == "finalize":
                next_document_plans = (
                    [item.model_copy(deep=True) for item in action.document_plans]
                    if action.document_plans
                    else [item.model_copy(deep=True) for item in working_state.document_plans]
                )
                working_state.apply_document_plans(next_document_plans)
                return ProjectOperationPlanResult(
                    task_id=task_id,
                    planner_status="planned",
                    document_plans=[item.model_copy(deep=True) for item in working_state.document_plans],
                    tools_used=[item.model_copy(deep=True) for item in working_state.tool_results],
                )
            if action.action == "stop_noop":
                return ProjectOperationPlanResult(
                    task_id=task_id,
                    planner_status="noop",
                    document_plans=[],
                    tools_used=[item.model_copy(deep=True) for item in working_state.tool_results],
                )
            raise ProjectPayloadError(f"unsupported project planner action: {action.action}")
        raise ProjectPayloadError("project planner exceeded maximum turns")

    def _require_project_payload(self, source_ref: MemorySourceRef) -> dict:
        if source_ref.type != "project_memory_import":
            raise ProjectPayloadError(f"unsupported source_ref.type for project import: {source_ref.type}")
        payload = source_ref.project_payload or {}
        if not isinstance(payload, dict):
            raise ProjectPayloadError("project_payload must be an object")
        return payload
