from __future__ import annotations

import json
import logging
from typing import Any

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.model_manager import ModelManager
from service.memory.base.contracts import MemoryWritePipelineContext, PreparedExtractContext

from ..schema.registry import MemorySchemaRegistry
from .structured_output import parse_planner_output
from .tools import SUPPORTED_PLANNER_TOOLS, execute_planner_tool

logger = logging.getLogger(__name__)

EXTRACT_PLANNER_SYSTEM_PROMPT = """You are the planner for the memory write pipeline.

You receive normalized source material, relevant prefetched memory context, and the allowed memory schemas.
Return either:
1. a JSON object with {"operations": [...]} using only write/edit/delete operations, or
2. a JSON object with {"tool_requests": [...]} to ask for bounded read-only tools (`ls`, `read`, `find`).

Rules:
- Use only supported memory_type values from the provided schema registry.
- `write` and `edit` operations must include meaningful `content`.
- Put identifier fields into `fields`, not inside the filename or path.
- Evidence should cite short excerpts from the source material or fetched files.
- Do not invent arbitrary filesystem paths.
- Output JSON only.
"""


def extract_operations(context: MemoryWritePipelineContext) -> dict:
    prepared = PreparedExtractContext.model_validate(context.phase_results.get("prepare_extract_context") or {})
    registry = MemorySchemaRegistry.load()
    prompt_messages = _build_initial_prompt(prepared=prepared, registry=registry)

    tool_results: list[dict[str, Any]] = []
    tools_used: list[dict[str, Any]] = []
    last_error: str | None = None
    for _ in range(2):
        raw_response = _invoke_planner_model(messages=prompt_messages, prepared=prepared, registry=registry)
        if not raw_response:
            break
        try:
            operations, tool_requests = parse_planner_output(raw_response, registry)
        except Exception as exc:
            last_error = str(exc)
            logger.warning("extract_operations: planner output parse failed: %s", exc)
            break

        if tool_requests:
            for request in tool_requests:
                result = execute_planner_tool(request["tool"], request["args"])
                tool_entry = {"tool": request["tool"], "args": request["args"], "result": result}
                tool_results.append(tool_entry)
                tools_used.append(tool_entry)
            prompt_messages = _build_followup_prompt(
                prepared=prepared,
                registry=registry,
                tool_results=tool_results,
            )
            continue

        structured_operations = [item.model_dump(mode="python", exclude_none=True) for item in operations]
        return {
            "task_id": context.task_id,
            "phase": "extract_operations",
            "planner_status": "planned",
            "structured_operations": structured_operations,
            "tools_available": list(SUPPORTED_PLANNER_TOOLS),
            "tools_used": tools_used,
        }

    return {
        "task_id": context.task_id,
        "phase": "extract_operations",
        "planner_status": "planner_unavailable" if last_error is None else "planner_failed",
        "structured_operations": [],
        "tools_available": list(SUPPORTED_PLANNER_TOOLS),
        "tools_used": tools_used,
        "planner_error": last_error,
    }


def _build_initial_prompt(*, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> list:
    user_payload = {
        "task_id": prepared.task_id,
        "source_kind": prepared.source_kind,
        "messages": prepared.messages,
        "text_blocks": prepared.text_blocks,
        "prefetched_context": prepared.prefetched_context,
        "allowed_schemas": registry.summary(),
    }
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=EXTRACT_PLANNER_SYSTEM_PROMPT),
        UserPromptMessage(role=PromptMessageRole.USER, content=json.dumps(user_payload, ensure_ascii=False, indent=2)),
    ]


def _build_followup_prompt(
    *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry, tool_results: list[dict[str, Any]]
) -> list:
    payload = {
        "task_id": prepared.task_id,
        "source_kind": prepared.source_kind,
        "messages": prepared.messages,
        "text_blocks": prepared.text_blocks,
        "prefetched_context": prepared.prefetched_context,
        "tool_results": tool_results,
        "allowed_schemas": registry.summary(),
    }
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=EXTRACT_PLANNER_SYSTEM_PROMPT),
        UserPromptMessage(role=PromptMessageRole.USER, content=json.dumps(payload, ensure_ascii=False, indent=2)),
    ]


def _invoke_planner_model(*, messages: list, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> str:
    try:
        model_manager = ModelManager()
        model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance("llm")
    except Exception as exc:
        logger.warning("extract_operations: planner model unavailable: %s", exc)
        return ""
    if model_instance is None:
        return ""

    request = ChatCompletionRequest(
        model=model_instance.model,
        messages=messages,
        temperature=0.0,
        stream=False,
    )
    response = model_instance.invoke_llm_sync(
        prompt_messages=request,
        user=prepared.user_id,
    )
    return str(response.message.content or "").strip()
