import json
from datetime import datetime, timedelta
from unittest.mock import ANY, MagicMock, call

import pytest

from runtime.memory.types import Memory, MemoryType, WorkingMemory


def _make_memory(memory_id: str = "mem-1", content: str = "hello") -> Memory:
    return Memory(id=memory_id, type=MemoryType.EPISODIC, content=content)


@pytest.fixture(autouse=True)
def mock_to_thread(monkeypatch):
    async def _run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("runtime.memory.types.working.asyncio.to_thread", _run_sync)


@pytest.mark.asyncio
async def test_add_memory() -> None:
    redis = MagicMock()
    pipeline = MagicMock()
    redis.pipeline.return_value = pipeline
    working = WorkingMemory(redis_client=redis, session_id="sess-1", ttl_seconds=60, max_entries=3)
    memory = _make_memory()
    start = datetime.now()

    memory_id = await working.add(memory)

    assert memory_id == memory.id
    assert memory.type == MemoryType.WORKING
    assert memory.metadata.session_id == "sess-1"
    assert memory.ttl is not None
    ttl_seconds = (memory.ttl - datetime.now()).total_seconds()
    assert 59 <= ttl_seconds <= 61

    index_key = working._index_key(memory.id)
    pipeline.set.assert_called_once()
    set_args, set_kwargs = pipeline.set.call_args
    assert set_args[0] == index_key
    assert set_kwargs["ex"] == 60
    payload = set_args[1]
    saved = json.loads(payload)
    assert saved["id"] == memory.id
    assert saved["type"] == MemoryType.WORKING
    pipeline.rpush.assert_called_once_with(working.key, memory.id)
    pipeline.expire.assert_called_once_with(working.key, 60)
    pipeline.ltrim.assert_called_once_with(working.key, -working.max_entries, -1)
    pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_memory_found() -> None:
    redis = MagicMock()
    working = WorkingMemory(redis_client=redis, session_id="sess-2", ttl_seconds=30)
    original = _make_memory()
    original_accessed = original.accessed_at
    serialized = json.dumps(original.to_dict(), default=str, ensure_ascii=False).encode()
    redis.get.return_value = serialized

    result = await working.get(original.id)

    assert isinstance(result, Memory)
    assert result.id == original.id
    assert result.accessed_at >= original_accessed
    redis.set.assert_called_once_with(working._index_key(original.id), ANY, ex=30)
    redis.expire.assert_called_once_with(working.key, 30)


@pytest.mark.asyncio
async def test_get_memory_not_found() -> None:
    redis = MagicMock()
    redis.get.return_value = None
    working = WorkingMemory(redis_client=redis, session_id="sess-3")

    result = await working.get("missing")

    assert result is None
    redis.set.assert_not_called()
    redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_list_memories_empty() -> None:
    redis = MagicMock()
    redis.lrange.return_value = []
    working = WorkingMemory(redis_client=redis, session_id="sess-4")

    result = await working.list_memories()

    assert result == []
    redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_list_memories_multiple() -> None:
    redis = MagicMock()
    pipeline = MagicMock()
    redis.pipeline.return_value = pipeline
    working = WorkingMemory(redis_client=redis, session_id="sess-5")
    mem1 = _make_memory("m1", "c1")
    mem2 = _make_memory("m2", "c2")
    redis.lrange.return_value = ["m1", "m2"]
    pipeline.execute.return_value = [
        json.dumps(mem1.to_dict(), default=str, ensure_ascii=False),
        json.dumps(mem2.to_dict(), default=str, ensure_ascii=False),
    ]

    result = await working.list_memories()

    assert [m.id for m in result] == ["m1", "m2"]
    pipeline.get.assert_has_calls(
        [call(working._index_key("m1")), call(working._index_key("m2"))]
    )
    pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_clear() -> None:
    redis = MagicMock()
    redis.lrange.return_value = ["m1", "m2"]
    redis.delete.side_effect = [2, 1]
    working = WorkingMemory(redis_client=redis, session_id="sess-6")

    deleted = await working.clear()

    assert deleted == 3
    redis.delete.assert_has_calls(
        [
            call(working._index_key("m1"), working._index_key("m2")),
            call(working.key),
        ]
    )


@pytest.mark.asyncio
async def test_clear_empty() -> None:
    redis = MagicMock()
    redis.lrange.return_value = []
    redis.delete.return_value = 0
    working = WorkingMemory(redis_client=redis, session_id="sess-7")

    deleted = await working.clear()

    assert deleted == 0
    redis.delete.assert_called_once_with(working.key)


@pytest.mark.asyncio
async def test_count() -> None:
    redis = MagicMock()
    redis.llen.return_value = 5
    working = WorkingMemory(redis_client=redis, session_id="sess-8")

    result = await working.count()

    assert result == 5
    redis.llen.assert_called_once_with(working.key)


@pytest.mark.asyncio
async def test_remove_existing() -> None:
    redis = MagicMock()
    redis.delete.return_value = 1
    redis.lrem.return_value = 1
    working = WorkingMemory(redis_client=redis, session_id="sess-9")

    result = await working.remove("m1")

    assert result is True
    redis.delete.assert_called_once_with(working._index_key("m1"))
    redis.lrem.assert_called_once_with(working.key, 0, "m1")


@pytest.mark.asyncio
async def test_remove_nonexistent() -> None:
    redis = MagicMock()
    redis.delete.return_value = 0
    redis.lrem.return_value = 0
    working = WorkingMemory(redis_client=redis, session_id="sess-10")

    result = await working.remove("missing")

    assert result is False
    redis.delete.assert_called_once_with(working._index_key("missing"))
    redis.lrem.assert_called_once_with(working.key, 0, "missing")


@pytest.mark.asyncio
async def test_from_short_term_memory() -> None:
    redis = MagicMock()
    working = WorkingMemory.from_short_term_memory(redis_client=redis, session_id="sess-11", max_turns=15)

    assert isinstance(working, WorkingMemory)
    assert working.max_entries == 15
    assert working.session_id == "sess-11"


@pytest.mark.asyncio
async def test_session_id_property() -> None:
    working = WorkingMemory(redis_client=MagicMock(), session_id="sess-12")

    assert working.session_id == "sess-12"


@pytest.mark.asyncio
async def test_key_property() -> None:
    working = WorkingMemory(redis_client=MagicMock(), session_id="sess-13")

    assert working.key == "memory:working:sess-13"
