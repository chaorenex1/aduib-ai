# QA Memory Service API 参考

## 概述

本文档详细描述了 QA Memory Service 的所有公共接口。所有接口均为异步方法，通过 RPC 框架暴露。

## 接口索引

| 接口 | 描述 | 权限 | 版本 |
|------|------|------|------|
| `retrieve_qa_kb` | 语义检索 QA 记忆库 | 读 | v1 |
| `qa_record_hit` | 记录 QA 使用命中 | 写 | v1 |
| `qa_upsert_candidate` | 创建/更新 QA 候选记录 | 写 | v1 |
| `qa_validate_and_update` | 验证并更新 QA 记录状态 | 写 | v1 |
| `qa_expire` | 清理过期 QA 记录 | 写 | v1 |
| `qa_detail` | 获取单个 QA 记录详情 | 读 | v1 |

## 详细接口说明

### 1. retrieve_qa_kb - 语义检索 QA 记忆库

```python
async def retrieve_qa_kb(
    self,
    query: str,
    namespace: str,
    top_k: int = 8,
    filters: Optional[List[str]] = None,
) -> Dict[str, Any]
```

**功能描述**: 根据查询文本进行语义搜索，返回最相关的 QA 记录。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `query` | `str` | 是 | - | 搜索查询文本 |
| `namespace` | `str` | 是 | - | 项目/命名空间标识符 |
| `top_k` | `int` | 否 | 8 | 返回结果数量 (1-50) |
| `filters` | `Optional[List[str]]` | 否 | `None` | 过滤条件列表 (保留字段) |

**返回值**:
```python
{
    "schema_version": 1,
    "results": [
        {
            "qa_id": "uuid-string",
            "question": "问题文本",
            "answer": "答案文本",
            "validation_level": 2,
            "confidence": 0.85,
            "scope": {},
            "tags": ["tag1", "tag2"],
            "source": {"label": "source_name"},
            "expiry_at": "2025-01-01T00:00:00",
            "relevance_score": 0.92,
            "evidence_refs": [],
            "resource_uri": "file://path/to/resource"
        }
    ],
    "meta": {
        "count": 5,
        "namespace": "project-123",
        "filters": []
    }
}
```

**字段说明**:
- `results[].validation_level`: 验证级别 (0-3)，值越大可信度越高
- `results[].confidence`: 置信度分数 (0.0-1.0)
- `results[].relevance_score`: 语义相关度分数 (0.0-1.0)
- `results[].expiry_at`: TTL 过期时间 (ISO 8601 格式)
- `results[].evidence_refs`: 证据引用列表
- `results[].resource_uri`: 原始资源 URI

**错误情况**:
- `query` 为空字符串时返回空结果列表
- `namespace` 不存在时返回空结果列表
- 向量数据库连接失败时返回空结果列表

**示例调用**:
```python
result = await service.retrieve_qa_kb(
    query="如何配置数据库连接池",
    namespace="project-123",
    top_k=5
)
```

### 2. qa_record_hit - 记录 QA 使用命中

```python
async def qa_record_hit(
    self,
    qa_id: str,
    namespace: str,
    used: bool = True,
    shown: bool = True,
    client: Optional[dict[str, Any]] = None,
) -> Dict[str, Any]
```

**功能描述**: 记录 QA 记录被展示或使用的统计信息。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `qa_id` | `str` | 是 | - | QA 记录唯一标识符 |
| `namespace` | `str` | 是 | - | 项目/命名空间标识符 |
| `used` | `bool` | 否 | `True` | 是否被实际使用 |
| `shown` | `bool` | 否 | `True` | 是否被展示给用户 |
| `client` | `Optional[dict]` | 否 | `None` | 客户端上下文信息 |

**返回值**:
```python
{
    "qa_id": "uuid-string",
    "namespace": "project-123",
    "status": "recorded"
}
```

**字段说明**:
- `status`: 操作状态，固定为 `"recorded"`

**副作用**:
- 更新 `usage_count` 计数（当 `shown=True` 时）
- 更新 `last_used_at` 时间戳（当 `used=True` 时）
- 创建 `QaMemoryEvent` 事件日志

**示例调用**:
```python
result = await service.qa_record_hit(
    qa_id="123e4567-e89b-12d3-a456-426614174000",
    namespace="project-123",
    used=True,
    shown=True,
    client={"user_id": "user-123", "session_id": "session-456"}
)
```

### 3. qa_upsert_candidate - 创建/更新 QA 候选记录

```python
async def qa_upsert_candidate(
    self,
    question_raw: str,
    answer_raw: str,
    namespace: str,
    tags: Optional[List[str]] = None,
    scope: Optional[Dict[str, str]] = None,
    time_sensitivity: str = "medium",
    evidence_refs: Optional[List[str]] = None,
    client: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

**功能描述**: 创建新的 QA 候选记录或更新现有记录。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `question_raw` | `str` | 是 | - | 原始问题文本 |
| `answer_raw` | `str` | 是 | - | 原始答案文本 |
| `namespace` | `str` | 是 | - | 项目/命名空间标识符 |
| `tags` | `Optional[List[str]]` | 否 | `None` | 标签列表 |
| `scope` | `Optional[Dict[str, str]]` | 否 | `None` | 作用域信息 |
| `time_sensitivity` | `str` | 否 | `"medium"` | 时间敏感性 (`low`/`medium`/`high`) |
| `evidence_refs` | `Optional[List[str]]` | 否 | `None` | 证据引用列表 |
| `client` | `Optional[Dict[str, Any]]` | 否 | `None` | 客户端上下文信息 |

**返回值**:
```python
{
    "record": {
        "qa_id": "uuid-string",
        "project_id": "project-123",
        "question": "处理后的问题文本",
        "answer": "处理后的答案文本",
        "summary": "AI生成的摘要",
        "tags": ["tag1", "tag2"],
        "metadata": {
            "scope": {},
            "time_sensitivity": "medium",
            "evidence_refs": [],
            "client": {},
            "stats": {...},
            "score": {...},
            "ttl": {...}
        },
        "scope": {},
        "evidence_refs": [],
        "time_sensitivity": "medium",
        "resource_uri": None,
        "status": "candidate",
        "level": "L0",
        "trust_score": 0.5,
        "confidence": 0.5,
        "usage_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "strong_signal_count": 0,
        "last_used_at": None,
        "last_validated_at": None,
        "ttl_expire_at": "2025-01-14T00:00:00",
        "created_at": "2024-12-26T10:00:00",
        "updated_at": "2024-12-26T10:00:00"
    }
}
```

**字段说明**:
- `record.status`: 初始状态为 `"candidate"`
- `record.level`: 初始级别为 `"L0"`
- `record.summary`: 由 LLM 自动生成的摘要
- `record.ttl_expire_at`: 基于 `BASE_TTL_DAYS` (14天) 计算的过期时间

**自动行为**:
1. 自动生成问题/答案摘要
2. 初始化验证统计信息
3. 设置 TTL 过期时间
4. 创建向量索引条目

**示例调用**:
```python
result = await service.qa_upsert_candidate(
    question_raw="如何重置用户密码",
    answer_raw="请访问设置页面，点击'安全设置'，然后选择'重置密码'选项。",
    namespace="project-123",
    tags=["authentication", "user-management"],
    scope={"module": "auth", "version": "v1.0"},
    time_sensitivity="low",
    evidence_refs=["docs/auth-guide.md"]
)
```

### 4. qa_validate_and_update - 验证并更新 QA 记录状态

```python
async def qa_validate_and_update(
    self,
    qa_id: str,
    namespace: str,
    result: str,
    signal_strength: str = "weak",
    reason: str = "",
    evidence_refs: Optional[List[str]] = None,
    execution: Optional[dict[str, Any]] = None,
    client: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

**功能描述**: 根据验证结果更新 QA 记录的状态、信任评分和 TTL。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `qa_id` | `str` | 是 | - | QA 记录唯一标识符 |
| `namespace` | `str` | 是 | - | 项目/命名空间标识符 |
| `result` | `str` | 是 | - | 验证结果 (`"pass"`/`"fail"`) |
| `signal_strength` | `str` | 否 | `"weak"` | 信号强度 (`"weak"`/`"medium"`/`"strong"`) |
| `reason` | `str` | 否 | `""` | 验证原因说明 |
| `evidence_refs` | `Optional[List[str]]` | 否 | `None` | 证据引用列表 |
| `execution` | `Optional[dict]` | 否 | `None` | 执行上下文信息 |
| `client` | `Optional[Dict[str, Any]]` | 否 | `None` | 客户端上下文信息 |

**返回值**:
```python
# 成功时
{
    "record": {
        // 完整序列化记录 (同 qa_upsert_candidate 返回格式)
    }
}

# 记录不存在时
{
    "status": "not_found",
    "qa_id": "uuid-string"
}
```

**验证逻辑**:
1. **结果归一化**: `result` 转换为小写
2. **信号归一化**: `signal_strength` 转换为 `weak`/`medium`/`strong`
3. **信号过滤**: 弱失败信号可能被忽略（如果已有强成功信号）
4. **统计更新**: 更新 `success_count`/`failure_count` 等统计
5. **信任评分**: 重新计算 `trust_score`
6. **验证级别**: 根据统计计算新的 `level` (L0-L3)
7. **状态更新**: 可能更新为 `active`/`stale`/`deprecated`
8. **TTL调整**: 强成功信号延长 TTL，强失败信号缩短 TTL

**TTL调整规则**:
- 强成功: 延长 30 天（最多 180 天）
- 强失败: 缩短至 7 天后过期
- 其他: 保持原 TTL

**示例调用**:
```python
result = await service.qa_validate_and_update(
    qa_id="123e4567-e89b-12d3-a456-426614174000",
    namespace="project-123",
    result="pass",
    signal_strength="strong",
    reason="用户确认答案正确",
    evidence_refs=["user-feedback-123"]
)
```

### 5. qa_expire - 清理过期 QA 记录

```python
async def qa_expire(
    self,
    batch_size: int = 200,
) -> Dict[str, Any]
```

**功能描述**: 清理已过期的 QA 记录，支持批量处理。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `batch_size` | `int` | 否 | `200` | 单次处理批次大小 |

**返回值**:
```python
{
    "expired": 15  # 实际处理的记录数量
}
```

**清理逻辑**:
1. **活跃记录**: 状态降级为 `stale`，TTL 缩短为原值一半（最少 1 天）
2. **非活跃记录**: 状态降级为 `deprecated`，TTL 设为 `None`
3. **跳过已废弃记录**: 状态为 `deprecated` 的记录不再处理
4. **向量索引更新**: 更新向量索引中的元数据

**调用时机**:
- 建议通过定时任务每日执行
- 可在系统低负载时执行
- 可配置多次调用以清理大量过期记录

**示例调用**:
```python
result = await service.qa_expire(batch_size=100)
```

### 6. qa_detail - 获取单个 QA 记录详情

```python
async def qa_detail(
    self,
    namespace: str,
    qa_id: str,
) -> Dict[str, Any]
```

**功能描述**: 获取单个 QA 记录的完整详情。

**参数**:
| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `namespace` | `str` | 是 | - | 项目/命名空间标识符 |
| `qa_id` | `str` | 是 | - | QA 记录唯一标识符 |

**返回值**:
```python
# 记录存在时
{
    "record": {
        // 完整序列化记录 (同 qa_upsert_candidate 返回格式)
    }
}

# 记录不存在时
{
    "status": "not_found",
    "qa_id": "uuid-string"
}
```

**字段说明**: 返回所有字段，包括完整的元数据和统计信息。

**示例调用**:
```python
result = await service.qa_detail(
    namespace="project-123",
    qa_id="123e4567-e89b-12d3-a456-426614174000"
)
```

## 错误处理约定

### 通用错误模式
```python
{
    "status": "error_type",
    "message": "可选错误描述",
    "code": "可选错误代码"
}
```

### 特定错误类型
1. **资源不存在**: `{"status": "not_found", ...}`
2. **验证失败**: 通过 `result: "fail"` 表示，非错误
3. **参数无效**: 静默处理或返回默认值
4. **系统错误**: 依赖 RPC 框架的错误传播机制

### 空值处理
- 空查询字符串: 返回空结果列表
- 空命名空间: 返回空结果列表
- 空标签列表: 转为空列表 `[]`
- 空元数据: 转为空字典 `{}`

## 序列化格式

### 日期时间字段
所有日期时间字段使用 ISO 8601 格式:
```python
"2024-12-26T10:30:45.123456"  # 带微秒
"2024-12-26T10:30:45"         # 不带微秒
```

### JSON 字段
- `tags`: 字符串列表 `["tag1", "tag2"]`
- `metadata`: 嵌套字典结构
- `scope`: 字符串键值对字典

### UUID 字段
使用标准 UUID 字符串格式:
```python
"123e4567-e89b-12d3-a456-426614174000"
```

## 版本管理

### 接口版本
- 当前版本: `schema_version = 1`
- 版本位置: 所有响应中的 `schema_version` 字段

### 向后兼容性
1. **新增字段**: 向后兼容
2. **移除字段**: 非向后兼容，需要版本升级
3. **字段类型变更**: 非向后兼容
4. **接口签名变更**: 非向后兼容

### 版本升级策略
1. 维护旧版本接口至少 6 个月
2. 通过 `schema_version` 字段区分版本
3. 提供迁移指南和工具

---

**文档版本**: 1.0
**最后更新**: 2025-12-26
**对应代码**: `rpc/service/qa_memory_service.py`