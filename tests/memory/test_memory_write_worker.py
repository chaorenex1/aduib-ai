from __future__ import annotations

import json
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.storage.base_storage import BaseStorage, StorageEntry, storage_manager
from runtime.tasks.memory_write_tasks import execute_memory_write
from service.memory.base.contracts import MemorySourceRef, MemoryWriteTaskView
from service.memory.base.enums import (
    MemoryQueueStatus,
    MemoryTaskPhase,
    MemoryTaskStatus,
    MemoryTriggerType,
)


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


def _build_task_view(*, task_id: str, phase: str, status: str = "running") -> MemoryWriteTaskView:
    return MemoryWriteTaskView(
        task_id=task_id,
        trace_id="trace-1",
        trigger_type=MemoryTriggerType.MEMORY_API,
        status=status,
        phase=phase,
        queue_status=MemoryQueueStatus.QUEUED,
        source_ref=MemorySourceRef(
            type="memory_api",
            id=task_id,
            path=f"memory_pipeline/users/u1/sources/{task_id}.json",
        ),
        archive_ref=None,
    )


def _run_worker(task_id: str, *, request_id: str) -> dict:
    execute_memory_write.push_request(id=request_id)
    try:
        return execute_memory_write.run(task_id)
    finally:
        execute_memory_write.pop_request()

def test_execute_memory_write_runs_all_phases_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    phase_calls: list[str] = []
    committed: dict[str, object] = {}

    def _fake_mark_running(task_id: str, *, phase: str):
        phase_calls.append(f"running:{phase}")
        return _build_task_view(task_id=task_id, phase=phase)

    def _fake_record_checkpoint(task_id: str, *, phase: str, result_ref=None, operator_notes=None):
        phase_calls.append(f"checkpoint:{phase}")
        return _build_task_view(task_id=task_id, phase=phase)

    def _fake_mark_committed(task_id: str, *, result_ref=None, operator_notes=None):
        phase_calls.append("committed")
        committed["task_id"] = task_id
        committed["result_ref"] = result_ref
        return _build_task_view(task_id=task_id, phase=MemoryTaskPhase.COMMITTED, status=MemoryTaskStatus.COMMITTED)

    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_running", _fake_mark_running)
    monkeypatch.setattr("service.memory.MemoryWriteTaskService.record_checkpoint", _fake_record_checkpoint)
    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_committed", _fake_mark_committed)

    result = _run_worker("task-1", request_id="celery-1")

    assert result["status"] == "committed"
    assert result["task_id"] == "task-1"
    assert result["final_phase"] == "committed"
    assert list(result["phase_results"]) == [
        "prepare_extract_context",
        "extract_operations",
        "resolve_operations",
        "build_staged_write_set",
        "apply_memory_files",
        "refresh_navigation",
        "refresh_metadata",
    ]
    assert phase_calls == [
        "running:prepare_extract_context",
        "checkpoint:prepare_extract_context",
        "running:extract_operations",
        "checkpoint:extract_operations",
        "running:resolve_operations",
        "checkpoint:resolve_operations",
        "running:build_staged_write_set",
        "checkpoint:build_staged_write_set",
        "running:apply_memory_files",
        "checkpoint:apply_memory_files",
        "running:refresh_navigation",
        "checkpoint:refresh_navigation",
        "running:refresh_metadata",
        "checkpoint:refresh_metadata",
        "committed",
    ]
    assert committed["task_id"] == "task-1"


def test_execute_memory_write_marks_manual_recovery_on_phase_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    recovery: dict[str, object] = {}

    def _fake_mark_running(task_id: str, *, phase: str):
        return _build_task_view(task_id=task_id, phase=phase)

    def _fake_record_checkpoint(task_id: str, *, phase: str, result_ref=None, operator_notes=None):
        if phase == MemoryTaskPhase.EXTRACT_OPERATIONS:
            raise RuntimeError("boom")
        return _build_task_view(task_id=task_id, phase=phase)

    def _fake_mark_needs_manual_recovery(task_id: str, *, phase: str, error: str, rollback_metadata=None):
        recovery["task_id"] = task_id
        recovery["phase"] = phase
        recovery["error"] = error
        recovery["rollback_metadata"] = rollback_metadata
        return _build_task_view(
            task_id=task_id,
            phase=phase,
            status=MemoryTaskStatus.NEEDS_MANUAL_RECOVERY,
        )

    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_running", _fake_mark_running)
    monkeypatch.setattr("service.memory.MemoryWriteTaskService.record_checkpoint", _fake_record_checkpoint)
    monkeypatch.setattr(
        "service.memory.MemoryWriteTaskService.mark_needs_manual_recovery",
        _fake_mark_needs_manual_recovery,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _run_worker("task-2", request_id="celery-2")

    assert recovery == {
        "task_id": "task-2",
        "phase": "extract_operations",
        "error": "boom",
        "rollback_metadata": {"worker_task_id": "celery-2"},
    }


def test_execute_memory_write_loads_pg_jsonl_conversation_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    conversation_uri = "memory_pipeline/users/u1/sources/conversations/codex__sess-1.jsonl"
    conversation_rows = [
        {
            "conversation_id": "codex:sess-1",
            "role": "user",
            "content_parts": [{"type": "text", "text": "hello"}],
            "created_at": "2026-04-18T10:00:00Z",
        },
        {
            "conversation_id": "codex:sess-1",
            "role": "assistant",
            "content_parts": [{"type": "text", "text": "world"}],
            "created_at": "2026-04-18T10:00:05Z",
        },
    ]
    storage.write_text_atomic(conversation_uri, "\n".join(json.dumps(row) for row in conversation_rows) + "\n")
    committed: dict[str, object] = {}

    def _fake_mark_running(task_id: str, *, phase: str):
        return MemoryWriteTaskView(
            task_id=task_id,
            trace_id="trace-1",
            trigger_type=MemoryTriggerType.MEMORY_API,
            status="running",
            phase=phase,
            queue_status=MemoryQueueStatus.QUEUED,
            source_ref=MemorySourceRef(
                type="conversation",
                id="codex:sess-1",
                storage="pg_jsonl",
                version=2,
                message_ref={"type": "jsonl", "uri": conversation_uri},
                external_source="codex",
                external_session_id="sess-1",
            ),
            archive_ref=None,
        )

    def _fake_record_checkpoint(task_id: str, *, phase: str, result_ref=None, operator_notes=None):
        return _build_task_view(task_id=task_id, phase=phase)

    def _fake_mark_committed(task_id: str, *, result_ref=None, operator_notes=None):
        committed["result_ref"] = result_ref
        return _build_task_view(task_id=task_id, phase=MemoryTaskPhase.COMMITTED, status=MemoryTaskStatus.COMMITTED)

    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_running", _fake_mark_running)
    monkeypatch.setattr("service.memory.MemoryWriteTaskService.record_checkpoint", _fake_record_checkpoint)
    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_committed", _fake_mark_committed)

    result = _run_worker("task-3", request_id="celery-3")

    prepare_context = result["phase_results"]["prepare_extract_context"]
    assert prepare_context["conversation_snapshot"]["storage"] == "pg_jsonl"
    assert prepare_context["conversation_snapshot"]["message_count"] == 2
    assert prepare_context["conversation_snapshot"]["messages"][0]["role"] == "user"
    assert prepare_context["source_ref"]["storage"] == "pg_jsonl"
    assert (
        committed["result_ref"]["phase_results"]["prepare_extract_context"]["conversation_snapshot"]["message_count"]
        == 2
    )


def test_execute_memory_write_marks_manual_recovery_when_pg_jsonl_sha_mismatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    conversation_uri = "memory_pipeline/users/u1/sources/conversations/codex__sess-1.jsonl"
    storage.write_text_atomic(
        conversation_uri,
        json.dumps(
            {
                "conversation_id": "codex:sess-1",
                "role": "user",
                "content_parts": [{"type": "text", "text": "hello"}],
                "created_at": "2026-04-18T10:00:00Z",
            }
        )
        + "\n",
    )
    recovery: dict[str, object] = {}

    def _fake_mark_running(task_id: str, *, phase: str):
        return MemoryWriteTaskView(
            task_id=task_id,
            trace_id="trace-1",
            trigger_type=MemoryTriggerType.MEMORY_API,
            status="running",
            phase=phase,
            queue_status=MemoryQueueStatus.QUEUED,
            source_ref=MemorySourceRef(
                type="conversation",
                id="codex:sess-1",
                storage="pg_jsonl",
                version=2,
                message_ref={"type": "jsonl", "uri": conversation_uri, "sha256": "bad-sha"},
            ),
            archive_ref=None,
        )

    def _fake_mark_needs_manual_recovery(task_id: str, *, phase: str, error: str, rollback_metadata=None):
        recovery["task_id"] = task_id
        recovery["phase"] = phase
        recovery["error"] = error
        recovery["rollback_metadata"] = rollback_metadata
        return _build_task_view(
            task_id=task_id,
            phase=phase,
            status=MemoryTaskStatus.NEEDS_MANUAL_RECOVERY,
        )

    monkeypatch.setattr("service.memory.MemoryWriteTaskService.mark_running", _fake_mark_running)
    monkeypatch.setattr(
        "service.memory.MemoryWriteTaskService.mark_needs_manual_recovery",
        _fake_mark_needs_manual_recovery,
    )

    with pytest.raises(ValueError, match="sha256"):
        _run_worker("task-4", request_id="celery-4")

    assert recovery["phase"] == "prepare_extract_context"
    assert recovery["rollback_metadata"] == {"worker_task_id": "celery-4"}
