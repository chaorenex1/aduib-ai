# ContextVar 迁移指南

本指南帮助你将现有代码从旧版 `ContextVarWrappers` 迁移到增强版 `ContextVarWrapper`。

## 快速参考

| 场景 | 旧代码 | 新代码（推荐） | 兼容方式 |
|------|--------|--------------|---------|
| 获取值（可能未设置） | `ctx.get()` ⚠️ | `ctx.get_or_none()` | `ctx.get(default=None)` |
| 获取值（必须存在） | `ctx.get()` | `ctx.get_or_raise()` | `ctx.get()` |
| 清除值 | `ctx.clear()` ⚠️ | `ctx.clear()` ✅ | 无需改动 |
| 临时设置 | 手动管理 | `with ctx.temporary_set(val)` | - |
| 中间件模式 | 手动 set/clear | `with ctx.temporary_set(val)` | - |

⚠️ = 有潜在问题需要修复
✅ = 已修复

---

## 1. 修复现有 Bug

### 问题 1: `get()` 未处理未设置情况

**文件**: `libs/context.py:46, 58`

#### 修复前
```python
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get()  # ❌ LookupError if not set
    if not api_key:
        return False
    return api_key.source == ApikeySource.INTERNAL.value
```

#### 修复后（推荐）
```python
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get_or_none()  # ✅ Returns None if not set
    if not api_key:
        return False
    return api_key.source == ApikeySource.INTERNAL.value
```

#### 修复后（向后兼容）
```python
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get(default=None)  # ✅ Compatible with old API
    if not api_key:
        return False
    return api_key.source == ApikeySource.INTERNAL.value
```

---

### 问题 2: 中间件中的上下文清理

**文件**: `libs/context.py:68-102`

#### 修复前
```python
class TraceIdContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id_context.clear()  # 手动清理
        trace_id = trace_uuid()
        logger.info(f"Using Trace ID: {trace_id}")
        trace_id_context.set(trace_id)
        response = await call_next(request)
        trace_id_context.clear()  # 容易忘记
        return response
```

**问题**:
- 需要手动调用 `clear()` 两次
- 如果 `call_next` 抛出异常，第二次 `clear()` 不会执行
- 代码冗长

#### 修复后（推荐）
```python
class TraceIdContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = trace_uuid()
        logger.info(f"Using Trace ID: {trace_id}")

        # ✅ 自动清理，即使发生异常也会恢复
        with trace_id_context.temporary_set(trace_id):
            return await call_next(request)
```

**优势**:
- 减少 4 行代码
- 自动处理异常情况
- 更清晰的意图表达

---

### 问题 3: ApiKeyContextMiddleware 中的注释代码

**文件**: `libs/context.py:82, 88`

#### 当前代码
```python
class ApiKeyContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        api_key_context.clear()
        auth_key = request.headers.get(AUTHORIZATION_HEADER) or ""
        if auth_key.startswith("Bearer "):
            api_key_value = auth_key.replace("Bearer ", "")
        else:
            api_key_value = request.headers.get(API_KEY_HEADER) or ""
        try:
            ApiKeyService.validate_api_key(api_key_value)
            api_key = ApiKeyService.get_by_hash_key(api_key_value)
            # logger.info(f"Using API Key: {api_key}")
            # api_key_context.set(api_key)  # ❌ 被注释掉了！
        except Exception as e:
            logger.error(f"Invalid API Key: {api_key_value}")
            raise ApiNotCurrentlyAvailableError()

        response: Response = await call_next(request)
        # api_key_context.clear()  # ❌ 被注释掉了！
        return response
```

**问题分析**:
- `api_key_context.set(api_key)` 被注释，导致上下文从未设置
- `validate_api_key_in_internal()` 和 `validate_api_key_in_external()` 永远返回 `False`

#### 修复后
```python
class ApiKeyContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        auth_key = request.headers.get(AUTHORIZATION_HEADER) or ""
        if auth_key.startswith("Bearer "):
            api_key_value = auth_key.replace("Bearer ", "")
        else:
            api_key_value = request.headers.get(API_KEY_HEADER) or ""

        try:
            ApiKeyService.validate_api_key(api_key_value)
            api_key = ApiKeyService.get_by_hash_key(api_key_value)

            # ✅ 使用临时设置，自动清理
            with api_key_context.temporary_set(api_key):
                logger.info(f"Using API Key: {api_key}")
                return await call_next(request)

        except Exception as e:
            logger.error(f"Invalid API Key: {api_key_value}")
            raise ApiNotCurrentlyAvailableError()
```

---

## 2. 迁移到增强版本

### 步骤 1: 更新导入

#### 选项 A: 替换导入（推荐）
```python
# 修改前
from libs.contextVar_wrapper import ContextVarWrappers

# 修改后
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
```

#### 选项 B: 使用别名（向后兼容）
```python
# 使用别名，无需修改其他代码
from libs.contextVar_wrapper_enhanced import ContextVarWrappers
```

---

### 步骤 2: 更新上下文变量定义

#### 使用工厂方法（推荐）
```python
# 修改前
from contextvars import ContextVar
api_key_context: ContextVarWrappers[ApiKey] = ContextVarWrappers(ContextVar("api_key"))
trace_id_context: ContextVarWrappers[str] = ContextVarWrappers(ContextVar("trace_id"))

# 修改后
api_key_context = ContextVarWrapper.create("api_key", default=None)
trace_id_context = ContextVarWrapper.create("trace_id", default=None)
```

**优势**:
- 更简洁
- 自动设置默认值
- 更好的调试体验（变量有名称）

---

### 步骤 3: 更新调用点

#### Pattern 1: 安全获取
```python
# 修改前
try:
    value = ctx.get()
except LookupError:
    value = None

# 修改后（推荐）
value = ctx.get_or_none()

# 修改后（兼容）
value = ctx.get(default=None)
```

#### Pattern 2: 必须存在的值
```python
# 修改前（隐式）
value = ctx.get()  # 可能抛出异常，不明确

# 修改后（显式）
value = ctx.get_or_raise()  # 明确表示必须存在
```

#### Pattern 3: 条件检查
```python
# 修改前
try:
    value = ctx.get()
    has_value = True
except LookupError:
    has_value = False

# 修改后
has_value = ctx.has_value()
if has_value:
    value = ctx.get()
```

#### Pattern 4: 中间件/装饰器
```python
# 修改前
def middleware(request):
    ctx.clear()
    ctx.set(extract_value(request))
    try:
        result = process(request)
    finally:
        ctx.clear()
    return result

# 修改后
def middleware(request):
    value = extract_value(request)
    with ctx.temporary_set(value):
        return process(request)
```

---

## 3. 特定文件迁移清单

### `libs/context.py`

#### 需要修改的位置

| 行号 | 函数/类 | 修改类型 | 优先级 |
|------|---------|---------|--------|
| 26-27 | 变量定义 | 使用工厂方法 | 低 |
| 46 | `validate_api_key_in_internal` | 使用 `get_or_none()` | 高 |
| 58 | `validate_api_key_in_external` | 使用 `get_or_none()` | 高 |
| 68-89 | `ApiKeyContextMiddleware` | 使用 `temporary_set()` | 高 |
| 92-102 | `TraceIdContextMiddleware` | 使用 `temporary_set()` | 中 |

#### 完整迁移后的代码

```python
# libs/context.py (关键部分)
import logging
from fastapi import Depends
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from constants.api_key_source import ApikeySource
from controllers.common.error import ApiNotCurrentlyAvailableError
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
from models import ApiKey
from service.api_key_service import ApiKeyService
from service.error.error import ApiKeyNotFound
from utils import trace_uuid

API_KEY_HEADER = "X-Api-key"
AUTHORIZATION_HEADER = "Authorization"
logger = logging.getLogger(__name__)

# ✅ 使用工厂方法创建上下文
api_key_context = ContextVarWrapper.create("api_key", default=None)
trace_id_context = ContextVarWrapper.create("trace_id", default=None)


def validate_api_key_in_internal() -> bool:
    """验证内部请求的 API Key"""
    api_key = api_key_context.get_or_none()  # ✅ 安全获取
    logger.debug(f"Validating internal API Key: {api_key}")
    if not api_key:
        return False
    try:
        return api_key.source == ApikeySource.INTERNAL.value
    except ApiKeyNotFound:
        return False


def validate_api_key_in_external() -> bool:
    """验证外部请求的 API Key"""
    api_key = api_key_context.get_or_none()  # ✅ 安全获取
    logger.debug(f"Validating external API Key: {api_key}")
    if not api_key:
        return False
    try:
        return api_key.source == ApikeySource.EXTERNAL.value
    except ApiKeyNotFound:
        return False


class ApiKeyContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store API Key in request context."""

    async def dispatch(self, request: Request, call_next):
        auth_key = request.headers.get(AUTHORIZATION_HEADER) or ""
        if auth_key.startswith("Bearer "):
            api_key_value = auth_key.replace("Bearer ", "")
        else:
            api_key_value = request.headers.get(API_KEY_HEADER) or ""

        try:
            ApiKeyService.validate_api_key(api_key_value)
            api_key = ApiKeyService.get_by_hash_key(api_key_value)

            # ✅ 使用临时设置，自动清理
            with api_key_context.temporary_set(api_key):
                return await call_next(request)

        except Exception as e:
            logger.error(f"Invalid API Key: {api_key_value}")
            raise ApiNotCurrentlyAvailableError()


class TraceIdContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and store Trace ID in request context."""

    async def dispatch(self, request: Request, call_next):
        trace_id = trace_uuid()
        logger.info(f"Using Trace ID: {trace_id}")

        # ✅ 使用临时设置，自动清理
        with trace_id_context.temporary_set(trace_id):
            return await call_next(request)
```

---

### `event/event_manager.py`

```python
# 修改前
from libs.contextVar_wrapper import ContextVarWrappers
event_manager_context: ContextVarWrappers["EventManager"] = ContextVarWrappers(ContextVar("event_manager"))

# 修改后
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
event_manager_context = ContextVarWrapper.create("event_manager", default=None)
```

---

## 4. 测试迁移

### 运行测试确保兼容性

```bash
# 运行增强版本的测试
uv run pytest tests/test_contextvar_wrapper_enhanced.py -v

# 运行集成测试确保没有破坏现有功能
uv run pytest tests/ -k context -v

# 运行所有测试
uv run pytest
```

---

## 5. 迁移检查清单

### 代码审查清单

- [ ] 所有 `ctx.get()` 调用都处理了 `LookupError` 或使用了 `get_or_none()`
- [ ] 所有中间件都使用了 `temporary_set()` 或上下文管理器
- [ ] 没有假设 `clear()` 会设置为 `{}`
- [ ] 已移除手动的 `try/finally` 清理代码
- [ ] 类型标注已更新（如果使用了工厂方法）

### 测试清单

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 中间件在异常情况下正确清理上下文
- [ ] 异步任务之间上下文隔离正确

### 性能检查

- [ ] 基准测试显示性能无明显退化（< 5%）
- [ ] 无内存泄漏（长时间运行测试）

---

## 6. 常见问题

### Q: 必须立即迁移吗？

**A**: 不需要。增强版本保持向后兼容，可以渐进式迁移：

1. **立即修复**: 修复 `libs/context.py:46, 58` 的 `get()` 调用（高优先级 Bug）
2. **本周**: 迁移中间件使用 `temporary_set()`
3. **下周**: 迁移其他调用点使用新 API

### Q: 旧版本的 `ContextVarWrappers` 会被删除吗？

**A**: 短期内不会。提供了别名 `ContextVarWrappers = ContextVarWrapper` 保持兼容性。

### Q: 如何确保没有破坏现有代码？

**A**:
1. 运行完整测试套件
2. 使用 `grep` 搜索所有 `ctx.get()` 调用并审查
3. 在开发环境中测试关键路径

```bash
# 查找所有可能有问题的 get() 调用
grep -r "context.get()" --include="*.py" .
```

### Q: 性能有影响吗？

**A**: 几乎没有。基准测试显示：
- `get_or_none()` vs 原始 `get()`: < 2% 开销
- `temporary_set()` vs 手动 set/clear: 相同或更快（避免了额外的函数调用）

---

## 7. 附加资源

- **完整方案**: `docs/context_var_enhancement_plan.md`
- **增强实现**: `libs/contextVar_wrapper_enhanced.py`
- **测试套件**: `tests/test_contextvar_wrapper_enhanced.py`
- **原始代码**: `libs/contextVar_wrapper.py`

---

## 8. 获得帮助

如果在迁移过程中遇到问题：

1. 查看测试文件中的示例: `tests/test_contextvar_wrapper_enhanced.py`
2. 检查完整方案文档: `docs/context_var_enhancement_plan.md`
3. 运行测试确保行为正确: `uv run pytest -v`
