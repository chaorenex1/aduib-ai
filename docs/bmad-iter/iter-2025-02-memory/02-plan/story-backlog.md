# 统一记忆系统 - 完整迭代故事清单

**迭代ID**: iter-2025-02-memory
**版本**: v3.0
**更新日期**: 2025-02-24
**总故事数**: 57

---

## 故事总览

| Sprint | 主题 | 故事数 | P0 | P1 | P2 | P3 |
|--------|------|--------|----|----|-----|-----|
| Sprint 1 | 基础架构 | 7 | 5 | 2 | 0 | 0 |
| Sprint 2 | 记忆类型 | 6 | 0 | 6 | 0 | 0 |
| Sprint 3 | 检索系统 | 5 | 1 | 4 | 0 | 0 |
| Sprint 4 | 生命周期 | 5 | 0 | 3 | 2 | 0 |
| Sprint 5 | 决策记忆 | 8 | 2 | 4 | 2 | 0 |
| Sprint 6 | 集成测试 | 4 | 0 | 0 | 4 | 0 |
| Sprint 7 | 记忆应用 | 12 | 1 | 6 | 3 | 2 |
| Sprint 8 | 高级应用 | 7 | 0 | 0 | 6 | 1 |
| Sprint 9 | 扩展功能 | 3 | 0 | 0 | 1 | 2 |
| **合计** | | **57** | **9** | **25** | **18** | **5** |

---

## Sprint 1: 基础架构 (P0-P1)

### STORY-001: 定义核心数据结构
**优先级**: P0 | **工作量**: M | **依赖**: 无

**描述**: 定义统一记忆系统的核心数据结构

**交付物**:
- `Memory` dataclass (id, type, content, embedding, metadata)
- `MemoryType` 枚举 (WORKING, EPISODIC, SEMANTIC)
- `Entity` 和 `Relation` dataclass
- `MemoryScope` 嵌套路径结构
- `MemoryLevel` 等级枚举 (L0-L4)

**文件**:
```
runtime/memory/types/base.py
runtime/memory/types/__init__.py
runtime/memory/__init__.py
```

---

### STORY-001b: 实现 MemoryClassifier
**优先级**: P0 | **工作量**: L | **依赖**: STORY-001

**描述**: 实现记忆自动分类器，支持来源/领域/范围多维度分类

**交付物**:
- `MemoryClassifier` 类
- LLM 分类 prompt
- 分类规则配置
- 自动项目/模块推断

**文件**:
```
runtime/memory/classification/classifier.py
runtime/memory/classification/rules.py
configs/memory/classification.yaml
```

---

### STORY-002: 实现 UnifiedMemoryManager
**优先级**: P0 | **工作量**: L | **依赖**: STORY-001, STORY-001b

**描述**: 实现统一记忆管理器，作为所有记忆操作的入口

**交付物**:
- `store()` 存储记忆
- `retrieve()` 检索记忆
- `update()` 更新记忆
- `forget()` 遗忘记忆
- `search()` 搜索记忆

**文件**:
```
runtime/memory/manager.py
tests/memory/test_manager.py
```

---

### STORY-003: 实现 WorkingMemory
**优先级**: P0 | **工作量**: M | **依赖**: STORY-002

**描述**: 实现工作记忆处理器，使用 Redis 存储当前会话上下文

**交付物**:
- `WorkingMemory` 类
- Redis 存储集成
- TTL 自动过期
- 与现有 `ShortTermRedisMemory` 兼容

**文件**:
```
runtime/memory/types/working.py
tests/memory/test_working.py
```

---

### STORY-004: 实现 UnifiedStorageAdapter
**优先级**: P0 | **工作量**: M | **依赖**: STORY-002

**描述**: 实现统一存储适配器，抽象 Redis/Milvus/Neo4j 存储差异

**交付物**:
- `StorageAdapter` 抽象接口
- `RedisStore` 实现
- `MilvusStore` 实现
- `GraphStore` 实现 (复用现有 Neo4j)

**文件**:
```
runtime/memory/storage/adapter.py
runtime/memory/storage/redis_store.py
runtime/memory/storage/milvus_store.py
runtime/memory/storage/graph_store.py
```

---

### STORY-028: 实现范围层级管理
**优先级**: P1 | **工作量**: M | **依赖**: STORY-001

**描述**: 实现记忆范围层级 (Personal > Work > Project > Module)

**交付物**:
- `MemoryScope` 路径结构
- `ScopeNode` 层级节点
- 范围继承检索
- 范围推断器

**文件**:
```
runtime/memory/scope/hierarchy.py
runtime/memory/scope/inferrer.py
tests/memory/test_scope.py
```

---

### STORY-029: 实现范围感知检索
**优先级**: P1 | **工作量**: M | **依赖**: STORY-028, STORY-002

**描述**: 实现范围感知的检索器，支持向上继承

**交付物**:
- `ScopeAwareRetriever` 类
- `InheritanceMode` 枚举
- 范围过滤器构建
- 范围相关性排序

**文件**:
```
runtime/memory/scope/retriever.py
```

---

## Sprint 2: 记忆类型 (P1)

### STORY-005: 实现 EpisodicMemory
**优先级**: P1 | **工作量**: M | **依赖**: STORY-003

**描述**: 实现情景记忆处理器，支持事件时间线和用户交互历史

**交付物**:
- `EpisodicMemory` 类
- `add_episode()` 方法
- `get_timeline()` 方法
- 时间范围查询
- 会话摘要生成

**文件**:
```
runtime/memory/types/episodic.py
tests/memory/test_episodic.py
```

---

### STORY-006: 实现 SemanticMemory
**优先级**: P1 | **工作量**: M | **依赖**: STORY-003

**描述**: 实现语义记忆处理器，存储知识事实和概念关系

**交付物**:
- `SemanticMemory` 类
- `add_knowledge()` 方法
- `query_knowledge()` 方法
- 向量相似度检索
- 与现有 `LongTermEmbeddingsMemory` 兼容

**文件**:
```
runtime/memory/types/semantic.py
tests/memory/test_semantic.py
```

---

### STORY-007: 实现 KnowledgeGraphLayer
**优先级**: P1 | **工作量**: L | **依赖**: STORY-001, STORY-004

**描述**: 实现知识图谱层，管理实体和关系

**交付物**:
- `KnowledgeGraphLayer` 类
- `add_entity()` / `add_relation()` 方法
- `query_entities()` / `traverse_relations()` 方法
- Neo4j 存储集成
- MemoryRef 轻量节点模型

**文件**:
```
runtime/memory/graph/knowledge_graph.py
runtime/memory/graph/__init__.py
tests/memory/test_knowledge_graph.py
```

---

### STORY-008: 集成现有 GraphMemory
**优先级**: P1 | **工作量**: M | **依赖**: STORY-007

**描述**: 将现有 `LongTermGraphMemory` 的三元组提取逻辑集成到新架构

**交付物**:
- 复用 `TripleCleaner` 逻辑
- 复用 `LLMGenerator.generate_triples()`
- 适配新的 `Entity`/`Relation` 结构
- 标记旧 `graph_memory.py` 为废弃

**文件**:
```
runtime/memory/graph/entity_extractor.py
runtime/memory/graph/relation_builder.py
```

---

### STORY-001c: 分类配置管理
**优先级**: P1 | **工作量**: S | **依赖**: STORY-001b

**描述**: 实现分类配置的管理功能

**交付物**:
- 项目/模块预定义配置
- 候选项目自动学习
- 配置热加载
- 配置管理 API

**文件**:
```
runtime/memory/classification/config.py
controllers/memory/classification.py
```

---

### STORY-001d: 用户自定义标签
**优先级**: P1 | **工作量**: M | **依赖**: STORY-001c

**描述**: 支持用户自定义标签和分类

**交付物**:
- `UserCustomTag` 模型
- 标签 CRUD API
- 记忆-标签关联
- 标签检索过滤

**文件**:
```
models/memory_tags.py
controllers/memory/tags.py
```

---

## Sprint 3: 检索系统 (P0-P1)

### STORY-009: 实现 HybridRetrievalEngine
**优先级**: P0 | **工作量**: L | **依赖**: STORY-006, STORY-007

**描述**: 实现混合检索引擎，支持向量+关键词+图谱多路召回

**交付物**:
- `VectorRecall` 组件
- `KeywordRecall` 组件
- `GraphRecall` 组件
- `TemporalRecall` 组件
- 并行召回框架

**文件**:
```
runtime/memory/retrieval/hybrid_retriever.py
runtime/memory/retrieval/vector_search.py
runtime/memory/retrieval/keyword_search.py
runtime/memory/retrieval/graph_search.py
runtime/memory/retrieval/__init__.py
```

---

### STORY-009b: 实现图索引预计算
**优先级**: P1 | **工作量**: M | **依赖**: STORY-009

**描述**: 实现图索引预计算，加速图检索

**交付物**:
- 实体倒排索引 (Redis)
- 邻居缓存 (Redis Sorted Set)
- 热路径物化
- 索引更新任务

**文件**:
```
runtime/memory/retrieval/graph_indexer.py
runtime/memory/retrieval/precompute.py
```

---

### STORY-009c: 实现多级缓存
**优先级**: P1 | **工作量**: M | **依赖**: STORY-009

**描述**: 实现多级缓存架构，加速检索

**交付物**:
- Query Cache (L1)
- Embedding Cache (L2)
- Hot Memory Cache (L3)
- 缓存失效策略

**文件**:
```
runtime/memory/retrieval/cache.py
```

---

### STORY-009d: 实现 RRF 融合重排
**优先级**: P1 | **工作量**: M | **依赖**: STORY-009

**描述**: 实现 RRF 融合和注意力加权重排

**交付物**:
- `RRFFusion` 类
- `AttentionWeightedReranker` 类
- 多路得分融合
- Cross-Encoder 重排 (可选)

**文件**:
```
runtime/memory/retrieval/fusion.py
runtime/memory/retrieval/reranker.py
```

---

### STORY-030: 实现安全检索策略
**优先级**: P1 | **工作量**: S | **依赖**: STORY-009

**描述**: 实现安全检索策略，控制决策等敏感记忆的检索

**交付物**:
- `SafetyLevel` 枚举
- 范围权限过滤
- 决策确定性过滤

**文件**:
```
runtime/memory/retrieval/safety.py
```

---

## Sprint 4: 生命周期 (P1-P2)

### STORY-010: 实现记忆整合机制
**优先级**: P1 | **工作量**: M | **依赖**: STORY-006

**描述**: 实现短期记忆到长期记忆的转换和整合

**交付物**:
- `Consolidation` 类
- 触发条件定义
- 摘要生成整合
- 实体关系提取

**文件**:
```
runtime/memory/lifecycle/consolidation.py
```

---

### STORY-010b: 实现注意力评分系统
**优先级**: P1 | **工作量**: M | **依赖**: STORY-010

**描述**: 实现注意力信号捕捉和评分

**交付物**:
- `AttentionSignal` 类型定义
- `AttentionScorer` 评分器
- 信号权重配置
- 时间衰减因子

**文件**:
```
runtime/memory/lifecycle/attention.py
```

---

### STORY-010c: 实现记忆升级服务
**优先级**: P1 | **工作量**: M | **依赖**: STORY-010b

**描述**: 实现基于注意力的记忆等级升级

**交付物**:
- `MemoryPromotion` 服务
- 升级规则配置
- 批量升级任务
- 升级事件记录

**文件**:
```
runtime/memory/lifecycle/promotion.py
```

---

### STORY-011: 实现遗忘机制
**优先级**: P2 | **工作量**: M | **依赖**: STORY-010b

**描述**: 实现基于重要性和时间衰减的遗忘机制

**交付物**:
- `Forgetting` 服务
- 遗忘曲线实现
- 遗忘保护
- 归档策略

**文件**:
```
runtime/memory/lifecycle/forgetting.py
runtime/memory/lifecycle/importance.py
```

---

### STORY-011c: 生命周期调度任务
**优先级**: P2 | **工作量**: S | **依赖**: STORY-010c, STORY-011

**描述**: 实现生命周期定时任务调度

**交付物**:
- 每日升级/遗忘任务
- 每周巩固任务
- 每月清理任务
- Celery 任务配置

**文件**:
```
runtime/memory/lifecycle/scheduler.py
runtime/tasks/memory_lifecycle_tasks.py
```

---

## Sprint 5: 决策记忆 (P0-P2)

### STORY-017: 决策数据模型
**优先级**: P1 | **工作量**: M | **依赖**: STORY-001

**描述**: 定义决策记忆的数据模型

**交付物**:
- `Decision` dataclass
- `DecisionStatus` / `DecisionCategory` 枚举
- `Evidence` / `Alternative` 模型
- `DecisionTimeline` 模型

**文件**:
```
runtime/memory/decision/models.py
models/decision.py
```

---

### STORY-022: 决策确定性评估
**优先级**: P0 | **工作量**: M | **依赖**: STORY-017

**描述**: 实现决策确定性评估，防止误识别

**交付物**:
- `DecisionCertainty` 等级枚举
- `CertaintyAssessor` 评估器
- 语言确定性分析
- 多因素评分

**文件**:
```
runtime/memory/decision/certainty.py
```

---

### STORY-023: 决策隔离分层
**优先级**: P0 | **工作量**: M | **依赖**: STORY-022

**描述**: 实现决策分层存储和隔离检索

**交付物**:
- 可信池 / 候选池 / 讨论池 / 隔离区
- `DecisionContextInjector` 注入规则
- 安全检索过滤

**文件**:
```
runtime/memory/decision/isolation.py
```

---

### STORY-018: 决策识别器
**优先级**: P1 | **工作量**: L | **依赖**: STORY-022, STORY-023

**描述**: 实现从记忆内容中识别决策

**交付物**:
- `DecisionRecognizer` 类
- 信号模式匹配
- LLM 决策提取 prompt
- 去重与关联

**文件**:
```
runtime/memory/decision/recognizer.py
```

---

### STORY-024: 用户确认流程
**优先级**: P1 | **工作量**: M | **依赖**: STORY-018

**描述**: 实现低确定性决策的用户确认流程

**交付物**:
- `ConfirmationTrigger` 触发规则
- `ConfirmationRequest` / `ConfirmationOption`
- 确认 API
- 确认超时处理

**文件**:
```
runtime/memory/decision/confirmation.py
controllers/memory/decision_confirm.py
```

---

### STORY-025: 冲突检测与解决
**优先级**: P1 | **工作量**: M | **依赖**: STORY-018

**描述**: 实现决策冲突检测和解决流程

**交付物**:
- `DecisionConflictDetector` 检测器
- LLM 矛盾分析
- 冲突解决 UI 流程
- 解决记录

**文件**:
```
runtime/memory/decision/conflict.py
```

---

### STORY-019: 证据收集与验证
**优先级**: P2 | **工作量**: L | **依赖**: STORY-018

**描述**: 实现决策执行证据的自动收集和验证

**交付物**:
- `EvidenceCollector` 收集器
- Git commit/PR 搜索
- 配置文件变更检测
- `EvidenceValidator` 验证器

**文件**:
```
runtime/memory/decision/evidence.py
```

---

### STORY-026: 决策撤回机制
**优先级**: P2 | **工作量**: S | **依赖**: STORY-023

**描述**: 实现错误决策的撤回和隔离

**交付物**:
- `DecisionRetraction` 服务
- 关联清理
- 撤回事件记录

**文件**:
```
runtime/memory/decision/retraction.py
```

---

## Sprint 6: 集成测试 (P2)

### STORY-012: 重构 QA Memory 集成
**优先级**: P2 | **工作量**: M | **依赖**: STORY-006

**描述**: 将 QA Memory 重构为使用统一记忆架构

**交付物**:
- `QAMemoryService` 使用 `UnifiedMemoryManager`
- 保持现有 API 兼容
- 信任评分机制保留

**文件**:
```
service/qa_memory_service.py (修改)
```

---

### STORY-013: AgentManager 集成
**优先级**: P2 | **工作量**: M | **依赖**: STORY-012

**描述**: 将 AgentManager 的记忆组件替换为新架构

**交付物**:
- `AgentMemory` 使用新架构
- Feature flag 控制
- 渐进式迁移支持

**文件**:
```
runtime/agent/agent_manager.py (修改)
runtime/agent/memory/agent_memory.py (修改)
```

---

### STORY-014: 编写单元测试
**优先级**: P2 | **工作量**: L | **依赖**: STORY-013

**描述**: 为所有核心组件编写单元测试

**交付物**:
- 测试覆盖率 ≥ 80%
- Mock 外部依赖
- 边界条件测试

**文件**:
```
tests/memory/**/*.py
```

---

### STORY-015: 编写集成测试
**优先级**: P2 | **工作量**: M | **依赖**: STORY-014

**描述**: 编写端到端集成测试

**交付物**:
- 完整记忆生命周期测试
- 多记忆类型交互测试
- 决策识别准确性测试

**文件**:
```
tests/memory/test_integration.py
```

---

## 依赖关系图

```
STORY-001 ─┬─▶ STORY-001b ─▶ STORY-002 ─┬─▶ STORY-003 ─▶ STORY-005
           │                            │              └─▶ STORY-006
           │                            │
           ├─▶ STORY-028 ─▶ STORY-029   ├─▶ STORY-004
           │                            │
           └─▶ STORY-017 ─▶ STORY-022 ─▶ STORY-023 ─▶ STORY-018
                                                          │
           STORY-007 ─▶ STORY-008                         │
               │                                          │
               └─────────────▶ STORY-009 ─┬─▶ STORY-009b  │
                                          ├─▶ STORY-009c  │
                                          ├─▶ STORY-009d  │
                                          └─▶ STORY-030   │
                                                          │
           STORY-006 ─▶ STORY-010 ─▶ STORY-010b ─▶ STORY-010c
                                          │              │
                                          └─▶ STORY-011 ─┴─▶ STORY-011c
                                                          │
           STORY-018 ─┬─▶ STORY-024                       │
                      ├─▶ STORY-025                       │
                      └─▶ STORY-019                       │
                                                          │
           STORY-023 ─▶ STORY-026                         │
                                                          │
           STORY-006 ─▶ STORY-012 ─▶ STORY-013 ─▶ STORY-014 ─▶ STORY-015
```

---

## 里程碑

| 里程碑 | Sprint | 完成条件 |
|--------|--------|----------|
| **M1: 基础可用** | Sprint 1-2 | 核心架构 + 三种记忆类型 |
| **M2: 检索完备** | Sprint 3 | 多路召回 + 图加速 |
| **M3: 生命周期** | Sprint 4 | 升级/遗忘机制 |
| **M4: 决策记忆** | Sprint 5 | 决策识别 + 风控 |
| **M5: 生产就绪** | Sprint 6 | 集成测试 + 迁移完成 |

---

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Neo4j 性能不足 | 中 | 高 | 先用 Redis 模拟图索引 |
| 决策误识别率高 | 中 | 高 | 严格的确定性分级 + 用户确认 |
| 迁移影响现有功能 | 低 | 高 | Feature flag + 渐进式迁移 |
| 检索延迟超标 | 低 | 中 | 多级缓存 + 预计算 |

---

## 验收标准

- [ ] UnifiedMemoryManager 实现所有核心接口
- [ ] 三种记忆类型 (Working, Episodic, Semantic) 可独立工作
- [ ] 范围层级 (Personal > Work > Project > Module) 正确继承
- [ ] 知识图谱层支持实体-关系存储和查询
- [ ] 混合检索支持向量+关键词+图谱
- [ ] 决策识别准确率 ≥ 85%，误识别率 < 5%
- [ ] 检索延迟 P99 < 100ms
- [ ] 单元测试覆盖率 ≥ 80%

---

## Sprint 7: 记忆应用 (P0-P3)

### STORY-031: 实现 YearlyRetriever
**优先级**: P2 | **工作量**: M | **依赖**: STORY-009
**来源**: yearly-summary.md

**描述**: 实现年度记忆检索器，支持按季度分片检索

**交付物**:
- `YearlyRetriever` 类
- 按季度分片检索
- 决策记忆检索
- 时间范围过滤

**文件**:
```
runtime/memory/application/yearly_retriever.py
```

---

### STORY-032: 实现 YearlyAggregator
**优先级**: P2 | **工作量**: M | **依赖**: STORY-031
**来源**: yearly-summary.md

**描述**: 实现年度数据聚合器，按范围/领域/月份聚合

**交付物**:
- `YearlyAggregator` 类
- 多维度聚合 (范围/领域/月份/主题)
- `YearlyMetrics` 统计指标
- 实体统计

**文件**:
```
runtime/memory/application/yearly_aggregator.py
```

---

### STORY-033: 实现成就识别器
**优先级**: P2 | **工作量**: M | **依赖**: STORY-032
**来源**: yearly-summary.md

**描述**: 从年度数据中识别成就

**交付物**:
- `AchievementRecognizer` 类
- 项目里程碑识别
- 技能突破识别
- 关键决策影响评估

**文件**:
```
runtime/memory/application/achievement_recognizer.py
```

---

### STORY-034: 实现 LLM 洞察提取
**优先级**: P2 | **工作量**: M | **依赖**: STORY-033
**来源**: yearly-summary.md

**描述**: 使用 LLM 从聚合数据中提取深度洞察

**交付物**:
- `InsightExtractor` 类
- 洞察提取 Prompt
- 趋势分析
- 来年建议生成

**文件**:
```
runtime/memory/application/insight_extractor.py
```

---

### STORY-035: 实现报告生成器
**优先级**: P2 | **工作量**: M | **依赖**: STORY-034
**来源**: yearly-summary.md

**描述**: 生成结构化年终总结报告

**交付物**:
- `ReportGenerator` 类
- Markdown 模板
- JSON 输出
- 多章节组织

**文件**:
```
runtime/memory/application/report_generator.py
controllers/memory/yearly_summary.py
```

---

### STORY-036: 实现可视化数据生成
**优先级**: P3 | **工作量**: M | **依赖**: STORY-035
**来源**: yearly-summary.md

**描述**: 生成可视化图表数据

**交付物**:
- `VisualizationGenerator` 类
- 月度热力图数据
- 技能雷达图数据
- 知识图谱迷你图

**文件**:
```
runtime/memory/application/visualization.py
```

---

### STORY-037: 实现 PDF 导出
**优先级**: P3 | **工作量**: S | **依赖**: STORY-036
**来源**: yearly-summary.md

**描述**: 支持年终总结 PDF 导出

**交付物**:
- PDF 模板
- 图表嵌入
- 样式配置

**文件**:
```
runtime/memory/application/pdf_exporter.py
```

---

### STORY-038: 实现序列模式挖掘算法
**优先级**: P1 | **工作量**: L | **依赖**: STORY-005
**来源**: pattern-to-skill.md

**描述**: 实现 PrefixSpan 序列模式挖掘

**交付物**:
- `SequencePatternMiner` 类
- PrefixSpan 算法实现
- 工作流边界识别
- 频繁序列过滤

**文件**:
```
runtime/memory/pattern/sequence_miner.py
```

---

### STORY-039: 实现决策模式挖掘
**优先级**: P1 | **工作量**: M | **依赖**: STORY-018
**来源**: pattern-to-skill.md

**描述**: 从决策记忆中挖掘决策模式

**交付物**:
- `DecisionPatternMiner` 类
- 决策因素提取
- 决策树构建
- 模式抽象

**文件**:
```
runtime/memory/pattern/decision_miner.py
```

---

### STORY-040: 实现 QA 模式挖掘
**优先级**: P1 | **工作量**: M | **依赖**: STORY-012
**来源**: pattern-to-skill.md

**描述**: 从 QA 记忆中挖掘问答模式

**交付物**:
- `QAPatternMiner` 类
- 问题聚类
- 答案模板提取
- 参数槽位识别

**文件**:
```
runtime/memory/pattern/qa_miner.py
```

---

### STORY-041: 实现模式价值评估器
**优先级**: P1 | **工作量**: M | **依赖**: STORY-038, STORY-039, STORY-040
**来源**: pattern-to-skill.md

**描述**: 评估模式的复用价值

**交付物**:
- `PatternEvaluator` 类
- `PatternMetrics` 指标
- 频率/成功率/通用性评分
- 价值得分计算

**文件**:
```
runtime/memory/pattern/evaluator.py
```

---

### STORY-042: 实现 Skill 生成器
**优先级**: P0 | **工作量**: L | **依赖**: STORY-041
**来源**: pattern-to-skill.md

**描述**: 从高价值模式自动生成 Agent Skill

**交付物**:
- `SkillGenerator` 类
- Skill 模板 (工作流/决策树/QA)
- LLM Skill 生成 Prompt
- 参数定义生成

**文件**:
```
runtime/memory/pattern/skill_generator.py
runtime/memory/pattern/skill_templates.py
```

---

## Sprint 8: 高级应用 (P2-P3)

### STORY-043: 实现 Skill 验证器
**优先级**: P2 | **工作量**: M | **依赖**: STORY-042
**来源**: pattern-to-skill.md

**描述**: 验证生成的 Skill 有效性

**交付物**:
- `SkillValidator` 类
- 测试实例回放
- 相似度评估
- 迭代优化

**文件**:
```
runtime/memory/pattern/skill_validator.py
```

---

### STORY-044: 实现 Skill 注册中心
**优先级**: P2 | **工作量**: M | **依赖**: STORY-043
**来源**: pattern-to-skill.md

**描述**: 实现 Skill 注册和管理

**交付物**:
- `SkillRegistry` 类
- Skill 文件生成
- 索引更新
- 重复检测

**文件**:
```
runtime/memory/pattern/skill_registry.py
controllers/memory/skills.py
```

---

### STORY-045: 实现 Skill 共享服务
**优先级**: P2 | **工作量**: M | **依赖**: STORY-044
**来源**: pattern-to-skill.md

**描述**: 实现 Skill 范围提升和共享

**交付物**:
- `SkillSharingService` 类
- 个人→团队→公共提升
- 质量检查
- 审核流程

**文件**:
```
runtime/memory/pattern/skill_sharing.py
```

---

### STORY-046: 实现模式挖掘定时任务
**优先级**: P2 | **工作量**: S | **依赖**: STORY-041
**来源**: pattern-to-skill.md

**描述**: 定时执行模式挖掘

**交付物**:
- 每周模式挖掘任务
- 新模式通知
- Skill 候选推荐

**文件**:
```
runtime/tasks/pattern_mining_tasks.py
```

---

### STORY-047: 实现角色识别器
**优先级**: P2 | **工作量**: M | **依赖**: STORY-018
**来源**: resume-project-generator.md

**描述**: 从项目记忆中识别用户角色

**交付物**:
- `RoleIdentifier` 类
- 角色信号词匹配
- 决策类型分析
- 角色置信度计算

**文件**:
```
runtime/memory/resume/role_identifier.py
```

---

### STORY-048: 实现贡献提取器
**优先级**: P2 | **工作量**: L | **依赖**: STORY-047
**来源**: resume-project-generator.md

**描述**: 从项目记忆中提取贡献

**交付物**:
- `ContributionExtractor` 类
- 决策贡献提取
- 问题解决提取
- Git 贡献提取

**文件**:
```
runtime/memory/resume/contribution_extractor.py
```

---

### STORY-049: 实现成果量化器
**优先级**: P2 | **工作量**: M | **依赖**: STORY-048
**来源**: resume-project-generator.md

**描述**: 量化贡献成果

**交付物**:
- `MetricsQuantifier` 类
- 显式指标提取
- Git 统计计算
- 隐式指标推断

**文件**:
```
runtime/memory/resume/metrics_quantifier.py
```

---

## Sprint 9: 扩展功能 (P2-P3)

### STORY-050: 实现 STAR 描述生成
**优先级**: P2 | **工作量**: M | **依赖**: STORY-049
**来源**: resume-project-generator.md

**描述**: 生成 STAR 格式简历描述

**交付物**:
- `STARGenerator` 类
- 多种描述风格
- 动词选择
- 技术栈突出

**文件**:
```
runtime/memory/resume/star_generator.py
```

---

### STORY-051: 实现项目经历聚合器
**优先级**: P3 | **工作量**: M | **依赖**: STORY-050
**来源**: resume-project-generator.md

**描述**: 聚合多项目经历

**交付物**:
- `ProjectExperienceAggregator` 类
- 多项目聚合
- 岗位匹配评分
- 亮点标签生成

**文件**:
```
runtime/memory/resume/project_aggregator.py
controllers/memory/resume.py
```

---

### STORY-052: 实现多格式导出
**优先级**: P3 | **工作量**: S | **依赖**: STORY-051
**来源**: resume-project-generator.md

**描述**: 支持简历多格式导出

**交付物**:
- Markdown 格式
- JSON 格式
- DOCX 格式

**文件**:
```
runtime/memory/resume/exporters.py
```

---

## 新增里程碑

| 里程碑 | Sprint | 完成条件 |
|--------|--------|----------|
| **M6: 年终总结** | Sprint 7 | 年终总结报告生成 |
| **M7: 模式学习** | Sprint 7-8 | 自动 Skill 生成 |
| **M8: 简历生成** | Sprint 8-9 | 项目经历自动生成 |

---

## 新增验收标准

- [ ] 年终总结包含成就/成长/建议
- [ ] 模式识别准确率 ≥ 80%
- [ ] Skill 生成验证通过率 ≥ 75%
- [ ] 简历描述包含量化成果
- [ ] 支持 Markdown/JSON/PDF/DOCX 导出
