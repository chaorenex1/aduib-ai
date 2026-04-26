from __future__ import annotations

from enum import StrEnum


class MemoryType(StrEnum):
    ENTITY = "entity"
    EVENT = "event"
    PATTERN = "pattern"
    PREFERENCE = "preference"
    PROFILE = "profile"
    REVIEW = "review"
    SKILL = "skill"
    SOLUTION = "solution"
    TASK = "task"
    TOOL = "tool"
    VERIFICATION = "verification"
    DEPLOYMENT = "deployment"
    INCIDENT = "incident"
    ROLLBACK = "rollback"
    RUNBOOK = "runbook"


class MemoryOpType(StrEnum):
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    IGNORE = "ignore"
    EXISTING = "existing"
    NOOP = "noop"


class MemoryMergeOpType(StrEnum):
    PATCH = "patch"
    SUM = "sum"
    REPLACE = "replace"
    IMMUTABLE = "immutable"


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
