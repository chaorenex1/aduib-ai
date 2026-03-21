from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import anyio


def run_async(coro_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
    """Run an async callable from sync code.

    This is a small wrapper around anyio.run/anyio.from_thread.run.

    It avoids calling anyio.run() from an existing event loop and provides
    a single place to adapt behavior across environments.
    """

    try:
        return anyio.run(coro_fn, *args, **kwargs)
    except RuntimeError:
        return anyio.from_thread.run(coro_fn, *args, **kwargs)
