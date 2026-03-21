"""
Shared utilities for protocol conversion.
Used by all converter modules (_openai_anthropic.py, _openai_responses.py, etc.)
"""

from __future__ import annotations

from typing import Any, Union


def extract_text_content(content: Union[str, list, None]) -> str:
    """Extract plain text from any content format (str, list of blocks, etc.)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("data") or ""
                if text:
                    parts.append(str(text))
            elif hasattr(item, "text") and item.text:
                parts.append(str(item.text))
            elif hasattr(item, "data") and item.data:
                parts.append(str(item.data))
        return "".join(parts)
    return str(content)


def normalize_tool_schema(schema: Any) -> Any:
    """
    Recursively clean a JSON Schema for cross-provider compatibility.
    Removes format:'uri' and recurses into nested schema keywords.
    """
    if not isinstance(schema, (dict, list)):
        return schema
    if isinstance(schema, list):
        return [normalize_tool_schema(item) for item in schema]

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "format" and value == "uri":
            continue
        elif key in ("properties", "$defs", "definitions") and isinstance(value, dict):
            result[key] = {k: normalize_tool_schema(v) for k, v in value.items()}
        elif key == "items":
            result[key] = normalize_tool_schema(value)
        elif key in ("anyOf", "allOf", "oneOf") and isinstance(value, list):
            result[key] = [normalize_tool_schema(v) for v in value]
        elif key == "additionalProperties" and isinstance(value, dict):
            result[key] = normalize_tool_schema(value)
        else:
            result[key] = value
    return result


STOP_REASON_OPENAI_TO_ANTHROPIC: dict[str, str] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "stop_sequence",
}

STOP_REASON_ANTHROPIC_TO_OPENAI: dict[str, str] = {v: k for k, v in STOP_REASON_OPENAI_TO_ANTHROPIC.items()}


def map_stop_reason_to_anthropic(finish_reason: str | None) -> str:
    return STOP_REASON_OPENAI_TO_ANTHROPIC.get(finish_reason or "", "end_turn")


def map_stop_reason_to_openai(stop_reason: str | None) -> str:
    return STOP_REASON_ANTHROPIC_TO_OPENAI.get(stop_reason or "", "stop")


def openai_tool_choice_to_anthropic(tool_choice: str | dict | None) -> str | dict | None:
    """Convert OpenAI tool_choice to Anthropic format.

    "none"     -> {"type": "none"}
    "auto"     -> {"type": "auto"}
    "required" -> {"type": "any"}
    {"type": "function", "function": {"name": "fn"}} -> {"type": "tool", "name": "fn"}
    """
    if tool_choice is None:
        return None
    if tool_choice == "none":
        return {"type": "none"}
    if tool_choice == "auto":
        return {"type": "auto"}
    if tool_choice == "required":
        return {"type": "any"}
    if isinstance(tool_choice, dict):
        fn_name = (tool_choice.get("function") or {}).get("name")
        if fn_name:
            return {"type": "tool", "name": fn_name}
    return {"type": "auto"}


def anthropic_tool_choice_to_openai(tool_choice: str | dict | object | None) -> str | dict | None:
    """Convert Anthropic tool_choice to OpenAI format.

    {"type":"auto"} -> "auto"
    {"type":"any"}  -> "required"
    {"type":"none"} -> "none"
    {"type":"tool","name":"fn"} -> {"type":"function","function":{"name":"fn"}}
    """
    if tool_choice is None:
        return None
    if isinstance(tool_choice, dict):
        tc = tool_choice
    elif hasattr(tool_choice, "model_dump"):
        tc = tool_choice.model_dump()
    else:
        tc = {"type": str(tool_choice)}

    t = tc.get("type", "auto")
    if t == "auto":
        return "auto"
    if t == "any":
        return "required"
    if t == "none":
        return "none"
    if t == "tool":
        name = tc.get("name")
        if name:
            return {"type": "function", "function": {"name": name}}
    return "auto"
