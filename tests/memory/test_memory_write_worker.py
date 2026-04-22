from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.tasks.memory_write_tasks import execute_memory_write
from service.memory import (
    MemoryQueueStatus,
    MemorySourceRef,
    MemoryTaskPhase,
    MemoryTaskStatus,
    MemoryTriggerType,
    MemoryWriteTaskView,
)


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
