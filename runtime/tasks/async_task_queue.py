from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AsyncTaskJob:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


class AsyncTaskQueue:
    def __init__(
        self,
        *,
        name: str,
        worker_count: int = 1,
        maxsize: int = 0,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be greater than 0")
        if maxsize < 0:
            raise ValueError("maxsize must be greater than or equal to 0")

        self.name = name
        self.worker_count = worker_count
        self.maxsize = maxsize
        self._queue: asyncio.Queue[AsyncTaskJob | None] = asyncio.Queue(maxsize=maxsize)
        self._handlers: dict[str, Callable[..., Awaitable[Any] | Any]] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._started = False

    def register_handler(
        self,
        task_name: str,
        handler: Callable[..., Awaitable[Any] | Any],
    ) -> None:
        self._handlers[task_name] = handler

    async def start(self) -> None:
        if self._started:
            return

        self._started = True
        self._workers = [
            asyncio.create_task(self._worker_loop(worker_index), name=f"{self.name}-worker-{worker_index}")
            for worker_index in range(self.worker_count)
        ]

    async def stop(self) -> None:
        if not self._started:
            return

        await self._queue.join()
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False

    async def submit(self, task_name: str, **kwargs: Any) -> None:
        if not self._started:
            raise RuntimeError(f"async task queue {self.name} is not started")
        if task_name not in self._handlers:
            raise KeyError(f"task handler is not registered: {task_name}")
        try:
            self._queue.put_nowait(AsyncTaskJob(name=task_name, kwargs=kwargs))
        except asyncio.QueueFull as exc:
            raise RuntimeError(f"async task queue {self.name} is full") from exc

    async def _worker_loop(self, worker_index: int) -> None:
        while True:
            job = await self._queue.get()
            try:
                if job is None:
                    return
                await self._execute_job(job, worker_index=worker_index)
            finally:
                self._queue.task_done()

    async def _execute_job(self, job: AsyncTaskJob, *, worker_index: int) -> None:
        handler = self._handlers[job.name]
        try:
            result = handler(**job.kwargs)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "Async task queue %s worker %s failed to execute %s",
                self.name,
                worker_index,
                job.name,
            )
