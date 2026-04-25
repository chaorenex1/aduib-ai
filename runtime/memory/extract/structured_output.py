from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from runtime.memory.base.contracts import (
    ExtractedMemoryFieldPlan,
    ExtractedMemoryOperation,
    L0L1SummaryResult,
    MemoryLineOperation,
    OrchestratorAction,
    OrchestratorStateDelta,
    PlannerToolRequest,
)
from runtime.memory.base.enums import OrchestratorStep

from ..schema.registry import MemorySchemaRegistry, normalize_memory_type


def parse_step_action(
    *,
    step: OrchestratorStep,
    raw_text: str,
) -> OrchestratorAction:
    payload = _load_json_payload(raw_text)
    if isinstance(payload, dict) and payload.get("action") is not None:
        return _normalize_explicit_action(OrchestratorAction.model_validate(payload))

    if step == OrchestratorStep.CHANGE_PLAN:
        tool_requests = _extract_tool_requests(payload)
        if tool_requests:
            return OrchestratorAction(action="request_tools", step=step, tool_requests=tool_requests)
        change_plan = payload.get("change_plan") or []
        if not change_plan:
            return OrchestratorAction(action="stop_noop")
        return OrchestratorAction(
            action="update_state",
            step=step,
            state_delta=OrchestratorStateDelta(
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
        field_plans = _normalize_field_plans(item.get("fields"), definition.fields)
        normalized.append(
            ExtractedMemoryOperation(
                memory_type=memory_type,
                target_branch=str(item.get("target_branch") or "").strip(),
                filename=str(item.get("filename") or "").strip(),
                reasoning=str(item.get("reasoning") or "").strip(),
                fields=field_plans,
            )
        )
    adapter = TypeAdapter(list[ExtractedMemoryOperation])
    return adapter.validate_python([item.model_dump(mode="python") for item in normalized])


def _normalize_field_plans(raw_fields: Any, schema_fields: list) -> list[ExtractedMemoryFieldPlan]:
    if not isinstance(raw_fields, list):
        raise ValueError("operations.fields must be a list")
    schema_merge_ops = {field.name: field.merge_op for field in schema_fields}
    normalized: list[ExtractedMemoryFieldPlan] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name not in schema_merge_ops:
            raise ValueError(f"operations field is not defined in schema: {name or '<empty>'}")
        merge_op = str(item.get("merge_op") or "").strip().lower()
        expected_merge_op = str(schema_merge_ops[name] or "").strip().lower()
        if merge_op != expected_merge_op:
            raise ValueError(f"operations field merge_op does not match schema: {name} {merge_op}")
        normalized.append(
            ExtractedMemoryFieldPlan(
                name=name,
                value=item.get("value"),
                merge_op=expected_merge_op,
                line_operations=_normalize_line_operations(item.get("line_operations")),
                reasoning=str(item.get("reasoning") or "").strip(),
            )
        )
    return normalized


def _normalize_line_operations(value: Any) -> list[MemoryLineOperation]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("field line_operations must be a list")
    return [MemoryLineOperation.model_validate(item) for item in value if isinstance(item, dict)]


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


def _normalize_explicit_action(action: OrchestratorAction) -> OrchestratorAction:
    if action.action != "update_state" or action.step is None or action.state_delta is None:
        return action

    if action.step == OrchestratorStep.CHANGE_PLAN:
        _ensure_only_fields(
            action,
            allowed_fields={"change_plan", "completed_steps"},
        )
        change_plan = action.state_delta.change_plan or []
        if not change_plan:
            return OrchestratorAction(action="stop_noop")
        return OrchestratorAction(
            action="update_state",
            step=action.step,
            state_delta=OrchestratorStateDelta(
                change_plan=change_plan,
                completed_steps=action.state_delta.completed_steps,
            ),
        )

    if action.step == OrchestratorStep.OPERATIONS:
        _ensure_only_fields(
            action,
            allowed_fields={"operations", "completed_steps"},
        )
        raw_operations = [
            item.model_dump(mode="python", exclude_none=True)
            for item in (action.state_delta.operations or [])
        ]
        normalized_operations = _normalize_operations_list(raw_operations, MemorySchemaRegistry.load())
        return OrchestratorAction(
            action="update_state",
            step=action.step,
            state_delta=OrchestratorStateDelta(
                operations=normalized_operations,
                completed_steps=action.state_delta.completed_steps,
            ),
        )

    _ensure_only_fields(
        action,
        allowed_fields={"summary_plan", "completed_steps"},
    )
    summary_plan = action.state_delta.summary_plan or []
    if not summary_plan:
        raise ValueError("summary update_state requires summary_plan")
    return OrchestratorAction(
        action="update_state",
        step=action.step,
        state_delta=OrchestratorStateDelta(
            summary_plan=summary_plan,
            completed_steps=action.state_delta.completed_steps,
        ),
    )


def _ensure_only_fields(action: OrchestratorAction, *, allowed_fields: set[str]) -> None:
    if action.state_delta is None:
        return
    provided = {
        key
        for key, value in action.state_delta.model_dump(mode="python", exclude_none=True).items()
        if value not in (None, [], {})
    }
    unexpected = sorted(provided - allowed_fields)
    if unexpected:
        raise ValueError(f"explicit {action.step} update_state contains unexpected fields: {', '.join(unexpected)}")
