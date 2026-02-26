from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Optional

from runtime.memory.classifier import MemoryClassifier
from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryScope, MemorySource, MemoryType


class UnifiedMemoryManager:
    """统一记忆管理器，作为所有记忆操作的入口。"""

    def __init__(
        self,
        storage: StorageAdapter,
        retrieval: Optional[RetrievalEngine] = None,
        classifier: Optional[MemoryClassifier] = None,
    ) -> None:
        """初始化记忆管理器。

        Args:
            storage: 存储适配器实例。
            retrieval: 检索引擎实例 (可选)。
            classifier: 分类器实例 (可选)。
        """

        self._storage = storage
        self._retrieval = retrieval
        self._classifier = classifier or MemoryClassifier()

    async def store(self, memory: Memory) -> str:
        """存储记忆。

        Args:
            memory: 记忆实体。

        Returns:
            记忆 ID。
        """

        if memory.embedding is None:
            embedding = await self._generate_embedding(memory.content)
            if embedding:
                memory.embedding = embedding

        await self._apply_classification(memory)

        now = datetime.now()
        memory.updated_at = now
        memory.accessed_at = now

        memory_id = await self._storage.save(memory)
        memory.id = memory_id
        return memory_id

    async def retrieve(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        limit: int = 10,
    ) -> list[Memory]:
        """检索记忆。

        Args:
            query: 查询字符串。
            memory_types: 记忆类型过滤。
            scope: 作用域过滤。
            time_range: 时间范围过滤。
            limit: 返回数量限制。

        Returns:
            匹配的记忆列表。
        """

        if self._retrieval is None:
            raise NotImplementedError("未配置检索引擎，无法执行检索。")

        results = await self._retrieval.search(
            query=query,
            memory_types=memory_types,
            scope=scope,
            time_range=time_range,
            limit=limit,
        )

        memories = [result.memory for result in results]
        memories = self._filter_memories(
            memories=memories,
            memory_types=memory_types,
            scope=scope,
            time_range=time_range,
        )

        await self._touch_memories(memories)
        return memories[:limit]

    async def update(self, memory_id: str, updates: dict[str, Any]) -> Optional[Memory]:
        """更新记忆。

        Args:
            memory_id: 记忆 ID。
            updates: 更新字段。

        Returns:
            更新后的记忆，不存在返回 None。
        """

        payload = dict(updates)
        payload["updated_at"] = datetime.now()
        return await self._storage.update(memory_id, payload)

    async def forget(self, memory_id: str) -> bool:
        """遗忘/删除记忆。

        Args:
            memory_id: 记忆 ID。

        Returns:
            是否删除成功。
        """

        return await self._storage.delete(memory_id)

    async def get(self, memory_id: str) -> Optional[Memory]:
        """根据 ID 获取单个记忆。

        Args:
            memory_id: 记忆 ID。

        Returns:
            记忆实体，不存在返回 None。
        """

        memory = await self._storage.get(memory_id)
        if memory is None:
            return None

        now = datetime.now()
        memory.accessed_at = now
        updated = await self._storage.update(memory_id, {"accessed_at": now})
        return updated or memory

    async def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        entity_filter: Optional[list[str]] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """高级搜索，返回带评分的结果。

        Args:
            query: 查询字符串。
            memory_types: 记忆类型过滤。
            scope: 作用域过滤。
            entity_filter: 实体 ID 过滤。
            time_range: 时间范围过滤。
            limit: 返回数量限制。
            min_score: 最低相关性得分。

        Returns:
            带评分的检索结果列表。
        """

        if self._retrieval is None:
            raise NotImplementedError("未配置检索引擎，无法执行搜索。")

        if entity_filter:
            results = await self._retrieval.search_by_entities(entity_filter, limit=limit)
            results = self._filter_results(
                results=results,
                memory_types=memory_types,
                scope=scope,
                entity_filter=entity_filter,
                time_range=time_range,
                min_score=min_score,
            )
        else:
            results = await self._retrieval.search(
                query=query,
                memory_types=memory_types,
                scope=scope,
                time_range=time_range,
                limit=limit,
                min_score=min_score,
            )

        await self._touch_memories([result.memory for result in results])
        return results[:limit]

    async def consolidate(self, session_id: str) -> list[Memory]:
        """整合会话记忆。

        将会话中的工作记忆整合为情景/语义记忆。

        Args:
            session_id: 会话 ID。

        Returns:
            整合后产生的新记忆列表。
        """

        memories = await self._storage.list_by_session(session_id)
        working_memories = [memory for memory in memories if memory.type == MemoryType.WORKING]
        if not working_memories:
            return []

        summary = self._build_summary(working_memories)
        metadata = self._build_consolidated_metadata(session_id, working_memories)
        consolidated = Memory(
            type=MemoryType.EPISODIC,
            content=summary,
            metadata=metadata,
        )

        await self.store(consolidated)
        return [consolidated]

    async def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在。"""

        return await self._storage.exists(memory_id)

    async def list_by_session(self, session_id: str) -> list[Memory]:
        """列出会话的所有记忆。"""

        return await self._storage.list_by_session(session_id)

    async def _touch_memories(self, memories: list[Memory]) -> None:
        """批量更新记忆的访问时间。"""

        if not memories:
            return

        now = datetime.now()
        for memory in memories:
            memory.accessed_at = now

        for memory in memories:
            await self._storage.update(memory.id, {"accessed_at": now})

    async def _apply_classification(self, memory: Memory) -> None:
        """根据分类器结果补充元数据。"""

        if self._classifier is None:
            return

        source = self._resolve_source(memory.metadata)
        context = self._build_classification_context(memory)
        classification = await self._classifier.classify(memory.content, source, context=context)

        memory.metadata.tags = self._merge_tags(memory.metadata.tags, classification.tags)
        if memory.metadata.scope == MemoryScope.PERSONAL and classification.scope != MemoryScope.PERSONAL:
            memory.metadata.scope = classification.scope

        if "classification" not in memory.metadata.extra:
            memory.metadata.extra["classification"] = classification.model_dump(mode="python")

    async def _generate_embedding(self, content: str) -> Optional[list[float]]:
        """尝试通过检索引擎生成 embedding。"""

        if self._retrieval is None:
            return None

        for attr in ("embed", "encode", "generate_embedding", "get_embedding", "embedding"):
            handler = getattr(self._retrieval, attr, None)
            if handler is None or not callable(handler):
                continue

            try:
                result = handler(content)
            except TypeError:
                continue

            if inspect.isawaitable(result):
                result = await result

            if isinstance(result, list) and result:
                return result

        return None

    @staticmethod
    def _merge_tags(*tag_groups: list[str]) -> list[str]:
        """合并标签并去重。"""

        merged: list[str] = []
        for tags in tag_groups:
            for tag in tags:
                if tag and tag not in merged:
                    merged.append(tag)
        return merged

    @staticmethod
    def _resolve_source(metadata: MemoryMetadata) -> MemorySource:
        """从元数据解析来源枚举。"""

        if metadata.source:
            try:
                return MemorySource(metadata.source)
            except ValueError:
                pass
        return MemorySource.CHAT

    @staticmethod
    def _build_classification_context(memory: Memory) -> dict[str, Any]:
        """构建分类器上下文。"""

        context: dict[str, Any] = dict(memory.metadata.extra)
        if memory.metadata.tags:
            context.setdefault("tags", memory.metadata.tags)
        if memory.metadata.session_id:
            context.setdefault("session_id", memory.metadata.session_id)
        if memory.metadata.agent_id:
            context.setdefault("agent_id", memory.metadata.agent_id)
        if memory.metadata.user_id:
            context.setdefault("user_id", memory.metadata.user_id)
        return context

    @staticmethod
    def _build_summary(memories: list[Memory]) -> str:
        """构建会话记忆的基础摘要。"""

        lines = []
        for memory in memories:
            content = memory.content.strip()
            if content:
                lines.append(content)
        return "\n".join(lines)

    @staticmethod
    def _build_consolidated_metadata(session_id: str, memories: list[Memory]) -> MemoryMetadata:
        """构建整合后的元数据。"""

        scope = MemoryScope.PERSONAL
        tags: list[str] = []
        for memory in memories:
            if memory.metadata.scope != MemoryScope.PERSONAL:
                scope = memory.metadata.scope
            tags.extend(memory.metadata.tags)

        return MemoryMetadata(
            session_id=session_id,
            scope=scope,
            tags=UnifiedMemoryManager._merge_tags(tags),
            source=MemorySource.CHAT.value,
        )

    @staticmethod
    def _filter_memories(
        memories: list[Memory],
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
    ) -> list[Memory]:
        """按条件过滤记忆列表。"""

        filtered = memories
        if memory_types:
            type_set = set(memory_types)
            filtered = [memory for memory in filtered if memory.type in type_set]

        if scope:
            filtered = [memory for memory in filtered if memory.metadata.scope == scope]

        if time_range:
            start, end = time_range
            if start > end:
                start, end = end, start
            filtered = [memory for memory in filtered if start <= memory.created_at <= end]

        return filtered

    @staticmethod
    def _filter_results(
        results: list[RetrievalResult],
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        entity_filter: Optional[list[str]] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """按条件过滤检索结果。"""

        filtered = [result for result in results if result.score >= min_score]
        memories = UnifiedMemoryManager._filter_memories(
            [result.memory for result in filtered],
            memory_types=memory_types,
            scope=scope,
            time_range=time_range,
        )
        memory_ids = {memory.id for memory in memories}
        filtered = [result for result in filtered if result.memory.id in memory_ids]

        if entity_filter:
            entity_set = set(entity_filter)
            filtered = [
                result
                for result in filtered
                if {entity.id for entity in result.memory.entities}.intersection(entity_set)
            ]

        return filtered
