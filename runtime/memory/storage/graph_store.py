from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory, MemoryType


class GraphStore(StorageAdapter[Memory]):
    """Graph-backed memory storage adapter."""

    def __init__(self, graph_store: Optional[Any] = None) -> None:
        self.graph_store = graph_store

    @staticmethod
    def _sanitize(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        return text.replace("'", "\\'")

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return f"'{self._sanitize(value)}'"

    def _format_properties(self, properties: dict[str, Any]) -> str:
        return ", ".join(f"{key}: {self._format_value(value)}" for key, value in properties.items())

    @staticmethod
    def _safe_rel_type(value: str) -> str:
        sanitized = re.sub(r"[^0-9A-Za-z_]", "_", value)
        if not sanitized:
            return "RELATED_TO"
        if sanitized[0].isdigit():
            return f"REL_{sanitized}"
        return sanitized

    async def _query(self, cypher: str) -> list[dict[str, Any]]:
        if self.graph_store is None:
            return []
        return await asyncio.to_thread(self.graph_store.query, cypher)

    @staticmethod
    def _extract_props(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        try:
            return dict(value)
        except (TypeError, ValueError):
            pass
        props = getattr(value, "_properties", None)
        if isinstance(props, dict):
            return props
        props = getattr(value, "properties", None)
        if isinstance(props, dict):
            return props
        return {}

    @staticmethod
    def _extract_rel_type(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            rel_type = value.get("type") or value.get("rel_type")
            if rel_type:
                return str(rel_type)
        rel_type = getattr(value, "type", None)
        if isinstance(rel_type, str):
            return rel_type
        return None

    @staticmethod
    def _extract_node_id(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            node_id = value.get("id")
            return str(node_id) if node_id is not None else None
        try:
            node_id = value.get("id")
            return str(node_id) if node_id is not None else None
        except Exception:
            pass
        node_id = getattr(value, "id", None)
        if node_id is not None:
            return str(node_id)
        props = getattr(value, "_properties", None)
        if isinstance(props, dict) and props.get("id") is not None:
            return str(props.get("id"))
        return None

    @staticmethod
    def _load_json(value: Any, fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if fallback is None:
            fallback = {}
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return fallback
        if isinstance(value, dict):
            return value
        return fallback

    def _memory_payload(self, memory: Memory) -> dict[str, Any]:
        memory_type = memory.type.value if isinstance(memory.type, MemoryType) else str(memory.type)
        metadata_json = json.dumps(memory.metadata.model_dump(mode="python"), ensure_ascii=False, default=str)
        return {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory_type,
            "session_id": memory.metadata.session_id,
            "created_at": memory.created_at.isoformat(),
            "importance": memory.importance,
            "metadata_json": metadata_json,
        }

    def _memory_from_props(
        self,
        props: dict[str, Any],
        entities: Optional[list[dict[str, Any]]] = None,
        relations: Optional[list[dict[str, Any]]] = None,
    ) -> Memory:
        metadata = self._load_json(props.get("metadata_json"))
        session_id = props.get("session_id")
        if session_id and "session_id" not in metadata:
            metadata["session_id"] = session_id
        memory_type = props.get("memory_type") or props.get("type") or MemoryType.WORKING.value
        content = props.get("content") or ""
        memory_data: dict[str, Any] = {
            "id": props.get("id"),
            "type": memory_type,
            "content": content,
            "metadata": metadata,
            "entities": entities or [],
            "relations": relations or [],
        }
        created_at = props.get("created_at")
        if created_at is not None:
            memory_data["created_at"] = created_at
        importance = props.get("importance")
        if importance is not None:
            memory_data["importance"] = importance
        return Memory.from_dict(memory_data)

    async def save(self, memory: Memory) -> str:
        if self.graph_store is None:
            return memory.id
        payload = self._memory_payload(memory)
        cypher = (
            "MERGE (m:Memory {id: "
            + self._format_value(payload["id"])
            + "}) SET m.content="
            + self._format_value(payload["content"])
            + ", m.memory_type="
            + self._format_value(payload["memory_type"])
            + ", m.session_id="
            + self._format_value(payload["session_id"])
            + ", m.created_at="
            + self._format_value(payload["created_at"])
            + ", m.importance="
            + self._format_value(payload["importance"])
            + ", m.metadata_json="
            + self._format_value(payload["metadata_json"])
        )
        await self._query(cypher)

        for entity in memory.entities:
            entity_type = entity.type.value if hasattr(entity.type, "value") else str(entity.type)
            properties_json = json.dumps(entity.properties, ensure_ascii=False, default=str)
            entity_cypher = (
                "MERGE (e:Entity {id: "
                + self._format_value(entity.id)
                + "}) SET e.name="
                + self._format_value(entity.name)
                + ", e.type="
                + self._format_value(entity_type)
                + ", e.properties_json="
                + self._format_value(properties_json)
            )
            await self._query(entity_cypher)
            link_cypher = (
                "MATCH (m:Memory {id: "
                + self._format_value(memory.id)
                + "}) MATCH (e:Entity {id: "
                + self._format_value(entity.id)
                + "}) MERGE (m)-[:HAS_ENTITY]->(e)"
            )
            await self._query(link_cypher)

        for relation in memory.relations:
            rel_type = self._safe_rel_type(relation.type)
            properties_json = json.dumps(relation.properties, ensure_ascii=False, default=str)
            rel_props = {
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "weight": relation.weight,
                "properties_json": properties_json,
            }
            rel_cypher = (
                "MATCH (e1:Entity {id: "
                + self._format_value(relation.source_id)
                + "}) MATCH (e2:Entity {id: "
                + self._format_value(relation.target_id)
                + "}) CREATE (e1)-[r:"
                + rel_type
                + " {"
                + self._format_properties(rel_props)
                + "}]->(e2)"
            )
            await self._query(rel_cypher)
        return memory.id

    async def get(self, memory_id: str) -> Optional[Memory]:
        if self.graph_store is None:
            return None
        cypher = f"MATCH (m:Memory {{id: {self._format_value(memory_id)}}}) RETURN m"
        rows = await self._query(cypher)
        if not rows:
            return None
        node = rows[0].get("m") if isinstance(rows[0], dict) else None
        props = self._extract_props(node)
        if "id" not in props:
            props["id"] = memory_id

        entities_cypher = (
            f"MATCH (m:Memory {{id: {self._format_value(memory_id)}}})-[:HAS_ENTITY]->(e:Entity) RETURN e"
        )
        entity_rows = await self._query(entities_cypher)
        entities: list[dict[str, Any]] = []
        for row in entity_rows:
            entity_node = row.get("e") if isinstance(row, dict) else None
            entity_props = self._extract_props(entity_node)
            if not entity_props:
                continue
            if not entity_props.get("id"):
                continue
            entity_type = entity_props.get("type") or entity_props.get("entity_type") or "concept"
            name = entity_props.get("name") or entity_props.get("id") or ""
            entities.append(
                {
                    "id": entity_props.get("id"),
                    "name": name,
                    "type": entity_type,
                    "properties": self._load_json(entity_props.get("properties_json")),
                }
            )

        relations_cypher = (
            "MATCH (m:Memory {id: "
            + self._format_value(memory_id)
            + "})-[:HAS_ENTITY]->(e1)-[r]->(e2) RETURN r"
        )
        relation_rows = await self._query(relations_cypher)
        relations: list[dict[str, Any]] = []
        for row in relation_rows:
            rel = row.get("r") if isinstance(row, dict) else None
            rel_props = self._extract_props(rel)
            rel_type = self._extract_rel_type(rel) or rel_props.get("type") or "RELATED_TO"
            source_id = rel_props.get("source_id")
            target_id = rel_props.get("target_id")
            if not source_id or not target_id:
                source_id = self._extract_node_id(getattr(rel, "start_node", None)) or source_id
                target_id = self._extract_node_id(getattr(rel, "end_node", None)) or target_id
            if not source_id or not target_id:
                continue
            relations.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "type": rel_type,
                    "properties": self._load_json(rel_props.get("properties_json")),
                    "weight": rel_props.get("weight", 1.0),
                }
            )

        return self._memory_from_props(props, entities=entities, relations=relations)

    async def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        if self.graph_store is None:
            return None
        existing = await self.get(memory_id)
        if existing is None:
            return None
        data = existing.to_dict()
        if isinstance(updates.get("metadata"), dict):
            metadata = data.get("metadata", {})
            metadata.update(updates["metadata"])
            data["metadata"] = metadata
            updates = {key: value for key, value in updates.items() if key != "metadata"}
        data.update(updates)
        memory = Memory.from_dict(data)
        payload = self._memory_payload(memory)
        cypher = (
            "MATCH (m:Memory {id: "
            + self._format_value(memory_id)
            + "}) SET m.content="
            + self._format_value(payload["content"])
            + ", m.memory_type="
            + self._format_value(payload["memory_type"])
            + ", m.session_id="
            + self._format_value(payload["session_id"])
            + ", m.created_at="
            + self._format_value(payload["created_at"])
            + ", m.importance="
            + self._format_value(payload["importance"])
            + ", m.metadata_json="
            + self._format_value(payload["metadata_json"])
        )
        await self._query(cypher)
        return memory

    async def delete(self, memory_id: str) -> bool:
        if self.graph_store is None:
            return False
        if not await self.exists(memory_id):
            return False
        cypher = f"MATCH (m:Memory {{id: {self._format_value(memory_id)}}}) DETACH DELETE m"
        await self._query(cypher)
        return True

    async def exists(self, memory_id: str) -> bool:
        if self.graph_store is None:
            return False
        cypher = f"MATCH (m:Memory {{id: {self._format_value(memory_id)}}}) RETURN count(m) AS count"
        rows = await self._query(cypher)
        if not rows:
            return False
        count = rows[0].get("count") if isinstance(rows[0], dict) else 0
        try:
            return int(count) > 0
        except (TypeError, ValueError):
            return False

    async def list_by_session(self, session_id: str) -> list[Memory]:
        if self.graph_store is None:
            return []
        cypher = (
            f"MATCH (m:Memory {{session_id: {self._format_value(session_id)}}}) RETURN m ORDER BY m.created_at"
        )
        rows = await self._query(cypher)
        memories: list[Memory] = []
        for row in rows:
            node = row.get("m") if isinstance(row, dict) else None
            props = self._extract_props(node)
            if not props:
                continue
            if "id" not in props:
                continue
            memories.append(self._memory_from_props(props))
        return memories
