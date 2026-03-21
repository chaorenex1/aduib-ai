"""
KnowledgeGraphLayer - 知识图谱层实现。

使用 BaseGraphStore 接口操作图数据库（Neo4j / PostgreSQL AGE）。
所有方法通过 asyncio.to_thread 将同步 graph_store 调用包装为异步。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from component.graph.base_graph import BaseGraphStore
from runtime.memory.types import Entity, Relation


class MemoryRef(BaseModel):
    """轻量记忆引用节点，存储于图数据库中。"""

    id: str
    memory_type: str  # episodic/semantic/procedural/perceptual
    user_id: str
    project_id: Optional[str]
    agent_id: Optional[str]
    memory_domain: str
    summary: str = ""
    created_at: Optional[datetime] = Field(default_factory=datetime.now)

    model_config = {"from_attributes": True}


class KnowledgeGraphLayer:
    """知识图谱层，通过 BaseGraphStore 管理实体和关系。"""

    def __init__(self, graph_store: BaseGraphStore) -> None:
        self._graph_store = graph_store

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _query(self, cypher: str) -> list[dict[str, Any]]:
        """将同步 graph_store.query 包装为异步调用。"""
        return self._graph_store.query(cypher)

    @staticmethod
    def _sanitize(value: Any) -> str:
        """转义 Cypher 字符串值，防止注入。"""
        if value is None:
            return ""
        text = str(value)
        # 先转义反斜杠，再转义单引号
        text = text.replace("\\", "\\\\").replace("'", "\\'")
        return text

    @staticmethod
    def _safe_rel_type(value: str) -> str:
        """将任意字符串规范化为合法的 Cypher 关系类型。"""
        sanitized = re.sub(r"[^0-9A-Za-z_]", "_", value)
        if not sanitized:
            return "RELATED_TO"
        if sanitized[0].isdigit():
            return f"REL_{sanitized}"
        return sanitized

    def _entity_from_data(self, data: dict[str, Any], entity_id: str = "") -> Optional[Entity]:
        """从图数据库行数据构建 Entity 对象。"""
        if not data:
            return None
        eid = entity_id or data.get("id", "")
        if not eid:
            return None
        name = data.get("name", "")
        props_raw = data.get("properties_json", "{}")
        try:
            properties = json.loads(props_raw) if props_raw else {}
        except (json.JSONDecodeError, TypeError):
            properties = {}
        return Entity(id=eid, name=name, properties=properties)

    def _relation_from_data(self, data: dict[str, Any]) -> Optional[Relation]:
        """从图数据库行数据构建 Relation 对象。"""
        if not data:
            return None
        source_id = data.get("source_id", "")
        target_id = data.get("target_id", "")
        if not source_id or not target_id:
            return None
        rel_type = data.get("rel_type") or data.get("type") or "RELATED_TO"
        weight = float(data.get("weight", 1.0))
        props_raw = data.get("properties_json", "{}")
        try:
            properties = json.loads(props_raw) if props_raw else {}
        except (json.JSONDecodeError, TypeError):
            properties = {}
        return Relation(
            source_id=source_id,
            target_id=target_id,
            type=rel_type,
            weight=weight,
            properties=properties,
        )

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    async def add_entity(self, entity: Entity) -> str:
        """添加或更新实体节点（MERGE 语义）。"""
        properties_json = json.dumps(entity.properties, ensure_ascii=False, default=str)
        cypher = (
            f"MERGE (e:Entity {{id: '{self._sanitize(entity.id)}'}}) "
            f"SET e.name = '{self._sanitize(entity.name)}', "
            f"e.properties_json = '{self._sanitize(properties_json)}'"
        )
        await self._query(cypher)
        return entity.id

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """按 ID 查询实体。"""
        cypher = (
            f"MATCH (e:Entity {{id: '{self._sanitize(entity_id)}'}}) "
            f"RETURN e.id AS id, e.name AS name, e.properties_json AS properties_json"
        )
        rows = await self._query(cypher)
        return self._entity_from_data(rows[0], entity_id) if rows else None

    async def query_entities(
        self,
        name: Optional[str] = None,
        limit: int = 50,
    ) -> list[Entity]:
        """查询实体，支持名称模糊匹配。"""
        conditions: list[str] = []
        if name:
            conditions.append(f"e.name CONTAINS '{self._sanitize(name)}'")
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        cypher = (
            f"MATCH (e:Entity){where_clause} "
            f"RETURN e.id AS id, e.name AS name, e.properties_json AS properties_json "
            f"LIMIT {limit}"
        )
        rows = await self._query(cypher)
        return [e for row in rows if (e := self._entity_from_data(row))]

    # ------------------------------------------------------------------
    # Relation operations
    # ------------------------------------------------------------------

    async def add_relation(self, relation: Relation) -> bool:
        """添加实体间关系边，关系属性存储在边上。"""
        rel_type = self._safe_rel_type(relation.type)
        properties_json = json.dumps(relation.properties, ensure_ascii=False, default=str)
        rel_props: dict[str, Any] = {
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "weight": relation.weight,
            "properties_json": properties_json,
        }
        self._graph_store.create_relationship(
            relation.source_id,
            relation.target_id,
            rel_type,
            rel_props,
        )
        return True

    async def get_relations(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "outgoing",
    ) -> list[Relation]:
        """获取实体的关系列表。"""
        sid = self._sanitize(entity_id)
        if direction == "outgoing":
            pattern = f"(e:Entity {{id: '{sid}'}})-[r]->(t:Entity)"
        elif direction == "incoming":
            pattern = f"(s:Entity)-[r]->(e:Entity {{id: '{sid}'}})"
        else:
            pattern = f"(e:Entity {{id: '{sid}'}})-[r]-(t:Entity)"

        where_clause = ""
        if relation_type:
            where_clause = f" WHERE type(r) = '{self._safe_rel_type(relation_type)}'"

        cypher = (
            f"MATCH {pattern}{where_clause} "
            f"RETURN r.source_id AS source_id, r.target_id AS target_id, "
            f"type(r) AS rel_type, r.weight AS weight, r.properties_json AS properties_json"
        )
        rows = await self._query(cypher)
        return [rel for row in rows if (rel := self._relation_from_data(row))]

    async def traverse_relations(
        self,
        start_entity_id: str,
        max_depth: int = 2,
        relation_types: Optional[list[str]] = None,
    ) -> list[Entity]:
        """从起始实体沿关系遍历，返回可达实体。"""
        sid = self._sanitize(start_entity_id)
        rel_filter = ""
        if relation_types:
            safe_types = "|".join(self._safe_rel_type(t) for t in relation_types)
            rel_filter = f":{safe_types}"
        cypher = (
            f"MATCH (start:Entity {{id: '{sid}'}})-[r{rel_filter}*1..{max_depth}]->(e:Entity) "
            f"WHERE e.id <> '{sid}' "
            f"RETURN DISTINCT e.id AS id, e.name AS name, e.properties_json AS properties_json"
        )
        rows = await self._query(cypher)
        return [e for row in rows if (e := self._entity_from_data(row))]

    # ------------------------------------------------------------------
    # MemoryRef operations
    # ------------------------------------------------------------------

    async def add_memory_ref(self, memory_ref: MemoryRef, entity_ids: Optional[list[str]] = None) -> str:
        """添加记忆引用节点，并将其与相关实体关联。"""
        cypher = (
            f"MERGE (m:MemoryRef {{id: '{self._sanitize(memory_ref.id)}'}}) "
            f"SET m.memory_type = '{self._sanitize(memory_ref.memory_type)}', "
            f"m.user_id = '{self._sanitize(memory_ref.user_id)}', "
            f"m.project_id = '{self._sanitize(memory_ref.project_id)}', "
            f"m.agent_id = '{self._sanitize(memory_ref.agent_id)}', "
            f"m.memory_domain = '{self._sanitize(memory_ref.memory_domain)}', "
            f"m.summary = '{self._sanitize(memory_ref.summary)}'"
        )
        await self._query(cypher)

        if entity_ids:
            for entity_id in entity_ids:
                link_cypher = (
                    f"MATCH (m:MemoryRef {{id: '{self._sanitize(memory_ref.id)}'}}) "
                    f"MATCH (e:Entity {{id: '{self._sanitize(entity_id)}'}}) "
                    f"MERGE (e)-[:REFERENCED_BY]->(m)"
                )
                await self._query(link_cypher)

        return memory_ref.id

    async def get_related_memories(
        self,
        entity_id: str,
        limit: int = 20,
    ) -> list[MemoryRef]:
        """获取与实体关联的记忆引用列表。"""
        sid = self._sanitize(entity_id)
        cypher = (
            f"MATCH (e:Entity {{id: '{sid}'}})-[:REFERENCED_BY]->(m:MemoryRef) "
            f"RETURN m.id AS id, m.memory_type AS memory_type, "
            f"m.user_id AS user_id, m.project_id AS project_id, m.agent_id AS agent_id, "
            f"m.memory_domain AS memory_domain, m.summary AS summary "
            f"LIMIT {limit}"
        )
        rows = await self._query(cypher)
        result: list[MemoryRef] = []
        for row in rows:
            mid = row.get("id", "")
            if not mid:
                continue
            result.append(
                MemoryRef(
                    id=mid,
                    memory_type=row.get("memory_type", "semantic"),
                    user_id=row.get("user_id", ""),
                    project_id=row.get("project_id"),
                    agent_id=row.get("agent_id"),
                    memory_domain=row.get("memory_domain", ""),
                    summary=row.get("summary", ""),
                )
            )
        return result

    async def find_similar_memories(
        self,
        memory_id: str,
        limit: int = 10,
    ) -> list[MemoryRef]:
        """查找通过共享实体与指定记忆相关的其他记忆引用。"""
        sid = self._sanitize(memory_id)
        cypher = (
            f"MATCH (m1:MemoryRef {{id: '{sid}'}})<-[:REFERENCED_BY]-(e:Entity)-[:REFERENCED_BY]->(m2:MemoryRef) "
            f"WHERE m2.id <> '{sid}' "
            f"RETURN DISTINCT m2.id AS id, m2.memory_type AS memory_type, "
            f"m2.user_id AS user_id, m2.project_id AS project_id, m2.agent_id AS agent_id, "
            f"m2.memory_domain AS memory_domain, m2.summary AS summary "
            f"LIMIT {limit}"
        )
        rows = await self._query(cypher)
        result: list[MemoryRef] = []
        for row in rows:
            mid = row.get("id", "")
            if not mid:
                continue
            result.append(
                MemoryRef(
                    id=mid,
                    memory_type=row.get("memory_type", "semantic"),
                    user_id=row.get("user_id", ""),
                    project_id=row.get("project_id"),
                    agent_id=row.get("agent_id"),
                    memory_domain=row.get("memory_domain", ""),
                    summary=row.get("summary", ""),
                )
            )
        return result

    async def get_memory_refs_by_entity_name(
        self,
        keyword: str,
        user_id: str,
        limit: int = 30,
    ) -> list[str]:
        """通过实体名称关键词查找关联记忆 ID（用于图谱预取）。"""
        cypher = (
            f"MATCH (e:Entity)-[:REFERENCED_BY]->(m:MemoryRef) "
            f"WHERE e.name CONTAINS '{self._sanitize(keyword)}' "
            f"AND m.user_id = '{self._sanitize(user_id)}' "
            f"RETURN m.id AS id "
            f"LIMIT {limit}"
        )
        rows = await self._query(cypher)
        return [row["id"] for row in rows if row.get("id")]

    async def get_neighbor_memory_refs(
        self,
        memory_ids: list[str],
        exclude_ids: set[str],
        user_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """1 跳邻居扩展：沿 SHARES_TOPIC / SHARES_TAG 边找关联记忆。

        Returns:
            list of dicts with keys: id, summary, memory_domain, memory_type, hop_count
        """
        if not memory_ids:
            return []
        ids_str = ", ".join(f"'{self._sanitize(mid)}'" for mid in memory_ids)
        exclude_clause = ""
        if exclude_ids:
            ex_str = ", ".join(f"'{self._sanitize(eid)}'" for eid in exclude_ids)
            exclude_clause = f" AND NOT n.id IN [{ex_str}]"
        cypher = (
            f"MATCH (m:MemoryRef)-[r:SHARES_TOPIC|SHARES_TAG]->(n:MemoryRef) "
            f"WHERE m.id IN [{ids_str}] "
            f"AND n.user_id = '{self._sanitize(user_id)}'"
            f"{exclude_clause} "
            f"RETURN n.id AS id, n.summary AS summary, "
            f"n.memory_domain AS memory_domain, n.memory_type AS memory_type, "
            f"count(m) AS hop_count, avg(coalesce(r.weight, 1.0)) AS avg_edge_weight "
            f"ORDER BY hop_count DESC "
            f"LIMIT {limit}"
        )
        return await self._query(cypher)

    async def link_memory_refs(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> None:
        """在两个 MemoryRef 节点之间创建有向关系边。"""
        safe_type = self._safe_rel_type(rel_type)
        props: dict[str, Any] = {
            "source_id": source_id,
            "target_id": target_id,
            **(properties or {}),
        }
        self._graph_store.create_relationship(
            source_id,
            target_id,
            safe_type,
            props,
        )
