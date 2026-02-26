import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from runtime.memory.manager import UnifiedMemoryManager
from runtime.memory.types.base import (
    Entity,
    EntityType,
    Memory,
    MemoryClassification,
    MemoryDomain,
    MemoryLifecycle,
    MemoryMetadata,
    MemoryScope,
    MemorySource,
    MemoryType,
)
from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult


def _make_memory(
    *,
    memory_id: str,
    content: str = "test content",
    memory_type: MemoryType = MemoryType.WORKING,
    scope: MemoryScope = MemoryScope.PERSONAL,
    tags: list[str] | None = None,
    session_id: str | None = None,
    created_at: datetime | None = None,
    entities: list[Entity] | None = None,
) -> Memory:
    metadata = MemoryMetadata(
        session_id=session_id,
        scope=scope,
        tags=tags or [],
    )
    return Memory(
        id=memory_id,
        type=memory_type,
        content=content,
        metadata=metadata,
        created_at=created_at or datetime.now(),
        entities=entities or [],
    )


@pytest.fixture
def mock_storage() -> AsyncMock:
    """创建 Mock StorageAdapter。"""
    storage = AsyncMock(spec=StorageAdapter)
    storage.save.return_value = "test-id-123"
    storage.get.return_value = None
    storage.update.return_value = None
    storage.delete.return_value = True
    storage.exists.return_value = True
    storage.list_by_session.return_value = []
    return storage


@pytest.fixture
def mock_retrieval() -> AsyncMock:
    """创建 Mock RetrievalEngine。"""
    retrieval = AsyncMock(spec=RetrievalEngine)
    retrieval.search.return_value = []
    retrieval.search_by_embedding.return_value = []
    retrieval.search_by_entities.return_value = []
    return retrieval


@pytest.fixture
def manager(mock_storage: AsyncMock) -> UnifiedMemoryManager:
    """创建 UnifiedMemoryManager 实例。"""
    return UnifiedMemoryManager(storage=mock_storage)


@pytest.fixture
def manager_with_retrieval(
    mock_storage: AsyncMock, mock_retrieval: AsyncMock
) -> UnifiedMemoryManager:
    """创建带检索引擎的 UnifiedMemoryManager。"""
    return UnifiedMemoryManager(storage=mock_storage, retrieval=mock_retrieval)


@pytest.mark.asyncio
async def test_store_memory(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    memory = _make_memory(memory_id="mem-1", content="simple memory")
    start = datetime.now()

    memory_id = await manager.store(memory)

    assert memory_id == "test-id-123"
    assert memory.id == "test-id-123"
    assert memory.updated_at >= start
    assert memory.accessed_at >= start
    assert memory.updated_at == memory.accessed_at
    mock_storage.save.assert_awaited_once_with(memory)


@pytest.mark.asyncio
async def test_store_memory_applies_classification(mock_storage: AsyncMock) -> None:
    classification = MemoryClassification(
        source=MemorySource.CHAT,
        domain=MemoryDomain.GENERAL,
        scope=MemoryScope.WORK,
        lifecycle=MemoryLifecycle.LONG,
        tags=["tag-a", "tag-b"],
    )
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=classification)

    manager = UnifiedMemoryManager(storage=mock_storage, classifier=classifier)
    memory = _make_memory(memory_id="mem-2", tags=["existing"])

    await manager.store(memory)

    classifier.classify.assert_awaited_once()
    assert memory.metadata.tags == ["existing", "tag-a", "tag-b"]
    assert "classification" in memory.metadata.extra


@pytest.mark.asyncio
async def test_retrieve_memories(
    manager_with_retrieval: UnifiedMemoryManager,
    mock_retrieval: AsyncMock,
    mock_storage: AsyncMock,
) -> None:
    now = datetime.now()
    matching = _make_memory(
        memory_id="mem-1",
        memory_type=MemoryType.WORKING,
        scope=MemoryScope.PERSONAL,
        created_at=now - timedelta(minutes=5),
    )
    non_matching = _make_memory(
        memory_id="mem-2",
        memory_type=MemoryType.SEMANTIC,
        scope=MemoryScope.WORK,
        created_at=now - timedelta(days=3),
    )
    mock_retrieval.search.return_value = [
        RetrievalResult(memory=matching, score=0.9, source="mock"),
        RetrievalResult(memory=non_matching, score=0.8, source="mock"),
    ]
    time_range = (now - timedelta(days=1), now + timedelta(days=1))

    results = await manager_with_retrieval.retrieve(
        query="hello",
        memory_types=[MemoryType.WORKING],
        scope=MemoryScope.PERSONAL,
        time_range=time_range,
        limit=5,
    )

    mock_retrieval.search.assert_awaited_once_with(
        query="hello",
        memory_types=[MemoryType.WORKING],
        scope=MemoryScope.PERSONAL,
        time_range=time_range,
        limit=5,
    )
    assert results == [matching]
    assert matching.accessed_at >= now
    mock_storage.update.assert_awaited_once()
    update_args = mock_storage.update.call_args.args
    assert update_args[0] == "mem-1"
    assert "accessed_at" in update_args[1]


@pytest.mark.asyncio
async def test_retrieve_without_engine_raises(manager: UnifiedMemoryManager) -> None:
    with pytest.raises(NotImplementedError):
        await manager.retrieve("missing")


@pytest.mark.asyncio
async def test_update_memory(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    updates = {"content": "updated"}

    await manager.update("mem-3", updates)

    mock_storage.update.assert_awaited_once()
    update_args = mock_storage.update.call_args.args
    assert update_args[0] == "mem-3"
    assert update_args[1]["content"] == "updated"
    assert isinstance(update_args[1]["updated_at"], datetime)


@pytest.mark.asyncio
async def test_forget_memory(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    result = await manager.forget("mem-4")

    assert result is True
    mock_storage.delete.assert_awaited_once_with("mem-4")


@pytest.mark.asyncio
async def test_get_memory(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    memory = _make_memory(memory_id="mem-5")
    mock_storage.get.return_value = memory
    mock_storage.update.return_value = memory
    start = datetime.now()

    result = await manager.get("mem-5")

    assert result is memory
    assert memory.accessed_at >= start
    mock_storage.get.assert_awaited_once_with("mem-5")
    mock_storage.update.assert_awaited_once()
    update_args = mock_storage.update.call_args.args
    assert update_args[0] == "mem-5"
    assert "accessed_at" in update_args[1]


@pytest.mark.asyncio
async def test_get_memory_not_found(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    mock_storage.get.return_value = None

    result = await manager.get("missing")

    assert result is None
    mock_storage.update.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_entity_filter(
    manager_with_retrieval: UnifiedMemoryManager,
    mock_retrieval: AsyncMock,
    mock_storage: AsyncMock,
) -> None:
    entity = Entity(id="entity-1", name="Entity", type=EntityType.CONCEPT)
    memory = _make_memory(memory_id="mem-6", entities=[entity])
    mock_retrieval.search_by_entities.return_value = [
        RetrievalResult(memory=memory, score=0.9, source="mock")
    ]

    results = await manager_with_retrieval.search(
        query="ignored",
        entity_filter=["entity-1"],
        limit=3,
    )

    mock_retrieval.search_by_entities.assert_awaited_once_with(["entity-1"], limit=3)
    mock_retrieval.search.assert_not_called()
    assert results and results[0].memory.id == "mem-6"
    mock_storage.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_with_query(
    manager_with_retrieval: UnifiedMemoryManager,
    mock_retrieval: AsyncMock,
    mock_storage: AsyncMock,
) -> None:
    memory = _make_memory(memory_id="mem-7", memory_type=MemoryType.SEMANTIC)
    mock_retrieval.search.return_value = [
        RetrievalResult(memory=memory, score=0.85, source="mock")
    ]

    results = await manager_with_retrieval.search(
        query="find this",
        memory_types=[MemoryType.SEMANTIC],
        scope=MemoryScope.PERSONAL,
        limit=2,
        min_score=0.3,
    )

    mock_retrieval.search.assert_awaited_once_with(
        query="find this",
        memory_types=[MemoryType.SEMANTIC],
        scope=MemoryScope.PERSONAL,
        time_range=None,
        limit=2,
        min_score=0.3,
    )
    mock_retrieval.search_by_entities.assert_not_called()
    assert results and results[0].memory.id == "mem-7"
    mock_storage.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidate_session(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    mock_storage.save.return_value = "consolidated-1"
    memory_one = _make_memory(
        memory_id="mem-8",
        content="first line",
        memory_type=MemoryType.WORKING,
        session_id="session-1",
        tags=["alpha"],
    )
    memory_two = _make_memory(
        memory_id="mem-9",
        content="second line",
        memory_type=MemoryType.WORKING,
        session_id="session-1",
        tags=["beta"],
        scope=MemoryScope.WORK,
    )
    mock_storage.list_by_session.return_value = [memory_one, memory_two]

    consolidated = await manager.consolidate("session-1")

    assert len(consolidated) == 1
    assert consolidated[0].type == MemoryType.EPISODIC
    assert consolidated[0].content == "first line\nsecond line"
    assert consolidated[0].metadata.session_id == "session-1"
    mock_storage.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidate_empty_session(
    manager: UnifiedMemoryManager, mock_storage: AsyncMock
) -> None:
    mock_storage.list_by_session.return_value = [
        _make_memory(memory_id="mem-10", memory_type=MemoryType.SEMANTIC)
    ]

    consolidated = await manager.consolidate("empty-session")

    assert consolidated == []
    mock_storage.save.assert_not_called()


@pytest.mark.asyncio
async def test_exists(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    result = await manager.exists("mem-11")

    assert result is True
    mock_storage.exists.assert_awaited_once_with("mem-11")


@pytest.mark.asyncio
async def test_list_by_session(manager: UnifiedMemoryManager, mock_storage: AsyncMock) -> None:
    memories = [_make_memory(memory_id="mem-12")]
    mock_storage.list_by_session.return_value = memories

    result = await manager.list_by_session("session-2")

    assert result == memories
    mock_storage.list_by_session.assert_awaited_once_with("session-2")
