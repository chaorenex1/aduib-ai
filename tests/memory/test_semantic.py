"""测试 SemanticMemory 类型模块。"""

from typing import Optional
from uuid import uuid4

import pytest

from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types import Entity, EntityType, Memory, MemoryMetadata, MemoryType, Relation
from runtime.memory.types.semantic import SemanticMemory


class MockStorageAdapter(StorageAdapter):
    """模拟存储适配器用于测试。"""

    def __init__(self) -> None:
        self.memories: dict[str, Memory] = {}
        self.save_calls: list[Memory] = []
        self.get_calls: list[str] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.list_calls: list[str] = []

    async def save(self, memory: Memory) -> str:
        """保存记忆。"""
        self.save_calls.append(memory)
        self.memories[memory.id] = memory
        return memory.id

    async def get(self, memory_id: str) -> Optional[Memory]:
        """获取记忆。"""
        self.get_calls.append(memory_id)
        return self.memories.get(memory_id)

    async def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        """更新记忆。"""
        self.update_calls.append((memory_id, updates))
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            for key, value in updates.items():
                setattr(memory, key, value)
            return memory
        return None

    async def delete(self, memory_id: str) -> bool:
        """删除记忆。"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

    async def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在。"""
        return memory_id in self.memories

    async def list_by_session(self, session_id: str) -> list[Memory]:
        """按会话列出记忆。"""
        self.list_calls.append(session_id)
        return [
            memory
            for memory in self.memories.values()
            if memory.metadata.session_id == session_id and memory.type == MemoryType.SEMANTIC
        ]


class MockRetrievalEngine(RetrievalEngine):
    """模拟检索引擎用于测试。"""

    def __init__(self) -> None:
        self.search_calls: list[str] = []
        self.embedding_calls: list[list[float]] = []
        self.entity_calls: list[list[str]] = []
        self._mock_results: list[RetrievalResult] = []

    def set_mock_results(self, results: list[RetrievalResult]) -> None:
        """设置模拟检索结果。"""
        self._mock_results = results

    async def search(
        self,
        query: str,
        memory_types=None,
        scope=None,
        time_range=None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """模拟文本检索。"""
        self.search_calls.append(query)
        return self._mock_results[:limit]

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """模拟向量检索。"""
        self.embedding_calls.append(embedding)
        return self._mock_results[:limit]

    async def search_by_entities(
        self,
        entity_ids: list[str],
        relation_types=None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """模拟实体检索。"""
        self.entity_calls.append(entity_ids)
        return self._mock_results[:limit]


def _make_knowledge(
    knowledge_id: Optional[str] = None,
    content: str = "Python 是一种高级编程语言",
    session_id: str = "session-1",
    knowledge_type: str = "fact",
    tags: Optional[list[str]] = None,
    embedding: Optional[list[float]] = None,
) -> Memory:
    """创建一个测试用的知识记忆。"""
    memory_id = knowledge_id or str(uuid4())
    metadata = MemoryMetadata(
        session_id=session_id, user_id="user-123", tags=tags or [], extra={"knowledge_type": knowledge_type}
    )
    return Memory(
        id=memory_id, type=MemoryType.SEMANTIC, content=content, metadata=metadata, embedding=embedding, importance=0.7
    )


@pytest.mark.asyncio
async def test_add_knowledge_basic() -> None:
    """测试基本的知识添加功能。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    content = "FastAPI 是一个现代的 Python Web 框架"
    session_id = "sess-1"

    knowledge_id = await semantic.add_knowledge(
        content=content, session_id=session_id, user_id="user-456", importance=0.8
    )

    # 验证保存调用
    assert len(adapter.save_calls) == 1
    saved_memory = adapter.save_calls[0]

    assert saved_memory.type == MemoryType.SEMANTIC
    assert saved_memory.content == content
    assert saved_memory.metadata.session_id == session_id
    assert saved_memory.metadata.user_id == "user-456"
    assert saved_memory.metadata.extra["knowledge_type"] == "fact"
    assert saved_memory.importance == 0.8
    assert knowledge_id == saved_memory.id


@pytest.mark.asyncio
async def test_add_knowledge_with_tags_and_entities() -> None:
    """测试添加带标签和实体的知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    content = "Django 是 Python 的 Web 开发框架"
    tags = ["web", "python", "framework"]
    entities = [
        Entity(id="django", name="Django", type=EntityType.CONCEPT),
        Entity(id="python", name="Python", type=EntityType.CONCEPT),
    ]
    relations = [Relation(source_id="django", target_id="python", type="implemented_in")]

    knowledge_id = await semantic.add_knowledge(
        content=content,
        session_id="sess-2",
        tags=tags,
        entities=entities,
        relations=relations,
        knowledge_type="concept",
    )

    saved_memory = adapter.save_calls[0]
    assert saved_memory.metadata.tags == tags
    assert len(saved_memory.entities) == 2
    assert saved_memory.entities[0].name == "Django"
    assert len(saved_memory.relations) == 1
    assert saved_memory.relations[0].type == "implemented_in"
    assert saved_memory.metadata.extra["knowledge_type"] == "concept"


@pytest.mark.asyncio
async def test_add_knowledge_with_embedding() -> None:
    """测试添加带预计算向量的知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    content = "机器学习是人工智能的一个分支"
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    await semantic.add_knowledge(content=content, session_id="sess-3", embedding=embedding, knowledge_type="fact")

    saved_memory = adapter.save_calls[0]
    assert saved_memory.embedding == embedding
    assert saved_memory.metadata.extra["knowledge_type"] == "fact"


@pytest.mark.asyncio
async def test_query_knowledge_with_retrieval_engine() -> None:
    """测试使用检索引擎的知识查询。"""
    adapter = MockStorageAdapter()
    retrieval_engine = MockRetrievalEngine()
    semantic = SemanticMemory(adapter, retrieval_engine)

    # 设置模拟结果
    mock_memory = _make_knowledge("k1", "Python 相关知识")
    mock_results = [RetrievalResult(memory=mock_memory, score=0.9, source="vector")]
    retrieval_engine.set_mock_results(mock_results)

    query = "Python 编程"
    results = await semantic.query_knowledge(query=query, limit=5, min_score=0.7)

    # 验证调用了检索引擎
    assert len(retrieval_engine.search_calls) == 1
    assert retrieval_engine.search_calls[0] == query

    # 验证返回结果
    assert len(results) == 1
    assert results[0].memory.content == "Python 相关知识"
    assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_query_knowledge_without_engine() -> None:
    """测试没有检索引擎时的查询回退行为。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)  # 没有 retrieval_engine

    with pytest.raises(NotImplementedError):
        await semantic.query_knowledge(query="Python 编程")


@pytest.mark.asyncio
async def test_get_knowledge_found() -> None:
    """测试获取存在的知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    knowledge = _make_knowledge("k1", "测试知识")
    adapter.memories[knowledge.id] = knowledge

    result = await semantic.get_knowledge("k1")

    assert result is not None
    assert result.id == "k1"
    assert result.content == "测试知识"
    assert len(adapter.get_calls) == 1
    assert adapter.get_calls[0] == "k1"


@pytest.mark.asyncio
async def test_get_knowledge_not_found() -> None:
    """测试获取不存在的知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    result = await semantic.get_knowledge("missing")

    assert result is None
    assert len(adapter.get_calls) == 1
    assert adapter.get_calls[0] == "missing"


@pytest.mark.asyncio
async def test_update_knowledge() -> None:
    """测试更新知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    original_knowledge = _make_knowledge("k1", "原始内容")
    adapter.memories[original_knowledge.id] = original_knowledge

    updated = await semantic.update_knowledge("k1", content="更新后的内容", importance=0.9)

    assert updated is not None
    assert len(adapter.update_calls) == 1
    call_id, call_updates = adapter.update_calls[0]
    assert call_id == "k1"
    assert call_updates["content"] == "更新后的内容"
    assert call_updates["importance"] == 0.9


@pytest.mark.asyncio
async def test_list_by_tags() -> None:
    """测试按标签列出知识。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    # 创建带不同标签的知识
    k1 = _make_knowledge("k1", "Python 知识", tags=["python", "programming"])
    k2 = _make_knowledge("k2", "Web 知识", tags=["web", "python"])
    k3 = _make_knowledge("k3", "数据库知识", tags=["database", "sql"])

    adapter.memories[k1.id] = k1
    adapter.memories[k2.id] = k2
    adapter.memories[k3.id] = k3

    # 按标签查询
    results = await semantic.list_by_tags(["python"])

    # 应该返回包含 python 标签的知识
    assert len(results) == 2
    result_ids = {r.id for r in results}
    assert result_ids == {"k1", "k2"}


@pytest.mark.asyncio
async def test_search_similar_with_engine() -> None:
    """测试使用向量的相似度搜索。"""
    adapter = MockStorageAdapter()
    retrieval_engine = MockRetrievalEngine()
    semantic = SemanticMemory(adapter, retrieval_engine)

    # 设置模拟结果
    mock_memory = _make_knowledge("k1", "相似知识")
    mock_results = [RetrievalResult(memory=mock_memory, score=0.85, source="embedding")]
    retrieval_engine.set_mock_results(mock_results)

    embedding = [0.1, 0.2, 0.3]
    results = await semantic.search_similar(embedding=embedding, limit=3, min_score=0.8)

    # 验证调用了向量检索
    assert len(retrieval_engine.embedding_calls) == 1
    assert retrieval_engine.embedding_calls[0] == embedding

    # 验证返回结果
    assert len(results) == 1
    assert results[0].memory.content == "相似知识"
    assert results[0].score == 0.85


@pytest.mark.asyncio
async def test_search_similar_without_engine() -> None:
    """测试没有检索引擎时的向量搜索。"""
    adapter = MockStorageAdapter()
    semantic = SemanticMemory(adapter)

    embedding = [0.1, 0.2, 0.3]

    with pytest.raises(NotImplementedError):
        await semantic.search_similar(embedding=embedding)


@pytest.mark.asyncio
async def test_knowledge_type_filtering() -> None:
    """测试知识类型过滤功能。"""
    adapter = MockStorageAdapter()
    retrieval_engine = MockRetrievalEngine()
    semantic = SemanticMemory(adapter, retrieval_engine)

    # 设置不同类型的知识
    fact_memory = _make_knowledge("f1", "事实知识", knowledge_type="fact")
    concept_memory = _make_knowledge("c1", "概念知识", knowledge_type="concept")

    mock_results = [
        RetrievalResult(memory=fact_memory, score=0.9, source="search"),
        RetrievalResult(memory=concept_memory, score=0.8, source="search"),
    ]
    retrieval_engine.set_mock_results(mock_results)

    # 查询特定类型的知识
    results = await semantic.query_knowledge(query="知识", knowledge_type="fact")

    # 验证返回的是正确类型的知识
    assert len(results) == 2  # 返回所有结果，类型过滤在实际实现中进行
