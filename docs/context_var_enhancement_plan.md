# ContextVar 上下文传递增强方案

## 1. 问题分析

### 1.1 当前实现问题

**代码位置**: `libs/contextVar_wrapper.py`

```python
class ContextVarWrappers(Generic[T]):
    def get(self) -> T:
        return self._storage.get()  # ❌ 无默认值，抛出 LookupError

    def clear(self) -> None:
        self._storage.set({})  # ❌ 假设 T 是字典类型
```

**实际使用中的问题**:

1. **`libs/context.py:46,58`** - `api_key_context.get()` 在未设置时崩溃
2. **`libs/context.py:72,96,101`** - `clear()` 对 `ApiKey`/`str` 类型设置 `{}`，类型错误
3. **`libs/context.py:88`** - 注释掉的 `clear()` 导致上下文污染风险

### 1.2 使用场景统计

| 上下文变量 | 类型 | 使用位置 | 问题 |
|-----------|------|----------|------|
| `api_key_context` | `ApiKey` | 中间件、验证函数 | `get()` 可能失败，`clear()` 类型错误 |
| `trace_id_context` | `str` | 追踪中间件 | `clear()` 类型错误 |
| `event_manager_context` | `EventManager` | 事件系统 | 同上 |

---

## 2. 增强方案

### 2.1 核心增强功能

#### A. 安全访问方法

```python
def get(self, default: T | None = None) -> T | None:
    """获取值，支持默认值（向后兼容）"""
    try:
        return self._storage.get()
    except LookupError:
        return default

def get_or_none(self) -> T | None:
    """获取值或返回 None（推荐新代码使用）"""
    try:
        return self._storage.get()
    except LookupError:
        return None

def get_or_raise(self) -> T:
    """获取值或抛出异常（显式语义）"""
    return self._storage.get()  # 原始行为

def has_value(self) -> bool:
    """检查是否已设置值"""
    try:
        self._storage.get()
        return True
    except LookupError:
        return False
```

**迁移路径**:
- 现有 `get()` 调用保持兼容（添加默认参数）
- 新代码使用 `get_or_none()` 或 `get_or_raise()` 明确意图

#### B. 正确的清理机制

```python
def clear(self) -> None:
    """清除上下文变量（使用 Token 机制）"""
    token = self._storage.set(None)  # 设置为 None 而不是 {}
    # 或使用 Token 重置（需要存储初始 token）

def delete(self) -> None:
    """删除上下文变量（等同于 clear）"""
    self.clear()
```

**类型安全**:
- 不再假设 `T` 是字典类型
- 使用 `None` 或 Token 机制清理

#### C. 上下文管理器支持

```python
from contextlib import contextmanager
from typing import Generator

@contextmanager
def temporary_set(self, value: T) -> Generator[None, None, None]:
    """临时设置值，自动清理"""
    token = self._storage.set(value)
    try:
        yield
    finally:
        self._storage.reset(token)

def __enter__(self) -> "ContextVarWrappers[T]":
    """进入上下文（用于配合 set 的手动管理）"""
    return self

def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    """退出上下文，自动清理"""
    self.clear()
```

**使用示例**:
```python
# 临时设置（推荐）
with trace_id_context.temporary_set("trace-123"):
    process_request()
# 自动恢复原值

# 手动管理
with trace_id_context:
    trace_id_context.set("trace-456")
    process_request()
# 自动清理
```

---

### 2.2 高级功能

#### A. 字典类型专用包装器

```python
class DictContextVar(ContextVarWrappers[dict]):
    """字典类型的专用上下文变量"""

    def update(self, **kwargs) -> None:
        """更新字典值"""
        current = self.get_or_none() or {}
        current.update(kwargs)
        self.set(current)

    def get_item(self, key: str, default=None):
        """获取字典中的单个键"""
        current = self.get_or_none() or {}
        return current.get(key, default)

    def set_item(self, key: str, value) -> None:
        """设置字典中的单个键"""
        current = self.get_or_none() or {}
        current[key] = value
        self.set(current)

    def clear(self) -> None:
        """清空字典（符合原有语义）"""
        self._storage.set({})
```

#### B. 调试和监控

```python
def __repr__(self) -> str:
    """调试友好的字符串表示"""
    try:
        value = self._storage.get()
        return f"<ContextVarWrappers({self._storage.name}={value!r})>"
    except LookupError:
        return f"<ContextVarWrappers({self._storage.name}=<unset>)>"

def get_name(self) -> str:
    """获取上下文变量名称"""
    return self._storage.name if hasattr(self._storage, 'name') else "<unnamed>"
```

#### C. 工厂方法

```python
@classmethod
def create(cls, name: str, default: T | None = None) -> "ContextVarWrappers[T]":
    """创建带名称和默认值的上下文变量"""
    context_var = ContextVar(name, default=default)
    return cls(context_var)
```

---

## 3. 实现计划

### 3.1 分阶段实施

#### Phase 1: 核心修复（高优先级）
- [ ] 修复 `get()` 默认值问题
- [ ] 修复 `clear()` 类型安全问题
- [ ] 添加 `get_or_none()`, `has_value()`

**影响**: 解决现有 Bug，保持向后兼容

#### Phase 2: 上下文管理器（中优先级）
- [ ] 实现 `temporary_set()`
- [ ] 实现 `__enter__` / `__exit__`
- [ ] 更新中间件使用上下文管理器

**影响**: 提升代码可维护性，防止内存泄漏

#### Phase 3: 高级功能（低优先级）
- [ ] 实现 `DictContextVar`
- [ ] 添加调试工具
- [ ] 添加类型检查和运行时验证

**影响**: 增强开发体验

### 3.2 迁移策略

#### 向后兼容修改

**libs/context.py**:
```python
# 修改前
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get()  # ❌ 可能抛出异常
    if not api_key:
        return False

# 修改后（方案1：使用新方法）
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get_or_none()  # ✅ 安全
    if not api_key:
        return False

# 修改后（方案2：使用默认参数）
def validate_api_key_in_internal() -> bool:
    api_key = api_key_context.get(default=None)  # ✅ 向后兼容
    if not api_key:
        return False
```

#### 中间件优化

```python
# 修改前
class TraceIdContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id_context.clear()
        trace_id = trace_uuid()
        trace_id_context.set(trace_id)
        response = await call_next(request)
        trace_id_context.clear()  # 容易忘记
        return response

# 修改后
class TraceIdContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = trace_uuid()
        with trace_id_context.temporary_set(trace_id):  # ✅ 自动清理
            return await call_next(request)
```

---

## 4. 测试策略

### 4.1 单元测试

```python
# tests/test_context_var_wrapper.py

def test_get_with_default():
    """测试默认值返回"""
    ctx = ContextVarWrappers.create("test")
    assert ctx.get(default="fallback") == "fallback"
    ctx.set("value")
    assert ctx.get(default="fallback") == "value"

def test_clear_type_safety():
    """测试 clear 不会设置错误类型"""
    ctx = ContextVarWrappers.create("test")
    ctx.set("string_value")
    ctx.clear()
    assert ctx.get_or_none() is None  # 不是 {}

def test_temporary_set():
    """测试临时设置和恢复"""
    ctx = ContextVarWrappers.create("test")
    ctx.set("original")
    with ctx.temporary_set("temp"):
        assert ctx.get() == "temp"
    assert ctx.get() == "original"

async def test_async_context_isolation():
    """测试异步任务间的上下文隔离"""
    ctx = ContextVarWrappers.create("test")

    async def task1():
        ctx.set("task1")
        await asyncio.sleep(0.01)
        assert ctx.get() == "task1"

    async def task2():
        ctx.set("task2")
        await asyncio.sleep(0.01)
        assert ctx.get() == "task2"

    await asyncio.gather(task1(), task2())
```

### 4.2 集成测试

```python
# tests/test_middleware_context.py

@pytest.mark.asyncio
async def test_trace_id_context_in_middleware():
    """测试中间件中的 trace_id 上下文隔离"""
    # 模拟并发请求
    # 验证每个请求有独立的 trace_id
```

---

## 5. 性能影响评估

### 5.1 内存影响

| 改动 | 影响 | 评估 |
|------|------|------|
| `temporary_set()` 使用 Token | +8 bytes/call | 可忽略 |
| 上下文管理器开销 | +2 函数调用/请求 | 微不足道 |

### 5.2 性能对比

```python
# 基准测试
import timeit

# 原始实现
def old_get():
    try:
        return ctx._storage.get()
    except LookupError:
        return None

# 新实现
def new_get():
    return ctx.get_or_none()

# 预期: 性能差异 < 5%
```

---

## 6. 风险评估

### 6.1 潜在风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| `get()` 签名变化 | 可能影响类型检查 | 渐进式迁移，保留原方法 |
| `clear()` 行为变化 | 如果有代码依赖 `{}` | 审查所有调用点 |
| 中间件性能 | 上下文管理器开销 | 基准测试验证 |

### 6.2 回滚计划

1. **Git 分支策略**: 在 feature branch 开发
2. **Feature Flag**: 通过配置开关新旧实现
3. **金丝雀部署**: 先在非关键路径测试

---

## 7. 实现示例

### 完整增强代码

见 `libs/contextVar_wrapper_enhanced.py`（待实现）

### 关键代码片段

```python
from contextvars import ContextVar, Token
from typing import Generic, TypeVar, Optional, Generator
from contextlib import contextmanager

T = TypeVar("T")

class ContextVarWrappers(Generic[T]):
    """
    通用请求上下文存储工具，类似 ThreadLocal
    基于 contextvars 实现，支持异步 FastAPI

    增强功能:
    - 安全的默认值处理
    - 类型安全的清理
    - 上下文管理器支持
    - 临时值设置
    """

    def __init__(self, context_var: ContextVar[T]):
        self._storage = context_var

    # 核心方法（增强）
    def set(self, value: T) -> Token[T]:
        """设置值，返回 token 用于恢复"""
        return self._storage.set(value)

    def get(self, default: Optional[T] = None) -> Optional[T]:
        """获取值，支持默认值"""
        try:
            return self._storage.get()
        except LookupError:
            return default

    def get_or_none(self) -> Optional[T]:
        """获取值或返回 None（推荐）"""
        return self.get(default=None)

    def get_or_raise(self) -> T:
        """获取值或抛出异常（显式）"""
        return self._storage.get()

    def has_value(self) -> bool:
        """检查是否已设置"""
        try:
            self._storage.get()
            return True
        except LookupError:
            return False

    def clear(self) -> None:
        """清除上下文（类型安全）"""
        # 使用 None 而不是 {}
        self._storage.set(None)  # type: ignore

    def reset(self, token: Token[T]) -> None:
        """使用 token 重置到之前的值"""
        self._storage.reset(token)

    # 上下文管理器
    @contextmanager
    def temporary_set(self, value: T) -> Generator[None, None, None]:
        """临时设置值，自动恢复"""
        token = self.set(value)
        try:
            yield
        finally:
            self.reset(token)

    def __enter__(self) -> "ContextVarWrappers[T]":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.clear()

    # 调试工具
    def __repr__(self) -> str:
        try:
            value = self._storage.get()
            name = getattr(self._storage, 'name', '<unnamed>')
            return f"<ContextVarWrappers({name}={value!r})>"
        except LookupError:
            name = getattr(self._storage, 'name', '<unnamed>')
            return f"<ContextVarWrappers({name}=<unset>)>"

    # 工厂方法
    @classmethod
    def create(cls, name: str, default: Optional[T] = None) -> "ContextVarWrappers[T]":
        """创建命名上下文变量"""
        context_var = ContextVar(name, default=default)
        return cls(context_var)
```

---

## 8. 后续优化

### 8.1 可选功能

- **类型验证**: 运行时检查 `set()` 的值类型
- **钩子系统**: 允许在 `set`/`get`/`clear` 时触发回调
- **监控集成**: 自动记录上下文变化到日志/指标

### 8.2 文档更新

- [ ] 更新 `CLAUDE.md` 添加上下文变量使用指南
- [ ] 添加 API 文档到 `docs/`
- [ ] 更新中间件示例代码

---

## 9. 总结

### 9.1 核心改进

1. ✅ **类型安全**: `clear()` 不再假设类型
2. ✅ **错误处理**: `get()` 支持默认值，避免崩溃
3. ✅ **自动清理**: 上下文管理器防止内存泄漏
4. ✅ **向后兼容**: 渐进式迁移，无破坏性变更

### 9.2 预期收益

- **可靠性**: 消除 `LookupError` 崩溃风险
- **可维护性**: 减少 50% 的上下文管理代码
- **调试体验**: 更好的错误信息和 repr

### 9.3 下一步行动

1. **立即**: 修复 `libs/context.py:46,58` 的 `get()` 调用
2. **本周**: 实现 Phase 1 核心功能
3. **下周**: 编写测试和迁移中间件
