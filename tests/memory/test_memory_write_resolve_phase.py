from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.storage.base_storage import BaseStorage, StorageEntry, storage_manager
from runtime.memory.write_pipeline import run_memory_write_task_phase
from service.memory.base.contracts import MemorySourceRef, MemoryWriteTaskView
from service.memory.base.enums import MemoryTaskPhase, MemoryTriggerType


class _InMemoryStorage(BaseStorage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, filename: str, data: bytes):
        self.files[self._normalize(filename)] = data

    def load(self, filename: str) -> bytes:
        return self.files[self._normalize(filename)]

    def load_stream(self, filename: str) -> Generator[bytes, None, None]:
        yield self.load(filename)

    def delete(self, filename: str):
        normalized = self._normalize(filename)
        prefix = f"{normalized}/"
        for key in [key for key in self.files if key == normalized or key.startswith(prefix)]:
            self.files.pop(key, None)

    def exists(self, filename: str) -> bool:
        normalized = self._normalize(filename)
        prefix = f"{normalized}/"
        return normalized in self.files or any(key.startswith(prefix) for key in self.files)

    def download(self, filename: str, target_file_path: str):
        Path(target_file_path).write_bytes(self.load(filename))

    def size(self, filename: str) -> int:
        return len(self.load(filename))

    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        normalized = self._normalize(path)
        prefix = f"{normalized}/" if normalized else ""
        files = sorted(key for key in self.files if key.startswith(prefix))
        entries: dict[str, StorageEntry] = {}

        for key in files:
            relative = key[len(prefix) :]
            parts = relative.split("/")
            if recursive:
                for index in range(len(parts) - 1):
                    dir_path = "/".join(part for part in [normalized, *parts[: index + 1]] if part)
                    entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)
                entries[key] = StorageEntry(path=key, is_file=True, is_dir=False, size=len(self.files[key]))
                continue

            if len(parts) == 1:
                entries[key] = StorageEntry(path=key, is_file=True, is_dir=False, size=len(self.files[key]))
            else:
                dir_path = "/".join(part for part in [normalized, parts[0]] if part)
                entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)

        return sorted(entries.values(), key=lambda entry: entry.path)

    @staticmethod
    def _normalize(path: str) -> str:
        return path.replace("\\", "/").strip("/")


def _build_task_view(*, task_id: str) -> MemoryWriteTaskView:
    return MemoryWriteTaskView(
        task_id=task_id,
        trace_id="trace-resolve",
        trigger_type=MemoryTriggerType.MEMORY_API,
        user_id="u1",
        agent_id="a1",
        project_id="proj-1",
        status=None,
        phase=MemoryTaskPhase.RESOLVE_OPERATIONS,
        source_ref=MemorySourceRef(
            type="memory_api", conversation_id=task_id, path=f"memory_pipeline/users/u1/sources/{task_id}.json"
        ),
        archive_ref=None,
    )


def _build_phase_results(*, operations: list[dict]) -> dict[str, dict]:
    return {
        "prepare_extract_context": {
            "task_id": "task-resolve",
            "phase": "prepare_extract_context",
            "source_kind": "memory_api",
            "source_hash": "sha-2",
            "source_ref": {"type": "memory_api", "conversation_id": "task-resolve"},
            "user_id": "u1",
            "agent_id": "a1",
            "project_id": "proj-1",
            "messages": [],
            "text_blocks": [],
            "prefetched_context": {
                "directory_views": [],
                "file_reads": [],
                "search_results": [],
                "already_read_paths": [],
            },
            "schema_bundle": [],
            "stats": {"message_count": 0, "text_block_count": 0},
        },
        "extract_operations": {
            "task_id": "task-resolve",
            "phase": "extract_operations",
            "planner_status": "planned",
            "structured_operations": operations,
            "tools_available": ["ls", "read", "find"],
            "tools_used": [],
        },
    }


def test_resolve_operations_maps_paths_and_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        "# Existing preference\n",
    )

    operations = [
        {
            "op": "edit",
            "memory_type": "preference",
            "fields": {"topic": "Python code style"},
            "content": "Prefer concise Python code.",
            "confidence": 0.8,
            "evidence": [{"kind": "message", "content": "Prefer concise Python code."}],
        },
        {
            "op": "write",
            "memory_type": "tool",
            "fields": {
                "tool_name": "read file",
                "static_desc": "Read a file from storage.",
                "total_calls": 3,
                "success_count": 3,
                "fail_count": 0,
                "total_time_ms": 120,
                "total_tokens": 45,
                "best_for": "Inspecting a single file.",
                "optimal_params": "Use precise paths.",
                "common_failures": "Missing files.",
                "recommendation": "Read before editing.",
                "guidelines": "## Guidelines\n### Good Cases\n- Debugging\n### Bad Cases\n- Guessing",
            },
            "content": "",
            "confidence": 0.9,
            "evidence": [{"kind": "message", "content": "Use read_file before editing."}],
        },
    ]

    result = run_memory_write_task_phase(
        task_id="task-resolve",
        phase=MemoryTaskPhase.RESOLVE_OPERATIONS,
        task=_build_task_view(task_id="task-resolve"),
        phase_results=_build_phase_results(operations=operations),
    )

    resolved = result["resolved_operations"]
    assert [item["target_path"] for item in resolved] == [
        "users/u1/memories/preference/Python-code-style.md",
        "agent/a1/memories/tool/read-file.md",
    ]
    assert resolved[0]["file_exists"] is True
    assert resolved[0]["memory_mode"] == "simple"
    assert resolved[0]["merge_strategy"] == "patch"
    assert resolved[1]["file_exists"] is False
    assert resolved[1]["memory_mode"] == "template"
    assert resolved[1]["merge_strategy"] == "template_fields"
    assert result["navigation_scopes"] == ["agent/a1/memories/tool", "users/u1/memories/preference"]


def test_resolve_operations_rejects_conflicting_delete_and_write(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    operations = [
        {
            "op": "write",
            "memory_type": "profile",
            "fields": {},
            "content": "AI engineer profile",
            "confidence": 0.7,
            "evidence": [{"kind": "message", "content": "AI engineer profile"}],
        },
        {
            "op": "delete",
            "memory_type": "profile",
            "fields": {},
            "content": "",
            "confidence": 0.4,
            "evidence": [{"kind": "message", "content": "remove profile"}],
        },
    ]

    with pytest.raises(ValueError, match="conflicting"):
        run_memory_write_task_phase(
            task_id="task-resolve",
            phase=MemoryTaskPhase.RESOLVE_OPERATIONS,
            task=_build_task_view(task_id="task-resolve"),
            phase_results=_build_phase_results(operations=operations),
        )
