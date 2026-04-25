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
    MEMORY_UPDATER = "memory_updater"
    COMMITTED = "committed"


class OrchestratorStep(StrEnum):
    CHANGE_PLAN = "change_plan"
    OPERATIONS = "operations"
