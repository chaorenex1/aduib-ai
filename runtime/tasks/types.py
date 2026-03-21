from dataclasses import dataclass
from typing import Any


@dataclass
class TaskExecutionResult:
    success: bool
    output: Any = None
    error: str | None = None
    meta: dict[str, Any] | None = None
