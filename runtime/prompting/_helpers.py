from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.section import PromptSection


def compact_text(value: object) -> str:
    text = str(value or "").strip()
    return text


def dump_data(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return "\n".join(f"- {key}: {dump_data(item)}" for key, item in value.items() if item not in (None, "", [], {}))
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        rendered: list[str] = []
        for item in value:
            item_text = dump_data(item)
            if item_text:
                rendered.append(f"- {item_text}")
        return "\n".join(rendered)
    return (
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
        if isinstance(value, (list, dict))
        else str(value)
    )


def build_section(
    *,
    section_id: str,
    title: str,
    channel: str,
    cache_policy: str,
    content: object,
    source: str,
    activation_reason: str | None = None,
    dynamic_variables: dict[str, object] | None = None,
) -> PromptSection | None:
    text = compact_text(dump_data(content))
    if not text:
        return None
    return PromptSection(
        section_id=section_id,
        title=title,
        channel=channel,
        cache_policy=cache_policy,
        content=text,
        source=source,
        activation_reason=activation_reason,
        dynamic_variables=dynamic_variables or {},
    )


def build_attachment(
    *,
    attachment_id: str,
    attachment_type: str,
    content: object,
    source: str,
    priority: int = 0,
    dedupe_key: str | None = None,
    activation_reason: str | None = None,
    dynamic_variables: dict[str, object] | None = None,
) -> PromptAttachment | None:
    text = compact_text(dump_data(content))
    if not text:
        return None
    return PromptAttachment(
        attachment_id=attachment_id,
        attachment_type=attachment_type,
        content=text,
        source=source,
        priority=priority,
        dedupe_key=dedupe_key,
        activation_reason=activation_reason,
        dynamic_variables=dynamic_variables or {},
    )


def get_extra(context: Any, key: str, default: Any = None) -> Any:
    return getattr(context, "extra", {}).get(key, default)
