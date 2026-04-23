from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import MemoryTaskFinalStatus, MemoryTaskPhase, MemoryTriggerType


class MemoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class MemorySourceRef(MemoryContract):
    type: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    path: str | None = None
    storage: str | None = None
    version: int | None = None
    message_ref: dict[str, Any] | None = None
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
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None


class MemoryWriteTaskView(MemoryWriteAccepted):
    queue_payload: dict[str, Any] | None = None
    result_ref: dict[str, Any] | None = None
    last_publish_error: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    last_error: str | None = None
    rollback_metadata: dict[str, Any] | None = None
    journal_ref: str | None = None
    operator_notes: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryWriteTaskResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    status: MemoryTaskFinalStatus | str | None = None
    phase: MemoryTaskPhase | str
    result_ref: dict[str, Any] | None = None
    archive_ref: ArchivedSourceRef | None = None
    journal_ref: str | None = None
    operator_notes: str | None = None
    last_error: str | None = None


class MemoryWritePipelineContext(MemoryContract):
    task_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    trigger_type: MemoryTriggerType
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    phase: MemoryTaskPhase | str
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None
    phase_results: dict[str, Any] = Field(default_factory=dict)


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
    schema_bundle: list[dict[str, Any]] = Field(default_factory=list)
    conversation_snapshot: dict[str, Any] | None = None
    session_snapshot: dict[str, Any] | None = None
    archived_snapshot: dict[str, Any] | None = None


class MemoryOperationEvidence(MemoryContract):
    kind: str = Field(default="message", min_length=1)
    content: str = Field(..., min_length=1)
    path: str | None = None


class ExtractedMemoryOperation(MemoryContract):
    op: Literal["write", "edit", "delete"]
    memory_type: str = Field(..., min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    evidence: list[MemoryOperationEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ResolvedMemoryOperation(MemoryContract):
    op: Literal["write", "edit", "delete"]
    memory_type: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    file_exists: bool
    merge_strategy: str = Field(..., min_length=1)
    memory_mode: Literal["simple", "template"]
    fields: dict[str, Any] = Field(default_factory=dict)
    field_merge_ops: dict[str, str] = Field(default_factory=dict)
    content: str = ""
    evidence: list[MemoryOperationEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    content_template: str | None = None
    schema_path: str | None = None


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
