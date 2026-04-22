from __future__ import annotations

from service.error.base import BaseServiceError


class MemoryServiceError(BaseServiceError):
    code = "memory_service_error"


class MemoryValidationError(MemoryServiceError):
    status_code = 400
    code = "memory_validation_error"


class MemoryArchiveError(MemoryServiceError):
    status_code = 500
    code = "memory_archive_error"


class MemoryWritePublishError(MemoryServiceError):
    status_code = 503
    code = "memory_queue_publish_failed"

    def __init__(self, message: str, *, task_id: str):
        super().__init__(message, details={"task_id": task_id})
        self.task_id = task_id


class MemoryWriteTaskError(MemoryServiceError):
    code = "memory_task_error"


class MemoryWriteTaskNotFoundError(MemoryWriteTaskError):
    status_code = 404
    code = "memory_task_not_found"


class MemoryWriteTaskReplayError(MemoryWriteTaskError):
    status_code = 409
    code = "memory_task_replay_conflict"
