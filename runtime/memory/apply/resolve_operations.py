from __future__ import annotations

from pathlib import Path
from string import Formatter
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.base.contracts import (
    ExtractedMemoryFieldPlan,
    ExtractedMemoryOperation,
    MemoryChangePlanItem,
    MemoryWritePipelineContext,
    PlannerToolUseResult,
    PreparedExtractContext,
    ResolvedMemoryOperation,
)
from runtime.memory.schema.registry import MemorySchemaDefinition, MemorySchemaRegistry
from service.memory.base.paths import normalize_path_segment


def resolve_operations(context: MemoryWritePipelineContext) -> dict:
    prepared = PreparedExtractContext.model_validate(context.phase_results.get("prepare_extract_context") or {})
    extracted_payload = context.phase_results.get("extract_operations") or {}
    change_plan = [MemoryChangePlanItem.model_validate(item) for item in extracted_payload.get("change_plan") or []]
    extracted_operations = [
        ExtractedMemoryOperation.model_validate(item) for item in extracted_payload.get("structured_operations") or []
    ]
    planned_operations = _validate_operations_match_change_plan(
        change_plan=change_plan,
        operations=extracted_operations,
    )
    registry = MemorySchemaRegistry.load()
    resolved_operations = _resolve_all_operations(
        operations=extracted_operations,
        planned_operations=planned_operations,
        registry=registry,
        prepared=prepared,
    )
    _validate_edit_operations_have_prior_reads(
        resolved_operations=resolved_operations,
        prepared=prepared,
        tools_used=extracted_payload.get("tools_used") or [],
    )
    navigation_scopes = sorted({str(Path(item.target_path).parent).replace("\\", "/") for item in resolved_operations})
    metadata_scopes = sorted(
        {
            item.target_path.split("/", 3)[0] + "/" + item.target_path.split("/", 3)[1]
            for item in resolved_operations
            if "/" in item.target_path
        }
    )
    return {
        "task_id": context.task_id,
        "phase": "resolve_operations",
        "resolved_operations": [item.model_dump(mode="python", exclude_none=True) for item in resolved_operations],
        "navigation_scopes": navigation_scopes,
        "metadata_scopes": metadata_scopes,
    }


def _resolve_all_operations(
    *,
    operations: list[ExtractedMemoryOperation],
    planned_operations: dict[tuple[str, str, str], MemoryChangePlanItem],
    registry: MemorySchemaRegistry,
    prepared: PreparedExtractContext,
) -> list[ResolvedMemoryOperation]:
    grouped: dict[str, list[ResolvedMemoryOperation]] = {}
    for operation in operations:
        resolved = _resolve_single_operation(
            operation=operation,
            planned_item=planned_operations[(operation.memory_type, operation.target_branch, operation.filename)],
            registry=registry,
            prepared=prepared,
            validate_existence=False,
        )
        grouped.setdefault(resolved.target_path, []).append(resolved)

    merged: list[ResolvedMemoryOperation] = []
    for target_path, items in grouped.items():
        op_kinds = {item.op for item in items}
        if "delete" in op_kinds and len(op_kinds) > 1:
            raise ValueError(f"conflicting operations for target_path: {target_path}")
        merged_item = _merge_resolved_operations(items)
        _validate_resolved_existence(merged_item)
        merged.append(merged_item)
    return merged


def _resolve_single_operation(
    *,
    operation: ExtractedMemoryOperation,
    planned_item: MemoryChangePlanItem,
    registry: MemorySchemaRegistry,
    prepared: PreparedExtractContext,
    validate_existence: bool = True,
) -> ResolvedMemoryOperation:
    definition = registry.require(operation.memory_type)
    format_values = _schema_format_values(prepared=prepared, field_plans=operation.fields)
    target_dir = _render_template(definition.directory, format_values, sanitize=False)
    target_name = _normalize_filename(operation.filename)
    if target_dir != operation.target_branch:
        raise ValueError(
            "operation target_branch does not match schema directory: "
            f"{operation.memory_type} {operation.target_branch}"
        )
    expected_filename = _render_filename(definition, format_values)
    if expected_filename != target_name:
        raise ValueError(
            f"operation filename does not match schema template: {operation.memory_type} {operation.filename}"
        )
    target_path = "/".join(part for part in [target_dir, target_name] if part)
    scoped_path = "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, target_path] if part)
    file_exists = storage_manager.exists(scoped_path)

    merge_strategy = (
        "delete" if planned_item.op == "delete" else ("template_fields" if definition.content_template else "patch")
    )
    field_values = _field_values_map(operation.fields)
    resolved = ResolvedMemoryOperation(
        op=planned_item.op,
        memory_type=definition.memory_type,
        target_path=target_path,
        target_name=target_name,
        file_exists=file_exists,
        merge_strategy=merge_strategy,
        memory_mode=definition.memory_mode,
        fields={key: value for key, value in field_values.items() if key != "content"},
        field_merge_ops={key: value for key, value in definition.field_merge_ops.items() if key != "content"},
        field_plans=operation.fields,
        content=str(field_values.get("content") or ""),
        content_template=definition.content_template,
        schema_path=definition.path,
    )
    if validate_existence:
        _validate_resolved_existence(resolved)
    return resolved


def _merge_resolved_operations(items: list[ResolvedMemoryOperation]) -> ResolvedMemoryOperation:
    if len(items) == 1:
        return items[0]

    first = items[0]
    if all(item.op == "delete" for item in items):
        return first

    merged_fields: dict[str, Any] = {}
    merged_field_plans: list[ExtractedMemoryFieldPlan] = []
    merged_content = ""
    file_exists = any(item.file_exists for item in items)
    for item in items:
        merged_fields.update(item.fields)
        merged_field_plans.extend(item.field_plans)
        if item.content:
            merged_content = item.content
    merged_op = "edit" if file_exists or any(item.op == "edit" for item in items) else "write"
    return ResolvedMemoryOperation(
        op=merged_op,
        memory_type=first.memory_type,
        target_path=first.target_path,
        target_name=first.target_name,
        file_exists=file_exists,
        merge_strategy=first.merge_strategy,
        memory_mode=first.memory_mode,
        fields=merged_fields,
        field_merge_ops=first.field_merge_ops,
        field_plans=merged_field_plans,
        content=merged_content,
        content_template=first.content_template,
        schema_path=first.schema_path,
    )


def _validate_resolved_existence(item: ResolvedMemoryOperation) -> None:
    if item.op in {"edit", "delete"} and not item.file_exists:
        raise ValueError(f"{item.op} requires existing target_path: {item.target_path}")


def _validate_edit_operations_have_prior_reads(
    *,
    resolved_operations: list[ResolvedMemoryOperation],
    prepared: PreparedExtractContext,
    tools_used: list[dict[str, Any]],
) -> None:
    observed_read_paths = prepared.prefetched_read_paths()
    observed_read_paths.update(_tool_read_paths(tools_used))
    for operation in resolved_operations:
        if operation.op != "edit":
            continue
        if operation.target_path not in observed_read_paths:
            raise ValueError(f"edit requires prior read of target_path: {operation.target_path}")


def _validate_operations_match_change_plan(
    *,
    change_plan: list[MemoryChangePlanItem],
    operations: list[ExtractedMemoryOperation],
) -> dict[tuple[str, str, str], MemoryChangePlanItem]:
    executable_plan = {
        (item.memory_type, item.target_branch, item.filename): item
        for item in change_plan
        if item.op in {"write", "edit", "delete"}
    }
    for operation in operations:
        key = (operation.memory_type, operation.target_branch, operation.filename)
        planned = executable_plan.get(key)
        if planned is None:
            target_path = f"{operation.target_branch}/{operation.filename}"
            raise ValueError(f"operation target does not match change_plan: {operation.memory_type} {target_path}")
    return executable_plan


def _tool_read_paths(items: list[dict[str, Any]]) -> set[str]:
    read_paths: set[str] = set()
    for item in items:
        try:
            tool_result = PlannerToolUseResult.model_validate(item)
        except Exception:
            continue
        if tool_result.tool != "read":
            continue
        result_path = str((tool_result.result or {}).get("path") or "").strip()
        args_path = str((tool_result.args or {}).get("path") or "").strip()
        if result_path:
            read_paths.add(result_path)
        if args_path:
            read_paths.add(args_path)
    return read_paths


def _render_filename(definition: MemorySchemaDefinition, values: dict[str, str]) -> str:
    raw_name = _render_template(definition.filename_template, values, sanitize=False)
    stem, suffix = Path(raw_name).stem, Path(raw_name).suffix or ".md"
    if raw_name == "profile.md":
        return raw_name
    return f"{normalize_path_segment(stem)}{suffix}"


def _normalize_filename(filename: str) -> str:
    raw_name = str(filename or "").strip().replace("\\", "/")
    stem, suffix = Path(raw_name).stem, Path(raw_name).suffix or ".md"
    if raw_name == "profile.md":
        return raw_name
    return f"{normalize_path_segment(stem)}{suffix}"


def _render_template(template: str, values: dict[str, str], *, sanitize: bool) -> str:
    required = [field_name for _, field_name, _, _ in Formatter().parse(template) if field_name]
    missing = [field_name for field_name in required if not str(values.get(field_name) or "").strip()]
    if missing:
        raise ValueError(f"missing fields for template rendering: {', '.join(missing)}")
    rendered = template.format(**values)
    return normalize_path_segment(rendered) if sanitize else rendered.replace("\\", "/")


def _stringify_template_value(value: Any) -> str:
    return str(value or "").strip()


def _schema_format_values(
    *,
    prepared: PreparedExtractContext,
    field_plans: list[ExtractedMemoryFieldPlan],
) -> dict[str, str]:
    format_values = {
        "user_id": prepared.user_id or "",
        "agent_id": prepared.agent_id or "",
        "project_id": prepared.project_id or "",
    }
    format_values.update({plan.name: _stringify_template_value(plan.value) for plan in field_plans})
    return format_values


def _field_values_map(field_plans: list[ExtractedMemoryFieldPlan]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for plan in field_plans:
        values[plan.name] = plan.value
    return values
