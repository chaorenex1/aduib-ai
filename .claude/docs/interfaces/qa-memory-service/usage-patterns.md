# QA Memory Service 使用模式与最佳实践

## 设计模式分析

### 1. 接口命名模式

#### 动词前缀约定
- **检索类**: `retrieve_` (检索记忆库)
- **记录类**: `record_` (记录命中/验证)
- **管理类**: `qa_` + 动作 (创建/验证/详情/过期)
- **详情类**: `detail` (获取单个记录)

#### 命名一致性
- 项目标识: 统一使用 `namespace` 参数名
- 记录标识: 统一使用 `qa_id` 参数名
- 批量参数: 使用 `batch_size` 而非 `limit`

### 2. 参数设计模式

#### 可选参数默认值
```python
# 良好实践：提供合理的默认值
top_k: int = 8
signal_strength: str = "weak"
time_sensitivity: str = "medium"
batch_size: int = 200
```

#### 空值处理模式
```python
# 模式1：转换为空列表
tags = tags or []
evidence_refs = evidence_refs or []

# 模式2：转换为空字典
metadata = metadata or {}
client = client or {}

# 模式3：使用默认值
confidence = max(0.0, min(1.0, confidence))
```

#### 枚举参数模式
```python
# 使用字符串字面量而非枚举类型
time_sensitivity: str = "medium"  # "low"/"medium"/"high"
signal_strength: str = "weak"     # "weak"/"medium"/"strong"
result: str = "pass"              # "pass"/"fail"
```

### 3. 返回值模式

#### 标准化响应结构
```python
# 成功响应模板
{
    "schema_version": 1,
    "results": [...],  # 或 "record": {...}
    "meta": {...}
}

# 错误响应模板
{
    "status": "error_type",
    "qa_id": "...",    # 可选
    "message": "..."   # 可选
}
```

#### 分页模式
当前版本不支持分页，通过 `top_k` 参数限制结果数量。

#### 嵌套对象模式
```python
# 深度嵌套的元数据
"metadata": {
    "scope": {...},
    "stats": {...},
    "score": {...},
    "ttl": {...},
    "client": {...}
}
```

### 4. 异步模式

#### 纯异步接口
所有接口均为 `async def` 定义，无同步版本。

#### 会话管理
- 数据库会话: 使用上下文管理器 (`with get_db() as session`)
- 资源清理: 自动提交/回滚
- 连接泄漏防护: 确保会话正确关闭

### 5. 错误处理模式

#### 静默失败模式
```python
# 模式1：返回空结果而非抛出异常
if not query.strip():
    return []

# 模式2：返回状态标识而非异常
if not record:
    return {"status": "not_found", "qa_id": qa_id}

# 模式3：忽略无效参数使用默认值
normalized = (signal_strength or "weak").lower()
```

#### 验证忽略模式
```python
# 弱失败信号可能被忽略的条件
if strength != "weak" or result != "fail":
    return False
strong_pass = int(stats.get("strong_pass", 0))
strong_fail = int(stats.get("strong_fail", 0))
return strong_pass >= 2 and strong_pass > strong_fail
```

## 最佳实践

### 1. 检索优化实践

#### 查询预处理
```python
# 最佳：去除空白，确保非空
query = query.strip()
if not query:
    return []

# 避免：直接传递原始查询
# matches = search(query)  # 可能导致空结果
```

#### 结果筛选策略
```python
# 优先返回已验证记录
if any(match["validation_level"] > 0 for match in matches):
    matches = [match for match in matches if match["validation_level"] > 0]

# 按综合评分排序
matches.sort(key=lambda item: item["score"], reverse=True)
```

#### 评分权重配置
```python
# 可调整的评分权重
final_score = (
    0.55 * relevance +      # 语义相关度 55%
    0.30 * trust +          # 信任评分 30%
    0.15 * freshness +      # 新鲜度 15%
    level_boost            # 验证级别加成
)
```

### 2. 记录管理实践

#### 批量操作优化
```python
# 使用批量参数提高性能
async def qa_expire(self, batch_size: int = 200)

# 循环处理大量记录
total_expired = 0
while True:
    result = await service.qa_expire(batch_size=200)
    expired = result.get("expired", 0)
    total_expired += expired
    if expired < 200:
        break
```

#### 元数据组织
```python
# 结构化元数据组织
metadata = {
    "scope": {"module": "auth", "version": "v1.0"},
    "time_sensitivity": "medium",
    "evidence_refs": ["doc1.md", "doc2.md"],
    "client": {"user_id": "123", "platform": "web"},
    "stats": {...},  # 验证统计
    "score": {...},  # 评分信息
    "ttl": {...}     # 生命周期信息
}
```

#### 标签使用规范
```python
# 最佳：使用有意义的标签
tags = ["authentication", "password-reset", "user-guide"]

# 避免：过度细化或含义模糊
tags = ["how-to", "tutorial", "guide"]  # 过于通用
tags = ["step1", "step2", "step3"]      # 无实际含义
```

### 3. 验证工作流实践

#### 验证信号强度选择
```python
# 根据验证来源选择信号强度
signal_strength_map = {
    "user_explicit_feedback": "strong",
    "automated_test_passed": "medium",
    "implicit_usage_pattern": "weak",
    "third_party_verification": "medium"
}
```

#### 验证频率控制
```python
# 避免过度验证的规则
# 1. 高级别记录减少验证频率
# 2. 近期已验证的记录降低优先级
# 3. 强成功记录可信任期更长
```

#### 结果解释标准化
```python
# 标准化的验证原因
reason_templates = {
    "pass": {
        "user_confirmed": "用户确认答案正确",
        "test_passed": "自动化测试通过",
        "expert_review": "专家审核通过"
    },
    "fail": {
        "outdated": "信息已过时",
        "incorrect": "答案不正确",
        "incomplete": "信息不完整"
    }
}
```

### 4. 生命周期管理实践

#### TTL 策略配置
```python
# 基础配置（可在子类中覆盖）
BASE_TTL_DAYS = 14          # 候选记录默认生存期
MAX_TTL_DAYS = 180          # 最大生存期
STRONG_PASS_TTL_BONUS_DAYS = 30  # 强成功奖励天数
STRONG_FAIL_MIN_TTL_DAYS = 7     # 强失败最小生存期
```

#### 状态转换规则
```
候选 (candidate)
    ├── 验证通过 → 活跃 (active)
    ├── 连续失败 → 陈旧 (stale) → 废弃 (deprecated)
    └── TTL过期 → 陈旧 (stale)

活跃 (active)
    ├── TTL过期 → 陈旧 (stale)
    ├── 连续失败 → 陈旧 (stale)
    └── 手动冻结 → 冻结 (frozen)

陈旧 (stale)
    ├── 重新验证通过 → 活跃 (active)
    └── TTL过期 → 废弃 (deprecated)
```

#### 清理调度建议
```python
# 推荐清理计划
schedule = {
    "高频": "qa_expire(batch_size=50)",    # 每小时执行
    "中频": "qa_expire(batch_size=200)",   # 每天执行
    "低频": "全面统计与优化",             # 每周执行
}
```

### 5. 性能优化实践

#### 向量索引管理
```python
# 索引更新策略
def _upsert_vector_entry(record, knowledge_base_id):
    # 先删除旧索引
    vector.delete_by_ids([str(record.id)])
    # 再创建新索引
    vector.add_texts([document])

# 批量更新优化
# 可考虑实现批量删除和添加
```

#### 数据库查询优化
```python
# 使用 IN 查询提高效率
rows = session.execute(
    select(QaMemoryRecord).where(
        QaMemoryRecord.id.in_(qa_ids),  # 批量查询
        QaMemoryRecord.status != QaMemoryStatus.DEPRECATED.value
    )
).scalars().all()
```

#### 内存使用优化
```python
# 限制结果集大小
matches.sort(key=lambda item: item["score"], reverse=True)
return matches[:limit]  # 严格限制返回数量

# 及时清理中间数据
qa_ids: set[str] = set()  # 使用集合去重
doc_map = {}              # 映射表避免重复查找
```

### 6. 监控与调试实践

#### 关键指标监控
```python
# 应监控的核心指标
metrics = {
    "search_latency": "检索延迟百分位数",
    "hit_rate": "检索命中率",
    "validation_rate": "验证成功率",
    "expiration_rate": "过期清理速率",
    "memory_usage": "向量索引内存使用",
    "db_connections": "数据库连接池状态"
}
```

#### 日志记录规范
```python
# 结构化日志记录
log_data = {
    "operation": "retrieve_qa_kb",
    "namespace": namespace,
    "query_length": len(query),
    "result_count": len(results),
    "latency_ms": latency,
    "cache_hit": cache_hit
}
logger.info("QA memory operation completed", extra=log_data)
```

#### 调试信息收集
```python
# 在开发环境启用详细日志
if settings.DEBUG:
    logger.debug(f"matches={matches}")
    logger.debug(f"scoring: relevance={relevance}, trust={trust}, freshness={freshness}")
```

## 常见陷阱与解决方案

### 陷阱1：过度频繁的验证

**问题**: 对同一记录进行多次弱信号验证，可能导致信任评分波动。

**解决方案**:
```python
# 实现验证冷却期
cooldown_hours = {
    "weak": 24,    # 弱信号冷却24小时
    "medium": 72,  # 中信号冷却72小时
    "strong": 168  # 强信号冷却7天
}

# 检查冷却期
last_validated = record.last_validated_at
if last_validated and (now - last_validated).hours < cooldown:
    return {"status": "cooldown", "next_available": next_time}
```

### 陷阱2：向量索引不一致

**问题**: 数据库记录与向量索引不同步。

**解决方案**:
```python
# 实现一致性检查
def check_consistency(project_id: str, batch_size: int = 100):
    db_ids = get_all_qa_ids_from_db(project_id, batch_size)
    vector_ids = get_all_vector_ids(project_id)

    missing_in_vector = db_ids - vector_ids
    orphaned_vectors = vector_ids - db_ids

    return {
        "missing_in_vector": list(missing_in_vector),
        "orphaned_vectors": list(orphaned_vectors),
        "consistency_rate": len(db_ids & vector_ids) / len(db_ids) if db_ids else 1.0
    }
```

### 陷阱3：标签爆炸

**问题**: 标签数量过多导致搜索性能下降。

**解决方案**:
```python
# 标签规范化策略
def normalize_tags(tags: List[str]) -> List[str]:
    # 1. 转换为小写
    # 2. 去除特殊字符
    # 3. 合并同义词
    # 4. 限制最大数量
    normalized = [tag.lower().strip() for tag in tags]
    normalized = [re.sub(r'[^\w\s-]', '', tag) for tag in normalized]
    normalized = list(dict.fromkeys(normalized))  # 去重保持顺序
    return normalized[:MAX_TAGS_PER_RECORD]  # 例如10个
```

### 陷阱4：查询词过短

**问题**: 过短的查询词导致搜索结果质量差。

**解决方案**:
```python
# 查询词增强
def enhance_query(query: str, context: Dict[str, Any] = None) -> str:
    query = query.strip()
    if len(query) < MIN_QUERY_LENGTH:  # 例如3个字符
        # 添加上下文信息
        if context and context.get("namespace"):
            query = f"{query} {context['namespace']}"
        # 添加常见后缀
        query = f"{query} how to guide tutorial"
    return query
```

## 扩展模式

### 插件模式
```python
# 可插拔的评分策略
class ScoringStrategy:
    def calculate(self, relevance, trust, freshness, level) -> float:
        raise NotImplementedError

class DefaultScoring(ScoringStrategy):
    weights = {"relevance": 0.55, "trust": 0.30, "freshness": 0.15}

    def calculate(self, relevance, trust, freshness, level):
        base = sum(w * v for w, v in zip(self.weights.values(), [relevance, trust, freshness]))
        return base + min(0.08, 0.02 * level)
```

### 缓存模式
```python
# 查询结果缓存
class QAMemoryServiceWithCache(QAMemoryService):
    def __init__(self, cache_backend):
        self.cache = cache_backend
        super().__init__()

    def search(self, project_id, query, limit=6, min_score=0.2):
        cache_key = f"qa_search:{project_id}:{query}:{limit}:{min_score}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        results = super().search(project_id, query, limit, min_score)
        self.cache.set(cache_key, results, ttl=300)  # 5分钟缓存
        return results
```

### 分片模式
```python
# 基于命名空间的分片
class ShardedQAMemoryService:
    def __init__(self, shard_count=4):
        self.shards = [
            QAMemoryService() for _ in range(shard_count)
        ]

    def _get_shard(self, namespace: str) -> QAMemoryService:
        shard_index = hash(namespace) % len(self.shards)
        return self.shards[shard_index]

    def search(self, project_id, query, limit=6, min_score=0.2):
        shard = self._get_shard(project_id)
        return shard.search(project_id, query, limit, min_score)
```

## 迁移指南

### 从 v0.x 迁移到 v1.0

#### 接口变更
1. `get_qa` 重命名为 `qa_detail`
2. `add_qa` 重命名为 `qa_upsert_candidate`
3. `validate_qa` 重命名为 `qa_validate_and_update`

#### 响应格式变更
```python
# v0.x 格式
{
    "data": [...],
    "total": 10
}

# v1.0 格式
{
    "schema_version": 1,
    "results": [...],
    "meta": {"count": 10, ...}
}
```

#### 必填字段变更
- 新增 `namespace` 为必填参数
- `tags` 从字符串改为字符串列表
- `metadata` 结构更规范化

### 数据迁移脚本
```python
async def migrate_v0_to_v1(old_connection, new_service):
    # 1. 导出旧数据
    old_records = await old_connection.fetch_all("SELECT * FROM qa_records")

    # 2. 转换并导入
    for old in old_records:
        await new_service.qa_upsert_candidate(
            question_raw=old["question"],
            answer_raw=old["answer"],
            namespace=old["project_id"] or "default",
            tags=old["tags"].split(",") if old["tags"] else [],
            # ... 其他字段转换
        )

    # 3. 验证数据一致性
    old_count = len(old_records)
    new_count = await new_service.get_count()
    assert old_count == new_count, f"数据不一致: {old_count} != {new_count}"
```

---

**文档版本**: 1.0
**最后更新**: 2025-12-26
**维护建议**: 定期回顾并更新最佳实践