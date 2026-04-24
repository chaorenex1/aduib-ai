from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.storage.base_storage import BaseStorage, StorageEntry, storage_manager
from runtime.memory.write_pipeline import run_memory_write_task_phase
from service.memory.base.contracts import ArchivedSourceRef, MemorySourceRef, MemoryWriteTaskView
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


def _build_task_view(
    *,
    task_id: str,
    trigger_type: MemoryTriggerType,
    source_ref: MemorySourceRef,
    archive_ref: ArchivedSourceRef | None = None,
) -> MemoryWriteTaskView:
    return MemoryWriteTaskView(
        task_id=task_id,
        trace_id="trace-1",
        trigger_type=trigger_type,
        user_id="u1",
        agent_id="a1",
        project_id="proj-1",
        status=None,
        phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
        source_ref=source_ref,
        archive_ref=archive_ref,
    )


def test_prepare_extract_context_normalizes_memory_api_archive_and_prefetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    archive_path = "memory_pipeline/users/u1/sources/memory_api/task-prepare.json"
    archive_payload = {
        "trigger_type": "memory_api",
        "task_id": "task-prepare",
        "trace_id": "trace-1",
        "scope": {"user_id": "u1", "agent_id": "a1", "project_id": "proj-1"},
        "payload": {
            "content": "Remember the async queue write pipeline and keep verification notes.",
            "memory_source": "user_input",
            "summary_enabled": False,
            "file_name": None,
        },
    }
    archive_text = json.dumps(archive_payload, ensure_ascii=False, indent=2)
    storage.write_text_atomic(archive_path, archive_text)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/overview.md",
        "# Overview\nThis directory tracks async queue write preferences.\n",
    )
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/summary.md",
        "# Summary\nAsync queue notes.\n",
    )
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/async-queue.md",
        "# Async Queue\nPrefer queue-first write pipeline changes with verification.\n",
    )

    task = _build_task_view(
        task_id="task-prepare",
        trigger_type=MemoryTriggerType.MEMORY_API,
        source_ref=MemorySourceRef(type="memory_api", conversation_id="task-prepare", path=archive_path),
        archive_ref=ArchivedSourceRef(
            path=archive_path,
            type="application/json",
            storage="default",
            content_sha256=hashlib.sha256(archive_text.encode("utf-8")).hexdigest(),
            size_bytes=len(archive_text.encode("utf-8")),
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-prepare",
        phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
        task=task,
        phase_results={},
    )

    assert result["source_kind"] == "memory_api"
    assert result["archive_ref"]["path"] == archive_path
    assert result["messages"][0]["role"] == "user"
    assert "async queue write pipeline" in result["text_blocks"][0]
    assert result["stats"]["message_count"] == 1
    assert result["stats"]["text_block_count"] == 1
    assert result["prefetched_context"]["directory_views"][0]["path"].endswith("preference")
    assert {item["path"] for item in result["prefetched_context"]["file_reads"]} >= {
        "users/u1/memories/preference/overview.md",
        "users/u1/memories/preference/summary.md",
    }
    assert result["prefetched_context"]["search_results"][0]["matches"][0]["path"].endswith("async-queue.md")


def test_prepare_extract_context_normalizes_session_commit_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    archive_path = "memory_pipeline/users/u1/sources/session_commit/session-7__task-prepare.json"
    archive_payload = {
        "trigger_type": "session_commit",
        "task_id": "task-prepare",
        "trace_id": "trace-1",
        "scope": {"user_id": "u1", "agent_id": "a1", "project_id": "proj-1"},
        "source_ref": {"type": "session_commit", "conversation_id": "session-7", "path": "conversation/session-7"},
        "session_snapshot": {
            "session_key": "session-7",
            "agent_session_id": 7,
            "message_count": 2,
            "messages": [
                {"role": "user", "content": "Ship the async pipeline."},
                {"role": "assistant", "content": "Add verification and rollback checkpoints."},
            ],
        },
    }
    archive_text = json.dumps(archive_payload, ensure_ascii=False, indent=2)
    storage.write_text_atomic(archive_path, archive_text)

    task = _build_task_view(
        task_id="task-prepare",
        trigger_type=MemoryTriggerType.SESSION_COMMIT,
        source_ref=MemorySourceRef(type="session_commit", conversation_id="session-7", path="conversation/session-7"),
        archive_ref=ArchivedSourceRef(
            path=archive_path,
            type="application/json",
            storage="default",
            content_sha256=hashlib.sha256(archive_text.encode("utf-8")).hexdigest(),
            size_bytes=len(archive_text.encode("utf-8")),
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-prepare",
        phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
        task=task,
        phase_results={},
    )

    assert result["source_kind"] == "session_commit"
    assert result["session_snapshot"]["message_count"] == 2
    assert [message["role"] for message in result["messages"]] == ["user", "assistant"]
    assert result["text_blocks"] == [
        "Ship the async pipeline.",
        "Add verification and rollback checkpoints.",
    ]
    assert result["stats"]["message_count"] == 2
