import concurrent.futures
import contextlib


@contextlib.contextmanager
def get_completion_service_executor():
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=100, thread_name_prefix="completionService") as executor:
            yield executor
    finally:
        ...


@contextlib.contextmanager
def get_webMemo_service_executor():
    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=100, thread_name_prefix="webMemo_service_executor"
        ) as executor:
            yield executor
    finally:
        ...
