from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TransformContext:
    """Resolved transform settings shared by processor pipelines."""

    split_rule: dict[str, Any]
    process_rule_mode: str
    chunk_size: int
    chunk_overlap: int
    separator: str
    doc_language: str | None = None
    normalize_leading_symbols: bool = True
