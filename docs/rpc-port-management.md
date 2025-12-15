# RPC服务端口管理改进说明

## 问题描述
原有的RPC服务在启动时可能遇到以下问题：
1. 重复启动导致端口占用错误
2. 配置的端口已被占用时无法自动切换
3. 缺少跨平台兼容的端口管理工具

## 解决方案

### 1. 单例模式防止重复启动

在 `app_factory.py` 中实现了单例模式：

```python
# 全局状态管理
_rpc_service_started = False
_rpc_service_lock = asyncio.Lock()
_rpc_service_task: Optional[asyncio.Task] = None

async def run_service_register(app: AduibAIApp):
    """确保RPC服务只启动一次"""
    global _rpc_service_started
    
    async with _rpc_service_lock:
        if _rpc_service_started:
            log.info("RPC service already started, skipping...")
            return
        
        log.info("Starting RPC service registration...")
        _rpc_service_started = True
    
    try:
        # ... 启动逻辑 ...
    except Exception as e:
        # 启动失败时重置状态
        async with _rpc_service_lock:
            _rpc_service_started = False
        raise
```

**关键特性：**
- 使用 `asyncio.Lock()` 确保线程安全
- 使用全局标志位 `_rpc_service_started` 跟踪服务状态
- 启动失败时自动重置状态，允许重试

### 2. 智能端口查找

创建了新的工具模块 `utils/port_utils.py`，提供以下功能：

#### 2.1 检查端口是否被占用
```python
def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """检查端口是否已被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True
```

#### 2.2 查找可用端口
```python
def find_free_port(start_port: int, max_attempts: int = 100) -> Optional[int]:
    """从指定端口开始查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    return None
```

#### 2.3 获取可用端口（支持首选端口）
```python
def get_free_port(preferred_port: Optional[int] = None) -> int:
    """
    获取可用端口
    - 如果首选端口可用，使用首选端口
    - 如果首选端口被占用，查找下一个可用端口
    - 如果都失败，让操作系统分配端口
    """
```

#### 2.4 获取本机IP
```python
def get_local_ip() -> str:
    """
    获取本机IP地址（跨平台兼容）
    使用连接外部地址的方式确定本机IP
    """
```

### 3. 应用集成

在 `app_factory.py` 的 `run_service_register` 函数中集成：

```python
# 获取IP和确定RPC端口
preferred_port = config.RPC_SERVICE_PORT if config.RPC_SERVICE_PORT > 0 else None
ip, port = get_ip_and_free_port(preferred_port=preferred_port)

log.info(f"RPC service will use IP: {ip}, Port: {port}")
```

**工作流程：**
1. 检查配置的首选端口（`config.RPC_SERVICE_PORT`）
2. 如果首选端口可用，使用首选端口
3. 如果首选端口被占用，自动查找下一个可用端口（最多尝试100个）
4. 如果都失败，让操作系统自动分配端口

### 4. 生命周期管理

改进了 `lifespan` 函数，确保正确的启动和关闭：

```python
@contextlib.asynccontextmanager
async def lifespan(app: AduibAIApp) -> AsyncIterator[None]:
    global _rpc_service_task
    
    # 启动阶段
    _rpc_service_task = asyncio.create_task(run_service_register(app))
    
    yield None
    
    # 关闭阶段
    if _rpc_service_task and not _rpc_service_task.done():
        _rpc_service_task.cancel()
        try:
            await _rpc_service_task
        except asyncio.CancelledError:
            log.info("RPC service task cancelled")
        async with _rpc_service_lock:
            _rpc_service_started = False
```

## 跨平台兼容性

所有端口管理功能使用Python标准库 `socket`，完全兼容：
- ✅ Windows
- ✅ Linux
- ✅ macOS
- ✅ Docker容器环境

## 测试

运行测试脚本验证功能：

```bash
python tests/test_port_utils.py
```

测试包括：
1. 获取本机IP地址
2. 检查端口占用状态
3. 查找可用端口
4. 首选端口处理
5. 端口冲突自动解决

## 配置说明

在配置文件中设置RPC服务端口：

```python
# configs/app_config.py
RPC_SERVICE_PORT = 50051  # 首选端口，如果被占用会自动查找下一个可用端口
```

设置为 `0` 或负数将让系统自动分配端口：
```python
RPC_SERVICE_PORT = 0  # 让操作系统自动分配
```

## 日志输出示例

```
2025-12-16 01:54:00,837 - app_factory - INFO - Starting RPC service registration...
2025-12-16 01:54:00,837 - utils.port_utils - INFO - Using preferred port: 50051
2025-12-16 01:54:00,838 - app_factory - INFO - RPC service will use IP: 192.168.1.100, Port: 50051
2025-12-16 01:54:00,839 - app_factory - INFO - Registered RPC service: aduib-rpc at 192.168.1.100:50051
```

如果端口被占用：
```
2025-12-16 01:54:00,838 - utils.port_utils - WARNING - Preferred port 50051 is in use, finding alternative...
2025-12-16 01:54:00,838 - utils.port_utils - INFO - Found free port: 50052
2025-12-16 01:54:00,838 - app_factory - INFO - RPC service will use IP: 192.168.1.100, Port: 50052
```

## 其他改进

### service/web_memo.py
将 `NetUtils.get_ip_and_free_port()` 替换为只获取IP地址，因为该场景不需要动态端口：

```python
from utils.port_utils import get_local_ip

host = get_local_ip()
notify_url = f"http://{host}:{config.APP_PORT}/v1/web_memo/notify?api_key={api_key.hash_key}"
```

## 总结

通过这些改进：
1. ✅ **防止重复启动**：单例模式确保RPC服务只启动一次
2. ✅ **智能端口管理**：自动处理端口冲突，查找可用端口
3. ✅ **跨平台兼容**：使用标准库，支持所有主流操作系统
4. ✅ **清晰的日志**：详细记录端口选择过程
5. ✅ **优雅的关闭**：正确清理资源和重置状态

这些改进确保了应用在各种环境下都能稳定运行，避免了端口占用导致的启动失败问题。

