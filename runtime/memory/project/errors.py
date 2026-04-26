from __future__ import annotations


class ProjectMemoryError(ValueError):
    """Base error for project-memory planning failures."""


class ProjectPayloadError(ProjectMemoryError):
    """Raised when a project import payload is malformed."""


class ProjectPathConflictError(ProjectMemoryError):
    """Raised when inferred project paths are inconsistent or invalid."""
