# ContextVarWrapper 使用示例

实用的代码示例，展示如何在不同场景下使用增强版 `ContextVarWrapper`。

---

## 基础用法

### 创建上下文变量

```python
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

# 方法 1: 使用工厂方法（推荐）
user_ctx = ContextVarWrapper.create("user_id", default=None)

# 方法 2: 手动创建
from contextvars import ContextVar
user_ctx = ContextVarWrapper(ContextVar("user_id"))

# 方法 3: 字典类型专用
from libs.contextVar_wrapper_enhanced import DictContextVar
request_data_ctx = DictContextVar.create("request_data")
```

### 设置和获取值

```python
# 设置值
user_ctx.set("user123")

# 获取值（多种方式）
user_id = user_ctx.get()                      # 返回值或 None
user_id = user_ctx.get(default="anonymous")   # 自定义默认值
user_id = user_ctx.get_or_none()              # 明确返回 None
user_id = user_ctx.get_or_raise()             # 不存在则抛出异常

# 检查是否存在
if user_ctx.has_value():
    user_id = user_ctx.get()
```

### 清除值

```python
# 清除上下文
user_ctx.clear()

# 验证已清除
assert user_ctx.get_or_none() is None
```

---

## 中间件模式

### FastAPI 中间件

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
import uuid

app = FastAPI()

# 创建上下文变量
request_id_ctx = ContextVarWrapper.create("request_id")
user_ctx = ContextVarWrapper.create("current_user")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求设置唯一 ID 和用户信息"""

    async def dispatch(self, request: Request, call_next):
        # 生成请求 ID
        request_id = str(uuid.uuid4())

        # 从 header 提取用户信息
        user_id = request.headers.get("X-User-ID", "anonymous")

        # 使用临时设置，自动清理
        with request_id_ctx.temporary_set(request_id):
            with user_ctx.temporary_set(user_id):
                # 添加到响应头
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response


# 在路由中使用
@app.get("/profile")
async def get_profile():
    request_id = request_id_ctx.get()
    user_id = user_ctx.get()
    return {
        "request_id": request_id,
        "user_id": user_id,
        "message": "Profile data"
    }
```

### 嵌套上下文管理

```python
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

tenant_ctx = ContextVarWrapper.create("tenant_id")
org_ctx = ContextVarWrapper.create("organization_id")
project_ctx = ContextVarWrapper.create("project_id")


class MultiTenantMiddleware(BaseHTTPMiddleware):
    """多租户上下文管理"""

    async def dispatch(self, request: Request, call_next):
        # 从请求提取租户信息
        tenant = extract_tenant(request)
        org = extract_organization(request)
        project = extract_project(request)

        # 嵌套上下文
        with tenant_ctx.temporary_set(tenant.id):
            with org_ctx.temporary_set(org.id):
                with project_ctx.temporary_set(project.id):
                    return await call_next(request)


# 在业务逻辑中使用
def save_document(doc_data):
    """保存文档，自动添加租户/组织/项目信息"""
    document = Document(
        **doc_data,
        tenant_id=tenant_ctx.get(),
        organization_id=org_ctx.get(),
        project_id=project_ctx.get()
    )
    db.session.add(document)
    db.session.commit()
```

---

## 日志和追踪

### 结构化日志上下文

```python
import logging
from libs.contextVar_wrapper_enhanced import DictContextVar

# 使用字典类型存储日志上下文
log_ctx = DictContextVar.create("log_context")


class StructuredLoggingFilter(logging.Filter):
    """将上下文信息注入日志记录"""

    def filter(self, record):
        # 从上下文获取额外信息
        context = log_ctx.get_or_none() or {}
        for key, value in context.items():
            setattr(record, key, value)
        return True


# 配置日志
logger = logging.getLogger(__name__)
logger.addFilter(StructuredLoggingFilter())


# 中间件设置日志上下文
class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 设置初始上下文
        log_ctx.set({
            "request_id": str(uuid.uuid4()),
            "path": request.url.path,
            "method": request.method,
        })

        try:
            response = await call_next(request)

            # 添加响应信息
            log_ctx.set_item("status_code", response.status_code)

            return response
        finally:
            log_ctx.clear()


# 在业务代码中添加上下文
def process_order(order_id):
    # 添加业务相关信息到日志上下文
    log_ctx.update(
        order_id=order_id,
        operation="process_order"
    )

    logger.info("Processing order")  # 自动包含所有上下文信息

    # 动态添加更多上下文
    log_ctx.set_item("payment_method", "credit_card")
    logger.info("Payment processed")
```

### 分布式追踪

```python
from libs.contextVar_wrapper_enhanced import ContextVarWrapper
import opentelemetry.trace as trace

# 存储当前 span
span_ctx = ContextVarWrapper.create("current_span")


def with_span(operation_name):
    """装饰器：为函数创建追踪 span"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(operation_name) as span:
                # 保存 span 到上下文
                with span_ctx.temporary_set(span):
                    return await func(*args, **kwargs)
        return wrapper
    return decorator


# 使用示例
@with_span("database_query")
async def fetch_user(user_id: str):
    # 可以从上下文获取当前 span 添加额外信息
    span = span_ctx.get_or_none()
    if span:
        span.set_attribute("user_id", user_id)

    # 执行数据库查询
    result = await db.query(f"SELECT * FROM users WHERE id = {user_id}")
    return result
```

---

## 数据库会话管理

### SQLAlchemy 会话上下文

```python
from sqlalchemy.orm import Session
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

# 存储数据库会话
db_session_ctx = ContextVarWrapper.create("db_session")


class DatabaseSessionMiddleware(BaseHTTPMiddleware):
    """为每个请求创建数据库会话"""

    async def dispatch(self, request: Request, call_next):
        # 创建会话
        session = SessionLocal()

        try:
            # 设置到上下文
            with db_session_ctx.temporary_set(session):
                response = await call_next(request)
                # 请求成功，提交事务
                session.commit()
                return response
        except Exception as e:
            # 发生错误，回滚
            session.rollback()
            raise
        finally:
            session.close()


# 在服务层获取会话
def get_current_session() -> Session:
    """获取当前请求的数据库会话"""
    session = db_session_ctx.get_or_none()
    if session is None:
        raise RuntimeError("No database session in current context")
    return session


# 业务代码
def create_user(username: str, email: str):
    session = get_current_session()
    user = User(username=username, email=email)
    session.add(user)
    # 会话会在中间件中自动提交或回滚
    return user
```

---

## 权限和认证

### 基于上下文的权限检查

```python
from typing import Optional
from libs.contextVar_wrapper_enhanced import ContextVarWrapper, DictContextVar

# 存储当前用户和权限
current_user_ctx = ContextVarWrapper.create("current_user")
permissions_ctx = DictContextVar.create("permissions")


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """认证和权限中间件"""

    async def dispatch(self, request: Request, call_next):
        # 从 JWT token 提取用户
        user = await extract_user_from_token(request)

        if user:
            # 加载用户权限
            user_permissions = await load_user_permissions(user.id)

            with current_user_ctx.temporary_set(user):
                with permissions_ctx.temporary_set(user_permissions):
                    return await call_next(request)
        else:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )


# 权限检查辅助函数
def require_permission(permission: str):
    """装饰器：要求特定权限"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not has_permission(permission):
                raise PermissionDenied(f"Required permission: {permission}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def has_permission(permission: str) -> bool:
    """检查当前用户是否有权限"""
    perms = permissions_ctx.get_or_none() or {}
    return permission in perms


def get_current_user():
    """获取当前用户"""
    user = current_user_ctx.get_or_none()
    if user is None:
        raise RuntimeError("No authenticated user in context")
    return user


# 使用示例
@app.delete("/users/{user_id}")
@require_permission("users.delete")
async def delete_user(user_id: str):
    current_user = get_current_user()
    logger.info(f"User {current_user.id} deleting user {user_id}")
    # ... 删除逻辑 ...
```

---

## 测试工具

### 测试上下文设置

```python
import pytest
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

user_ctx = ContextVarWrapper.create("user")


# Pytest fixture
@pytest.fixture
def with_user_context():
    """为测试提供用户上下文"""
    test_user = User(id="test123", username="testuser")

    with user_ctx.temporary_set(test_user):
        yield test_user

    # 自动清理


# 使用 fixture
def test_user_profile(with_user_context):
    # 上下文自动设置
    profile = get_user_profile()
    assert profile["username"] == "testuser"


# 自定义测试上下文管理器
class TestContext:
    """测试环境上下文管理器"""

    def __init__(self, **contexts):
        self.contexts = contexts
        self.tokens = []

    def __enter__(self):
        for ctx_var, value in self.contexts.items():
            token = ctx_var.set(value)
            self.tokens.append((ctx_var, token))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for ctx_var, token in reversed(self.tokens):
            ctx_var.reset(token)


# 使用自定义上下文
def test_with_multiple_contexts():
    with TestContext(
        user_ctx=User(id="test"),
        tenant_ctx="tenant123",
        org_ctx="org456"
    ):
        # 所有上下文都已设置
        assert user_ctx.get().id == "test"
        assert tenant_ctx.get() == "tenant123"
```

---

## 缓存和性能优化

### 基于上下文的缓存

```python
from functools import wraps
from libs.contextVar_wrapper_enhanced import DictContextVar

# 请求级缓存
request_cache_ctx = DictContextVar.create("request_cache")


def request_cached(key_func=None):
    """装饰器：在请求范围内缓存函数结果"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"

            # 尝试从缓存获取
            cached_value = request_cache_ctx.get_item(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            request_cache_ctx.set_item(cache_key, result)

            return result
        return wrapper
    return decorator


# 中间件初始化缓存
class RequestCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 为每个请求创建空缓存
        with request_cache_ctx.temporary_set({}):
            return await call_next(request)


# 使用缓存装饰器
@request_cached(key_func=lambda user_id: f"user:{user_id}")
async def get_user_expensive(user_id: str):
    """耗时操作，在同一请求中只执行一次"""
    await asyncio.sleep(1)  # 模拟耗时
    return {"id": user_id, "name": "User"}


# 在同一请求中多次调用
async def process_request():
    user1 = await get_user_expensive("123")  # 执行查询
    user2 = await get_user_expensive("123")  # 从缓存返回
    assert user1 is user2  # 相同对象
```

---

## 异步任务隔离

### Celery/后台任务

```python
from celery import Celery
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

tenant_ctx = ContextVarWrapper.create("tenant_id")
app = Celery("tasks")


@app.task
def process_data(tenant_id: str, data: dict):
    """后台任务，需要租户上下文"""
    # 在任务中设置上下文
    with tenant_ctx.temporary_set(tenant_id):
        # 业务逻辑可以访问上下文
        result = process_tenant_data(data)
        return result


def process_tenant_data(data: dict):
    """需要租户上下文的业务逻辑"""
    tenant_id = tenant_ctx.get()
    logger.info(f"Processing data for tenant {tenant_id}")
    # ... 处理逻辑 ...
```

### AsyncIO 任务

```python
import asyncio
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

request_ctx = ContextVarWrapper.create("request_id")


async def background_task():
    """后台任务继承父任务的上下文"""
    request_id = request_ctx.get_or_none()
    if request_id:
        logger.info(f"Background task for request {request_id}")


async def handle_request(request_id: str):
    """处理请求并启动后台任务"""
    with request_ctx.temporary_set(request_id):
        # 启动后台任务（会继承上下文）
        asyncio.create_task(background_task())

        # 主逻辑
        await process_request()
```

---

## 调试和监控

### 上下文快照

```python
from libs.contextVar_wrapper_enhanced import ContextVarWrapper

# 多个上下文变量
user_ctx = ContextVarWrapper.create("user")
request_ctx = ContextVarWrapper.create("request_id")
tenant_ctx = ContextVarWrapper.create("tenant")


def get_context_snapshot() -> dict:
    """获取所有上下文的快照（用于调试）"""
    return {
        "user": user_ctx.get_or_none(),
        "request_id": request_ctx.get_or_none(),
        "tenant": tenant_ctx.get_or_none(),
    }


# 错误处理中记录上下文
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    context_snapshot = get_context_snapshot()

    logger.error(
        f"Unhandled exception: {exc}",
        extra={"context": context_snapshot},
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": context_snapshot.get("request_id")
        }
    )
```

### 性能监控

```python
import time
from libs.contextVar_wrapper_enhanced import DictContextVar

# 存储性能指标
metrics_ctx = DictContextVar.create("metrics")


class PerformanceMiddleware(BaseHTTPMiddleware):
    """收集请求性能指标"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 初始化指标
        metrics_ctx.set({
            "request_start": start_time,
            "db_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        })

        try:
            response = await call_next(request)

            # 计算总耗时
            duration = time.time() - start_time
            metrics = metrics_ctx.get()

            # 添加到响应头
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            response.headers["X-DB-Queries"] = str(metrics["db_queries"])

            # 记录慢请求
            if duration > 1.0:
                logger.warning(
                    f"Slow request: {request.url.path}",
                    extra={"metrics": metrics, "duration": duration}
                )

            return response
        finally:
            metrics_ctx.clear()


# 在数据库层增加计数
def execute_query(sql: str):
    metrics_ctx.update(db_queries=metrics_ctx.get_item("db_queries", 0) + 1)
    # ... 执行查询 ...
```

---

## 最佳实践

### 1. 命名约定

```python
# ✅ 好的命名
user_context = ContextVarWrapper.create("current_user")
request_id_ctx = ContextVarWrapper.create("request_id")
db_session_ctx = ContextVarWrapper.create("db_session")

# ❌ 不好的命名
ctx1 = ContextVarWrapper.create("ctx")
data = ContextVarWrapper.create("d")
```

### 2. 使用类型提示

```python
from typing import Optional
from models import User

user_ctx: ContextVarWrapper[Optional[User]] = ContextVarWrapper.create("user")

def get_current_user() -> User:
    user = user_ctx.get_or_none()
    if user is None:
        raise RuntimeError("No user in context")
    return user
```

### 3. 避免过度使用

```python
# ❌ 不要滥用上下文传递函数参数
def process(data):
    config = config_ctx.get()  # 不好
    # ...

# ✅ 显式传递更清晰
def process(data, config):
    # ...

# ✅ 上下文适合跨层传递的横切关注点
def log_operation():
    request_id = request_id_ctx.get()  # 好，日志上下文
    logger.info(f"[{request_id}] Operation completed")
```

### 4. 文档化上下文依赖

```python
def save_document(doc_data: dict) -> Document:
    """
    保存文档到数据库。

    依赖上下文:
        - tenant_ctx: 租户 ID（必需）
        - user_ctx: 当前用户（必需）
        - db_session_ctx: 数据库会话（可选，如有则使用）

    Args:
        doc_data: 文档数据

    Returns:
        保存的文档对象

    Raises:
        RuntimeError: 如果缺少必需的上下文
    """
    tenant_id = tenant_ctx.get_or_raise()
    user = user_ctx.get_or_raise()
    session = db_session_ctx.get_or_none() or SessionLocal()

    # ... 实现 ...
```

---

## 总结

增强版 `ContextVarWrapper` 提供：

- ✅ **类型安全** - 不再假设类型
- ✅ **自动清理** - 上下文管理器防止泄漏
- ✅ **灵活访问** - 多种获取方法适应不同场景
- ✅ **调试友好** - 清晰的 repr 和命名
- ✅ **异步安全** - 完全支持 asyncio

选择合适的模式并遵循最佳实践，让你的代码更健壮、更易维护！
