from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from runtime.memory.base.contracts import (
    ExtractedMemoryFieldPlan,
    ExtractedMemoryOperation,
    MemoryChangePlanItem,
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
    _reject_legacy_batch_fields(payload)
    if isinstance(payload, dict) and payload.get("action") is not None:
        return _normalize_explicit_action(OrchestratorAction.model_validate(payload))

    tool_requests = _extract_tool_requests(payload)
    if tool_requests:
        return OrchestratorAction(action="request_tools", step=step, tool_requests=tool_requests)

    if step == OrchestratorStep.CHANGE_PLAN:
        if payload.get("planning_complete") is True and payload.get("change_plan_item") is not None:
            raise ValueError("change_plan response cannot mix change_plan_item and planning_complete")
        if payload.get("planning_complete") is True:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(planning_complete=True),
            )
        if payload.get("change_plan_item") is not None:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    change_plan_item=_normalize_change_plan_item(payload.get("change_plan_item")),
                    supersedes_target_key=_normalize_optional_string(payload.get("supersedes_target_key")),
                ),
            )
        return OrchestratorAction(action="stop_noop")

    if payload.get("change_plan_item") is not None and payload.get("operation_item") is not None:
        raise ValueError("operations response cannot mix change_plan_item and operation_item")
    if payload.get("change_plan_item") is not None:
        return OrchestratorAction(
            action="update_state",
            step=OrchestratorStep.CHANGE_PLAN,
            state_delta=OrchestratorStateDelta(
                change_plan_item=_normalize_change_plan_item(payload.get("change_plan_item")),
                supersedes_target_key=_normalize_optional_string(payload.get("supersedes_target_key")),
            ),
        )
    if payload.get("operation_item") is None:
        raise ValueError("operations response requires operation_item or tool_requests")
    return OrchestratorAction(
        action="update_state",
        step=OrchestratorStep.OPERATIONS,
        state_delta=OrchestratorStateDelta(
            operation_item=_normalize_single_operation_item(payload.get("operation_item"), MemorySchemaRegistry.load())
        ),
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


def _reject_legacy_batch_fields(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    if payload.get("change_plan") is not None:
        raise ValueError("legacy batch change_plan output is not supported")
    if payload.get("operations") is not None:
        raise ValueError("legacy batch operations output is not supported")
    if payload.get("summary_plan") is not None:
        raise ValueError("summary output is not supported in extract orchestrator")


def _normalize_change_plan_item(value: Any) -> MemoryChangePlanItem:
    if not isinstance(value, dict):
        raise ValueError("change_plan_item must be an object")
    return MemoryChangePlanItem.model_validate(value)


def _normalize_single_operation_item(value: Any, registry: MemorySchemaRegistry) -> ExtractedMemoryOperation:
    if not isinstance(value, dict):
        raise ValueError("operation_item must be an object")
    memory_type = normalize_memory_type(value.get("memory_type"))
    definition = registry.get(memory_type)
    if not definition:
        raise ValueError(f"unsupported memory_type: {value.get('memory_type')}")
    field_plans = _normalize_field_plans(value.get("fields"), definition.fields)
    operation = ExtractedMemoryOperation(
        memory_type=memory_type,
        target_branch=str(value.get("target_branch") or "").strip(),
        filename=str(value.get("filename") or "").strip(),
        reasoning=str(value.get("reasoning") or "").strip(),
        fields=field_plans,
    )
    adapter = TypeAdapter(ExtractedMemoryOperation)
    return adapter.validate_python(operation.model_dump(mode="python"))


def _normalize_field_plans(raw_fields: Any, schema_fields: list) -> list[ExtractedMemoryFieldPlan]:
    if not isinstance(raw_fields, list):
        raise ValueError("operation_item.fields must be a list")
    schema_merge_ops = {field.name: field.merge_op for field in schema_fields}
    normalized: list[ExtractedMemoryFieldPlan] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name not in schema_merge_ops:
            raise ValueError(f"operation_item field is not defined in schema: {name or '<empty>'}")
        merge_op = str(item.get("merge_op") or "").strip().lower()
        expected_merge_op = str(schema_merge_ops[name] or "").strip().lower()
        if merge_op != expected_merge_op:
            raise ValueError(f"operation_item field merge_op does not match schema: {name} {merge_op}")
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


def _normalize_optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_explicit_action(action: OrchestratorAction) -> OrchestratorAction:
    if action.action != "update_state" or action.step is None or action.state_delta is None:
        return action

    if action.step == OrchestratorStep.CHANGE_PLAN:
        _ensure_only_fields(
            action,
            allowed_fields={"change_plan_item", "supersedes_target_key", "planning_complete"},
        )
        has_change_plan_item = action.state_delta.change_plan_item is not None
        has_planning_complete = action.state_delta.planning_complete is not None
        if has_change_plan_item and has_planning_complete:
            raise ValueError("change_plan update_state cannot mix change_plan_item and planning_complete")
        if not has_change_plan_item and not has_planning_complete:
            raise ValueError("change_plan update_state requires change_plan_item or planning_complete")
        return OrchestratorAction(
            action="update_state",
            step=action.step,
            state_delta=OrchestratorStateDelta(
                change_plan_item=action.state_delta.change_plan_item,
                supersedes_target_key=action.state_delta.supersedes_target_key,
                planning_complete=action.state_delta.planning_complete,
            ),
        )

    _ensure_only_fields(
        action,
        allowed_fields={"operation_item"},
    )
    if action.state_delta.operation_item is None:
        raise ValueError("operations update_state requires operation_item")
    normalized_operation = _normalize_single_operation_item(
        action.state_delta.operation_item.model_dump(mode="python", exclude_none=True),
        MemorySchemaRegistry.load(),
    )
    return OrchestratorAction(
        action="update_state",
        step=action.step,
        state_delta=OrchestratorStateDelta(operation_item=normalized_operation),
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
