# Neo4j 数据模型设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 存储分层原则

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     统一记忆存储分层                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                         Neo4j 存储                                │ │
│  │                     (关系图谱 - 轻量索引)                          │ │
│  │                                                                   │ │
│  │  ✅ 适合存储:                                                     │ │
│  │  • 实体节点 (Entity) - 人、概念、项目、技术                        │ │
│  │  • 关系边 (Relation) - 实体间的关联                               │ │
│  │  • 记忆引用节点 (MemoryRef) - 轻量指针，非完整内容                 │ │
│  │  • 分类层级 (Taxonomy) - 项目/模块/主题树                         │ │
│  │                                                                   │ │
│  │  ❌ 不适合存储:                                                   │ │
│  │  • 记忆完整内容 (content) → Milvus/PostgreSQL                     │ │
│  │  • 向量 (embedding) → Milvus                                      │ │
│  │  • 临时/高频数据 → Redis                                          │ │
│  │  • 大文本/文档 → PostgreSQL                                       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              │ memory_id 关联                           │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                        Milvus 存储                                │ │
│  │                    (向量 + 元数据)                                 │ │
│  │  • embedding 向量                                                 │ │
│  │  • content 文本 (用于检索展示)                                    │ │
│  │  • 基础 metadata (level, attention, tags)                        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      PostgreSQL 存储                              │ │
│  │                    (完整记录 + 事件)                               │ │
│  │  • Memory 完整记录 (所有字段)                                     │ │
│  │  • AttentionEvent 信号事件                                        │ │
│  │  • 用户配置、标签定义                                             │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                        Redis 存储                                 │ │
│  │                    (缓存 + 临时)                                   │ │
│  │  • 工作记忆 (会话级)                                              │ │
│  │  • 热点缓存                                                       │ │
│  │  • 倒排索引                                                       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Neo4j 节点类型

### 2.1 节点模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Neo4j Node Types                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  (1) MemoryRef - 记忆引用节点 (轻量)                                    │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :MemoryRef {                                        │               │
│  │   id: "mem_001",           // 记忆ID (主键)         │               │
│  │   type: "semantic",        // working/episodic/semantic             │
│  │   level: "L3",             // 记忆等级              │               │
│  │   summary: "向量检索实现",  // 简短摘要 (<100字)    │               │
│  │   created_at: datetime,                             │               │
│  │   attention_score: 0.85                             │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│  注意: 不存 content/embedding，仅存引用                                │
│                                                                         │
│  (2) Entity - 实体节点                                                  │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :Entity {                                           │               │
│  │   id: "ent_001",                                    │               │
│  │   name: "Milvus",          // 实体名称              │               │
│  │   type: "technology",      // person/concept/tech/project/event    │
│  │   aliases: ["向量数据库"], // 别名                  │               │
│  │   description: "...",      // 简短描述              │               │
│  │   importance: 0.9                                   │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  (3) User - 用户节点                                                    │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :User {                                             │               │
│  │   id: "user_123",                                   │               │
│  │   name: "张三"                                      │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  (4) Project - 项目节点                                                 │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :Project {                                          │               │
│  │   id: "proj_llm",                                   │               │
│  │   name: "llm-platform",                             │               │
│  │   description: "LLM 平台项目"                       │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  (5) Module - 模块节点                                                  │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :Module {                                           │               │
│  │   id: "mod_memory",                                 │               │
│  │   name: "runtime/memory",                           │               │
│  │   path: "runtime/memory"                            │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  (6) Topic - 主题节点                                                   │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :Topic {                                            │               │
│  │   id: "topic_retrieval",                            │               │
│  │   name: "检索优化",                                 │               │
│  │   category: "optimization"                          │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  (7) Session - 会话节点                                                 │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ :Session {                                          │               │
│  │   id: "sess_abc123",                                │               │
│  │   started_at: datetime,                             │               │
│  │   ended_at: datetime                                │               │
│  │ }                                                   │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 关系类型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Neo4j Relationship Types                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  记忆-实体关系                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│  (MemoryRef)-[:MENTIONS {weight, position}]->(Entity)                  │
│  // 记忆提及某实体                                                      │
│                                                                         │
│  (MemoryRef)-[:ABOUT]->(Topic)                                         │
│  // 记忆关于某主题                                                      │
│                                                                         │
│  (MemoryRef)-[:BELONGS_TO]->(Project)                                  │
│  // 记忆属于某项目                                                      │
│                                                                         │
│  (MemoryRef)-[:IN_MODULE]->(Module)                                    │
│  // 记忆涉及某模块                                                      │
│                                                                         │
│  记忆-记忆关系                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│  (MemoryRef)-[:SIMILAR_TO {score}]->(MemoryRef)                        │
│  // 语义相似 (预计算)                                                   │
│                                                                         │
│  (MemoryRef)-[:FOLLOWS]->(MemoryRef)                                   │
│  // 时序跟随 (同会话)                                                   │
│                                                                         │
│  (MemoryRef)-[:REFERENCES]->(MemoryRef)                                │
│  // 引用关系                                                            │
│                                                                         │
│  (MemoryRef)-[:SUPERSEDES]->(MemoryRef)                                │
│  // 替代/更新关系                                                       │
│                                                                         │
│  实体-实体关系                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│  (Entity)-[:RELATED_TO {type, weight}]->(Entity)                       │
│  // 通用关联                                                            │
│                                                                         │
│  (Entity)-[:IS_A]->(Entity)                                            │
│  // 类型关系 (Milvus IS_A 向量数据库)                                   │
│                                                                         │
│  (Entity)-[:PART_OF]->(Entity)                                         │
│  // 组成关系                                                            │
│                                                                         │
│  (Entity)-[:DEPENDS_ON]->(Entity)                                      │
│  // 依赖关系                                                            │
│                                                                         │
│  用户关系                                                               │
│  ─────────────────────────────────────────────────────────────────────  │
│  (User)-[:CREATED]->(MemoryRef)                                        │
│  // 用户创建记忆                                                        │
│                                                                         │
│  (User)-[:INTERESTED_IN {weight}]->(Entity)                            │
│  // 用户关注实体                                                        │
│                                                                         │
│  (User)-[:WORKS_ON]->(Project)                                         │
│  // 用户参与项目                                                        │
│                                                                         │
│  (User)-[:PREFERS {value}]->(Setting)                                  │
│  // 用户偏好                                                            │
│                                                                         │
│  分类层级                                                               │
│  ─────────────────────────────────────────────────────────────────────  │
│  (Project)-[:CONTAINS]->(Module)                                       │
│  (Module)-[:CONTAINS]->(Module)   // 子模块                            │
│  (Topic)-[:SUBTOPIC_OF]->(Topic)                                       │
│                                                                         │
│  会话关系                                                               │
│  ─────────────────────────────────────────────────────────────────────  │
│  (Session)-[:CONTAINS]->(MemoryRef)                                    │
│  (Session)-[:BY]->(User)                                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 完整图模型示例

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Graph Model Example                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                              (User:张三)                                │
│                                  │                                      │
│                 ┌────────────────┼────────────────┐                    │
│            [WORKS_ON]      [INTERESTED_IN]   [CREATED]                 │
│                 │                │                │                    │
│                 ▼                ▼                ▼                    │
│          (Project:llm)    (Entity:向量检索)  (MemoryRef:mem_001)       │
│                 │                │           "如何实现向量检索"         │
│            [CONTAINS]       [RELATED_TO]          │                    │
│                 │                │                │                    │
│                 ▼                ▼                │                    │
│          (Module:memory)  (Entity:Milvus)        │                    │
│                 │                ▲                │                    │
│            [IN_MODULE]      [MENTIONS]      [ABOUT]                    │
│                 │                │                │                    │
│                 └────────────────┴────────────────┘                    │
│                                  │                                      │
│                                  ▼                                      │
│                         (Topic:检索优化)                                │
│                                  │                                      │
│                           [SUBTOPIC_OF]                                │
│                                  │                                      │
│                                  ▼                                      │
│                         (Topic:性能优化)                                │
│                                                                         │
│  ────────────────────────────────────────────────────────────────────  │
│                                                                         │
│         (MemoryRef:mem_001)                                            │
│                 │                                                       │
│       [SIMILAR_TO:0.85]                                                │
│                 │                                                       │
│                 ▼                                                       │
│         (MemoryRef:mem_089)──[MENTIONS]──▶(Entity:Milvus)              │
│         "Milvus 性能优化"                                               │
│                 │                                                       │
│            [FOLLOWS]  (同会话内)                                        │
│                 │                                                       │
│                 ▼                                                       │
│         (MemoryRef:mem_090)                                            │
│         "索引参数调优"                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 数据量估算

### 4.1 节点数量

| 节点类型 | 估算数量 | 平均大小 | 说明 |
|----------|----------|----------|------|
| MemoryRef | 100万 | ~200B | 仅存引用，不存内容 |
| Entity | 10万 | ~300B | 实体去重后 |
| User | 1000 | ~100B | 活跃用户 |
| Project | 100 | ~150B | 项目数 |
| Module | 1000 | ~100B | 模块数 |
| Topic | 500 | ~150B | 主题数 |
| Session | 10万 | ~100B | 会话数 |

### 4.2 关系数量

| 关系类型 | 估算数量 | 说明 |
|----------|----------|------|
| MENTIONS | 500万 | 每记忆平均 5 个实体 |
| SIMILAR_TO | 200万 | 预计算 top-k 相似 |
| FOLLOWS | 50万 | 会话内时序 |
| BELONGS_TO | 100万 | 每记忆 1 项目 |
| INTERESTED_IN | 5万 | 用户兴趣 |

### 4.3 存储估算

```
节点: ~100万 × 200B = ~200MB
关系: ~800万 × 100B = ~800MB
索引: ~500MB
────────────────────────────
总计: ~1.5GB (可控)
```

---

## 5. 典型查询场景

### 5.1 用户兴趣扩展

```cypher
// 找到用户关注的实体，及相关记忆
MATCH (u:User {id: $user_id})-[:INTERESTED_IN]->(e:Entity)
      <-[:MENTIONS]-(m:MemoryRef)
WHERE m.level IN ['L3', 'L4']
RETURN m.id, m.summary, e.name
ORDER BY m.attention_score DESC
LIMIT 20
```

### 5.2 上下文扩展

```cypher
// 从当前记忆扩展相关记忆
MATCH (current:MemoryRef {id: $memory_id})
      -[:MENTIONS]->(e:Entity)
      <-[:MENTIONS]-(related:MemoryRef)
WHERE related.id <> current.id
WITH related, count(e) as shared_entities
ORDER BY shared_entities DESC
LIMIT 10
RETURN related.id, related.summary, shared_entities
```

### 5.3 项目知识图谱

```cypher
// 获取项目下的知识结构
MATCH (p:Project {id: $project_id})-[:CONTAINS]->(mod:Module)
      <-[:IN_MODULE]-(m:MemoryRef)-[:ABOUT]->(t:Topic)
RETURN mod.name, collect(DISTINCT t.name) as topics,
       count(m) as memory_count
ORDER BY memory_count DESC
```

### 5.4 实体关系链

```cypher
// 找到两个实体间的关系路径
MATCH path = shortestPath(
  (e1:Entity {name: $entity1})-[*..4]-(e2:Entity {name: $entity2})
)
RETURN path
```

### 5.5 相似记忆聚类

```cypher
// 获取记忆的相似簇
MATCH (m:MemoryRef {id: $memory_id})
      -[:SIMILAR_TO*1..2]-(similar:MemoryRef)
RETURN DISTINCT similar.id, similar.summary
LIMIT 20
```

---

## 6. 数据同步策略

### 6.1 写入时机

```python
class Neo4jSyncService:
    """Neo4j 数据同步服务"""

    async def on_memory_created(self, memory: Memory):
        """记忆创建时同步"""
        # 1. 创建 MemoryRef 节点
        await self.graph.create_node("MemoryRef", {
            "id": memory.id,
            "type": memory.type.value,
            "level": memory.level.value,
            "summary": memory.summary[:100],  # 截断
            "attention_score": memory.attention_score,
            "created_at": memory.created_at.isoformat()
        })

        # 2. 提取并创建实体关系
        entities = await self.extract_entities(memory.content)
        for entity in entities:
            await self._ensure_entity(entity)
            await self.graph.create_relationship(
                memory.id, entity.id, "MENTIONS",
                {"weight": entity.weight}
            )

        # 3. 创建分类关系
        if memory.project:
            await self.graph.create_relationship(
                memory.id, memory.project, "BELONGS_TO", {}
            )

    async def on_memory_updated(self, memory: Memory, changes: dict):
        """记忆更新时同步"""
        # 仅同步关键字段变化
        if "level" in changes or "attention_score" in changes:
            await self.graph.query("""
                MATCH (m:MemoryRef {id: $id})
                SET m.level = $level, m.attention_score = $score
            """, {
                "id": memory.id,
                "level": memory.level.value,
                "score": memory.attention_score
            })

    async def on_memory_deleted(self, memory_id: str):
        """记忆删除时同步"""
        await self.graph.query("""
            MATCH (m:MemoryRef {id: $id})
            DETACH DELETE m
        """, {"id": memory_id})
```

### 6.2 批量预计算

```python
class Neo4jPrecompute:
    """预计算任务"""

    async def compute_similar_relations(self, batch_size: int = 1000):
        """预计算相似关系 (每日执行)"""
        # 从 Milvus 获取相似度 top-k
        # 写入 Neo4j SIMILAR_TO 关系
        ...

    async def compute_user_interests(self, user_id: str):
        """计算用户兴趣 (访问时更新)"""
        # 基于用户访问的记忆，统计实体频率
        # 更新 INTERESTED_IN 关系
        ...
```

---

## 7. 不存入 Neo4j 的数据

| 数据 | 原因 | 存储位置 |
|------|------|----------|
| `content` 完整内容 | 文本太大，图查询不需要 | PostgreSQL / Milvus |
| `embedding` 向量 | 高维数据不适合图存储 | Milvus |
| 注意力事件流 | 高频写入，时序数据 | PostgreSQL / Redis |
| 临时工作记忆 | 生命周期短，高频变化 | Redis |
| 用户会话状态 | 临时数据 | Redis |
| 文件附件 | 大对象 | S3 / MinIO |

---

## 8. 总结

### Neo4j 存储内容

| 类别 | 内容 | 用途 |
|------|------|------|
| **记忆引用** | id, type, level, summary | 图遍历入口 |
| **实体** | 人、技术、概念、项目 | 知识连接 |
| **关系** | mentions, similar_to, follows | 关联推理 |
| **分类** | project, module, topic 层级 | 结构化索引 |
| **用户画像** | 兴趣、偏好、项目归属 | 个性化推荐 |

### 不存储内容

| 类别 | 原因 |
|------|------|
| 完整内容/向量 | 数据量大，图不需要 |
| 临时/高频数据 | 不适合图写入 |
| 大对象 | 图数据库不擅长 |

---

是否确认此数据模型设计?
