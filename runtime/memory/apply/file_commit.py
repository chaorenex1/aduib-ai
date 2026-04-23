from __future__ import annotations

import json

from component.storage.base_storage import storage_manager
from configs import config
from service.memory.base.contracts import MemoryWritePipelineContext

from .rollback import deserialize_snapshot


def apply_memory_files(context: MemoryWritePipelineContext) -> dict:
    staged = context.phase_results.get("build_staged_write_set") or {}
    memory_mutations = staged.get("memory_mutations") or []
    rollback_plan = staged.get("rollback_plan") or {}
    journal_ref = _journal_path(context.task_id)
    applied_paths: list[str] = []
    try:
        for mutation in memory_mutations:
            scoped_path = _to_scoped_path(mutation["target_path"])
            if mutation["op"] == "delete":
                storage_manager.delete(scoped_path)
            else:
                storage_manager.write_text_atomic(scoped_path, mutation["desired_content"])
                storage_manager.read_text(scoped_path)
            applied_paths.append(mutation["target_path"])
        journal_payload = {
            "task_id": context.task_id,
            "phase": "apply_memory_files",
            "applied_paths": applied_paths,
            "journal_entries": staged.get("journal_entries") or [],
        }
        storage_manager.write_text_atomic(journal_ref, json.dumps(journal_payload, ensure_ascii=False, indent=2))
        return {
            "task_id": context.task_id,
            "phase": "apply_memory_files",
            "applied_memory_files": applied_paths,
            "journal_ref": journal_ref.replace(f"{config.MEMORY_TREE_ROOT_DIR}/", "", 1),
            "rollback_metadata": {
                "applied_paths": applied_paths,
                "rolled_back_paths": [],
                "rollback_failed_paths": [],
            },
        }
    except Exception:
        rollback_metadata = {"applied_paths": applied_paths, "rolled_back_paths": [], "rollback_failed_paths": []}
        try:
            snapshot = deserialize_snapshot(rollback_plan.get("snapshot") or {})
            storage_manager.restore(snapshot)
            rollback_metadata["rolled_back_paths"] = rollback_plan.get("target_paths") or []
        except Exception:
            rollback_metadata["rollback_failed_paths"] = rollback_plan.get("target_paths") or []
        raise RuntimeError(json.dumps({"phase": "apply_memory_files", "rollback_metadata": rollback_metadata}))


def _journal_path(task_id: str) -> str:
    return f"{config.MEMORY_TREE_ROOT_DIR}/.system/memory-write-journals/{task_id}-apply-memory-files.json"


def _to_scoped_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)
