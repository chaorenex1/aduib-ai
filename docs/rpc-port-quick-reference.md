# RPC端口管理 - 快速参考

## 使用方法

### 1. 在代码中使用端口工具

```python
from utils.port_utils import (
    is_port_in_use,
    find_free_port,
    get_free_port,
    get_local_ip,
    get_ip_and_free_port
)

# 检查端口是否被占用
if is_port_in_use(8080):
    print("Port 8080 is in use")

# 查找从50000开始的第一个可用端口
port = find_free_port(50000)

# 获取可用端口（如果50051可用则使用，否则查找替代）
port = get_free_port(preferred_port=50051)

# 获取本机IP
ip = get_local_ip()

# 一次性获取IP和端口
ip, port = get_ip_and_free_port(preferred_port=50051)
```

### 2. 配置RPC服务端口

编辑配置文件 `configs/app_config.py` 或环境变量：

```python
# 方式1: 指定首选端口（如果被占用会自动查找下一个）
RPC_SERVICE_PORT = 50051

# 方式2: 让系统自动分配
RPC_SERVICE_PORT = 0

# 方式3: 禁用自动端口分配（使用默认行为）
RPC_SERVICE_PORT = -1
```

### 3. RPC服务启动逻辑

RPC服务通过以下方式确保只启动一次：

```python
# 在 lifespan 中自动启动
async def lifespan(app: AduibAIApp) -> AsyncIterator[None]:
    # 启动RPC服务（单例模式，只会启动一次）
    _rpc_service_task = asyncio.create_task(run_service_register(app))
    
    yield None
    
    # 关闭时自动清理
```

### 4. 查看日志

启动应用后查看日志：

```bash
# 成功使用首选端口
INFO - Using preferred port: 50051
INFO - RPC service will use IP: 192.168.1.100, Port: 50051

# 首选端口被占用，使用替代端口
WARNING - Preferred port 50051 is in use, finding alternative...
INFO - Found free port: 50052
INFO - RPC service will use IP: 192.168.1.100, Port: 50052

# 服务已经启动，跳过重复启动
INFO - RPC service already started, skipping...
```

## 常见问题

### Q: 如何指定固定端口？
A: 在配置文件中设置 `RPC_SERVICE_PORT = 50051`（或你想要的端口号）

### Q: 如果指定的端口被占用会怎样？
A: 系统会自动查找下一个可用端口（最多尝试100个端口）

### Q: 如何让系统自动分配端口？
A: 设置 `RPC_SERVICE_PORT = 0`

### Q: RPC服务会重复启动吗？
A: 不会，使用单例模式确保只启动一次

### Q: 在Docker中运行需要特殊配置吗？
A: 不需要，端口工具完全兼容Docker环境

### Q: 如何测试端口工具？
A: 运行 `python tests/test_port_utils.py`

## 技术细节

### 端口查找策略
1. 优先使用配置的首选端口
2. 如果首选端口被占用，从首选端口+1开始查找
3. 最多尝试100个端口
4. 如果都失败，让操作系统自动分配端口

### 单例实现
- 使用 `asyncio.Lock()` 保证线程安全
- 使用全局标志位跟踪服务状态
- 启动失败时自动重置状态

### 跨平台兼容
- 使用Python标准库 `socket`
- 支持 Windows、Linux、macOS
- Docker容器环境完全兼容

## 相关文件

- `utils/port_utils.py` - 端口工具实现
- `app_factory.py` - RPC服务启动逻辑
- `tests/test_port_utils.py` - 功能测试
- `docs/rpc-port-management.md` - 详细文档

