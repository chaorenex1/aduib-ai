"""
测试KnowledgeGraphLayer的实现。
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from runtime.memory.graph.knowledge_graph import KnowledgeGraphLayer, MemoryRef
from runtime.memory.storage.graph_store import GraphStore
from runtime.memory.types.base import Entity, Relation, EntityType


@pytest.fixture
def mock_graph_store():
    """创建模拟的GraphStore。"""
    store = Mock(spec=GraphStore)
    store._query = AsyncMock(return_value=[])
    return store


@pytest.fixture
def knowledge_graph_with_store(mock_graph_store):
    """创建使用GraphStore的KnowledgeGraphLayer实例。"""
    return KnowledgeGraphLayer(graph_store=mock_graph_store)


@pytest.fixture
def knowledge_graph_memory_only():
    """创建内存模式的KnowledgeGraphLayer实例。"""
    return KnowledgeGraphLayer(graph_store=None)


@pytest.fixture
def sample_entity():
    """创建示例实体。"""
    return Entity(
        id="entity-001",
        name="Python编程",
        type=EntityType.CONCEPT,
        properties={"description": "编程语言", "difficulty": "medium"}
    )


@pytest.fixture
def sample_relation():
    """创建示例关系。"""
    return Relation(
        source_id="entity-001",
        target_id="entity-002",
        type="RELATES_TO",
        properties={"strength": "high"},
        weight=0.8
    )


@pytest.fixture
def sample_memory_ref():
    """创建示例记忆引用。"""
    return MemoryRef(
        id="memory-001",
        memory_type="episodic",
        summary="学习Python基础语法",
        created_at=datetime.now(),
        importance=0.7
    )


class TestKnowledgeGraphLayer:
    """KnowledgeGraphLayer测试用例。"""

    @pytest.mark.asyncio
    async def test_add_entity_and_get_entity_with_graph_store(self, knowledge_graph_with_store, sample_entity, mock_graph_store):
        """测试使用GraphStore添加和获取实体。"""
        # 准备模拟的查询结果
        mock_graph_store._query.side_effect = [
            [],  # MERGE entity 操作
            [{"e": {"id": "entity-001", "name": "Python编程", "type": "CONCEPT", "properties_json": '{"description": "编程语言", "difficulty": "medium"}'}}]  # 查询结果
        ]

        # 执行添加实体
        result = await knowledge_graph_with_store.add_entity(sample_entity)
        assert result == "entity-001"

        # 验证调用了GraphStore
        assert mock_graph_store._query.call_count >= 1

        # 执行获取实体
        retrieved = await knowledge_graph_with_store.get_entity("entity-001")
        assert retrieved is not None
        assert retrieved.id == "entity-001"
        assert retrieved.name == "Python编程"
        assert retrieved.type == EntityType.CONCEPT

    @pytest.mark.asyncio
    async def test_add_entity_and_get_entity_memory_mode(self, knowledge_graph_memory_only, sample_entity):
        """测试内存模式下添加和获取实体。"""
        # 执行添加实体
        result = await knowledge_graph_memory_only.add_entity(sample_entity)
        assert result == "entity-001"

        # 执行获取实体
        retrieved = await knowledge_graph_memory_only.get_entity("entity-001")
        assert retrieved is not None
        assert retrieved.id == "entity-001"
        assert retrieved.name == "Python编程"
        assert retrieved.type == EntityType.CONCEPT

    @pytest.mark.asyncio
    async def test_add_entity_duplicate_upsert(self, knowledge_graph_memory_only, sample_entity):
        """测试重复添加实体的upsert行为。"""
        # 第一次添加
        result1 = await knowledge_graph_memory_only.add_entity(sample_entity)
        assert result1 == "entity-001"

        # 修改实体名称后再次添加
        sample_entity.name = "Python进阶编程"
        result2 = await knowledge_graph_memory_only.add_entity(sample_entity)
        assert result2 == "entity-001"

        # 验证实体被更新
        retrieved = await knowledge_graph_memory_only.get_entity("entity-001")
        assert retrieved.name == "Python进阶编程"

    @pytest.mark.asyncio
    async def test_query_entities_by_name(self, knowledge_graph_memory_only):
        """测试按名称查询实体。"""
        # 添加多个实体
        entity1 = Entity(id="1", name="Python编程", type=EntityType.CONCEPT, properties={})
        entity2 = Entity(id="2", name="Java编程", type=EntityType.CONCEPT, properties={})
        entity3 = Entity(id="3", name="Python web开发", type=EntityType.CONCEPT, properties={})

        await knowledge_graph_memory_only.add_entity(entity1)
        await knowledge_graph_memory_only.add_entity(entity2)
        await knowledge_graph_memory_only.add_entity(entity3)

        # 查询包含"Python"的实体
        results = await knowledge_graph_memory_only.query_entities(name="Python")
        assert len(results) == 2
        assert all("Python" in entity.name for entity in results)

    @pytest.mark.asyncio
    async def test_query_entities_by_type(self, knowledge_graph_memory_only):
        """测试按类型查询实体。"""
        # 添加不同类型的实体
        entity1 = Entity(id="1", name="用户A", type=EntityType.USER, properties={})
        entity2 = Entity(id="2", name="Python概念", type=EntityType.CONCEPT, properties={})
        entity3 = Entity(id="3", name="用户B", type=EntityType.USER, properties={})

        await knowledge_graph_memory_only.add_entity(entity1)
        await knowledge_graph_memory_only.add_entity(entity2)
        await knowledge_graph_memory_only.add_entity(entity3)

        # 查询USER类型的实体
        results = await knowledge_graph_memory_only.query_entities(entity_type=EntityType.USER)
        assert len(results) == 2
        assert all(entity.type == EntityType.USER for entity in results)

    @pytest.mark.asyncio
    async def test_add_relation(self, knowledge_graph_memory_only, sample_relation):
        """测试添加关系。"""
        # 先添加相关的实体
        entity1 = Entity(id="entity-001", name="Python", type=EntityType.CONCEPT, properties={})
        entity2 = Entity(id="entity-002", name="Web开发", type=EntityType.CONCEPT, properties={})

        await knowledge_graph_memory_only.add_entity(entity1)
        await knowledge_graph_memory_only.add_entity(entity2)

        # 添加关系
        result = await knowledge_graph_memory_only.add_relation(sample_relation)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_relations_with_direction_filter(self, knowledge_graph_memory_only):
        """测试带方向过滤的关系获取。"""
        # 准备实体
        entity1 = Entity(id="entity-001", name="Python", type=EntityType.CONCEPT, properties={})
        entity2 = Entity(id="entity-002", name="Web开发", type=EntityType.CONCEPT, properties={})
        entity3 = Entity(id="entity-003", name="Django", type=EntityType.CONCEPT, properties={})

        await knowledge_graph_memory_only.add_entity(entity1)
        await knowledge_graph_memory_only.add_entity(entity2)
        await knowledge_graph_memory_only.add_entity(entity3)

        # 添加关系
        relation1 = Relation(source_id="entity-001", target_id="entity-002", type="RELATES_TO", properties={}, weight=0.8)
        relation2 = Relation(source_id="entity-003", target_id="entity-001", type="PART_OF", properties={}, weight=0.9)

        await knowledge_graph_memory_only.add_relation(relation1)
        await knowledge_graph_memory_only.add_relation(relation2)

        # 测试outgoing关系
        outgoing = await knowledge_graph_memory_only.get_relations("entity-001", direction="outgoing")
        assert len(outgoing) == 1
        assert outgoing[0].target_id == "entity-002"

        # 测试incoming关系
        incoming = await knowledge_graph_memory_only.get_relations("entity-001", direction="incoming")
        assert len(incoming) == 1
        assert incoming[0].source_id == "entity-003"

        # 测试both方向
        both = await knowledge_graph_memory_only.get_relations("entity-001", direction="both")
        assert len(both) == 2

    @pytest.mark.asyncio
    async def test_traverse_relations(self, knowledge_graph_memory_only):
        """测试关系遍历（深度1和2）。"""
        # 创建一个小的知识图谱: A -> B -> C, A -> D
        entities = [
            Entity(id="A", name="Entity A", type=EntityType.CONCEPT, properties={}),
            Entity(id="B", name="Entity B", type=EntityType.CONCEPT, properties={}),
            Entity(id="C", name="Entity C", type=EntityType.CONCEPT, properties={}),
            Entity(id="D", name="Entity D", type=EntityType.CONCEPT, properties={})
        ]
        for entity in entities:
            await knowledge_graph_memory_only.add_entity(entity)

        relations = [
            Relation(source_id="A", target_id="B", type="RELATES_TO", properties={}, weight=1.0),
            Relation(source_id="B", target_id="C", type="RELATES_TO", properties={}, weight=1.0),
            Relation(source_id="A", target_id="D", type="RELATES_TO", properties={}, weight=1.0)
        ]
        for relation in relations:
            await knowledge_graph_memory_only.add_relation(relation)

        # 深度1遍历
        depth1_entities = await knowledge_graph_memory_only.traverse_relations("A", max_depth=1)
        depth1_ids = [e.id for e in depth1_entities]
        assert "B" in depth1_ids
        assert "D" in depth1_ids
        assert "C" not in depth1_ids

        # 深度2遍历
        depth2_entities = await knowledge_graph_memory_only.traverse_relations("A", max_depth=2)
        depth2_ids = [e.id for e in depth2_entities]
        assert "B" in depth2_ids
        assert "C" in depth2_ids
        assert "D" in depth2_ids

    @pytest.mark.asyncio
    async def test_add_memory_ref_with_entity_association(self, knowledge_graph_memory_only, sample_memory_ref):
        """测试添加记忆引用并关联到实体。"""
        # 先添加实体
        entity = Entity(id="entity-001", name="Python学习", type=EntityType.CONCEPT, properties={})
        await knowledge_graph_memory_only.add_entity(entity)

        # 添加记忆引用并关联
        result = await knowledge_graph_memory_only.add_memory_ref(sample_memory_ref, entity_ids=["entity-001"])
        assert result == "memory-001"

    @pytest.mark.asyncio
    async def test_get_related_memories(self, knowledge_graph_memory_only, sample_memory_ref):
        """测试获取与实体关联的记忆引用。"""
        # 准备数据
        entity = Entity(id="entity-001", name="Python学习", type=EntityType.CONCEPT, properties={})
        await knowledge_graph_memory_only.add_entity(entity)
        await knowledge_graph_memory_only.add_memory_ref(sample_memory_ref, entity_ids=["entity-001"])

        # 获取关联的记忆
        related_memories = await knowledge_graph_memory_only.get_related_memories("entity-001")
        assert len(related_memories) == 1
        assert related_memories[0].id == "memory-001"

    @pytest.mark.asyncio
    async def test_find_similar_memories_in_memory_mode(self, knowledge_graph_memory_only, sample_memory_ref):
        """测试内存模式下查找相似记忆（应优雅降级）。"""
        await knowledge_graph_memory_only.add_memory_ref(sample_memory_ref)

        # 内存模式下应返回空列表
        similar = await knowledge_graph_memory_only.find_similar_memories("memory-001")
        assert similar == []

    @pytest.mark.asyncio
    async def test_graceful_behavior_without_graph_store(self):
        """测试没有GraphStore时的优雅行为。"""
        kg = KnowledgeGraphLayer(graph_store=None)

        # 添加实体应该正常工作
        entity = Entity(id="test", name="Test", type=EntityType.CONCEPT, properties={})
        result = await kg.add_entity(entity)
        assert result == "test"

        # 获取实体应该正常工作
        retrieved = await kg.get_entity("test")
        assert retrieved is not None
        assert retrieved.id == "test"

        # 其他操作也应该正常工作，不会抛出异常
        relations = await kg.get_relations("test")
        assert relations == []

        entities = await kg.traverse_relations("test")
        assert entities == []


class TestMemoryRef:
    """MemoryRef模型测试。"""

    def test_memory_ref_creation(self):
        """测试MemoryRef的创建。"""
        memory_ref = MemoryRef(
            id="test-001",
            memory_type="episodic",
            summary="测试记忆引用",
            importance=0.8
        )

        assert memory_ref.id == "test-001"
        assert memory_ref.memory_type == "episodic"
        assert memory_ref.summary == "测试记忆引用"
        assert memory_ref.importance == 0.8
        assert memory_ref.created_at is not None

    def test_memory_ref_defaults(self):
        """测试MemoryRef的默认值。"""
        memory_ref = MemoryRef(
            id="test-002",
            memory_type="semantic"
        )

        assert memory_ref.summary == ""
        assert memory_ref.importance == 0.5
        assert memory_ref.created_at is not None


if __name__ == "__main__":
    pytest.main([__file__])