from __future__ import annotations

import asyncio
import json
from typing import Optional

from pymilvus import DataType, MilvusClient

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory


class MilvusStore(StorageAdapter[Memory]):
    """Milvus-backed memory storage adapter."""

    def __init__(
        self,
        uri: str,
        token: str = "",
        user: str = "",
        password: str = "",
        database: str = "default",
        collection_name: str = "unified_memory",
        dimension: int = 1536,
    ) -> None:
        self.uri = uri
        self.token = token
        self.user = user
        self.password = password
        self.database = database
        self.collection_name = collection_name
        self.dimension = dimension
        self._client: Optional[MilvusClient] = None

    def _get_client(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(
                uri=self.uri,
                token=self.token,
                user=self.user,
                password=self.password,
                database=self.database,
            )
        return self._client

    def _ensure_collection(self) -> None:
        client = self._get_client()
        if client.has_collection(self.collection_name):
            return
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=128, is_primary=True)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.dimension)
        schema.add_field(field_name="metadata_json", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="memory_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="created_at", datatype=DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="IP",
            params={"M": 8, "efConstruction": 64},
        )
        client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    def _memory_payload(self, memory: Memory) -> dict[str, object]:
        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False)
        embedding = memory.embedding if memory.embedding is not None else []
        return {
            "id": memory.id,
            "content": memory.content,
            "embedding": embedding,
            "metadata_json": payload,
            "memory_type": str(memory.type),
            "session_id": memory.metadata.session_id or "",
            "created_at": int(memory.created_at.timestamp() * 1000),
        }

    async def save(self, memory: Memory) -> str:
        def _save() -> str:
            self._ensure_collection()
            payload = self._memory_payload(memory)
            self._get_client().insert(collection_name=self.collection_name, data=[payload])
            return memory.id

        return await asyncio.to_thread(_save)

    async def get(self, memory_id: str) -> Optional[Memory]:
        def _get() -> Optional[Memory]:
            self._ensure_collection()
            results = self._get_client().query(
                collection_name=self.collection_name,
                filter=f'id == "{memory_id}"',
                output_fields=["metadata_json"],
            )
            if not results:
                return None
            raw = results[0].get("metadata_json")
            if not raw:
                return None
            return Memory.from_dict(json.loads(raw))

        return await asyncio.to_thread(_get)

    async def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        def _update() -> Optional[Memory]:
            self._ensure_collection()
            results = self._get_client().query(
                collection_name=self.collection_name,
                filter=f'id == "{memory_id}"',
                output_fields=["metadata_json"],
            )
            if not results:
                return None
            raw = results[0].get("metadata_json")
            if not raw:
                return None
            data = json.loads(raw)
            data.update(updates)
            memory = Memory.from_dict(data)
            payload = self._memory_payload(memory)
            self._get_client().upsert(collection_name=self.collection_name, data=[payload])
            return memory

        return await asyncio.to_thread(_update)

    async def delete(self, memory_id: str) -> bool:
        def _delete() -> bool:
            self._ensure_collection()
            results = self._get_client().query(
                collection_name=self.collection_name,
                filter=f'id == "{memory_id}"',
                output_fields=["id"],
            )
            if not results:
                return False
            self._get_client().delete(collection_name=self.collection_name, filter=f'id == "{memory_id}"')
            return True

        return await asyncio.to_thread(_delete)

    async def exists(self, memory_id: str) -> bool:
        def _exists() -> bool:
            self._ensure_collection()
            results = self._get_client().query(
                collection_name=self.collection_name,
                filter=f'id == "{memory_id}"',
                output_fields=["id"],
            )
            return bool(results)

        return await asyncio.to_thread(_exists)

    async def list_by_session(self, session_id: str) -> list[Memory]:
        def _list() -> list[Memory]:
            self._ensure_collection()
            results = self._get_client().query(
                collection_name=self.collection_name,
                filter=f'session_id == "{session_id}"',
                output_fields=["metadata_json"],
            )
            memories: list[Memory] = []
            for item in results or []:
                raw = item.get("metadata_json")
                if not raw:
                    continue
                memories.append(Memory.from_dict(json.loads(raw)))
            return memories

        return await asyncio.to_thread(_list)
