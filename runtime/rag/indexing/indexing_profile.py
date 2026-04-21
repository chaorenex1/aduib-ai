from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class IndexingProfile:
    """Resolved indexing policy for one knowledge base and operation mode."""

    with_keywords: bool = True
    full_delete_method: Literal["delete", "delete_all"] = "delete"
