# 504错误排查和监控指南

## 问题现象
应用启动一段时间后出现504超时错误。

## 已实施的修复

### 1. 数据库连接池优化
- ✅ 增加了 `pool_recycle=3600`（1小时回收连接）
- ✅ 增加了 `pool_pre_ping=True`（连接前验证）
- ✅ 增加了 `max_overflow=20`（允许临时增加连接）
- ✅ 增加了连接超时配置

### 2. 数据库会话管理
- ✅ 修复会话泄漏问题
- ✅ 自动提交和回滚事务
- ✅ 确保会话正确关闭

### 3. HTTP客户端配置
- ✅ 增加超时时间（5秒 → 5-10分钟）
- ✅ 细化超时配置（connect, read, write）
- ✅ 减少客户端缓存时间（1小时 → 30分钟）

### 4. Redis连接配置
- ✅ 增加连接超时和socket超时
- ✅ 启用健康检查
- ✅ 启用超时重试

### 5. 应用生命周期管理
- ✅ 增加关闭时的资源清理逻辑
- ✅ 正确停止事件管理器
- ✅ 关闭数据库连接池
- ✅ 清理HTTP客户端缓存

## 如何验证修复是否生效

### 1. 检查应用日志

启动时应看到：
```
INFO [app_factory.py] - Lifespan is starting
INFO [app_factory.py] - Event manager started
INFO [redis_cache.py] - Redis initialized successfully
INFO [snowflake_id.py] - Snowflake IDGenerator initialized
```

关闭时应看到：
```
INFO [app_factory.py] - Application is shutting down, cleaning up resources...
INFO [app_factory.py] - Event manager stopped
INFO [app_factory.py] - Database connections closed
INFO [app_factory.py] - HTTP client cache cleared
INFO [app_factory.py] - Application shutdown complete
```

### 2. 监控数据库连接池

在代码中添加监控：
```python
from models.engine import engine

# 检查连接池状态
pool = engine.pool
print(f"Pool size: {pool.size()}")
print(f"Checked in: {pool.checkedin()}")
print(f"Overflow: {pool.overflow()}")
print(f"Checked out: {pool.checkedout()}")
```

正常情况下：
- `checkedin` 应该接近 `size`（连接被归还）
- `overflow` 应该较小（临时连接数少）
- `checkedout` 应该较小（活跃连接数少）

### 3. 测试Redis连接

```python
from component.cache.redis_cache import redis_client

# 测试连接
try:
    redis_client.ping()
    print("Redis connection OK")
except Exception as e:
    print(f"Redis connection failed: {e}")
```

### 4. 监控HTTP请求

查看日志中的请求处理时间：
```
INFO [context.py] - Process time: XXX.XX ms
```

如果处理时间突然增加或出现大量超时，说明可能还有问题。

## 如果问题仍然存在

### 1. 检查数据库服务器

```sql
-- PostgreSQL
-- 查看当前连接数
SELECT count(*) FROM pg_stat_activity;

-- 查看最大连接数
SHOW max_connections;

-- 查看慢查询
SELECT pid, now() - query_start as duration, query 
FROM pg_stat_activity 
WHERE state = 'active' 
ORDER BY duration DESC;
```

### 2. 检查Redis服务器

```bash
# 检查Redis连接数
redis-cli INFO clients

# 检查慢查询
redis-cli SLOWLOG GET 10
```

### 3. 增加更详细的日志

在 `configs/logging` 中调整日志级别：
```python
# 临时开启调试模式
DEBUG = True

# 或者只针对特定模块
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
logging.getLogger('httpx').setLevel(logging.DEBUG)
```

### 4. 调整配置参数

如果问题仍然存在，可能需要调整：

**数据库连接池**（`models/engine.py`）：
```python
pool_size=100,          # 增加连接池大小
max_overflow=50,        # 增加溢出连接数
pool_recycle=1800,      # 减少回收时间（30分钟）
```

**HTTP超时**（`runtime/clients/httpx_client/http_client.py`）：
```python
timeout=900.0,    # 增加到15分钟
read=900.0,       # 增加读取超时
```

**Redis超时**（`component/cache/redis_cache.py`）：
```python
socket_timeout=10,              # 增加超时时间
health_check_interval=15,       # 减少健康检查间隔
```

### 5. 检查网络配置

- 检查负载均衡器超时设置（如Nginx、ALB等）
- 检查防火墙规则
- 检查网络连接稳定性

### 6. 检查系统资源

```bash
# Linux
top              # 查看CPU和内存使用
netstat -an      # 查看网络连接状态
lsof -i          # 查看打开的网络连接

# Windows
tasklist         # 查看进程
netstat -an      # 查看网络连接
```

### 7. 性能分析

使用Python profiler分析性能瓶颈：
```python
import cProfile
import pstats

# 分析特定函数
profiler = cProfile.Profile()
profiler.enable()
# ... 执行代码 ...
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## 常见504原因及解决方案

| 原因 | 症状 | 解决方案 |
|------|------|----------|
| 数据库连接池耗尽 | 请求堆积，数据库操作超时 | ✅ 已修复：增加pool_size和max_overflow |
| 数据库连接过期 | 长时间空闲后第一次请求失败 | ✅ 已修复：pool_pre_ping和pool_recycle |
| HTTP客户端超时 | 外部API调用失败 | ✅ 已修复：增加超时时间 |
| Redis连接阻塞 | 缓存操作卡住 | ✅ 已修复：增加超时配置 |
| 会话泄漏 | 内存和连接数持续增长 | ✅ 已修复：正确关闭会话 |
| 长时间运行的请求 | LLM调用超时 | ✅ 已修复：增加read timeout |
| 负载均衡器超时 | Nginx等返回504 | 需检查：增加upstream超时 |
| 网络问题 | 间歇性超时 | 需检查：网络配置 |

## 推荐的监控指标

1. **应用指标**：
   - 请求响应时间（P50, P95, P99）
   - 错误率（4xx, 5xx）
   - 并发请求数

2. **数据库指标**：
   - 连接池使用率
   - 查询响应时间
   - 慢查询数量

3. **Redis指标**：
   - 连接数
   - 命令响应时间
   - 内存使用率

4. **系统指标**：
   - CPU使用率
   - 内存使用率
   - 网络I/O
   - 磁盘I/O

## 联系支持

如果以上方法都无法解决问题，请收集以下信息：
1. 完整的错误日志（包括堆栈跟踪）
2. 系统资源使用情况
3. 数据库和Redis的连接状态
4. 网络配置信息
5. 问题复现步骤

