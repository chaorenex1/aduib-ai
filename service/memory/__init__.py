"""Memory domain service package."""

from .builders import (
    build_memory_api_idempotency_key,
    build_queue_payload,
    build_task_request_idempotency_key,
    new_task_id,
    new_trace_id,
)
from .contracts import (
    ArchivedSourceRef,
    MemoryRetrievedMemory,
    MemoryRetrieveQuery,
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteAccepted,
    MemoryWriteCommand,
    MemoryWriteTaskResult,
    MemoryWriteTaskView,
)
from .enums import MemoryQueueStatus, MemoryTaskPhase, MemoryTaskStatus, MemoryTriggerType
from .errors import (
    MemoryArchiveError,
    MemoryServiceError,
    MemoryValidationError,
    MemoryWritePublishError,
    MemoryWriteTaskError,
    MemoryWriteTaskNotFoundError,
    MemoryWriteTaskReplayError,
)
from .mappers import (
    memory_create_request_to_command,
    memory_retrieve_request_to_query,
    retrieved_memories_to_response,
    task_create_request_to_command,
)
from .memory_service import MemoryService
from .paths import build_memory_api_archive_path, build_session_commit_archive_path, normalize_path_segment
from .source_archive_service import MemorySourceArchiveService
from .write_ingest_service import MemoryWriteIngestService
from .write_task_service import MEMORY_WRITE_TASK_NAME, MemoryWriteTaskService

__all__ = [
    "MEMORY_WRITE_TASK_NAME",
    "ArchivedSourceRef",
    "MemoryArchiveError",
    "MemoryQueueStatus",
    "MemoryRetrieveQuery",
    "MemoryRetrievedMemory",
    "MemoryService",
    "MemoryServiceError",
    "MemorySourceArchiveService",
    "MemorySourceRef",
    "MemoryTaskCreateCommand",
    "MemoryTaskPhase",
    "MemoryTaskStatus",
    "MemoryTriggerType",
    "MemoryValidationError",
    "MemoryWriteAccepted",
    "MemoryWriteCommand",
    "MemoryWriteIngestService",
    "MemoryWritePublishError",
    "MemoryWriteTaskError",
    "MemoryWriteTaskNotFoundError",
    "MemoryWriteTaskReplayError",
    "MemoryWriteTaskResult",
    "MemoryWriteTaskService",
    "MemoryWriteTaskView",
    "build_memory_api_archive_path",
    "build_memory_api_idempotency_key",
    "build_queue_payload",
    "build_session_commit_archive_path",
    "build_task_request_idempotency_key",
    "memory_create_request_to_command",
    "memory_retrieve_request_to_query",
    "new_task_id",
    "new_trace_id",
    "normalize_path_segment",
    "retrieved_memories_to_response",
    "task_create_request_to_command",
]
