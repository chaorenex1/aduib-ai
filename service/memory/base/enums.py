from __future__ import annotations

from enum import StrEnum


class MemoryTriggerType(StrEnum):
    MEMORY_API = "memory_api"
    SESSION_COMMIT = "session_commit"


class MemoryTaskFinalStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class MemoryTaskPhase(StrEnum):
    ACCEPTED = "accepted"
    PREPARE_EXTRACT_CONTEXT = "prepare_extract_context"
    EXTRACT_OPERATIONS = "extract_operations"
    RESOLVE_OPERATIONS = "resolve_operations"
    BUILD_STAGED_WRITE_SET = "build_staged_write_set"
    APPLY_MEMORY_FILES = "apply_memory_files"
    REFRESH_NAVIGATION = "refresh_navigation"
    REFRESH_METADATA = "refresh_metadata"
    COMMITTED = "committed"
