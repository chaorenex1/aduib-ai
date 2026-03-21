import hashlib
import json
import logging
from typing import Any, Optional

from models import ToolCallResult
from models.engine import get_db
from runtime.generator.generator import LLMGenerator
from runtime.tool.base.tool import Tool
from runtime.tool.base.tool_provider import ToolController
from runtime.tool.builtin_tool.tool_provider import BuiltinToolController
from runtime.tool.entities import ToolInvokeResult, ToolProviderType
from runtime.tool.mcp.tool_provider import McpToolController
from runtime.tool.skill.tool_provider import SKILLToolController
from utils import jsonable_encoder

logger = logging.getLogger(__name__)


class ToolManager:
    """
    ToolManager is responsible for managing tool providers and their controllers.
    """

    providers: dict[str, ToolController] = {}

    def __init__(self):
        self.providers = {ToolProviderType.BUILTIN: BuiltinToolController()}
        from libs.context import get_app_home

        self.providers[ToolProviderType.SKILL] = SKILLToolController(app_home=get_app_home())
        self.providers[ToolProviderType.LOCAL] = McpToolController()
        self.providers[ToolProviderType.MCP] = McpToolController()

    def get_builtin_tool_controller(self):
        return self.providers[ToolProviderType.BUILTIN]

    def get_skill_controller(self):
        return self.providers.get(ToolProviderType.SKILL)

    def get_tool_provider(self, tool_provider: str):
        return self.providers.get(ToolProviderType(tool_provider), None)

    @staticmethod
    def _cache_key(tool_name: str, arguments: dict) -> str:
        try:
            params = json.dumps(arguments, sort_keys=True)
        except Exception:
            params = arguments
        digest = hashlib.sha256(params.encode()).hexdigest()[:16]
        return f"tool_result:{tool_name}:{digest}"

    @staticmethod
    def _generate_tool_call_id(tool_name: str, arguments: str) -> str:
        return f"{tool_name}_{hashlib.sha256(arguments.encode()).hexdigest()[:16]}"

    def _llm_score_tools_slice(self, query: str, tools_slice: list[Tool]) -> list[str]:
        try:
            tool_schemas = [t.get_tool_schema() for t in tools_slice]
            texts: list[str] = LLMGenerator.choice_tool(query, tool_schemas)
            valid_names = {t.entity.name for t in tools_slice}
            return [n for n in texts if isinstance(n, str) and n in valid_names]
        except Exception as ex:
            logger.warning("Tool slice LLM scoring failed: %s", ex)
            return []

    def _llm_choice_tools_with_slicing(self, query: str, tools: list[Tool]) -> list[Tool]:
        from configs import config

        slice_size = config.TOOL_CHOICE_SLICE_SIZE
        max_workers = config.TOOL_CHOICE_SLICE_WORKERS
        if len(tools) <= slice_size:
            names = self._llm_score_tools_slice(query, tools)
        else:
            slices = [tools[i : i + slice_size] for i in range(0, len(tools), slice_size)]
            all_names: list[str] = []
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._llm_score_tools_slice, query, sl): sl for sl in slices}
                for future in as_completed(futures):
                    try:
                        all_names.extend(future.result())
                    except Exception as ex:
                        logger.warning("Tool slice scoring failed: %s", ex)
            seen: set[str] = set()
            names = []
            for n in all_names:
                if n not in seen:
                    seen.add(n)
                    names.append(n)
        name_set = set(names)
        return [t for t in tools if t.entity.name in name_set]

    async def llm_choice_tool(self, query: str) -> list[Tool]:
        if not query:
            return []
        if self.providers:
            result: list[Tool] = []
            for provider in self.providers.values():
                result.extend(self._llm_choice_tools_with_slicing(query, provider.get_tools()))
            return result
        else:
            return []

    def list_tool_providers(self) -> list[str]:
        """
        List all registered tool providers

        :return: list of tool provider types
        """
        return list(self.providers.keys())

    async def invoke_tool(
        self,
        tool_name: str,
        tool_arguments: dict[str, Any],
        tool_provider: str,
        tool_call_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> ToolInvokeResult | None:
        tool_controller: ToolController = self.get_tool_provider(tool_provider)
        if not tool_controller:
            return ToolInvokeResult(
                error=f"Tool provider {tool_provider} not found", success=False, tool_call_id=tool_call_id
            )

        tool = tool_controller.get_tool(tool_name)
        if not tool:
            return ToolInvokeResult(
                error=f"Tool {tool_name} not found in provider {tool_provider}",
                success=False,
                tool_call_id=tool_call_id,
            )

        from component.cache.redis_cache import redis_client
        from configs import config

        cache_key = None
        if config.TOOL_CACHE_ENABLED:
            cache_key = self._cache_key(tool_name, tool_arguments or "{}")
            cached = redis_client.get(cache_key)
            if cached is not None:
                logger.info("%Cache hit for tool {tool_name}")
                return ToolInvokeResult.model_validate_json(cached)

        call_result = ToolCallResult(
            message_id=message_id,
            tool_call_id=tool_call_id or self._generate_tool_call_id(tool_name, tool_arguments or "{}"),
            tool_call_name=tool_name,
            tool_call_args=json.dumps(tool_arguments, sort_keys=True) if tool_arguments else None,
            state="failed",
        )
        result: ToolInvokeResult
        try:
            tool_arguments["tool_manager"] = self
            result = next(await tool.invoke(tool_parameters=tool_arguments, message_id=message_id))
            if result and result.success:
                result.tool_call_id = tool_call_id or self._generate_tool_call_id(tool_name, tool_arguments or "{}")
                call_result.state = "success"
                call_result.result = json.dumps(jsonable_encoder(result, exclude_none=True))
                if cache_key is not None and result.data is not None:
                    redis_client.setex(cache_key, config.TOOL_CACHE_TTL, result.model_dump_json(exclude_none=True))
                logger.info("%Tool {tool_name} invoked successfully")
            else:
                call_result.state = "failed"
                logger.warning("%Tool {tool_name} invoked but returned no result.")
        except Exception as ex:
            logger.exception(f"Error invoking tool {tool_name}: {ex}")
            call_result.state = "failed"
            result = ToolInvokeResult(error=str(ex), success=False, tool_call_id=tool_call_id)

        with get_db() as session:
            existing_result = (
                session.query(ToolCallResult)
                .filter(
                    ToolCallResult.tool_call_id == call_result.tool_call_id,
                )
                .first()
            )
            if existing_result:
                existing_result.state = call_result.state
                existing_result.result = call_result.result
                session.add(existing_result)
                session.commit()
            else:
                session.add(call_result)
                session.commit()
        return result
