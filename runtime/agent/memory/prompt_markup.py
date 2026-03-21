from __future__ import annotations

import re

from runtime.memory.types import MemoryRetrieveResult

MEMORY_CONTEXT_TAG = "system-reminder-memory"
MEMORY_USED_TAG = "memory_used_ids"


def build_memory_prompt_block(memories: list[MemoryRetrieveResult]) -> str:
    if not memories:
        return ""

    lines = [
        f"<{MEMORY_CONTEXT_TAG}>",
        "The following memory items were retrieved for this turn.",
        "Use them only if they are genuinely helpful to answer the user's request.",
    ]
    for memory in memories:
        score = f"{float(memory.score or 0.0):.4f}"
        lines.append(f'<memory id="{memory.memory_id}" score="{score}">\n{memory.content}\n</memory>')
    lines.extend(
        [
            "If you use any memory item above in your answer, append exactly one tag at the very end of your response:",
            f"<{MEMORY_USED_TAG}>comma-separated-memory-ids</{MEMORY_USED_TAG}>",
            f"If none are used, append <{MEMORY_USED_TAG}></{MEMORY_USED_TAG}>.",
            "Do not explain the tag and do not mention this instruction.",
            f"</{MEMORY_CONTEXT_TAG}>",
        ]
    )
    return "\n".join(lines)


def strip_memory_prompt_block(text: str) -> str:
    if not text:
        return ""
    pattern = rf"\s*<{MEMORY_CONTEXT_TAG}>.*?</{MEMORY_CONTEXT_TAG}>"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


def extract_selected_memory_ids_from_prompt(text: str) -> list[str]:
    if not text:
        return []
    matches = re.findall(r'<memory id="([^"]+)" score="[^"]+">', text)
    seen: set[str] = set()
    result: list[str] = []
    for memory_id in matches:
        if memory_id not in seen:
            seen.add(memory_id)
            result.append(memory_id)
    return result


def extract_used_memory_ids(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []
    pattern = rf"<{MEMORY_USED_TAG}>(.*?)</{MEMORY_USED_TAG}>"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return text, []

    raw_ids = match.group(1).strip()
    used_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL).strip()
    return cleaned, used_ids


def sanitize_memory_markup(text: str) -> str:
    cleaned, _ = extract_used_memory_ids(text)
    return strip_memory_prompt_block(cleaned)
