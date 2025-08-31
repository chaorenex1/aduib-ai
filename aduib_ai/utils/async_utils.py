import asyncio
import threading


class AsyncUtils:
    @classmethod
    def run_async(cls,coro):
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(coro)
        except RuntimeError:
            # 没有 loop，新建一个
            return asyncio.run(coro)
        else:
            # 有 loop，直接创建任务
            return loop.create_task(coro)

    @classmethod
    def get_or_create_event_loop(cls):
        """Gets or creates an event loop."""
        try:
            asyncio.create_task()
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop




class CountDownLatch:
    """A synchronization aid that allows one or more threads to wait until
    a set of operations being performed in other threads completes.
    """
    def __init__(self, count: int):
        self.count = count
        self.condition = threading.Condition()

    def count_down(self):
        with self.condition:
            self.count -= 1
            if self.count <= 0:
                self.condition.notify_all()

    def await_(self):
        with self.condition:
            while self.count > 0:
                self.condition.wait()
