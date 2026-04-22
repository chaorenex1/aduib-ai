from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import MemoryQueueStatus, MemoryTaskPhase, MemoryTaskStatus, MemoryTriggerType


class MemoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class MemorySourceRef(MemoryContract):
    type: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    external_source: str | None = None
    external_session_id: str | None = None


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
    status: MemoryTaskStatus
    phase: MemoryTaskPhase | str
    queue_status: MemoryQueueStatus
    source_ref: MemorySourceRef
    archive_ref: ArchivedSourceRef | None = None


class MemoryWriteTaskView(MemoryWriteAccepted):
    queue_payload: dict[str, Any] | None = None
    result_ref: dict[str, Any] | None = None
    retry_count: int = 0
    retry_budget: int = 0
    last_publish_error: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    last_error: str | None = None
    rollback_metadata: dict[str, Any] | None = None
    journal_ref: str | None = None
    operator_notes: str | None = None
    replayed_by: str | None = None
    replayed_at: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryWriteTaskResult(MemoryContract):
    task_id: str = Field(..., min_length=1)
    status: MemoryTaskStatus | str
    phase: MemoryTaskPhase | str
    result_ref: dict[str, Any] | None = None
    archive_ref: ArchivedSourceRef | None = None
    journal_ref: str | None = None
    operator_notes: str | None = None
    last_error: str | None = None
