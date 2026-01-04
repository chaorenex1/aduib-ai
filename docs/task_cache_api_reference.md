# Task Cache API Reference (P1 Enhanced)

## 概述

Task Cache API 提供完整的任务缓存和历史管理功能，支持 Orchestrator 客户端的任务结果存储、查询、导出和管理。

**Base URL**: `/v1`

**认证**: 所有 API 端点（除 `/health`）需要在 Header 中提供 API Key:
```
Authorization: Bearer YOUR_API_KEY
```

---

## 端点列表

### 健康检查

#### `GET /health`

检查服务健康状态

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "status": "healthy",
    "service": "aduib-ai"
  }
}
```

---

### 缓存查询

#### `GET /v1/api/cache/query`

查询缓存，命中时自动增加 `hit_count`

**查询参数**:
- `request_hash` (required) - SHA256 哈希值
- `mode` (required) - 执行模式
- `backend` (required) - 后端类型

**成功响应** (200):
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "task_id": 123,
    "output": "任务输出内容",
    "success": true,
    "created_at": "2026-01-04T12:00:00",
    "hit_count": 5
  }
}
```

**未命中响应** (404):
```json
{
  "code": 404,
  "msg": "Cache not found",
  "data": {}
}
```

---

### 任务保存

#### `POST /v1/api/tasks/save`

保存单个任务结果

**请求体**:
```json
{
  "request": "git status",
  "mode": "command",
  "backend": "claude",
  "success": true,
  "output": "On branch main\nnothing to commit",
  "error": null,
  "run_id": "run-123",
  "duration_seconds": 1.5
}
```

**字段验证**:
- `request`: 1-10000 字符
- `mode`: 必须是 `command`, `agent`, `prompt`, `skill`, `backend` 之一
- `backend`: 必须是 `claude`, `gemini`, `codex`, `openai`, `deepseek`, `other` 之一
- `duration_seconds`: 0-3600 秒

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "task_id": 124,
    "request_hash": "7a8b9c0d1e2f3456...",
    "success": true
  }
}
```

---

### 批量保存 (P1 新增)

#### `POST /v1/api/tasks/batch`

批量保存多个任务（最多 100 个）

**请求体**:
```json
{
  "tasks": [
    {
      "request": "task 1",
      "mode": "command",
      "backend": "claude",
      "success": true,
      "output": "output 1"
    },
    {
      "request": "task 2",
      "mode": "agent",
      "backend": "gemini",
      "success": false,
      "output": "output 2",
      "error": "Error message"
    }
  ]
}
```

**限制**:
- 最少 1 个任务
- 最多 100 个任务

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "saved_count": 45,
    "updated_count": 3,
    "failed_count": 2,
    "total_processed": 50,
    "task_ids": [125, 126, 127, ...]
  }
}
```

---

### 任务历史

#### `GET /v1/api/tasks/history`

获取任务历史记录

**查询参数**:
- `limit` (optional, default=50) - 每页数量 (1-1000)
- `offset` (optional, default=0) - 偏移量
- `mode` (optional) - 按模式过滤
- `backend` (optional) - 按后端过滤

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "tasks": [
      {
        "id": 123,
        "request": "git status",
        "request_hash": "7a8b9c0d...",
        "mode": "command",
        "backend": "claude",
        "success": true,
        "output": "...",
        "error": null,
        "run_id": "run-123",
        "duration_seconds": 1.5,
        "hit_count": 5,
        "created_at": "2026-01-04T12:00:00",
        "updated_at": "2026-01-04T12:05:00"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

---

### 统计信息

#### `GET /v1/api/stats`

获取缓存和任务统计

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "total_tasks": 1234,
    "cache_hit_rate": 65.5,
    "success_rate": 98.2,
    "backends": {
      "claude": 500,
      "gemini": 400,
      "codex": 334
    },
    "modes": {
      "command": 600,
      "agent": 400,
      "prompt": 234
    }
  }
}
```

---

### 数据导出 (P1 新增)

#### `GET /v1/api/tasks/export`

导出任务数据为 JSON 或 CSV

**查询参数**:
- `format` (optional, default="json") - 导出格式: `json` 或 `csv`
- `mode` (optional) - 按模式过滤
- `backend` (optional) - 按后端过滤
- `limit` (optional, default=1000) - 最大数量 (1-10000)

**JSON 响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "format": "json",
    "count": 100,
    "tasks": [
      {
        "id": 123,
        "request": "...",
        "mode": "command",
        "backend": "claude",
        ...
      }
    ]
  }
}
```

**CSV 响应**:
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=tasks_export.csv`
- 包含所有字段的 CSV 文件

---

### 删除任务 (P1 新增)

#### `DELETE /v1/api/tasks/{task_id}`

删除指定任务

**路径参数**:
- `task_id` (required) - 任务 ID

**成功响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "deleted": true,
    "task_id": 123
  }
}
```

**未找到响应**:
```json
{
  "code": 404,
  "msg": "Task 123 not found",
  "data": {}
}
```

---

### 清理旧任务 (P1 新增)

#### `DELETE /v1/api/tasks/cleanup`

清理指定天数之前的旧任务

**查询参数**:
- `days` (optional, default=30) - 保留天数 (1-365)

**响应**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "deleted_count": 45,
    "days": 30
  }
}
```

---

## 数据模型

### TaskDataRequest

```typescript
{
  request: string          // 1-10000 字符
  mode: string            // command|agent|prompt|skill|backend
  backend: string         // claude|gemini|codex|openai|deepseek|other
  success: boolean
  output: string
  error?: string          // 最多 5000 字符
  run_id?: string         // 最多 64 字符
  duration_seconds?: number  // 0-3600 秒
}
```

### CachedResultResponse

```typescript
{
  task_id: number
  output: string
  success: boolean
  created_at: string      // ISO 8601 格式
  hit_count: number
}
```

### TaskHistoryResponse

```typescript
{
  id: number
  request: string
  request_hash: string
  mode: string
  backend: string
  success: boolean
  output: string
  error: string | null
  run_id: string | null
  duration_seconds: number | null
  hit_count: number
  created_at: string
  updated_at: string
}
```

---

## 错误响应

所有错误响应使用统一格式：

```json
{
  "code": <错误码>,
  "msg": "<错误描述>",
  "data": {}
}
```

**常见错误码**:
- `400` - 请求参数错误
- `404` - 资源未找到
- `500` - 服务器内部错误

---

## 使用示例

### Python 示例

```python
import requests
import hashlib

BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. 保存任务
def save_task(request, mode, backend, success, output):
    response = requests.post(
        f"{BASE_URL}/v1/api/tasks/save",
        headers=headers,
        json={
            "request": request,
            "mode": mode,
            "backend": backend,
            "success": success,
            "output": output
        }
    )
    return response.json()

# 2. 查询缓存
def query_cache(request, mode, backend):
    # 计算哈希
    content = f"{request}:{mode}:{backend}"
    request_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    response = requests.get(
        f"{BASE_URL}/v1/api/cache/query",
        headers=headers,
        params={
            "request_hash": request_hash,
            "mode": mode,
            "backend": backend
        }
    )
    return response.json()

# 3. 批量保存
def batch_save_tasks(tasks):
    response = requests.post(
        f"{BASE_URL}/v1/api/tasks/batch",
        headers=headers,
        json={"tasks": tasks}
    )
    return response.json()

# 4. 导出数据
def export_tasks(format='json', mode=None, limit=1000):
    params = {"format": format, "limit": limit}
    if mode:
        params["mode"] = mode

    response = requests.get(
        f"{BASE_URL}/v1/api/tasks/export",
        headers=headers,
        params=params
    )

    if format == 'json':
        return response.json()
    else:
        return response.text  # CSV content
```

### cURL 示例

```bash
# 健康检查
curl http://localhost:8000/health

# 保存任务
curl -X POST http://localhost:8000/v1/api/tasks/save \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "request": "git status",
    "mode": "command",
    "backend": "claude",
    "success": true,
    "output": "On branch main"
  }'

# 批量保存
curl -X POST http://localhost:8000/v1/api/tasks/batch \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"request": "task 1", "mode": "command", "backend": "claude", "success": true, "output": "output 1"},
      {"request": "task 2", "mode": "agent", "backend": "gemini", "success": true, "output": "output 2"}
    ]
  }'

# 查询缓存
curl "http://localhost:8000/v1/api/cache/query?request_hash=HASH&mode=command&backend=claude" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 获取历史
curl "http://localhost:8000/v1/api/tasks/history?limit=10&mode=command" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 导出为 CSV
curl "http://localhost:8000/v1/api/tasks/export?format=csv&limit=100" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -o tasks.csv

# 删除任务
curl -X DELETE "http://localhost:8000/v1/api/tasks/123" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 清理 30 天前的任务
curl -X DELETE "http://localhost:8000/v1/api/tasks/cleanup?days=30" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 性能指标

### 响应时间
- 缓存查询: < 100ms (99th percentile: 200ms)
- 任务保存: < 150ms
- 批量保存 (50 tasks): < 2s
- 历史查询: < 200ms
- 统计信息: < 300ms

### 限制
- 批量保存: 最多 100 个任务/请求
- 历史查询: 最多 1000 个任务/请求
- 数据导出: 最多 10000 个任务/请求
- 请求大小: 最大 10MB

---

## P1 新增功能总结

✅ **批量操作**
- `POST /v1/api/tasks/batch` - 批量保存任务（最多 100 个）

✅ **增强验证**
- 字段长度限制
- 枚举值验证（mode, backend）
- 数值范围验证（duration_seconds: 0-3600）

✅ **数据导出**
- `GET /v1/api/tasks/export` - 支持 JSON 和 CSV 格式
- 支持过滤和分页

✅ **任务管理**
- `DELETE /v1/api/tasks/{task_id}` - 删除单个任务
- `DELETE /v1/api/tasks/cleanup` - 批量清理旧任务

✅ **性能优化**
- 批量保存性能：50 个任务 < 2 秒
- 数据库索引优化
- 请求参数验证

---

## 更新日志

### v1.1.0 (P1) - 2026-01-04
- ✅ 新增批量保存端点
- ✅ 新增数据导出功能（JSON/CSV）
- ✅ 新增任务删除和清理端点
- ✅ 增强请求参数验证
- ✅ 性能测试和优化

### v1.0.0 (P0) - 2026-01-04
- ✅ 初始版本
- ✅ 基础缓存查询和保存
- ✅ 任务历史查询
- ✅ 统计信息
- ✅ 健康检查

---

**文档版本**: 1.1.0
**最后更新**: 2026-01-04
**维护者**: ADUIB-AI Team
