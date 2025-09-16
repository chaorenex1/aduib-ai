"""
Utility functions for cleaning up async HTTP clients to prevent resource leaks.
"""

import asyncio

from libs.cache import in_memory_llm_clients_cache


async def close_async_clients():
    """
    Close all cached async HTTP clients to prevent resource leaks.

    This function iterates through all cached clients in LLM's in-memory cache
    and closes any aiohttp client sessions that are still open.
    """
    # Import here to avoid circular import

    cache_dict = getattr(in_memory_llm_clients_cache, "cache_dict", {})

    for key, handler in cache_dict.items():
        if hasattr(handler, "client"):
            client = handler.client
            # Check if the httpx client has an aiohttp transport
            if hasattr(client, "_transport") and hasattr(client._transport, "aclose"):
                try:
                    await client._transport.aclose()
                except Exception:
                    # Silently ignore errors during cleanup
                    pass
            # Also close the httpx client itself
            if hasattr(client, "aclose") and not client.is_closed:
                try:
                    await client.aclose()
                except Exception:
                    # Silently ignore errors during cleanup
                    pass

        # Handle any other objects with aclose method
        elif hasattr(handler, "aclose"):
            try:
                await handler.aclose()
            except Exception:
                # Silently ignore errors during cleanup
                pass


def register_async_client_cleanup():
    """
    Register the async client cleanup function to run at exit.

    This ensures that all async HTTP clients are properly closed when the program exits.
    """
    import atexit

    def cleanup_wrapper():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the cleanup coroutine
                loop.create_task(close_async_clients())
            else:
                # Run the cleanup coroutine
                loop.run_until_complete(close_async_clients())
        except Exception:
            # If we can't get an event loop or it's already closed, try creating a new one
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(close_async_clients())
                loop.close()
            except Exception:
                # Silently ignore errors during cleanup
                pass

    atexit.register(cleanup_wrapper)
