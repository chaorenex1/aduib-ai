from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import MemoryTaskFinalStatus, MemoryTaskPhase, MemoryTriggerType, OrchestratorStep


class MemoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @classmethod
    def json_schema(cls) -> str:
        return json.dumps(cls.model_json_schema(), ensure_ascii=False, indent=2)


class MemorySourceRef(MemoryContract):
    type: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    external_source: str | None = None
    external_session_id: str | None = None


class ConversationSourceMetadata(MemoryContract):
    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class ConversationContentPart(MemoryContract):
    type: str = Field(..., min_length=1)
    text: str | None = None
    data_base64: str | None = None
    file_id: str | None = None
    mime_type: str | None = None
    name: str | None = None


class ConversationMessageRecord(MemoryContract):
    role: str = Field(..., min_length=1)
    content_parts: list[ConversationContentPart] = Field(default_factory=list, min_length=1)
    created_at: str | None = None


class ConversationSourceCreateCommand(MemoryContract):
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    external_source: str = Field(..., min_length=1)
    external_session_id: str = Field(..., min_length=1)
    title: str | None = None
    messages: list[ConversationMessageRecord] = Field(default_factory=list, min_length=1)
    metadata: ConversationSourceMetadata | None = None


class ConversationSourceAppendCommand(MemoryContract):
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    conversation_id: str = Field(..., min_length=1)
    message: ConversationMessageRecord


class ConversationSourceGetQuery(MemoryContract):
    user_id: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)


class ConversationMessageRef(MemoryContract):
    type: str = Field(..., min_length=1)
    uri: str = Field(..., min_length=1)
    path: str | None = None
    sha256: str | None = None


class ConversationSourceView(MemoryContract):
    conversation_id: str = Field(..., min_length=1)
    type: str = Field(default="conversation", min_length=1)
    title: str | None = None
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    external_source: str = Field(..., min_length=1)
    external_session_id: str = Field(..., min_length=1)
    message_ref: ConversationMessageRef
    message_count: int = Field(..., ge=1)
    modalities: list[str] = Field(default_factory=list)
    version: int = Field(..., ge=1)
    created_at: str | None = None
    updated_at: str | None = None


class ConversationAppendResult(MemoryContract):
    conversation_id: str = Field(..., min_length=1)
    appended: bool = True
    message_count: int = Field(..., ge=1)
    version: int = Field(..., ge=1)
    updated_at: str | None = None


class MemoryWriteCommand(MemoryContract):
    content: str | None = None
    file_content: str | None = None
    file_name: str | None = None
    project_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    summary_enabled: bool = False
    memory_source: str | None = None


class MemoryTaskCreateCommand(MemoryContract):
    trigger_type: MemoryTriggerType
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    source_ref: MemorySourceRef


class MemoryRetrieveQuery(MemoryContract):
    query: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    retrieve_type: str = Field(..., min_length=1)
    top_k: int = 5
    score_threshold: float = 0.6
    filters: dict[str, Any] = Field(default_factory=dict)


class ArchivedSourceRef(MemoryContract):
    path: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    storage: str = Field("default", min_length=1)
    content_sha256: str | None = None
    size_bytes: int | None = None


class MemoryRetrievedMemory(MemoryContract):
    content: str
    memory_id: str = Field(..., min_length=1)
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryWriteAccepted(MemoryContract):
    task_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    trigger_type: MemoryTriggerType
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    status: MemoryTaskFinalStatus | None = None
    phase: MemoryTaskPhase | str
    stage: str | None = None
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None


class MemoryWriteTaskView(MemoryWriteAccepted):
    failure_message: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryWriteTaskResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    status: MemoryTaskFinalStatus | str | None = None
    phase: MemoryTaskPhase | str
    stage: str | None = None
    archive_ref: ArchivedSourceRef | None = None
    failure_message: str | None = None


class PreparedExtractContext(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: MemoryTaskPhase | str = MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT
    source_kind: str = Field(..., min_length=1)
    source_hash: str = Field(..., min_length=1)
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    language: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    text_blocks: list[str] = Field(default_factory=list)
    prefetched_context: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
    conversation_snapshot: dict[str, Any] | None = None
    session_snapshot: dict[str, Any] | None = None
    archived_snapshot: dict[str, Any] | None = None

    def prefetched_read_paths(self) -> set[str]:
        prefetched = self.prefetched_context or {}
        file_reads = prefetched.get("file_reads") or []
        paths = {
            str(path).strip()
            for path in (prefetched.get("already_read_paths") or [])
            if str(path).strip()
        }
        paths.update(
            str(item.get("path") or "").strip()
            for item in file_reads
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        )
        return paths


class MemoryOperationEvidence(MemoryContract):
    kind: str = Field(default="message", min_length=1)
    content: str = Field(..., min_length=1)
    path: str | None = None


class MemoryChangePlanItem(MemoryContract):
    memory_type: str = Field(..., min_length=1)
    target_branch: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    op: Literal["write", "edit", "delete", "ignore"]
    reasoning: str = Field(..., min_length=1)


class PlannerToolRequest(MemoryContract):
    tool: Literal["ls", "read", "find"]
    args: dict[str, Any] = Field(default_factory=dict)


class PlannerToolUseResult(MemoryContract):
    tool: Literal["ls", "read", "find"]
    args: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class MemoryLineOperation(MemoryContract):
    kind: Literal["replace_range", "delete_range", "insert_after", "insert_before", "append_eof"]
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    anchor_text: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    reasoning: str = Field(..., min_length=1)


class ExtractedMemoryFieldPlan(MemoryContract):
    name: str = Field(..., min_length=1)
    value: Any = None
    merge_op: Literal["patch", "sum", "replace", "immutable"]
    line_operations: list[MemoryLineOperation] = Field(default_factory=list)
    reasoning: str = Field(..., min_length=1)


class ExtractedMemoryOperation(MemoryContract):
    memory_type: str = Field(..., min_length=1)
    target_branch: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    reasoning: str = Field(..., min_length=1)
    fields: list[ExtractedMemoryFieldPlan] = Field(default_factory=list)


class MemoryReadEvidence(MemoryContract):
    path: str = Field(..., min_length=1)
    content: str = ""
    source: Literal["prefetch", "tool_read"]


class MemoryTargetProgress(MemoryContract):
    target_key: str = Field(..., min_length=1)
    change_plan_item: MemoryChangePlanItem
    status: Literal["awaiting_read", "ready_for_operation", "operated", "ignored"]
    required_read_path: str | None = None
    read_evidence_paths: list[str] = Field(default_factory=list)
    operation_item: ExtractedMemoryOperation | None = None


class OrchestratorWorkingState(MemoryContract):
    prefetched_read_paths: list[str] = Field(default_factory=list)
    targets: list[MemoryTargetProgress] = Field(default_factory=list)
    planning_complete: bool = False
    tool_results: list[PlannerToolUseResult] = Field(default_factory=list)

    @staticmethod
    def operation_target_key(
        *,
        memory_type: str,
        target_branch: str,
        filename: str,
    ) -> str:
        return "|".join(
            [
                str(memory_type or "").strip(),
                str(target_branch or "").strip(),
                str(filename or "").strip(),
            ]
        )

    @staticmethod
    def target_key(
        *,
        memory_type: str,
        target_branch: str,
        filename: str,
    ) -> str:
        return OrchestratorWorkingState.operation_target_key(
            memory_type=memory_type,
            target_branch=target_branch,
            filename=filename,
        )

    def apply_state_delta(self, *, step: OrchestratorStep, state_delta: OrchestratorStateDelta) -> None:
        if step == OrchestratorStep.CHANGE_PLAN and state_delta.operation_item is not None:
            raise ValueError("change_plan step cannot apply operation_item")
        if step == OrchestratorStep.OPERATIONS and state_delta.planning_complete is not None:
            raise ValueError("operations step cannot update planning_complete")

        if state_delta.change_plan_item is not None:
            self.upsert_change_plan_item(
                item=state_delta.change_plan_item,
                supersedes_target_key=state_delta.supersedes_target_key,
            )
        if state_delta.planning_complete is not None:
            self.planning_complete = state_delta.planning_complete
        if state_delta.operation_item is not None:
            self.apply_operation_item(state_delta.operation_item)

    def apply_tool_result(self, result: PlannerToolUseResult) -> None:
        self.tool_results.append(result)
        if result.tool != "read":
            return
        observed_paths = {
            str((result.args or {}).get("path") or "").strip(),
            str((result.result or {}).get("path") or "").strip(),
        }
        observed_paths = {path for path in observed_paths if path}
        if not observed_paths:
            return
        for target in self.targets:
            if target.status != "awaiting_read" or not target.required_read_path:
                continue
            if target.required_read_path not in observed_paths:
                continue
            for path in sorted(observed_paths):
                if path not in target.read_evidence_paths:
                    target.read_evidence_paths.append(path)
            target.status = "ready_for_operation"

    def upsert_change_plan_item(
        self,
        *,
        item: MemoryChangePlanItem,
        supersedes_target_key: str | None = None,
    ) -> None:
        new_target_key = self.operation_target_key(
            memory_type=item.memory_type,
            target_branch=item.target_branch,
            filename=item.filename,
        )
        insert_index: int | None = None
        carryover = self._pop_target(supersedes_target_key) if supersedes_target_key else None
        if carryover is not None:
            insert_index = carryover[0]
        existing_same = self._pop_target(new_target_key)
        if existing_same is not None and insert_index is None:
            insert_index = existing_same[0]
        existing_target = (
            carryover[1]
            if carryover is not None and carryover[1].target_key == new_target_key
            else (existing_same[1] if existing_same is not None else None)
        )
        read_evidence_paths = list(existing_target.read_evidence_paths) if existing_target is not None else []
        operation_item = existing_target.operation_item if existing_target is not None else None
        target = self._build_target_progress(
            item=item,
            target_key=new_target_key,
            read_evidence_paths=read_evidence_paths,
            operation_item=operation_item,
        )
        if insert_index is None or insert_index >= len(self.targets):
            self.targets.append(target)
        else:
            self.targets.insert(insert_index, target)

    def apply_operation_item(self, item: ExtractedMemoryOperation) -> None:
        target_key = self.operation_target_key(
            memory_type=item.memory_type,
            target_branch=item.target_branch,
            filename=item.filename,
        )
        target = self._target_by_key(target_key)
        if target is None:
            raise ValueError(f"operation target does not exist in working state: {target_key}")
        if target.change_plan_item.op == "ignore":
            raise ValueError(f"operation target is ignored: {target_key}")
        if target.status == "awaiting_read":
            raise ValueError(f"operation target requires prior read evidence: {target_key}")
        target.operation_item = item
        target.status = "operated"

    def next_target_awaiting_read(self) -> MemoryTargetProgress | None:
        return next((item for item in self.targets if item.status == "awaiting_read"), None)

    def next_target_ready_for_operation(self) -> MemoryTargetProgress | None:
        return next((item for item in self.targets if item.status == "ready_for_operation"), None)

    def finalized_change_plan(self) -> list[MemoryChangePlanItem]:
        return [item.change_plan_item for item in self.targets]

    def finalized_operations(self) -> list[ExtractedMemoryOperation]:
        return [item.operation_item for item in self.targets if item.operation_item is not None]

    def has_executable_targets(self) -> bool:
        return any(item.change_plan_item.op in {"write", "edit", "delete"} for item in self.targets)

    def _target_by_key(self, target_key: str) -> MemoryTargetProgress | None:
        return next((item for item in self.targets if item.target_key == target_key), None)

    def _pop_target(self, target_key: str | None) -> tuple[int, MemoryTargetProgress] | None:
        if not target_key:
            return None
        for index, item in enumerate(self.targets):
            if item.target_key == target_key:
                self.targets.pop(index)
                return index, item
        return None

    def _build_target_progress(
        self,
        *,
        item: MemoryChangePlanItem,
        target_key: str,
        read_evidence_paths: list[str],
        operation_item: ExtractedMemoryOperation | None,
    ) -> MemoryTargetProgress:
        required_read_path = f"{item.target_branch}/{item.filename}" if item.op == "edit" else None
        observed_reads = {path for path in self.prefetched_read_paths if path}
        observed_reads.update(path for path in read_evidence_paths if path)
        if item.op == "ignore":
            status = "ignored"
            required_read_path = None
            operation_item = None
        elif required_read_path and required_read_path not in observed_reads:
            status = "awaiting_read"
            operation_item = None
        elif operation_item is not None:
            status = "operated"
        else:
            status = "ready_for_operation"
        return MemoryTargetProgress(
            target_key=target_key,
            change_plan_item=item,
            status=status,
            required_read_path=required_read_path,
            read_evidence_paths=sorted(set(read_evidence_paths)),
            operation_item=operation_item,
        )


class OrchestratorStateDelta(MemoryContract):
    change_plan_item: MemoryChangePlanItem | None = None
    supersedes_target_key: str | None = None
    planning_complete: bool | None = None
    operation_item: ExtractedMemoryOperation | None = None


class OrchestratorAction(MemoryContract):
    action: Literal[
        "request_tools",
        "update_state",
        "finalize",
        "stop_noop",
    ]
    step: OrchestratorStep | None = None
    reasoning: str = ""
    tool_requests: list[PlannerToolRequest] = Field(default_factory=list)
    state_delta: OrchestratorStateDelta | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> OrchestratorAction:
        if self.action == "request_tools" and (not self.tool_requests or self.step is None):
            raise ValueError("request_tools action requires tool_requests")
        if self.action == "update_state" and (self.state_delta is None or self.step is None):
            raise ValueError("update_state action requires step and state_delta")
        return self


class ReasoningTraceStep(MemoryContract):
    step: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractOperationsPhaseResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="extract_operations", min_length=1)
    planner_status: str = Field(..., min_length=1)
    change_plan: list[MemoryChangePlanItem] = Field(default_factory=list)
    structured_operations: list[ExtractedMemoryOperation] = Field(default_factory=list)
    tools_available: list[str] = Field(default_factory=list)
    tools_used: list[PlannerToolUseResult] = Field(default_factory=list)
    reasoning_trace: list[ReasoningTraceStep] = Field(default_factory=list)
    planner_error: str | None = None


class MemoryUpdateContext(MemoryContract):
    task_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    trigger_type: MemoryTriggerType
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None
    prepared_context: PreparedExtractContext
    extract_result: ExtractOperationsPhaseResult

    @classmethod
    def from_task(
        cls,
        *,
        task,
        prepared_context: PreparedExtractContext,
        extract_result: ExtractOperationsPhaseResult,
    ) -> MemoryUpdateContext:
        return cls(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            user_id=getattr(task, "user_id", None),
            agent_id=getattr(task, "agent_id", None),
            project_id=getattr(task, "project_id", None),
            source_ref=task.source_ref,
            archive_ref=task.archive_ref,
            prepared_context=prepared_context,
            extract_result=extract_result,
        )


class NavigationBranchFileState(MemoryContract):
    path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    op: Literal["write", "edit", "delete", "existing"]
    desired_content: str | None = None
    previous_content: str | None = None


class NavigationDocumentPlan(MemoryContract):
    op: Literal["write", "edit", "noop"]
    path: str = Field(..., min_length=1)
    markdown_body: str = ""
    based_on_existing: bool


class NavigationSummaryBranchPlan(MemoryContract):
    branch_path: str = Field(..., min_length=1)
    overview: NavigationDocumentPlan
    summary: NavigationDocumentPlan


class GenerateNavigationSummaryPhaseResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="generate_navigation_summary", min_length=1)
    navigation_mutations: list[NavigationSummaryBranchPlan] = Field(default_factory=list)
    planner_error: str | None = None


class ResolvedMemoryOperation(MemoryContract):
    op: Literal["write", "edit", "delete"]
    memory_type: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    file_exists: bool
    merge_strategy: str = Field(..., min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    field_merge_ops: dict[str, str] = Field(default_factory=dict)
    field_plans: list[ExtractedMemoryFieldPlan] = Field(default_factory=list)
    content: str = ""
    content_template: str | None = None
    schema_path: str | None = None


class ResolveOperationsResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="resolve_operations", min_length=1)
    resolved_operations: list[ResolvedMemoryOperation] = Field(default_factory=list)
    navigation_scopes: list[str] = Field(default_factory=list)
    metadata_scopes: list[str] = Field(default_factory=list)


class MemoryMutationPlan(MemoryContract):
    op: Literal["write", "edit", "delete"]
    memory_type: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    desired_content: str | None = None
    previous_content: str | None = None
    file_exists: bool
    memory_mode: str = Field(..., min_length=1)
    merge_strategy: str = Field(..., min_length=1)


class NavigationTarget(MemoryContract):
    branch_path: str = Field(..., min_length=1)
    overview_path: str = Field(..., min_length=1)
    summary_path: str = Field(..., min_length=1)


class MetadataTarget(MemoryContract):
    scope_path: str = Field(..., min_length=1)


class RollbackPlan(MemoryContract):
    snapshot: dict[str, Any] = Field(default_factory=dict)
    target_paths: list[str] = Field(default_factory=list)


class PatchPlanResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="build_staged_write_set", min_length=1)
    memory_mutations: list[MemoryMutationPlan] = Field(default_factory=list)
    navigation_targets: list[NavigationTarget] = Field(default_factory=list)
    metadata_targets: list[MetadataTarget] = Field(default_factory=list)
    rollback_plan: RollbackPlan = Field(default_factory=RollbackPlan)
    journal_entries: list[dict[str, Any]] = Field(default_factory=list)
    staging_manifest: dict[str, int] = Field(default_factory=dict)


class PatchApplyResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="apply_memory_files", min_length=1)
    applied_memory_files: list[str] = Field(default_factory=list)
    journal_ref: str | None = None
    rollback_metadata: dict[str, Any] = Field(default_factory=dict)


class NavigationSummaryResult(GenerateNavigationSummaryPhaseResult):
    pass


class NavigationRefreshResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="refresh_navigation", min_length=1)
    navigation_files: list[str] = Field(default_factory=list)


class MetadataRefreshResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    phase: str = Field(default="refresh_metadata", min_length=1)
    metadata_scopes: list[str] = Field(default_factory=list)
    record_counts: dict[str, int] = Field(default_factory=dict)


class NavigationManagerResult(MemoryContract):
    summary_result: NavigationSummaryResult
    refresh_result: NavigationRefreshResult
    metadata_result: MetadataRefreshResult


class MemoryCommittedResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    status: str = Field(default="success", min_length=1)
    final_phase: str = Field(default="committed", min_length=1)
    final_stage: str = Field(default="committed", min_length=1)
    extract_result: ExtractOperationsPhaseResult
    resolve_result: ResolveOperationsResult
    patch_plan_result: PatchPlanResult
    patch_apply_result: PatchApplyResult
    navigation_result: NavigationManagerResult
    journal_ref: str | None = None
    rollback_metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryReadRecord(MemoryContract):
    memory_id: str = Field(..., min_length=1)
    memory_class: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    scope_type: str = Field(..., min_length=1)
    scope_path: str = Field(..., min_length=1)
    directory_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    topic: str | None = None
    source_type: str | None = None
    visibility: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)
    file_sha256: str | None = None
    content_bytes: int | None = None
    projection_payload: dict[str, Any] = Field(default_factory=dict)
    memory_created_at: str | None = None
    memory_updated_at: str | None = None
    indexed_at: str | None = None
    refreshed_by_task_id: str | None = None


class MemoryReadListResult(MemoryContract):
    items: list[MemoryReadRecord] = Field(default_factory=list)
    next_cursor: str | None = None


class MemoryContentResult(MemoryContract):
    memory_id: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
