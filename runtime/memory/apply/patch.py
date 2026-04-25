from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

import yaml

from runtime.memory.base.contracts import PreparedExtractContext, ResolvedMemoryOperation


def build_desired_document(
    *,
    task_id: str,
    prepared: PreparedExtractContext,
    operation: ResolvedMemoryOperation,
    current_content: str | None,
) -> str:
    current_text = str(current_content or "")
    if operation.op == "edit" and _has_line_operations(operation):
        current_text = _apply_field_line_operations(current_text, operation)
    current_metadata, current_body = parse_markdown_document(current_content or "")
    if current_text != str(current_content or ""):
        current_metadata, current_body = parse_markdown_document(current_text)
    merged_fields = _merge_fields(operation=operation, current_metadata=current_metadata)
    body = _merge_body(operation=operation, current_body=current_body, merged_fields=merged_fields)
    metadata = _build_document_metadata(
        task_id=task_id,
        prepared=prepared,
        operation=operation,
        current_metadata=current_metadata,
        merged_fields=merged_fields,
    )
    return serialize_markdown_document(metadata=metadata, body=body)


def parse_markdown_document(content: str) -> tuple[dict[str, Any], str]:
    text = str(content or "")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    body = match.group(2).strip()
    return metadata if isinstance(metadata, dict) else {}, body


def serialize_markdown_document(*, metadata: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
    normalized_body = str(body or "").strip()
    return f"---\n{frontmatter}\n---\n\n{normalized_body}\n"


def compute_content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _merge_fields(*, operation: ResolvedMemoryOperation, current_metadata: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    line_operation_fields = {plan.name for plan in operation.field_plans if plan.line_operations}
    field_names = set(operation.field_merge_ops) | set(operation.fields) | line_operation_fields
    for field_name in sorted(field_names):
        if field_name == "content":
            continue
        if field_name in line_operation_fields:
            merged[field_name] = current_metadata.get(field_name)
            continue
        merge_op = operation.field_merge_ops.get(field_name, "patch")
        old_value = current_metadata.get(field_name)
        new_value = operation.fields.get(field_name)
        merged[field_name] = _merge_value(old_value=old_value, new_value=new_value, merge_op=merge_op)
    return merged


def _merge_body(*, operation: ResolvedMemoryOperation, current_body: str, merged_fields: dict[str, Any]) -> str:
    if operation.op == "delete":
        return ""
    content_field_has_line_ops = any(plan.name == "content" and plan.line_operations for plan in operation.field_plans)
    if content_field_has_line_ops:
        return current_body
    if operation.memory_mode == "template" and operation.content_template:
        render_values = {**merged_fields, **_derive_template_values(merged_fields)}
        return operation.content_template.format(**render_values).strip()
    return _patch_text(current_body, operation.content)


def _build_document_metadata(
    *,
    task_id: str,
    prepared: PreparedExtractContext,
    operation: ResolvedMemoryOperation,
    current_metadata: dict[str, Any],
    merged_fields: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    title = str(
        current_metadata.get("title")
        or merged_fields.get("title")
        or merged_fields.get("topic")
        or merged_fields.get("tool_name")
        or operation.target_name.rsplit(".", 1)[0].replace("-", " ")
    ).strip()
    metadata = {
        "schema_version": current_metadata.get("schema_version", 1),
        "kind": operation.memory_type,
        "memory_id": current_metadata.get("memory_id")
        or _build_memory_id(task_id=task_id, target_path=operation.target_path),
        "user_id": prepared.user_id,
        "agent_id": prepared.agent_id,
        "project_id": prepared.project_id,
        "title": title,
        "created_at": current_metadata.get("created_at") or now,
        "updated_at": now,
        "source": current_metadata.get("source") or {"type": "derived", "trace": task_id},
        "visibility": current_metadata.get("visibility") or "internal",
        "status": current_metadata.get("status") or "active",
    }
    if current_metadata.get("tags") or operation.memory_type:
        metadata["tags"] = current_metadata.get("tags") or [operation.memory_type]
    for key, value in merged_fields.items():
        if value is not None and value != "":
            metadata[key] = value
    return metadata


def _build_memory_id(*, task_id: str, target_path: str) -> str:
    digest = hashlib.sha256(f"{task_id}:{target_path}".encode()).hexdigest()
    return f"mem_{digest[:16]}"


def _merge_value(*, old_value: Any, new_value: Any, merge_op: str) -> Any:
    if merge_op == "immutable":
        return old_value if old_value not in (None, "", [], {}) else new_value
    if merge_op == "sum":
        return int(old_value or 0) + int(new_value or 0)
    if merge_op == "replace":
        return old_value if new_value is None else new_value
    if isinstance(new_value, str) or isinstance(old_value, str):
        return _patch_text(str(old_value or ""), str(new_value or ""))
    return new_value if new_value is not None else old_value


def _patch_text(current_text: str, patch_text: str) -> str:
    current = str(current_text or "").strip()
    patch = str(patch_text or "").strip()
    if not patch:
        return current
    if not current:
        return patch
    if patch in current:
        return current
    return f"{current}\n\n{patch}".strip()


def _has_line_operations(operation: ResolvedMemoryOperation) -> bool:
    return any(plan.line_operations for plan in operation.field_plans)


def _apply_field_line_operations(text: str, operation: ResolvedMemoryOperation) -> str:
    updated_text = str(text or "")
    all_operations = [
        line_operation
        for plan in operation.field_plans
        for line_operation in plan.line_operations
    ]
    for line_operation in _sort_line_operations(all_operations):
        updated_text = _apply_single_line_operation(updated_text, line_operation)
    return updated_text


def _sort_line_operations(line_operations: list) -> list:
    def _sort_key(item) -> tuple[int, int]:
        start = item.start_line or 10**9
        return (-start, 0 if item.kind in {"replace_range", "delete_range"} else 1)

    return sorted(line_operations, key=_sort_key)


def _apply_single_line_operation(text: str, line_operation) -> str:
    lines = str(text or "").splitlines()
    kind = line_operation.kind
    if kind == "append_eof":
        appended = str(line_operation.new_text or "").rstrip()
        if not appended:
            return text
        return "\n".join(lines + appended.splitlines()).strip("\n") + "\n"

    start_index = (line_operation.start_line or 1) - 1
    end_index = (line_operation.end_line or line_operation.start_line or 1) - 1
    replacement_lines = str(line_operation.new_text or "").splitlines()

    if kind == "replace_range":
        lines[start_index : end_index + 1] = replacement_lines
        return "\n".join(lines).strip("\n") + "\n"
    if kind == "delete_range":
        lines[start_index : end_index + 1] = []
        return "\n".join(lines).strip("\n") + ("\n" if lines else "")
    if kind in {"insert_before", "insert_after"}:
        anchor_index = _locate_anchor_index(lines, line_operation)
        insert_index = anchor_index if kind == "insert_before" else anchor_index + 1
        lines[insert_index:insert_index] = replacement_lines
        return "\n".join(lines).strip("\n") + "\n"
    return text


def _locate_anchor_index(lines: list[str], line_operation) -> int:
    anchor_text = str(line_operation.anchor_text or "").strip()
    if anchor_text:
        for index, line in enumerate(lines):
            if anchor_text in line:
                return index
    return max((line_operation.start_line or 1) - 1, 0)


def _derive_template_values(fields: dict[str, Any]) -> dict[str, Any]:
    total_calls = int(fields.get("total_calls") or 0)
    success_count = int(fields.get("success_count") or 0)
    fail_count = int(fields.get("fail_count") or 0)
    total_time_ms = int(fields.get("total_time_ms") or 0)
    total_tokens = int(fields.get("total_tokens") or 0)
    success_rate = round((success_count / total_calls) * 100, 2) if total_calls else 0
    avg_time = f"{round(total_time_ms / total_calls, 2)}ms" if total_calls else "0ms"
    avg_tokens = round(total_tokens / total_calls, 2) if total_calls else 0
    return {
        "success_rate": success_rate,
        "avg_time": avg_time,
        "avg_tokens": avg_tokens,
        "fail_count": fail_count,
    }
