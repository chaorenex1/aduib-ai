from __future__ import annotations

from pathlib import Path
from string import Formatter
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from service.memory.base.contracts import (
    ExtractedMemoryOperation,
    MemoryWritePipelineContext,
    PreparedExtractContext,
    ResolvedMemoryOperation,
)
from service.memory.base.paths import normalize_path_segment

from .schema.registry import MemorySchemaDefinition, MemorySchemaRegistry


def resolve_operations(context: MemoryWritePipelineContext) -> dict:
    prepared = PreparedExtractContext.model_validate(context.phase_results.get("prepare_extract_context") or {})
    extracted_payload = context.phase_results.get("extract_operations") or {}
    extracted_operations = [
        ExtractedMemoryOperation.model_validate(item) for item in extracted_payload.get("structured_operations") or []
    ]
    registry = MemorySchemaRegistry.load()
    resolved_operations = _resolve_all_operations(
        operations=extracted_operations,
        registry=registry,
        prepared=prepared,
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
    registry: MemorySchemaRegistry,
    prepared: PreparedExtractContext,
) -> list[ResolvedMemoryOperation]:
    grouped: dict[str, list[ResolvedMemoryOperation]] = {}
    for operation in operations:
        resolved = _resolve_single_operation(
            operation=operation, registry=registry, prepared=prepared, validate_existence=False
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
    registry: MemorySchemaRegistry,
    prepared: PreparedExtractContext,
    validate_existence: bool = True,
) -> ResolvedMemoryOperation:
    definition = registry.require(operation.memory_type)
    format_values = {
        "user_id": prepared.user_id or "",
        "agent_id": prepared.agent_id or "",
        "project_id": prepared.project_id or "",
    }
    format_values.update({key: _stringify_template_value(value) for key, value in operation.fields.items()})

    target_dir = _render_template(definition.directory, format_values, sanitize=False)
    target_name = _render_filename(definition, format_values)
    target_path = "/".join(part for part in [target_dir, target_name] if part)
    scoped_path = "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, target_path] if part)
    file_exists = storage_manager.exists(scoped_path)

    merge_strategy = (
        "delete" if operation.op == "delete" else ("template_fields" if definition.content_template else "patch")
    )
    resolved = ResolvedMemoryOperation(
        op=operation.op,
        memory_type=definition.memory_type,
        target_path=target_path,
        target_name=target_name,
        file_exists=file_exists,
        merge_strategy=merge_strategy,
        memory_mode=definition.memory_mode,
        fields=operation.fields,
        field_merge_ops=definition.field_merge_ops,
        content=operation.content,
        evidence=operation.evidence,
        confidence=operation.confidence,
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
    merged_content = ""
    merged_evidence = []
    max_confidence = 0.0
    file_exists = any(item.file_exists for item in items)
    for item in items:
        merged_fields.update(item.fields)
        if item.content:
            merged_content = item.content
        merged_evidence.extend(item.evidence)
        max_confidence = max(max_confidence, item.confidence)
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
        content=merged_content,
        evidence=merged_evidence,
        confidence=max_confidence,
        content_template=first.content_template,
        schema_path=first.schema_path,
    )


def _validate_resolved_existence(item: ResolvedMemoryOperation) -> None:
    if item.op in {"edit", "delete"} and not item.file_exists:
        raise ValueError(f"{item.op} requires existing target_path: {item.target_path}")


def _render_filename(definition: MemorySchemaDefinition, values: dict[str, str]) -> str:
    raw_name = _render_template(definition.filename_template, values, sanitize=False)
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
