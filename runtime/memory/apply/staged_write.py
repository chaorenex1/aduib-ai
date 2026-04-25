from __future__ import annotations

from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.base.contracts import (
    MemoryWritePipelineContext,
    PreparedExtractContext,
    ResolvedMemoryOperation,
)

from .patch import build_desired_document
from .rollback import serialize_snapshot

SUPPORTED_NAVIGATION_DIRECTORIES = {
    "preference",
    "event",
    "entity",
    "task",
    "verification",
    "review",
    "ops",
}


def build_staged_write_set(context: MemoryWritePipelineContext) -> dict:
    prepared = PreparedExtractContext.model_validate(context.phase_results.get("prepare_extract_context") or {})
    resolve_result = context.phase_results.get("resolve_operations") or {}
    resolved_operations = [
        ResolvedMemoryOperation.model_validate(item) for item in resolve_result.get("resolved_operations") or []
    ]
    memory_mutations: list[dict[str, Any]] = []
    snapshot_targets: list[str] = []
    for operation in resolved_operations:
        snapshot_targets.append(_to_scoped_path(operation.target_path))
        current_content = (
            storage_manager.read_text(_to_scoped_path(operation.target_path)) if operation.file_exists else None
        )
        desired_content = None
        if operation.op != "delete":
            desired_content = build_desired_document(
                task_id=context.task_id,
                prepared=prepared,
                operation=operation,
                current_content=current_content,
            )
        memory_mutations.append(
            {
                "op": operation.op,
                "memory_type": operation.memory_type,
                "target_path": operation.target_path,
                "target_name": operation.target_name,
                "desired_content": desired_content,
                "previous_content": current_content,
                "file_exists": operation.file_exists,
                "memory_mode": operation.memory_mode,
                "merge_strategy": operation.merge_strategy,
            }
        )

    navigation_targets = [
        {
            "branch_path": directory_path,
            "overview_path": f"{directory_path}/overview.md",
            "summary_path": f"{directory_path}/summary.md",
        }
        for directory_path in resolve_result.get("navigation_scopes") or []
        if _is_supported_navigation_dir(directory_path)
    ]
    snapshot_targets.extend(_to_scoped_path(item["overview_path"]) for item in navigation_targets)
    snapshot_targets.extend(_to_scoped_path(item["summary_path"]) for item in navigation_targets)
    snapshot = storage_manager.snapshot(snapshot_targets)
    rollback_plan = {
        "snapshot": serialize_snapshot(snapshot),
        "target_paths": [item["target_path"] for item in memory_mutations],
    }
    metadata_mutations = [
        {"scope_path": scope_path} for scope_path in sorted(set(resolve_result.get("metadata_scopes") or []))
    ]
    journal_entries = [
        {"action": item["op"], "target_path": item["target_path"], "memory_type": item["memory_type"]}
        for item in memory_mutations
    ]
    return {
        "task_id": context.task_id,
        "phase": "build_staged_write_set",
        "memory_mutations": memory_mutations,
        "navigation_targets": navigation_targets,
        "metadata_mutations": metadata_mutations,
        "rollback_plan": rollback_plan,
        "journal_entries": journal_entries,
        "staging_manifest": {
            "memory_mutation_count": len(memory_mutations),
            "navigation_target_count": len(navigation_targets),
            "metadata_mutation_count": len(metadata_mutations),
        },
    }


def _is_supported_navigation_dir(directory_path: str) -> bool:
    parts = [part for part in str(directory_path or "").split("/") if part]
    if (
        len(parts) == 4
        and parts[:3] == ["users", parts[1], "memories"]
        and parts[3] in SUPPORTED_NAVIGATION_DIRECTORIES
    ):
        return True
    return len(parts) == 3 and parts[:2] == ["users", parts[1]] and parts[2] == "project"


def _to_scoped_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)
