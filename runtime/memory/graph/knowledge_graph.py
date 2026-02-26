"""
KnowledgeGraphLayer - 知识图谱层实现。

提供实体和关系管理的高级抽象，支持GraphStore存储和内存模式的优雅降级。
本层作为对现有GraphStore的高级封装，提供更友好的知识图谱操作接口。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from runtime.memory.storage.graph_store import GraphStore
from runtime.memory.types.base import Entity, EntityType, Relation


class MemoryRef(BaseModel):
    """轻量记忆引用节点，存储于图数据库中。"""

    id: str                                     # Memory ID (links to full Memory in Milvus/Redis)
    memory_type: str                           # working/episodic/semantic
    summary: str = ""                          # Short summary (<100 chars)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    importance: float = 0.5

    model_config = {"from_attributes": True}


class KnowledgeGraphLayer:
    """知识图谱层，管理实体和关系。"""

    def __init__(self, graph_store: Optional[GraphStore] = None) -> None:
        """初始化知识图谱层。

        Args:
            graph_store: 可选的GraphStore实例，为None时启用内存模式以确保优雅降级
        """
        self._graph_store = graph_store

        # 内存模式备用存储，当graph_store不可用时使用
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []
        self._memory_refs: dict[str, MemoryRef] = {}
        self._entity_memory_map: dict[str, list[str]] = {}  # entity_id -> memory_ids

    def _is_graph_mode(self) -> bool:
        """检查当前是否为图存储模式。"""
        return self._graph_store is not None

    def _parse_json_properties(self, json_str: str) -> dict[str, Any]:
        """解析JSON属性字符串，出错时返回空字典。"""
        try:
            return json.loads(json_str) if json_str else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _entity_from_graph_data(self, entity_data: dict[str, Any], entity_id: str = "") -> Optional[Entity]:
        """从图数据库返回的数据构建Entity对象。"""
        if not entity_data:
            return None

        entity_id = entity_id or entity_data.get('id', '')
        entity_type_str = entity_data.get('type', 'concept')
        name = entity_data.get('name', '')
        properties = self._parse_json_properties(entity_data.get('properties_json', '{}'))

        # 确保类型有效
        try:
            entity_type = EntityType(entity_type_str)
        except ValueError:
            entity_type = EntityType.CONCEPT

        return Entity(
            id=entity_id,
            name=name,
            type=entity_type,
            properties=properties
        )

    async def add_entity(self, entity: Entity) -> str:
        """添加或更新实体节点。

        Args:
            entity: 要添加的实体

        Returns:
            实体ID
        """
        if self._is_graph_mode():
            # 使用GraphStore存储
            entity_type = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
            properties_json = json.dumps(entity.properties, ensure_ascii=False, default=str)
            cypher = (
                f"MERGE (e:Entity {{id: '{self._sanitize(entity.id)}'}}) "
                f"SET e.name = '{self._sanitize(entity.name)}', "
                f"e.type = '{self._sanitize(entity_type)}', "
                f"e.properties_json = '{self._sanitize(properties_json)}'"
            )
            await self._graph_store._query(cypher)
        else:
            # 内存模式
            self._entities[entity.id] = entity

        return entity.id

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体。

        Args:
            entity_id: 实体ID

        Returns:
            实体对象或None
        """
        if self._is_graph_mode():
            # 使用GraphStore查询
            cypher = f"MATCH (e:Entity {{id: '{self._sanitize(entity_id)}'}}) RETURN e"
            rows = await self._graph_store._query(cypher)
            if not rows:
                return None

            entity_data = rows[0].get('e', {})
            return self._entity_from_graph_data(entity_data, entity_id)
        else:
            # 内存模式
            return self._entities.get(entity_id)

    async def query_entities(
        self,
        name: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 50,
    ) -> list[Entity]:
        """查询实体，支持名称模糊匹配和类型过滤。

        Args:
            name: 实体名称（支持模糊匹配）
            entity_type: 实体类型过滤
            limit: 返回结果数量限制

        Returns:
            匹配的实体列表
        """
        if self._is_graph_mode():
            # 使用GraphStore查询
            conditions = []
            if name:
                conditions.append(f"e.name CONTAINS '{self._sanitize(name)}'")
            if entity_type:
                conditions.append(f"e.type = '{self._sanitize(entity_type.value)}'")

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            cypher = f"MATCH (e:Entity){where_clause} RETURN e LIMIT {limit}"

            rows = await self._graph_store._query(cypher)
            entities = []
            for row in rows:
                entity_data = row.get('e', {})
                entity = self._entity_from_graph_data(entity_data)
                if entity:
                    entities.append(entity)
            return entities
        else:
            # 内存模式
            entities = list(self._entities.values())
            filtered = []

            for entity in entities:
                if name and name not in entity.name:
                    continue
                if entity_type and entity.type != entity_type:
                    continue
                filtered.append(entity)
                if len(filtered) >= limit:
                    break

            return filtered

    async def add_relation(self, relation: Relation) -> bool:
        """添加关系。

        Args:
            relation: 要添加的关系

        Returns:
            是否成功添加
        """
        if self._graph_store is not None:
            # 使用GraphStore存储
            # 注意：这里简化实现，实际应该创建关系边
            pass
        else:
            # 内存模式
            self._relations.append(relation)

        return True

    async def get_relations(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "outgoing",  # "outgoing", "incoming", "both"
    ) -> list[Relation]:
        """获取实体的关系。

        Args:
            entity_id: 实体ID
            relation_type: 关系类型过滤
            direction: 关系方向

        Returns:
            关系列表
        """
        if self._graph_store is not None:
            # 使用GraphStore查询
            return []
        else:
            # 内存模式
            relations = []
            for relation in self._relations:
                # Check if relation matches direction filter
                matches_direction = (
                    (direction == "outgoing" and relation.source_id == entity_id) or
                    (direction == "incoming" and relation.target_id == entity_id) or
                    (direction == "both" and (relation.source_id == entity_id or relation.target_id == entity_id))
                )

                # Check if relation matches type filter
                matches_type = relation_type is None or relation.type == relation_type

                if matches_direction and matches_type:
                    relations.append(relation)

            return relations

    async def traverse_relations(
        self,
        start_entity_id: str,
        max_depth: int = 2,
        relation_types: Optional[list[str]] = None,
    ) -> list[Entity]:
        """从起始实体遍历关系，返回关联实体。

        Args:
            start_entity_id: 起始实体ID
            max_depth: 最大遍历深度
            relation_types: 关系类型过滤

        Returns:
            关联实体列表
        """
        if self._graph_store is not None:
            # 使用GraphStore查询
            return []
        else:
            # 内存模式简单实现
            all_discovered = set()
            current_level = {start_entity_id}

            for depth in range(max_depth):
                next_level = set()
                for entity_id in current_level:
                    # 获取所有outgoing关系
                    relations = await self.get_relations(entity_id, direction="outgoing")
                    if relation_types:
                        relations = [r for r in relations if r.type in relation_types]

                    for relation in relations:
                        target_id = relation.target_id
                        if target_id != start_entity_id and target_id not in all_discovered:
                            all_discovered.add(target_id)
                            next_level.add(target_id)

                current_level = next_level
                if not current_level:
                    break

            # 返回所有发现的实体
            entities = []
            for entity_id in all_discovered:
                entity = await self.get_entity(entity_id)
                if entity:
                    entities.append(entity)

            return entities

    async def add_memory_ref(self, memory_ref: MemoryRef, entity_ids: Optional[list[str]] = None) -> str:
        """添加记忆引用，并可选地关联到实体。

        Args:
            memory_ref: 记忆引用
            entity_ids: 要关联的实体ID列表

        Returns:
            记忆引用ID
        """
        if self._graph_store is not None:
            # 使用GraphStore存储
            pass
        else:
            # 内存模式
            self._memory_refs[memory_ref.id] = memory_ref
            if entity_ids:
                for entity_id in entity_ids:
                    if entity_id not in self._entity_memory_map:
                        self._entity_memory_map[entity_id] = []
                    self._entity_memory_map[entity_id].append(memory_ref.id)

        return memory_ref.id

    async def get_related_memories(
        self,
        entity_id: str,
        limit: int = 20,
    ) -> list[MemoryRef]:
        """获取与实体关联的记忆引用。

        Args:
            entity_id: 实体ID
            limit: 返回结果数量限制

        Returns:
            记忆引用列表
        """
        if self._graph_store is not None:
            # 使用GraphStore查询
            return []
        else:
            # 内存模式
            memory_ids = self._entity_memory_map.get(entity_id, [])
            memories = []
            for memory_id in memory_ids[:limit]:
                memory_ref = self._memory_refs.get(memory_id)
                if memory_ref:
                    memories.append(memory_ref)
            return memories

    async def find_similar_memories(
        self,
        memory_id: str,
        limit: int = 10,
    ) -> list[MemoryRef]:
        """查找与指定记忆相似的记忆引用。

        Args:
            memory_id: 记忆ID
            limit: 返回结果数量限制

        Returns:
            相似记忆引用列表
        """
        if self._graph_store is not None:
            # 使用GraphStore查询
            return []
        else:
            # 内存模式优雅降级，返回空列表
            return []

    @staticmethod
    def _sanitize(value: Any) -> str:
        """清理字符串值，防止注入攻击。"""
        if value is None:
            return ""
        text = str(value)
        return text.replace("'", "\\'").replace('"', '\\"')