from typing import Any

from aduib_rpc.server.rpc_execution.service_call import client


@client("aduib_mcp_server-jsonrpc", stream=True)
class CrawlService:
    """Crawl Service for handling crawl requests."""

    async def crawl(self, urls: list[str], query: str = None) -> dict[str, Any]:
        # Implement crawling logic here
        ...

    async def web_search(self, web_content: str) -> list[str]:
        """Perform web search using multiple search engines concurrently."""
        ...
