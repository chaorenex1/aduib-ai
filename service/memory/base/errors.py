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


class MemoryReadError(MemoryServiceError):
    code = "memory_read_error"


class MemoryReadNotFoundError(MemoryReadError):
    status_code = 404
    code = "memory_read_not_found"


class ConversationSourceError(MemoryServiceError):
    code = "conversation_source_error"


class ConversationSourceValidationError(ConversationSourceError):
    status_code = 400
    code = "conversation_source_validation_error"


class ConversationSourceNotFoundError(ConversationSourceError):
    status_code = 404
    code = "conversation_source_not_found"


class ConversationSourceConflictError(ConversationSourceError):
    status_code = 409
    code = "conversation_source_conflict"


class ConversationSourceCorruptedError(ConversationSourceError):
    status_code = 500
    code = "conversation_source_corrupted"


class MemoryProjectError(MemoryServiceError):
    code = "memory_project_error"


class MemoryProjectNotFoundError(MemoryProjectError):
    status_code = 404
    code = "memory_project_not_found"
