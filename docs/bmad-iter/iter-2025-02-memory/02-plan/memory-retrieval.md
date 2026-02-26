# 记忆检索架构设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 检索流程总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Memory Retrieval Pipeline                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Query: "如何实现记忆检索"                                                   │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 1: Query Understanding (查询理解)                    ~5ms     │   │
│  │ ├─ 意图识别                                                         │   │
│  │ ├─ 实体提取                                                         │   │
│  │ ├─ 查询扩展 (同义词、上下位词)                                       │   │
│  │ └─ 上下文补充 (会话历史)                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 2: Multi-Path Recall (多路召回)                     ~30ms     │   │
│  │                          并行执行                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │  Vector  │  │ Keyword  │  │  Graph   │  │ Temporal │            │   │
│  │  │  Recall  │  │  Recall  │  │  Recall  │  │  Recall  │            │   │
│  │  │  (ANN)   │  │  (BM25)  │  │ (Cypher) │  │  (Range) │            │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │   │
│  │       │             │             │             │                   │   │
│  │       └─────────────┴──────┬──────┴─────────────┘                   │   │
│  │                            ▼                                        │   │
│  │                    Candidate Pool                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 3: Fusion & Rerank (融合重排)                       ~15ms     │   │
│  │ ├─ 去重合并                                                         │   │
│  │ ├─ 多路得分融合 (RRF / Weighted)                                    │   │
│  │ ├─ Cross-Encoder 重排 (可选)                                        │   │
│  │ └─ 注意力/等级加权                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Phase 4: Post-Processing (后处理)                          ~5ms     │   │
│  │ ├─ 权限过滤                                                         │   │
│  │ ├─ 多样性优化                                                       │   │
│  │ ├─ 上下文组装                                                       │   │
│  │ └─ 记录检索事件 (用于注意力更新)                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     ▼                                                                       │
│  Results: [Memory, Memory, ...]                              Total ~55ms   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 多路召回详解

### 2.1 向量召回 (Vector Recall)

```python
class VectorRecall:
    """向量相似度召回"""

    def __init__(self, milvus_client, embeddings):
        self.milvus = milvus_client
        self.embeddings = embeddings

    async def recall(
        self,
        query: str,
        filters: dict,
        top_k: int = 100
    ) -> list[RecallResult]:
        # 1. Query embedding
        query_vec = await self.embeddings.embed_query(query)

        # 2. ANN search with filters
        results = await self.milvus.search(
            collection="memories",
            data=[query_vec],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            filter=self._build_filter(filters),
            output_fields=["id", "content", "level", "attention_score"]
        )

        return [
            RecallResult(
                memory_id=r.id,
                score=r.distance,
                source="vector"
            )
            for r in results[0]
        ]
```

### 2.2 关键词召回 (Keyword Recall)

```python
class KeywordRecall:
    """BM25 关键词召回"""

    def __init__(self, es_client):
        self.es = es_client

    async def recall(
        self,
        query: str,
        expanded_terms: list[str],  # 扩展词
        filters: dict,
        top_k: int = 50
    ) -> list[RecallResult]:
        # 构建 BM25 查询
        should_clauses = [
            {"match": {"content": {"query": query, "boost": 2.0}}},
            {"match": {"content": {"query": " ".join(expanded_terms), "boost": 1.0}}},
            {"match": {"tags": {"query": query, "boost": 1.5}}},
        ]

        results = await self.es.search(
            index="memories",
            body={
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "filter": self._build_filter(filters)
                    }
                },
                "size": top_k
            }
        )

        return [
            RecallResult(
                memory_id=hit["_id"],
                score=hit["_score"],
                source="keyword"
            )
            for hit in results["hits"]["hits"]
        ]
```

### 2.3 图召回 (Graph Recall) ⭐ 关键加速

```python
class GraphRecall:
    """知识图谱召回 - 关系推理加速"""

    def __init__(self, graph_store):
        self.graph = graph_store

    async def recall(
        self,
        query: str,
        entities: list[str],      # 从query提取的实体
        context_memories: list[str],  # 当前上下文记忆ID
        top_k: int = 30
    ) -> list[RecallResult]:
        results = []

        # 策略1: 实体关联召回
        if entities:
            entity_results = await self._recall_by_entities(entities, top_k)
            results.extend(entity_results)

        # 策略2: 上下文扩展召回 (从当前记忆出发)
        if context_memories:
            context_results = await self._recall_by_context(context_memories, top_k)
            results.extend(context_results)

        return results

    async def _recall_by_entities(
        self,
        entities: list[str],
        top_k: int
    ) -> list[RecallResult]:
        """通过实体关系召回相关记忆"""

        # Cypher 查询: 找到与实体相关的记忆
        cypher = """
        MATCH (e:Entity)-[r]->(m:Memory)
        WHERE e.name IN $entities
        WITH m, count(r) as rel_count, collect(type(r)) as relations
        ORDER BY rel_count DESC
        LIMIT $top_k
        RETURN m.id as memory_id,
               rel_count * 0.1 as score,
               relations
        """

        results = await self.graph.query(cypher, {
            "entities": entities,
            "top_k": top_k
        })

        return [
            RecallResult(
                memory_id=r["memory_id"],
                score=r["score"],
                source="graph_entity",
                metadata={"relations": r["relations"]}
            )
            for r in results
        ]

    async def _recall_by_context(
        self,
        context_memories: list[str],
        top_k: int
    ) -> list[RecallResult]:
        """从上下文记忆扩展召回相关记忆"""

        # 多跳查询: 从当前记忆出发，找关联记忆
        cypher = """
        MATCH (start:Memory)-[r*1..2]-(related:Memory)
        WHERE start.id IN $context_ids
          AND NOT related.id IN $context_ids
        WITH related,
             min(length(r)) as hops,
             count(*) as paths
        ORDER BY hops ASC, paths DESC
        LIMIT $top_k
        RETURN related.id as memory_id,
               (1.0 / hops) * 0.5 + (paths * 0.1) as score
        """

        results = await self.graph.query(cypher, {
            "context_ids": context_memories,
            "top_k": top_k
        })

        return [
            RecallResult(
                memory_id=r["memory_id"],
                score=r["score"],
                source="graph_context"
            )
            for r in results
        ]
```

### 2.4 时序召回 (Temporal Recall)

```python
class TemporalRecall:
    """时序召回 - 基于时间关联"""

    async def recall(
        self,
        time_range: tuple[datetime, datetime],
        current_time: datetime,
        top_k: int = 20
    ) -> list[RecallResult]:
        # 召回时间窗口内的记忆
        # 越近的记忆得分越高
        ...
```

---

## 3. 图加速技术

### 3.1 预计算图索引

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Graph Acceleration Techniques                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  技术1: 实体-记忆倒排索引 (预计算)                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ entity_memory_index (Redis Hash)                                │   │
│  │                                                                  │   │
│  │ "entity:python" → ["mem_001", "mem_015", "mem_089", ...]       │   │
│  │ "entity:fastapi" → ["mem_002", "mem_015", "mem_042", ...]      │   │
│  │ "entity:milvus" → ["mem_003", "mem_089", ...]                  │   │
│  │                                                                  │   │
│  │ 优势: O(1) 查找实体相关记忆，无需图遍历                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  技术2: 记忆邻居缓存 (预计算 + TTL)                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ memory_neighbors_cache (Redis Sorted Set)                       │   │
│  │                                                                  │   │
│  │ "neighbors:mem_001" → {                                         │   │
│  │   "mem_015": 0.95,  # 1跳邻居，高相关                            │   │
│  │   "mem_089": 0.82,  # 1跳邻居                                   │   │
│  │   "mem_042": 0.65,  # 2跳邻居                                   │   │
│  │ }                                                                │   │
│  │                                                                  │   │
│  │ 优势: 跳过实时图遍历，直接获取相关记忆                            │   │
│  │ 更新: 记忆新增/修改时异步更新缓存                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  技术3: 高频路径物化 (定期批量计算)                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ hot_paths (PostgreSQL 表)                                       │   │
│  │                                                                  │   │
│  │ source_id  │ target_id │ path_type   │ strength │ updated_at   │   │
│  │ ───────────┼───────────┼─────────────┼──────────┼───────────── │   │
│  │ mem_001    │ mem_015   │ co_entity   │ 0.95     │ 2025-02-24   │   │
│  │ mem_001    │ mem_089   │ same_topic  │ 0.82     │ 2025-02-24   │   │
│  │                                                                  │   │
│  │ 优势: 复杂图关系预计算，查询时直接JOIN                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 图索引实现

```python
class GraphIndexer:
    """图索引预计算服务"""

    def __init__(self, redis, graph_store):
        self.redis = redis
        self.graph = graph_store

    async def build_entity_index(self, memory: Memory):
        """构建实体倒排索引"""
        entities = await self._extract_entities(memory.content)

        pipe = self.redis.pipeline()
        for entity in entities:
            # 添加到实体倒排索引
            pipe.sadd(f"entity:{entity.lower()}:memories", memory.id)
            # 记录记忆关联的实体
            pipe.sadd(f"memory:{memory.id}:entities", entity.lower())
        await pipe.execute()

    async def build_neighbor_cache(self, memory_id: str):
        """构建邻居缓存"""
        # 查询1-2跳邻居
        cypher = """
        MATCH (m:Memory {id: $memory_id})-[r*1..2]-(neighbor:Memory)
        WHERE neighbor.id <> $memory_id
        WITH neighbor,
             min(length(r)) as hops,
             count(*) as paths
        RETURN neighbor.id as neighbor_id,
               (1.0 / hops) * paths * 0.1 as score
        ORDER BY score DESC
        LIMIT 50
        """

        neighbors = await self.graph.query(cypher, {"memory_id": memory_id})

        if neighbors:
            # 存入 Sorted Set
            await self.redis.zadd(
                f"neighbors:{memory_id}",
                {n["neighbor_id"]: n["score"] for n in neighbors}
            )
            # 设置 TTL (1天后过期重建)
            await self.redis.expire(f"neighbors:{memory_id}", 86400)

    async def get_neighbors_fast(
        self,
        memory_ids: list[str],
        top_k: int = 20
    ) -> list[str]:
        """快速获取邻居 (从缓存)"""
        all_neighbors = {}

        for memory_id in memory_ids:
            cache_key = f"neighbors:{memory_id}"

            # 尝试从缓存获取
            cached = await self.redis.zrevrange(cache_key, 0, top_k, withscores=True)

            if cached:
                for neighbor_id, score in cached:
                    if neighbor_id not in memory_ids:  # 排除输入自身
                        current = all_neighbors.get(neighbor_id, 0)
                        all_neighbors[neighbor_id] = max(current, score)
            else:
                # 缓存未命中，触发异步构建
                asyncio.create_task(self.build_neighbor_cache(memory_id))

        # 按得分排序返回
        sorted_neighbors = sorted(all_neighbors.items(), key=lambda x: -x[1])
        return [n[0] for n in sorted_neighbors[:top_k]]
```

---

## 4. 其他加速技术

### 4.1 多级缓存架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Multi-Level Cache Architecture                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Level 1: Query Cache (查询缓存)                      TTL: 5min        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 完全相同的查询 → 直接返回结果                                     │   │
│  │ Key: hash(query + filters + user_id)                            │   │
│  │ 命中率: ~15-20% (重复问题)                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓ miss                                     │
│  Level 2: Embedding Cache (向量缓存)                  TTL: 1hour       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 相同文本的 embedding → 跳过重复计算                               │   │
│  │ Key: hash(text)                                                  │   │
│  │ 节省: ~80ms per embedding call                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓ miss                                     │
│  Level 3: Hot Memory Cache (热点记忆缓存)            TTL: 30min        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 高频访问的记忆完整数据 → 跳过数据库查询                           │   │
│  │ 基于 LRU + 访问频率                                              │   │
│  │ 容量: Top 10000 memories                                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓ miss                                     │
│  Level 4: Index Layer (索引层)                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Milvus (向量) + Elasticsearch (关键词) + Graph Index (图)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  Level 5: Storage Layer (存储层)                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ PostgreSQL (元数据) + Milvus (向量) + Neo4j (图)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 缓存实现

```python
class RetrievalCache:
    """检索缓存服务"""

    def __init__(self, redis):
        self.redis = redis

    async def get_or_compute_embedding(
        self,
        text: str,
        embedder: Callable
    ) -> list[float]:
        """带缓存的 embedding 计算"""
        cache_key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"

        # 尝试获取缓存
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # 计算 embedding
        embedding = await embedder(text)

        # 存入缓存 (1小时)
        await self.redis.setex(cache_key, 3600, json.dumps(embedding))

        return embedding

    async def get_or_search(
        self,
        query: str,
        filters: dict,
        searcher: Callable
    ) -> list[Memory]:
        """带缓存的查询"""
        cache_key = self._build_query_key(query, filters)

        # 尝试获取缓存
        cached = await self.redis.get(cache_key)
        if cached:
            memory_ids = json.loads(cached)
            return await self._batch_get_memories(memory_ids)

        # 执行搜索
        results = await searcher(query, filters)

        # 存入缓存 (5分钟)
        memory_ids = [m.id for m in results]
        await self.redis.setex(cache_key, 300, json.dumps(memory_ids))

        return results
```

### 4.3 并行召回优化

```python
class ParallelRetriever:
    """并行多路召回"""

    async def retrieve(
        self,
        query: str,
        context: RetrievalContext
    ) -> list[Memory]:
        # 并行执行所有召回路径
        tasks = [
            self.vector_recall.recall(query, context.filters),
            self.keyword_recall.recall(query, context.expanded_terms, context.filters),
            self.graph_recall.recall(query, context.entities, context.context_memories),
            self.temporal_recall.recall(context.time_range, context.current_time),
        ]

        # 等待所有完成 (带超时)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        all_candidates = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Recall path {i} failed: {result}")
                continue
            all_candidates.extend(result)

        return all_candidates
```

---

## 5. 融合重排策略

### 5.1 RRF (Reciprocal Rank Fusion)

```python
class RRFFusion:
    """倒数排名融合"""

    K = 60  # RRF 常数

    def fuse(self, recall_results: dict[str, list[RecallResult]]) -> list[FusedResult]:
        """
        recall_results: {
            "vector": [RecallResult, ...],
            "keyword": [RecallResult, ...],
            "graph": [RecallResult, ...],
        }
        """
        scores = defaultdict(float)
        sources = defaultdict(set)

        for source, results in recall_results.items():
            for rank, result in enumerate(results, 1):
                # RRF 公式: 1 / (K + rank)
                scores[result.memory_id] += 1 / (self.K + rank)
                sources[result.memory_id].add(source)

        # 多路命中加权 (同时被多路召回的记忆更相关)
        for memory_id in scores:
            source_count = len(sources[memory_id])
            if source_count >= 2:
                scores[memory_id] *= (1 + 0.1 * source_count)

        # 排序
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])

        return [
            FusedResult(
                memory_id=memory_id,
                score=score,
                sources=list(sources[memory_id])
            )
            for memory_id, score in sorted_items
        ]
```

### 5.2 注意力加权重排

```python
class AttentionWeightedReranker:
    """注意力加权重排"""

    LEVEL_WEIGHTS = {
        MemoryLevel.L4_CORE: 1.5,
        MemoryLevel.L3_LONG: 1.3,
        MemoryLevel.L2_SHORT: 1.1,
        MemoryLevel.L1_WORKING: 1.0,
        MemoryLevel.L0_TRANSIENT: 0.8,
    }

    async def rerank(
        self,
        fused_results: list[FusedResult],
        memories: dict[str, Memory]
    ) -> list[RankedMemory]:
        ranked = []

        for result in fused_results:
            memory = memories[result.memory_id]

            # 基础分
            base_score = result.score

            # 等级加权
            level_weight = self.LEVEL_WEIGHTS.get(memory.level, 1.0)

            # 注意力加权
            attention_weight = 1 + (memory.attention_score * 0.3)  # 最多+30%

            # 新鲜度加权
            freshness = self._compute_freshness(memory.updated_at)

            # 最终分数
            final_score = base_score * level_weight * attention_weight * freshness

            ranked.append(RankedMemory(
                memory=memory,
                score=final_score,
                sources=result.sources
            ))

        # 排序
        ranked.sort(key=lambda x: -x.score)

        return ranked
```

---

## 6. 加速效果对比

### 6.1 延迟分析

| 阶段 | 无优化 | 有优化 | 加速比 |
|------|--------|--------|--------|
| Query Understanding | 10ms | 5ms | 2x |
| Vector Recall | 50ms | 30ms | 1.7x |
| Keyword Recall | 30ms | 20ms | 1.5x |
| **Graph Recall** | **200ms** | **15ms** | **13x** |
| Fusion & Rerank | 20ms | 10ms | 2x |
| Post-Processing | 10ms | 5ms | 2x |
| **Total** | **320ms** | **55ms** | **5.8x** |

### 6.2 图加速关键技术

| 技术 | 效果 | 适用场景 |
|------|------|----------|
| 实体倒排索引 | 100x | 实体相关查询 |
| 邻居缓存 | 50x | 上下文扩展 |
| 热路径物化 | 20x | 高频关系查询 |
| 批量查询 | 5x | 多记忆关联 |

---

## 7. 完整检索服务

```python
class UnifiedMemoryRetriever:
    """统一记忆检索服务"""

    def __init__(
        self,
        vector_recall: VectorRecall,
        keyword_recall: KeywordRecall,
        graph_recall: GraphRecall,
        temporal_recall: TemporalRecall,
        cache: RetrievalCache,
        reranker: AttentionWeightedReranker,
        graph_indexer: GraphIndexer,
    ):
        self.vector_recall = vector_recall
        self.keyword_recall = keyword_recall
        self.graph_recall = graph_recall
        self.temporal_recall = temporal_recall
        self.cache = cache
        self.reranker = reranker
        self.graph_indexer = graph_indexer

    async def retrieve(
        self,
        query: str,
        user_id: str,
        context: Optional[RetrievalContext] = None,
        top_k: int = 10
    ) -> list[RankedMemory]:
        start_time = time.time()

        # Phase 1: Query Understanding
        query_info = await self._understand_query(query, context)

        # Phase 2: Multi-Path Recall (并行)
        recall_results = await self._parallel_recall(query, query_info)

        # Phase 3: Fusion
        fused = self.fusion.fuse(recall_results)

        # 获取完整记忆数据
        memory_ids = [f.memory_id for f in fused[:top_k * 2]]
        memories = await self._batch_get_memories(memory_ids)

        # Phase 4: Rerank
        ranked = await self.reranker.rerank(fused, memories)

        # Phase 5: Post-Processing
        results = self._post_process(ranked, user_id, top_k)

        # 记录检索事件 (用于注意力更新)
        asyncio.create_task(self._record_retrieval_event(
            query=query,
            results=[r.memory.id for r in results],
            latency_ms=(time.time() - start_time) * 1000
        ))

        return results

    async def _parallel_recall(
        self,
        query: str,
        query_info: QueryInfo
    ) -> dict[str, list[RecallResult]]:
        """并行多路召回"""

        # 图召回使用预计算索引加速
        graph_task = self._accelerated_graph_recall(query_info)

        tasks = {
            "vector": self.vector_recall.recall(query, query_info.filters),
            "keyword": self.keyword_recall.recall(query, query_info.expanded_terms, query_info.filters),
            "graph": graph_task,
        }

        if query_info.time_range:
            tasks["temporal"] = self.temporal_recall.recall(query_info.time_range)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {
            name: result if not isinstance(result, Exception) else []
            for name, result in zip(tasks.keys(), results)
        }

    async def _accelerated_graph_recall(
        self,
        query_info: QueryInfo
    ) -> list[RecallResult]:
        """加速图召回 (使用预计算索引)"""
        results = []

        # 1. 实体倒排索引查询 (O(1))
        if query_info.entities:
            for entity in query_info.entities:
                memory_ids = await self.cache.redis.smembers(
                    f"entity:{entity.lower()}:memories"
                )
                for mid in memory_ids:
                    results.append(RecallResult(
                        memory_id=mid,
                        score=0.5,
                        source="graph_entity_index"
                    ))

        # 2. 邻居缓存查询 (O(1))
        if query_info.context_memories:
            neighbor_ids = await self.graph_indexer.get_neighbors_fast(
                query_info.context_memories,
                top_k=30
            )
            for nid in neighbor_ids:
                results.append(RecallResult(
                    memory_id=nid,
                    score=0.3,
                    source="graph_neighbor_cache"
                ))

        return results
```

---

## 8. 更新迭代故事

| Story ID | 标题 | 优先级 |
|----------|------|--------|
| **STORY-009** | **实现 HybridRetrievalEngine** | **P0 (提升)** |
| **STORY-009b** | **实现图索引预计算** | **P1 新增** |
| **STORY-009c** | **实现多级缓存** | **P1 新增** |
| **STORY-009d** | **实现 RRF 融合重排** | **P1 新增** |

---

是否确认此设计?
