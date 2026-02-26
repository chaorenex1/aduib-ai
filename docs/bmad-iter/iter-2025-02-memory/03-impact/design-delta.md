# 设计变更文档

**迭代ID**: iter-2025-02-memory
**创建日期**: 2025-02-24
**文档版本**: v1.0

---

## 1. 概述

本文档记录统一记忆系统与现有架构之间的设计差异，以及需要进行的架构调整。

---

## 2. 架构对比

### 2.1 现有架构

```
┌─────────────────────────────────────────────────────────┐
│                    AgentManager                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │              MemoryManager (L100-134)            │  │
│  │  • 缓存: {agent_id}_{session_id}                 │  │
│  │  • 检索: run_in_executor 包装同步调用            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    AgentMemory                          │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │ ShortTermRedisMemory│  │ LongTermEmbeddingsMemory│  │
│  │ (Redis List)        │  │ (Milvus)                │  │
│  └─────────────────────┘  └─────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ LongTermGraphMemory (Optional, Neo4j)           │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  QAMemoryService                        │
│  • 独立服务，与 AgentMemory 无集成                      │
│  • 自有信任评分、等级晋升逻辑                           │
│  • Milvus + PostgreSQL 存储                             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 目标架构

```
┌─────────────────────────────────────────────────────────┐
│                    AgentManager                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │              MemoryManager (重构)                │  │
│  │  • 委托给 UnifiedMemoryManager                   │  │
│  │  • 保持现有接口兼容                              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│               UnifiedMemoryManager (新增)               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │WorkingMemory│ │EpisodicMemory│ │SemanticMemory│      │
│  │ (Redis)     │ │ (Milvus)    │ │ (Milvus)    │      │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘      │
│         │               │               │              │
│  ┌──────┴───────────────┴───────────────┴──────────┐  │
│  │           KnowledgeGraphLayer (新增)            │  │
│  │  • 实体-关系存储                                │  │
│  │  • 图遍历检索                                   │  │
│  └──────────────────────────────────────────────────┘  │
│                           │                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │         HybridRetrievalEngine (新增)            │  │
│  │  • 向量检索 + 关键词检索 + 图检索               │  │
│  │  • RRF 融合重排                                 │  │
│  └──────────────────────────────────────────────────┘  │
│                           │                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │         UnifiedStorageAdapter (新增)            │  │
│  │  • Redis (工作记忆)                             │  │
│  │  • Milvus (向量/语义)                           │  │
│  │  • Neo4j (图，可选)                             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           │ 集成
                           ▼
┌─────────────────────────────────────────────────────────┐
│               QAMemoryService (集成)                    │
│  • 作为 SemanticMemory 的特化实现                       │
│  • 复用信任评分、等级晋升逻辑                           │
│  • 统一存储接口                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 关键设计变更

### 3.1 记忆类型统一

| 现有 | 目标 | 变更说明 |
|------|------|----------|
| ShortTermRedisMemory | WorkingMemory | 扩展：支持任务上下文、临时状态 |
| LongTermEmbeddingsMemory | EpisodicMemory | 重命名：强调事件时间线语义 |
| N/A | SemanticMemory | 新增：知识事实存储，集成 QA Memory |
| LongTermGraphMemory | KnowledgeGraphLayer | 升级：从可选组件变为核心层 |

### 3.2 存储抽象层

**现有模式**:
```python
class AgentMemory:
    def __init__(self, ...):
        self.short_term = ShortTermRedisMemory(...)
        self.long_term = LongTermEmbeddingsMemory(...)
        self.graph = LongTermGraphMemory(...)  # 可选
```

**目标模式**:
```python
class UnifiedMemoryManager:
    def __init__(self, storage: UnifiedStorageAdapter):
        self.storage = storage
        self.working = WorkingMemory(storage.redis)
        self.episodic = EpisodicMemory(storage.milvus)
        self.semantic = SemanticMemory(storage.milvus)
        self.graph = KnowledgeGraphLayer(storage.graph)
        self.retriever = HybridRetrievalEngine(...)
```

### 3.3 检索策略变更

**现有**: 单路检索（向量 OR 关键词）
```python
# LongTermEmbeddingsMemory.retrieve()
results = self.vector.search_by_vector(query_embedding)
```

**目标**: 多路并行检索 + RRF 融合
```python
# HybridRetrievalEngine.retrieve()
async def retrieve(self, query: str, **filters) -> list[Memory]:
    # 并行执行多路检索
    vector_results, keyword_results, graph_results = await asyncio.gather(
        self.vector_search.search(query),
        self.keyword_search.search(query),
        self.graph_search.search(query)
    )
    # RRF 融合重排
    return self.reranker.fuse(vector_results, keyword_results, graph_results)
```

### 3.4 生命周期管理

**现有**: 被动过期（TTL）
```python
# redis_memory.py - 无主动管理
# qa_memory_service.py - TTL 过期
```

**目标**: 主动整合 + 智能遗忘
```python
class LifecycleManager:
    async def consolidate(self, session_id: str):
        """工作记忆 → 长期记忆整合"""
        working_memories = await self.working.get_session(session_id)
        for memory in working_memories:
            importance = await self.evaluate_importance(memory)
            if importance > self.threshold:
                await self.episodic.store(memory)

    async def forget(self, memory_id: str):
        """基于重要性的遗忘"""
        memory = await self.storage.get(memory_id)
        if memory.importance < self.forget_threshold:
            await self.storage.delete(memory_id)
```

---

## 4. 接口变更

### 4.1 新增接口

```python
# UnifiedMemoryManager 核心接口
class UnifiedMemoryManager:
    async def store(self, memory: Memory) -> str: ...
    async def retrieve(self, query: str, **filters) -> list[Memory]: ...
    async def update(self, memory_id: str, updates: dict) -> Memory: ...
    async def forget(self, memory_id: str) -> bool: ...
    async def consolidate(self, session_id: str) -> list[Memory]: ...
    async def search(
        self,
        query: str,
        memory_types: list[MemoryType] = None,
        scope: MemoryScope = None,
        entity_filter: list[str] = None,
        time_range: tuple[datetime, datetime] = None,
        limit: int = 10,
    ) -> list[Memory]: ...
```

### 4.2 兼容性适配器

```python
class AgentMemoryAdapter(MemoryBase):
    """向后兼容适配器"""

    def __init__(self, unified_manager: UnifiedMemoryManager):
        self._manager = unified_manager

    # 实现现有 MemoryBase 接口
    def add_memory(self, message: Message) -> None: ...
    def get_memory(self, query: str) -> list[dict]: ...
    def delete_memory(self) -> None: ...
```

### 4.3 弃用接口

| 接口 | 弃用版本 | 替代方案 |
|------|----------|----------|
| `AgentMemory.__init__()` | v1.0 | `UnifiedMemoryManager` |
| `ShortTermRedisMemory` | v1.0 | `WorkingMemory` |
| `LongTermEmbeddingsMemory` | v1.0 | `EpisodicMemory` |

---

## 5. 数据模型变更

### 5.1 新增数据结构

```python
@dataclass
class Memory:
    id: str                          # UUID
    type: MemoryType                  # WORKING | EPISODIC | SEMANTIC
    content: str                      # 记忆内容
    embedding: Optional[list[float]]  # 向量表示
    metadata: MemoryMetadata          # 元信息
    entities: list[Entity]            # 关联实体
    relations: list[Relation]         # 关联关系
    scope: MemoryScope                # 范围层级
    created_at: datetime
    updated_at: datetime
    accessed_at: datetime
    importance: float                 # 重要性评分 0-1
    decay_rate: float                 # 衰减速率
    ttl: Optional[datetime]           # 过期时间

class MemoryScope(Enum):
    PERSONAL = "personal"    # 个人级别
    WORK = "work"            # 工作空间级别
    PROJECT = "project"      # 项目级别
    MODULE = "module"        # 模块级别
```

### 5.2 QaMemoryRecord 扩展

```python
# 新增字段 (向后兼容)
class QaMemoryRecord:
    # ... 现有字段 ...

    # 新增
    scope: str = "personal"          # 范围层级
    memory_type: str = "semantic"    # 统一记忆类型
    unified_id: Optional[str] = None # 统一记忆系统 ID
```

---

## 6. 配置变更

### 6.1 新增配置项

```python
# configs/memory/memory_config.py (新增)
class MemoryConfig(BaseModel):
    # 工作记忆配置
    working_memory_ttl: int = 3600  # 1小时
    working_memory_max_size: int = 100

    # 记忆整合配置
    consolidation_threshold: float = 0.5
    consolidation_interval: int = 300  # 5分钟

    # 遗忘配置
    forget_threshold: float = 0.1
    forget_check_interval: int = 86400  # 1天

    # 检索配置
    retrieval_top_k: int = 20
    retrieval_rerank_top_k: int = 10
    retrieval_score_threshold: float = 0.3

    # 范围层级配置
    default_scope: str = "personal"
    scope_hierarchy: list[str] = ["personal", "work", "project", "module"]

    # 图存储配置
    enable_graph: bool = True
    graph_backend: str = "neo4j"  # neo4j | postgres_age | embedded
```

### 6.2 环境变量

```bash
# .env 新增
MEMORY_ENABLE_GRAPH=true
MEMORY_GRAPH_BACKEND=neo4j
MEMORY_WORKING_TTL=3600
MEMORY_CONSOLIDATION_INTERVAL=300
MEMORY_RETRIEVAL_TOP_K=20
```

---

## 7. 迁移策略

### 7.1 数据迁移

```python
# scripts/migrate_memory.py
async def migrate_agent_memory():
    """迁移现有 AgentMemory 数据到统一系统"""

    # 1. 迁移 Redis 短期记忆
    for key in redis.scan_iter("agent_*_memory"):
        data = redis.lrange(key, 0, -1)
        for item in data:
            memory = Memory(
                type=MemoryType.WORKING,
                content=item["content"],
                # ... 转换其他字段
            )
            await unified_manager.store(memory)

    # 2. 迁移 Milvus 长期记忆
    # 使用 Milvus query 遍历现有 collection
    # 转换为新的 Memory 格式

    # 3. 迁移 QA Memory
    # 保持原有数据，添加 unified_id 关联
```

### 7.2 双写过渡

```python
class DualWriteMemoryManager:
    """过渡期双写管理器"""

    def __init__(self, old: AgentMemory, new: UnifiedMemoryManager):
        self.old = old
        self.new = new
        self.dual_write_enabled = True

    async def store(self, memory: Memory):
        # 写入新系统
        memory_id = await self.new.store(memory)

        # 双写到旧系统
        if self.dual_write_enabled:
            message = memory.to_message()
            self.old.add_memory(message)

        return memory_id
```

---

## 8. 测试策略

### 8.1 单元测试

| 组件 | 测试文件 | 覆盖目标 |
|------|----------|----------|
| Memory 数据结构 | `tests/memory/test_types.py` | 序列化/反序列化 |
| WorkingMemory | `tests/memory/test_working.py` | Redis 操作 |
| EpisodicMemory | `tests/memory/test_episodic.py` | Milvus 操作 |
| HybridRetriever | `tests/memory/test_retrieval.py` | RRF 融合逻辑 |

### 8.2 集成测试

| 场景 | 测试文件 | 验证目标 |
|------|----------|----------|
| 端到端存储检索 | `tests/memory/test_e2e.py` | 完整流程 |
| 兼容性适配器 | `tests/memory/test_adapter.py` | 旧接口兼容 |
| 数据迁移 | `tests/memory/test_migration.py` | 迁移脚本 |

---

## 9. 回滚计划

如果新系统出现问题，可通过以下步骤回滚：

1. **关闭 feature flag**: `MEMORY_USE_UNIFIED=false`
2. **切换到旧实现**: AgentManager 自动使用旧 AgentMemory
3. **验证功能**: 运行回归测试
4. **数据同步**: 如有需要，从新系统同步增量数据到旧系统

---

## 10. 时间线

| 阶段 | 内容 | Sprint |
|------|------|--------|
| Phase 1 | 核心数据结构 + 存储适配器 | Sprint 1 |
| Phase 2 | 记忆类型实现 + 图层 | Sprint 2 |
| Phase 3 | 检索引擎 + 生命周期 | Sprint 3-4 |
| Phase 4 | 决策记忆 | Sprint 5 |
| Phase 5 | 集成测试 + 迁移 | Sprint 6 |
| Phase 6 | 高级应用 | Sprint 7-9 |
