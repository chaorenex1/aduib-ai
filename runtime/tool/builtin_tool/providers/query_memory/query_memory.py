from __future__ import annotations

import logging
from typing import Any

from runtime.agent_manager import AgentManager
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult

logger = logging.getLogger(__name__)


class QueryMemoryTool(BuiltinTool):
    """
    A tool to query agent memory.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            query = tool_parameters.get("query", "")
            user_id = tool_parameters.get("user_id", "")
            agent_manager: AgentManager = tool_parameters.get("agent_manager")
            short_term = tool_parameters.get("short_term", False)
            if not query:
                return ToolInvokeResult(name=self.entity.name, success=False, error="'query' is required")

            results = await agent_manager.memory_manager.retrieve_context(query=query, long_term_memory=not short_term)

            payload_results = results.get("long_term", []) if not short_term else results.get("short_term", [])
            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "query": query,
                    "total": len(payload_results),
                    "results": payload_results,
                },
                meta={
                    "message_id": message_id,
                    "user_id": user_id,
                },
            )
        except ValueError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
        except Exception as exc:
            logger.exception("Query memory failed")
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
