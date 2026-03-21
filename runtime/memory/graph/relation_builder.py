"""
RelationBuilder - 将提取的三元组构建到 KnowledgeGraphLayer 中。

提供便捷的方法将实体和关系添加到知识图谱，支持记忆引用关联。
"""

from __future__ import annotations

import logging
from typing import Optional

from runtime.memory.graph.knowledge_graph import KnowledgeGraphLayer, MemoryRef
from runtime.memory.types import Entity, Relation

logger = logging.getLogger(__name__)


class RelationBuilder:
    """将提取的三元组构建到 KnowledgeGraphLayer 中。"""

    def __init__(self, knowledge_graph: KnowledgeGraphLayer) -> None:
        self._graph = knowledge_graph

    async def build_from_triples(
        self,
        triples: list[tuple[Entity, Relation, Entity]],
        memory_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """将三元组添加到知识图谱。

        Args:
            triples: (subject, relation, object) Entity tuples
            memory_id: Optional memory ID to create MemoryRef association

        Returns:
            (entities_added, relations_added) counts
        """
        if not triples:
            return 0, 0

        entities_added = 0
        relations_added = 0
        entity_ids_for_memory = []

        try:
            # 添加所有实体和关系
            for subject, relation, obj in triples:
                # 添加实体（如果已存在则更新）
                await self._graph.add_entity(subject)
                await self._graph.add_entity(obj)
                entities_added += 2

                # 添加关系
                await self._graph.add_relation(relation)
                relations_added += 1

                # 记录实体ID用于记忆关联
                entity_ids_for_memory.extend([subject.id, obj.id])

            # 去重实体ID
            unique_entity_ids = list(set(entity_ids_for_memory))

            # 创建记忆引用关联
            if memory_id and unique_entity_ids:
                memory_ref = MemoryRef(
                    id=memory_id,
                    memory_type="semantic",  # 默认为语义记忆
                    summary="",
                    importance=0.5,
                )
                await self._graph.add_memory_ref(memory_ref, unique_entity_ids)

            # 实际添加的唯一实体数量（去重）
            actual_entities_added = len(unique_entity_ids)

            return actual_entities_added, relations_added

        except Exception as e:
            logger.error(f"构建三元组到图谱失败: {e}")
            return 0, 0

    async def build_from_text(
        self,
        text: str,
        extractor,  # EntityExtractor type hint会导致循环导入
        memory_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """便捷方法：从文本提取并构建。

        Args:
            text: 要处理的文本
            extractor: EntityExtractor实例
            memory_id: Optional memory ID to create MemoryRef association

        Returns:
            (entities_added, relations_added) counts
        """
        try:
            triples = await extractor.extract_from_text(text)
            return await self.build_from_triples(triples, memory_id)
        except Exception as e:
            logger.error(f"从文本构建图谱失败: {e}")
            return 0, 0
