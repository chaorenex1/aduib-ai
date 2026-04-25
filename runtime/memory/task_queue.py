from __future__ import annotations

import logging

from configs import config
from libs.context import app_context
from runtime.tasks.async_task_queue import AsyncTaskQueue
from service.memory.base.builders import MEMORY_WRITE_TASK_NAME

logger = logging.getLogger(__name__)

MEMORY_WRITE_TASK_QUEUE_EXTENSION = "memory_write_task_queue"


class MemoryWriteTaskQueueRuntime:
    @classmethod
    async def start(cls, app) -> AsyncTaskQueue:
        queue = app.extensions.get(MEMORY_WRITE_TASK_QUEUE_EXTENSION)
        if queue is not None:
            return queue

        worker_count = max(1, int(getattr(config, "MEMORY_WRITE_QUEUE_WORKERS", 1)))
        maxsize = max(1, int(getattr(config, "MEMORY_WRITE_QUEUE_MAXSIZE", 1000)))
        queue = AsyncTaskQueue(
            name="memory-write",
            worker_count=worker_count,
            maxsize=maxsize,
        )
        queue.register_handler(MEMORY_WRITE_TASK_NAME, cls._execute_memory_write_task)
        await queue.start()
        app.extensions[MEMORY_WRITE_TASK_QUEUE_EXTENSION] = queue
        logger.info("Memory write async queue started with %s worker(s)", worker_count)
        return queue

    @classmethod
    async def stop(cls, app) -> None:
        queue = app.extensions.pop(MEMORY_WRITE_TASK_QUEUE_EXTENSION, None)
        if queue is None:
            return

        await queue.stop()
        logger.info("Memory write async queue stopped")

    @classmethod
    async def enqueue(cls, *, task_id: str) -> None:
        queue = cls._get_queue()
        await queue.submit(MEMORY_WRITE_TASK_NAME, task_id=task_id)

    @classmethod
    def _get_queue(cls) -> AsyncTaskQueue:
        app = app_context.get()
        if app is None:
            raise RuntimeError("app context is unavailable for memory write task queue")

        queue = app.extensions.get(MEMORY_WRITE_TASK_QUEUE_EXTENSION)
        if queue is None:
            raise RuntimeError("memory write task queue is not initialized")
        return queue

    @staticmethod
    async def _execute_memory_write_task(*, task_id: str) -> None:
        from runtime.memory.write_state_machine import MemoryStateMachineRuntime

        await MemoryStateMachineRuntime.execute_memory_write_task(task_id)
