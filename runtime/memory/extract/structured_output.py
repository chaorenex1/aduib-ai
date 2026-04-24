from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from service.memory.base.contracts import (
    ExtractedMemoryOperation,
    L0L1SummaryResult,
    MemoryOperationEvidence,
    OrchestratorAction,
    OrchestratorStateDelta,
    PlannerToolRequest,
)
from service.memory.base.enums import OrchestratorStep

from ..schema.registry import MemorySchemaRegistry, normalize_memory_type


def parse_step_action(
    *,
    step: OrchestratorStep,
    raw_text: str,
) -> OrchestratorAction:
    payload = _load_json_payload(raw_text)
    if step == OrchestratorStep.CHANGE_PLAN:
        tool_requests = _extract_tool_requests(payload)
        if tool_requests:
            return OrchestratorAction(action="request_tools", step=step, tool_requests=tool_requests)
        identified_memories = payload.get("identified_memories") or []
        change_plan = payload.get("change_plan") or []
        if not identified_memories and not change_plan:
            return OrchestratorAction(action="stop_noop")
        return OrchestratorAction(
            action="update_state",
            step=step,
            state_delta=OrchestratorStateDelta(
                identified_memories=identified_memories,
                change_plan=change_plan,
            ),
        )

    if step == OrchestratorStep.OPERATIONS:
        tool_requests = _extract_tool_requests(payload)
        if tool_requests:
            return OrchestratorAction(action="request_tools", step=step, tool_requests=tool_requests)
        operations = _normalize_operations_list(payload.get("operations") or [], MemorySchemaRegistry.load())
        return OrchestratorAction(
            action="update_state",
            step=step,
            state_delta=OrchestratorStateDelta(operations=operations),
        )

    tool_requests = _extract_tool_requests(payload)
    if tool_requests:
        return OrchestratorAction(action="request_tools", step=step, tool_requests=tool_requests)
    summary = L0L1SummaryResult.model_validate(payload)
    return OrchestratorAction(
        action="update_state",
        step=step,
        state_delta=OrchestratorStateDelta(summary_plan=[] if summary is None else [summary]),
    )


def _load_json_payload(raw_text: str) -> Any:
    text = str(raw_text or "").strip()
    if not text:
        return {}
    candidates = [text]
    for start, end in (("{", "}"), ("[", "]")):
        start_index = text.find(start)
        end_index = text.rfind(end)
        if start_index != -1 and end_index != -1 and end_index > start_index:
            candidates.append(text[start_index : end_index + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("planner output is not valid JSON")
def _normalize_operations_list(items: list[Any], registry: MemorySchemaRegistry) -> list[ExtractedMemoryOperation]:
    normalized: list[ExtractedMemoryOperation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        memory_type = normalize_memory_type(item.get("memory_type"))
        definition = registry.get(memory_type)
        if not definition:
            continue
        operation = str(item.get("op") or "write").strip().lower()
        if operation not in {"write", "edit", "delete"}:
            continue
        allowed_field_names = {field.name for field in definition.fields}
        raw_fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        fields = {key: value for key, value in raw_fields.items() if key in allowed_field_names}
        for key, value in item.items():
            if key in {"op", "memory_type", "fields", "content", "confidence", "evidence"}:
                continue
            if key in allowed_field_names:
                fields.setdefault(key, value)
        evidence = _normalize_evidence(item.get("evidence"))
        try:
            confidence = float(item.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        normalized.append(
            ExtractedMemoryOperation(
                op=operation,
                memory_type=memory_type,
                fields=fields,
                content=str(item.get("content") or ""),
                evidence=evidence,
                confidence=max(0.0, min(confidence, 1.0)),
            )
        )
    adapter = TypeAdapter(list[ExtractedMemoryOperation])
    return adapter.validate_python([item.model_dump(mode="python") for item in normalized])


def _normalize_evidence(value: Any) -> list[MemoryOperationEvidence]:
    if isinstance(value, str) and value.strip():
        return [MemoryOperationEvidence(kind="message", content=value.strip())]
    if not isinstance(value, list):
        return []

    evidence: list[MemoryOperationEvidence] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            evidence.append(MemoryOperationEvidence(kind="message", content=item.strip()))
        elif isinstance(item, dict):
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            evidence.append(
                MemoryOperationEvidence(
                    kind=str(item.get("kind") or "message").strip() or "message",
                    content=content,
                    path=str(item.get("path") or "").strip() or None,
                )
            )
    return evidence


def _normalize_tool_request(value: Any) -> PlannerToolRequest:
    if not isinstance(value, dict):
        raise ValueError("tool_requests entries must be objects")
    return PlannerToolRequest(
        tool=str(value.get("tool") or "").strip().lower(),
        args=value.get("args") if isinstance(value.get("args"), dict) else {},
    )


def _extract_tool_requests(payload: Any) -> list[PlannerToolRequest]:
    if isinstance(payload, dict) and isinstance(payload.get("tool_requests"), list):
        return [_normalize_tool_request(item) for item in payload.get("tool_requests") or []]
    return []
