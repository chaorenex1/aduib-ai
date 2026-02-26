# 统一记忆系统 - 迭代计划

**迭代ID**: iter-2025-02-memory
**版本**: v1.0
**创建日期**: 2025-02-24

---

## 1. 架构设计

### 1.1 系统架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ AgentManager │  │ ChatService  │  │ QAMemory API │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
└─────────┼─────────────────┼─────────────────┼────────────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     UnifiedMemoryManager                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Memory Interface                            │ │
│  │   store(memory) → ID        retrieve(query) → [Memory]            │ │
│  │   update(id, memory)        forget(id)                            │ │
│  │   consolidate()             search(query, filters) → [Memory]      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │              Memory Type Processors                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │  Working    │  │  Episodic   │  │  Semantic   │               │  │
│  │  │  Memory     │  │  Memory     │  │  Memory     │               │  │
│  │  │             │  │             │  │             │               │  │
│  │  │ • 当前对话  │  │ • 事件时间线│  │ • 知识事实  │               │  │
│  │  │ • 任务上下文│  │ • 用户交互  │  │ • 概念关系  │               │  │
│  │  │ • 临时状态  │  │ • 会话摘要  │  │ • QA 知识   │               │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│  └─────────┼────────────────┼────────────────┼───────────────────────┘  │
│            │                │                │                          │
│  ┌─────────┴────────────────┴────────────────┴───────────────────────┐  │
│  │                   Knowledge Graph Layer                           │  │
│  │  ┌──────────────────────────────────────────────────────────────┐ │  │
│  │  │                    Entity-Relation Store                     │ │  │
│  │  │  • Entity nodes (User, Concept, Event, Fact)                 │ │  │
│  │  │  • Relations (HAS, KNOWS, PREFERS, RELATES_TO)               │ │  │
│  │  │  • Temporal links (BEFORE, AFTER, DURING)                    │ │  │
│  │  │  • Inference rules (implied relations)                       │ │  │
│  │  └──────────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                    Hybrid Retrieval Engine                        │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │  │
│  │  │  Vector   │  │  Keyword  │  │   Graph   │  │  Temporal │      │  │
│  │  │  Search   │  │  Search   │  │ Traversal │  │   Range   │      │  │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘      │  │
│  │        └──────────────┴──────────────┴──────────────┘             │  │
│  │                           │ Reranker                              │  │
│  └───────────────────────────┼───────────────────────────────────────┘  │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     Unified Storage Adapter                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │    Redis    │  │   Milvus    │  │   Neo4j     │               │  │
│  │  │  (Working)  │  │  (Vector)   │  │   (Graph)   │               │  │
│  │  │             │  │             │  │  (Optional) │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据结构

```python
# Memory Entity
@dataclass
class Memory:
    id: str                          # UUID
    type: MemoryType                  # WORKING | EPISODIC | SEMANTIC
    content: str                      # 记忆内容
    embedding: Optional[list[float]]  # 向量表示
    metadata: MemoryMetadata          # 元信息
    entities: list[Entity]            # 关联实体
    relations: list[Relation]         # 关联关系
    created_at: datetime
    updated_at: datetime
    accessed_at: datetime
    importance: float                 # 重要性评分 0-1
    decay_rate: float                 # 衰减速率
    ttl: Optional[datetime]           # 过期时间

class MemoryType(Enum):
    WORKING = "working"       # 工作记忆 - 当前上下文
    EPISODIC = "episodic"     # 情景记忆 - 事件时间线
    SEMANTIC = "semantic"     # 语义记忆 - 知识事实

@dataclass
class Entity:
    id: str
    name: str
    type: EntityType          # USER | CONCEPT | EVENT | FACT | PREFERENCE
    properties: dict

@dataclass
class Relation:
    source_id: str
    target_id: str
    type: str                 # HAS, KNOWS, PREFERS, RELATES_TO, etc.
    properties: dict
    weight: float             # 关系强度
```

### 1.3 目录结构

```
runtime/memory/
├── __init__.py
├── manager.py                    # UnifiedMemoryManager
├── types/
│   ├── __init__.py
│   ├── base.py                   # Memory, Entity, Relation
│   ├── working.py                # WorkingMemory
│   ├── episodic.py               # EpisodicMemory
│   └── semantic.py               # SemanticMemory
├── graph/
│   ├── __init__.py
│   ├── knowledge_graph.py        # KnowledgeGraphLayer
│   ├── entity_extractor.py       # 实体提取器
│   └── relation_builder.py       # 关系构建器
├── retrieval/
│   ├── __init__.py
│   ├── hybrid_retriever.py       # HybridRetrievalEngine
│   ├── vector_search.py          # 向量检索
│   ├── keyword_search.py         # 关键词检索
│   └── graph_search.py           # 图检索
├── storage/
│   ├── __init__.py
│   ├── adapter.py                # UnifiedStorageAdapter
│   ├── redis_store.py            # Redis存储
│   ├── milvus_store.py           # Milvus存储
│   └── graph_store.py            # 图存储(可选Neo4j)
└── lifecycle/
    ├── __init__.py
    ├── consolidation.py          # 记忆整合
    ├── forgetting.py             # 遗忘机制
    └── importance.py             # 重要性评估
```

---

## 2. 迭代故事

### Sprint 1: 基础架构 (P0)

| Story ID | 标题 | 描述 | 预估工作量 |
|----------|------|------|------------|
| STORY-001 | 定义核心数据结构 | Memory, Entity, Relation 类型定义 | S |
| STORY-002 | 实现 UnifiedMemoryManager | 统一记忆管理器核心接口 | M |
| STORY-003 | 实现 WorkingMemory | 工作记忆处理器 (Redis) | M |
| STORY-004 | 实现 UnifiedStorageAdapter | 统一存储适配器 | M |

### Sprint 2: 记忆类型扩展 (P1)

| Story ID | 标题 | 描述 | 预估工作量 |
|----------|------|------|------------|
| STORY-005 | 实现 EpisodicMemory | 情景记忆处理器 | M |
| STORY-006 | 实现 SemanticMemory | 语义记忆处理器 | M |
| STORY-007 | 实现 KnowledgeGraphLayer | 知识图谱层 | L |
| STORY-008 | 集成现有 GraphMemory | 重用三元组提取逻辑 | M |

### Sprint 3: 检索与生命周期 (P2)

| Story ID | 标题 | 描述 | 预估工作量 |
|----------|------|------|------------|
| STORY-009 | 实现 HybridRetrievalEngine | 多路召回检索引擎 | L |
| STORY-010 | 实现记忆整合机制 | 短期→长期记忆转换 | M |
| STORY-011 | 实现遗忘机制 | 基于重要性和时间的遗忘 | M |
| STORY-012 | 重构 QA Memory 集成 | 使用统一记忆架构 | M |

### Sprint 4: 集成与测试 (P2)

| Story ID | 标题 | 描述 | 预估工作量 |
|----------|------|------|------------|
| STORY-013 | AgentManager 集成 | 替换现有 AgentMemory | M |
| STORY-014 | 编写单元测试 | 核心组件测试覆盖 | M |
| STORY-015 | 编写集成测试 | 端到端测试 | M |
| STORY-016 | 性能基准测试 | 检索延迟、吞吐量 | S |

---

## 3. 依赖关系

```
STORY-001 ──┬──▶ STORY-002 ──┬──▶ STORY-003 ──▶ STORY-004
            │                │
            │                └──▶ STORY-005
            │                │
            │                └──▶ STORY-006
            │
            └──▶ STORY-007 ──▶ STORY-008
                     │
                     └──────────▶ STORY-009
                                      │
                                      ▼
                              STORY-010 ──▶ STORY-011
                                      │
                                      ▼
                              STORY-012 ──▶ STORY-013
                                      │
                                      ▼
                              STORY-014 ──▶ STORY-015 ──▶ STORY-016
```

---

## 4. 技术决策

### 4.1 存储选择

| 存储 | 用途 | 理由 |
|------|------|------|
| Redis | 工作记忆 | 低延迟、TTL 支持、现有基础设施 |
| Milvus | 向量存储 | 高性能向量检索、现有集成 |
| Neo4j | 图存储 (可选) | 现有 GraphMemory 代码可复用 |

### 4.2 不使用 Neo4j 的备选方案

如果不引入 Neo4j，可在 Milvus 中模拟简单图结构：
- 使用 metadata 存储实体类型和关系
- 使用嵌套查询实现简单的图遍历
- 复杂推理仍需图数据库

### 4.3 API 设计

```python
# 核心接口
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
        entity_filter: list[str] = None,
        time_range: tuple[datetime, datetime] = None,
        limit: int = 10,
    ) -> list[Memory]: ...
```

---

## 5. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 图数据库性能问题 | 中 | 高 | 先用 Milvus metadata 模拟，按需引入 Neo4j |
| 记忆检索延迟高 | 中 | 中 | 并行检索、缓存热点记忆 |
| 迁移现有数据困难 | 低 | 中 | 提供迁移脚本、支持双写过渡期 |
| 存储成本增加 | 低 | 低 | 配置遗忘策略、压缩冷数据 |

---

## 6. 验收标准

- [ ] UnifiedMemoryManager 实现所有核心接口
- [ ] 三种记忆类型 (Working, Episodic, Semantic) 可独立工作
- [ ] 知识图谱层支持实体-关系存储和查询
- [ ] 混合检索支持向量+关键词+图谱
- [ ] AgentManager 成功集成新记忆系统
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 检索延迟 P99 < 100ms

---

## 7. 下一步

执行: `/bmad-iter next` 开始 STORY-001 实现
