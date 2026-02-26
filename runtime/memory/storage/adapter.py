from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from runtime.memory.types.base import Memory

MemoryT = TypeVar("MemoryT", bound=Memory)


class StorageAdapter(ABC, Generic[MemoryT]):
    """统一存储适配器抽象基类。"""

    @abstractmethod
    async def save(self, memory: MemoryT) -> str:
        """保存记忆，返回 ID。"""

    @abstractmethod
    async def get(self, memory_id: str) -> Optional[MemoryT]:
        """根据 ID 获取记忆。"""

    @abstractmethod
    async def update(self, memory_id: str, updates: dict) -> Optional[MemoryT]:
        """更新记忆。"""

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """删除记忆。"""

    @abstractmethod
    async def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在。"""

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[MemoryT]:
        """列出会话相关的所有记忆。"""
