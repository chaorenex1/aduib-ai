import asyncio
import threading
from concurrent import futures
from types import CoroutineType, FunctionType


class AsyncUtils:
    class AsyncUtils:
        @classmethod
        def run_async(cls, func_or_coro, *args, **kwargs):
            """
            使用线程池在独立事件循环中运行协程任务，
            主线程阻塞等待结果。
            """

            def run_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # 判断是协程对象还是函数
                    if isinstance(func_or_coro, CoroutineType):
                        coro = func_or_coro
                    elif isinstance(func_or_coro, FunctionType):
                        coro = func_or_coro(*args, **kwargs)
                    else:
                        raise TypeError("func_or_coro must be an async function or coroutine object")
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            # 在线程池中执行协程
            async_thread_pool = futures.ThreadPoolExecutor(thread_name_prefix="async_thread_pool")
            with async_thread_pool:
                future = async_thread_pool.submit(run_in_thread)
                return future.result()

    @classmethod
    def run_async_gen(cls, func_or_coro, *args, **kwargs):
        """
        使用线程池在独立事件循环中运行协程任务，
        主线程阻塞等待结果。
        """

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # # 判断是协程对象还是函数
                # if isinstance(func_or_coro, CoroutineType):
                #     coro = func_or_coro
                # elif isinstance(func_or_coro, FunctionType):
                #     coro = func_or_coro(*args, **kwargs)
                # else:
                #     raise TypeError("func_or_coro must be an async function or coroutine object")
                async def async_call():
                    if isinstance(func_or_coro, CoroutineType):
                        resp = await func_or_coro
                    elif isinstance(func_or_coro, FunctionType):
                        resp = func_or_coro(*args, **kwargs)
                    else:
                        raise TypeError("func_or_coro must be an async function or coroutine object")
                    # if hasattr(resp, '__aiter__'):
                    #     async for chunk in resp
                    #         yield chunk
                    #     resp = await resp.__anext__()
                    # return resp
                    return resp

                complete = loop.run_until_complete(async_call())
                if hasattr(complete, "__aiter__"):

                    async def iterate():
                        async for item in complete:
                            yield item

                    return iterate()
                else:
                    return complete
            finally:
                loop.close()

        # 在线程池中执行协程
        async_thread_pool = futures.ThreadPoolExecutor(thread_name_prefix="async_thread_pool")
        with async_thread_pool:
            future = async_thread_pool.submit(run_in_thread)
            return future.result()


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
