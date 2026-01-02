import os
import sys

from .client_clenup import register_async_client_cleanup

# Avoid atexit asyncio loop manipulation under pytest, which can cause noisy
# "I/O operation on closed file" logging errors on Windows during interpreter shutdown.
_is_pytest = (
    os.environ.get("PYTEST_CURRENT_TEST") is not None
    or os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") is not None
    or any("pytest" in (arg or "") for arg in sys.argv)
)

if not _is_pytest:
    register_async_client_cleanup()

from .http_client import get_async_httpx_client, get_httpx_client

__all__ = ["get_httpx_client", "get_async_httpx_client"]
