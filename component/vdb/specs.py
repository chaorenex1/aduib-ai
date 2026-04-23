from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VectorStoreSpec:
    collection_name: str
    attributes: list[str] = field(default_factory=list)
    embedding_dim: int | None = None
