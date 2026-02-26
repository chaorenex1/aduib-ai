"""语义记忆实现，用于存储知识事实和概念关系。"""

from __future__ import annotations

import logging
from typing import Optional

from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Entity, Memory, MemoryMetadata, MemoryType, Relation

logger = logging.getLogger(__name__)


class SemanticMemory:
    """语义记忆处理器，存储知识事实和概念关系，支持向量相似度检索。"""

    def __init__(
        self,
        storage_adapter: StorageAdapter,
        retrieval_engine: Optional[RetrievalEngine] = None,
    ) -> None:
        """初始化语义记忆处理器。

        Args:
            storage_adapter: 存储适配器实例，用于持久化记忆
            retrieval_engine: 可选的检索引擎，用于向量相似度搜索
        """
        self.storage = storage_adapter
        self.retrieval_engine = retrieval_engine

    async def add_knowledge(
        self,
        content: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        entities: Optional[list[Entity]] = None,
        relations: Optional[list[Relation]] = None,
        importance: float = 0.5,
        embedding: Optional[list[float]] = None,
        knowledge_type: str = "fact",
    ) -> str:
        """添加知识到语义记忆中。

        Args:
            content: 知识内容
            session_id: 会话 ID
            user_id: 用户 ID
            tags: 标签列表
            entities: 实体列表
            relations: 关系列表
            importance: 重要性评分 (0.0-1.0)
            embedding: 预计算的向量嵌入
            knowledge_type: 知识类型 (fact, concept, rule, preference)

        Returns:
            str: 创建的记忆 ID
        """
        # 构建语义记忆元数据
        metadata = MemoryMetadata(
            session_id=session_id,
            user_id=user_id,
            tags=tags or [],
            extra={"knowledge_type": knowledge_type}
        )

        # 创建记忆对象
        memory = Memory(
            type=MemoryType.SEMANTIC,
            content=content,
            metadata=metadata,
            embedding=embedding,
            entities=entities or [],
            relations=relations or [],
            importance=importance
        )

        # 保存到存储
        memory_id = await self.storage.save(memory)
        logger.debug(
            "Added semantic memory: session=%s, type=%s, tags=%s",
            session_id, knowledge_type, tags
        )

        return memory_id

    async def query_knowledge(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
        tags: Optional[list[str]] = None,
        knowledge_type: Optional[str] = None,
    ) -> list[RetrievalResult]:
        """查询语义知识。

        Args:
            query: 查询文本
            limit: 返回结果限制
            min_score: 最小相似度分数
            tags: 标签过滤（暂不支持）
            knowledge_type: 知识类型过滤（暂不支持）

        Returns:
            list[RetrievalResult]: 检索结果列表

        Raises:
            NotImplementedError: 如果没有配置检索引擎
        """
        if self.retrieval_engine is None:
            raise NotImplementedError("查询知识需要配置检索引擎")

        # 使用检索引擎进行搜索
        # TODO: 实现 tags 和 knowledge_type 过滤
        results = await self.retrieval_engine.search(
            query=query,
            memory_types=[MemoryType.SEMANTIC],
            limit=limit,
            min_score=min_score
        )

        logger.debug(
            "Query knowledge returned %d results for query: %s",
            len(results), query[:50]
        )

        return results

    async def get_knowledge(self, knowledge_id: str) -> Optional[Memory]:
        """获取单个知识记忆。

        Args:
            knowledge_id: 记忆 ID

        Returns:
            Optional[Memory]: 记忆对象，如果不存在则返回 None
        """
        return await self.storage.get(knowledge_id)

    async def update_knowledge(
        self,
        knowledge_id: str,
        content: Optional[str] = None,
        **updates
    ) -> Optional[Memory]:
        """更新知识记忆。

        Args:
            knowledge_id: 记忆 ID
            content: 新的内容
            **updates: 其他要更新的字段

        Returns:
            Optional[Memory]: 更新后的记忆对象，如果不存在则返回 None
        """
        update_dict = {}
        if content is not None:
            update_dict["content"] = content
        update_dict.update(updates)

        return await self.storage.update(knowledge_id, update_dict)

    async def list_by_tags(self, tags: list[str], limit: int = 50) -> list[Memory]:
        """按标签列出知识。

        Args:
            tags: 标签列表
            limit: 返回结果限制

        Returns:
            list[Memory]: 匹配的记忆列表
        """
        # 由于当前存储适配器接口限制，我们通过模拟存储来过滤
        # 在实际实现中，这里应该有更高效的标签索引
        all_memories = []

        # 简化实现：假设我们能获取所有语义记忆
        # 实际应该有专门的标签索引接口
        if hasattr(self.storage, 'memories'):
            for memory in self.storage.memories.values():
                if (memory.type == MemoryType.SEMANTIC and
                    any(tag in memory.metadata.tags for tag in tags)):
                    all_memories.append(memory)

        return all_memories[:limit]

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """基于向量相似度搜索知识。

        Args:
            embedding: 查询向量
            limit: 返回结果限制
            min_score: 最小相似度分数

        Returns:
            list[RetrievalResult]: 检索结果列表

        Raises:
            NotImplementedError: 如果没有配置检索引擎
        """
        if self.retrieval_engine is None:
            raise NotImplementedError("向量相似度搜索需要配置检索引擎")

        # 使用检索引擎进行向量搜索
        results = await self.retrieval_engine.search_by_embedding(
            embedding=embedding,
            limit=limit,
            min_score=min_score
        )

        return results