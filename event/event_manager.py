import asyncio
import inspect
from typing import Callable, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar

from libs.contextVar_wrapper import ContextVarWrappers

event_manager_context: ContextVarWrappers['EventManager']=ContextVarWrappers(ContextVar("event_manager"))

class EventManager:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[..., Any]]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._executor = ThreadPoolExecutor(thread_name_prefix="EventManagerWorker")

    def subscribe(self, event: str):
        """装饰器: 注册事件回调"""
        def decorator(func: Callable[..., Any]):
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(func)
            return func
        return decorator

    async def emit(self, event: str, *args, **kwargs):
        """发布事件"""
        await self._queue.put((event, args, kwargs))

    async def _dispatch(self):
        """事件分发循环"""
        while self._running:
            event, args, kwargs = await self._queue.get()
            if event in self._subscribers:
                for callback in self._subscribers[event]:
                    if inspect.iscoroutinefunction(callback):
                        # 异步函数 → asyncio 直接调度
                        asyncio.create_task(callback(*args, **kwargs))
                    else:
                        # 同步函数 → 放到线程池执行
                        asyncio.get_running_loop().run_in_executor(
                            self._executor, lambda: callback(*args, **kwargs)
                        )
            self._queue.task_done()

    def start(self):
        """启动事件循环"""
        self._running = True
        asyncio.create_task(self._dispatch())

    async def stop(self):
        """停止事件循环"""
        self._running = False
        await self._queue.join()
        self._executor.shutdown(wait=True)