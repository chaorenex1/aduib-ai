from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from runtime.memory.types.base import Memory, MemoryScope, MemoryType


@dataclass(slots=True)
class RetrievalResult:
    """检索结果封装。"""

    memory: Memory
    score: float
    source: str


class RetrievalEngine(ABC):
    """混合检索引擎抽象基类。"""

    @abstractmethod
    async def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """执行混合检索。"""

        raise NotImplementedError

    @abstractmethod
    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """向量相似度检索。"""

        raise NotImplementedError

    @abstractmethod
    async def search_by_entities(
        self,
        entity_ids: list[str],
        relation_types: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """基于实体的图检索。"""

        raise NotImplementedError
