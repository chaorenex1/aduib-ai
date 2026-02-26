import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from runtime.memory.storage.graph_store import GraphStore
from runtime.memory.storage.milvus_store import MilvusStore
from runtime.memory.storage.redis_store import RedisStore
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryType


def make_memory(
    memory_id: str = "mem-1",
    content: str = "hello",
    session_id: str = "sess-1",
) -> Memory:
    return Memory(
        id=memory_id,
        type=MemoryType.WORKING,
        content=content,
        embedding=[0.1, 0.2],
        metadata=MemoryMetadata(session_id=session_id),
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture(autouse=True)
def mock_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("runtime.memory.storage.redis_store.asyncio.to_thread", _run_sync)
    monkeypatch.setattr("runtime.memory.storage.milvus_store.asyncio.to_thread", _run_sync)
    monkeypatch.setattr("runtime.memory.storage.graph_store.asyncio.to_thread", _run_sync)


@pytest.fixture
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.pipeline.return_value = MagicMock()
    return redis


@pytest.fixture
def mock_graph_store() -> MagicMock:
    graph = MagicMock()
    graph.query.return_value = []
    return graph


class TestRedisStore:
    @pytest.mark.asyncio
    async def test_save(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        memory = make_memory()

        result = await store.save(memory)

        assert result == memory.id
        pipeline = mock_redis.pipeline.return_value
        pipeline.set.assert_called_once()
        set_args, _ = pipeline.set.call_args
        assert set_args[0] == store._memory_key(memory.id)
        pipeline.zadd.assert_called_once_with(
            store._session_key(memory.metadata.session_id),
            {memory.id: memory.created_at.timestamp()},
        )
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_with_ttl(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        memory = make_memory()
        memory.ttl = datetime.now() + timedelta(seconds=120)

        await store.save(memory)

        pipeline = mock_redis.pipeline.return_value
        _, set_kwargs = pipeline.set.call_args
        assert "ex" in set_kwargs
        assert isinstance(set_kwargs["ex"], int)
        assert set_kwargs["ex"] >= 1

    @pytest.mark.asyncio
    async def test_get_found(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        memory = make_memory()
        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False).encode()
        mock_redis.get.return_value = payload

        result = await store.get(memory.id)

        assert isinstance(result, Memory)
        assert result.id == memory.id
        mock_redis.get.assert_called_once_with(store._memory_key(memory.id))

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mock_redis.get.return_value = None

        result = await store.get("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_update(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        memory = make_memory()
        mock_redis.get.return_value = json.dumps(memory.to_dict(), default=str, ensure_ascii=False).encode()

        result = await store.update(memory.id, {"content": "updated"})

        assert isinstance(result, Memory)
        assert result.content == "updated"
        mock_redis.get.assert_called_once_with(store._memory_key(memory.id))
        mock_redis.set.assert_called_once()
        set_args, _ = mock_redis.set.call_args
        saved = json.loads(set_args[1])
        assert saved["content"] == "updated"

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mock_redis.get.return_value = None

        result = await store.update("missing", {"content": "updated"})

        assert result is None
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        memory = make_memory()
        mock_redis.get.return_value = json.dumps(memory.to_dict(), default=str, ensure_ascii=False).encode()
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [1, 1]

        result = await store.delete(memory.id)

        assert result is True
        pipeline.delete.assert_called_once_with(store._memory_key(memory.id))
        pipeline.zrem.assert_called_once_with(store._session_key(memory.metadata.session_id), memory.id)
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mock_redis.get.return_value = None

        result = await store.delete("missing")

        assert result is False
        mock_redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mock_redis.exists.return_value = 1

        result = await store.exists("mem-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mock_redis.exists.return_value = 0

        result = await store.exists("mem-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_by_session(self, mock_redis: MagicMock) -> None:
        store = RedisStore(mock_redis)
        mem1 = make_memory("mem-1", "one")
        mem2 = make_memory("mem-2", "two")
        mock_redis.zrange.return_value = [b"mem-1", b"mem-2"]
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [
            json.dumps(mem1.to_dict(), default=str, ensure_ascii=False).encode(),
            json.dumps(mem2.to_dict(), default=str, ensure_ascii=False).encode(),
        ]

        result = await store.list_by_session(mem1.metadata.session_id or "")

        assert [memory.id for memory in result] == ["mem-1", "mem-2"]
        pipeline.get.assert_has_calls(
            [call(store._memory_key("mem-1")), call(store._memory_key("mem-2"))]
        )


class TestMilvusStore:
    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_save(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        memory = make_memory()

        result = await store.save(memory)

        assert result == memory.id
        expected = store._memory_payload(memory)
        client.insert.assert_called_once_with(collection_name=store.collection_name, data=[expected])

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_get_found(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        memory = make_memory()
        client.query.return_value = [
            {"metadata_json": json.dumps(memory.to_dict(), default=str, ensure_ascii=False)}
        ]

        result = await store.get(memory.id)

        assert isinstance(result, Memory)
        assert result.id == memory.id

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_get_not_found(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        client.query.return_value = []

        result = await store.get("missing")

        assert result is None

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_update(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        memory = make_memory()
        client.query.return_value = [
            {"metadata_json": json.dumps(memory.to_dict(), default=str, ensure_ascii=False)}
        ]

        result = await store.update(memory.id, {"content": "updated"})

        assert isinstance(result, Memory)
        assert result.content == "updated"
        upsert_args = client.upsert.call_args.kwargs["data"][0]
        assert upsert_args["content"] == "updated"

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_delete(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        client.query.return_value = [{"id": "mem-1"}]

        result = await store.delete("mem-1")

        assert result is True
        client.delete.assert_called_once_with(
            collection_name=store.collection_name,
            filter='id == "mem-1"',
        )

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_exists(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        client.query.return_value = [{"id": "mem-1"}]

        result = await store.exists("mem-1")

        assert result is True

    @pytest.mark.asyncio
    @patch("runtime.memory.storage.milvus_store.MilvusClient")
    async def test_list_by_session(self, mock_milvus_client: MagicMock) -> None:
        client = MagicMock()
        client.has_collection.return_value = True
        mock_milvus_client.return_value = client
        store = MilvusStore(uri="http://milvus.local")
        mem1 = make_memory("mem-1", "one", "sess-1")
        mem2 = make_memory("mem-2", "two", "sess-1")
        client.query.return_value = [
            {"metadata_json": json.dumps(mem1.to_dict(), default=str, ensure_ascii=False)},
            {"metadata_json": json.dumps(mem2.to_dict(), default=str, ensure_ascii=False)},
        ]

        result = await store.list_by_session("sess-1")

        assert [memory.id for memory in result] == ["mem-1", "mem-2"]


class TestGraphStore:
    @pytest.mark.asyncio
    async def test_save(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        memory = make_memory()

        result = await store.save(memory)

        assert result == memory.id
        cypher = mock_graph_store.query.call_args.args[0]
        assert "MERGE (m:Memory" in cypher

    @pytest.mark.asyncio
    async def test_save_no_graph(self) -> None:
        store = GraphStore(None)
        memory = make_memory()

        result = await store.save(memory)

        assert result == memory.id

    @pytest.mark.asyncio
    async def test_get_found(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        memory = make_memory()
        props = {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.type.value,
            "session_id": memory.metadata.session_id,
            "created_at": memory.created_at.isoformat(),
            "importance": memory.importance,
            "metadata_json": json.dumps(
                memory.metadata.model_dump(mode="python"), ensure_ascii=False, default=str
            ),
        }
        mock_graph_store.query.side_effect = [[{"m": props}], [], []]

        result = await store.get(memory.id)

        assert isinstance(result, Memory)
        assert result.id == memory.id
        assert result.metadata.session_id == memory.metadata.session_id

    @pytest.mark.asyncio
    async def test_get_no_graph(self) -> None:
        store = GraphStore(None)

        result = await store.get("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_update(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        memory = make_memory()
        props = {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.type.value,
            "session_id": memory.metadata.session_id,
            "created_at": memory.created_at.isoformat(),
            "importance": memory.importance,
            "metadata_json": json.dumps(
                memory.metadata.model_dump(mode="python"), ensure_ascii=False, default=str
            ),
        }
        mock_graph_store.query.side_effect = [[{"m": props}], [], [], []]

        result = await store.update(memory.id, {"content": "updated"})

        assert isinstance(result, Memory)
        assert result.content == "updated"
        cypher = mock_graph_store.query.call_args_list[-1].args[0]
        assert "MATCH (m:Memory" in cypher
        assert "SET m.content=" in cypher

    @pytest.mark.asyncio
    async def test_delete(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        mock_graph_store.query.side_effect = [[{"count": 1}], []]

        result = await store.delete("mem-1")

        assert result is True
        cypher = mock_graph_store.query.call_args_list[-1].args[0]
        assert "DETACH DELETE" in cypher

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        mock_graph_store.query.return_value = [{"count": 2}]

        result = await store.exists("mem-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        mock_graph_store.query.return_value = [{"count": 0}]

        result = await store.exists("mem-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_by_session(self, mock_graph_store: MagicMock) -> None:
        store = GraphStore(mock_graph_store)
        mem1 = make_memory("mem-1", "one", "sess-1")
        mem2 = make_memory("mem-2", "two", "sess-1")
        mock_graph_store.query.return_value = [
            {
                "m": {
                    "id": mem1.id,
                    "content": mem1.content,
                    "memory_type": mem1.type.value,
                    "session_id": mem1.metadata.session_id,
                    "metadata_json": json.dumps(
                        mem1.metadata.model_dump(mode="python"), ensure_ascii=False, default=str
                    ),
                }
            },
            {
                "m": {
                    "id": mem2.id,
                    "content": mem2.content,
                    "memory_type": mem2.type.value,
                    "session_id": mem2.metadata.session_id,
                    "metadata_json": json.dumps(
                        mem2.metadata.model_dump(mode="python"), ensure_ascii=False, default=str
                    ),
                }
            },
        ]

        result = await store.list_by_session("sess-1")

        assert [memory.id for memory in result] == ["mem-1", "mem-2"]
