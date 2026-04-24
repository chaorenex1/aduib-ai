from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from service.memory.base.contracts import (
    ChangePlanStepResult,
    ExtractedMemoryOperation,
    L0L1SummaryResult,
    MemoryChangePlanResult,
    MemoryOperationEvidence,
    MemoryOperationGenerationResult,
    PlannerToolRequest,
)

from ..schema.registry import MemorySchemaRegistry, normalize_memory_type

GROUPED_OUTPUT_KEYS = {
    "profile": "profile",
    "preferences": "preference",
    "events": "event",
    "entities": "entity",
    "tasks": "task",
    "verifications": "verification",
    "reviews": "review",
    "solutions": "solution",
    "patterns": "pattern",
    "tools": "tool",
    "skills": "skill",
    "runbooks": "runbook",
    "deployments": "deployment",
    "incidents": "incident",
    "rollbacks": "rollback",
}


def parse_planner_output(
    raw_text: str, registry: MemorySchemaRegistry
) -> tuple[list[ExtractedMemoryOperation], list[PlannerToolRequest]]:
    payload = _load_json_payload(raw_text)
    if isinstance(payload, dict) and isinstance(payload.get("tool_requests"), list):
        tool_requests = [_normalize_tool_request(item) for item in payload.get("tool_requests") or []]
        if tool_requests:
            return [], tool_requests
    operations = _extract_operations(payload=payload, registry=registry)
    return operations, []


def parse_memory_change_plan_output(raw_text: str) -> MemoryChangePlanResult:
    payload = _load_json_payload(raw_text)
    return MemoryChangePlanResult.model_validate(payload)


def parse_memory_change_plan_step_output(
    raw_text: str,
) -> ChangePlanStepResult:
    payload = _load_json_payload(raw_text)
    if isinstance(payload, dict) and isinstance(payload.get("tool_requests"), list):
        tool_requests = [_normalize_tool_request(item) for item in payload.get("tool_requests") or []]
        if tool_requests:
            return ChangePlanStepResult(tool_requests=tool_requests)
    return ChangePlanStepResult(change_plan=MemoryChangePlanResult.model_validate(payload))


def parse_memory_operation_generation_output(raw_text: str) -> MemoryOperationGenerationResult:
    payload = _load_json_payload(raw_text)
    normalized_operations = _normalize_operations_list(payload.get("operations") or [], MemorySchemaRegistry.load())
    return MemoryOperationGenerationResult(operations=normalized_operations)


def parse_memory_operation_step_output(
    raw_text: str,
) -> tuple[list[PlannerToolRequest], MemoryOperationGenerationResult]:
    payload = _load_json_payload(raw_text)
    tool_requests = _extract_tool_requests(payload)
    if tool_requests:
        return tool_requests, MemoryOperationGenerationResult()
    normalized_operations = _normalize_operations_list(payload.get("operations") or [], MemorySchemaRegistry.load())
    return [], MemoryOperationGenerationResult(operations=normalized_operations)


def parse_l0_l1_summary_output(raw_text: str) -> L0L1SummaryResult:
    payload = _load_json_payload(raw_text)
    return L0L1SummaryResult.model_validate(payload)


def parse_summary_step_output(
    raw_text: str,
) -> tuple[list[PlannerToolRequest], L0L1SummaryResult | None]:
    payload = _load_json_payload(raw_text)
    tool_requests = _extract_tool_requests(payload)
    if tool_requests:
        return tool_requests, None
    return [], L0L1SummaryResult.model_validate(payload)


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


def _extract_operations(payload: Any, registry: MemorySchemaRegistry) -> list[ExtractedMemoryOperation]:
    if isinstance(payload, dict) and isinstance(payload.get("operations"), list):
        return _normalize_operations_list(payload.get("operations") or [], registry)
    if isinstance(payload, dict):
        grouped_operations: list[dict[str, Any]] = []
        for key, memory_type in GROUPED_OUTPUT_KEYS.items():
            if key not in payload:
                continue
            value = payload.get(key)
            if isinstance(value, dict):
                grouped_operations.append({"op": "write", "memory_type": memory_type, **value})
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        grouped_operations.append({"op": "write", "memory_type": memory_type, **item})
        if grouped_operations:
            return _normalize_operations_list(grouped_operations, registry)
    return []


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
