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
from controllers.memory.schemas import TaskCreateRequest
from runtime.memory.source_archive import MemorySourceArchiveRuntime
from service.memory import ConversationRepository, MemoryWriteTaskService
from service.memory.base.contracts import (
    ArchivedSourceRef,
    MemoryWriteTaskView,
)
from service.memory.base.enums import MemoryTaskPhase
from service.memory.base.errors import MemoryValidationError
from service.memory.base.mappers import task_create_request_to_command


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


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_archive_session_commit_writes_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    monkeypatch.setattr(
        MemorySourceArchiveRuntime,
        "_load_session_messages",
        staticmethod(
            lambda agent_session_id, user_id, agent_id: [
                {
                    "message_id": "m1",
                    "role": "user",
                    "content": "hello",
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "agent_session_id": agent_session_id,
                    "model_name": "gpt",
                    "provider_name": "openai",
                    "created_at": "2026-04-22T00:00:00+00:00",
                }
            ]
        ),
    )

    request = TaskCreateRequest(
        user_id="u1",
        agent_id="7",
        project_id="p1",
        trigger_type="session_commit",
        source_ref={"type": "session_commit", "conversation_id": "session-7", "path": "conversation/session-7"},
    )
    command = task_create_request_to_command(request)

    archive_ref = await MemorySourceArchiveRuntime.archive_session_commit(
        command,
        task_id="task-1",
        trace_id="trace-1",
    )

    assert archive_ref.path.endswith("memory_pipeline/users/u1/sources/session_commit/session-7__task-1.json")
    snapshot = json.loads(storage.read_text(archive_ref.path))
    assert snapshot["trigger_type"] == "session_commit"
    assert snapshot["session_snapshot"]["agent_session_id"] == 7
    assert snapshot["session_snapshot"]["message_count"] == 1


@pytest.mark.anyio
async def test_accept_task_request_archives_session_commit_before_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    request = TaskCreateRequest(
        user_id="u1",
        agent_id="7",
        project_id="p1",
        trigger_type="session_commit",
        source_ref={"type": "session_commit", "conversation_id": "session-7", "path": "conversation/session-7"},
    )
    command = task_create_request_to_command(request)

    fake_archive = ArchivedSourceRef(
        path="memory_pipeline/users/u1/sources/session_commit/session-7__task-1.json",
        type="application/json",
        storage="default",
        content_sha256="abc",
        size_bytes=10,
    )
    captured: dict[str, object] = {}

    async def _fake_archive_session_commit(payload, *, task_id: str, trace_id: str):
        captured["archive_payload"] = payload
        captured["archive_task_id"] = task_id
        captured["archive_trace_id"] = trace_id
        return fake_archive

    def _fake_create_task(**kwargs):
        captured["create_task"] = kwargs
        return MemoryWriteTaskView(
            task_id=kwargs["task_id"],
            trace_id=kwargs["trace_id"],
            trigger_type=kwargs["trigger_type"],
            status=None,
            phase=MemoryTaskPhase.ACCEPTED,
            source_ref=kwargs["source_ref"],
            archive_ref=kwargs["archive_ref"],
        )

    def _fake_publish_task(task):
        return MemoryWriteTaskView(
            task_id=task.task_id,
            trace_id="trace-queued",
            trigger_type="session_commit",
            status=None,
            phase=MemoryTaskPhase.ACCEPTED,
            source_ref=command.source_ref,
            archive_ref=fake_archive,
        )

    monkeypatch.setattr(
        MemorySourceArchiveRuntime,
        "archive_session_commit",
        staticmethod(_fake_archive_session_commit),
    )
    monkeypatch.setattr(MemoryWriteTaskService, "create_task", staticmethod(_fake_create_task))
    monkeypatch.setattr(MemoryWriteTaskService, "_publish_task", staticmethod(_fake_publish_task))

    accepted = await MemoryWriteTaskService.accept_task_request(command)

    assert accepted.trigger_type == "session_commit"
    assert accepted.status is None
    assert accepted.archive_ref is not None
    assert captured["create_task"]["archive_ref"] == fake_archive


@pytest.mark.anyio
async def test_accept_task_request_normalizes_conversation_source_ref_from_pg(monkeypatch: pytest.MonkeyPatch) -> None:
    request = TaskCreateRequest(
        user_id="u1",
        agent_id="a1",
        project_id="p1",
        trigger_type="memory_api",
        source_ref={
            "type": "conversation",
            "conversation_id": "codex:sess-1",
        },
    )
    command = task_create_request_to_command(request)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        ConversationRepository,
        "get_conversation",
        staticmethod(
            lambda **_: type(
                "ConversationView",
                (),
                {
                    "conversation_id": "codex:sess-1",
                },
            )()
        ),
    )

    def _fake_create_task(**kwargs):
        captured["source_ref"] = kwargs["source_ref"]
        return MemoryWriteTaskView(
            task_id=kwargs["task_id"],
            trace_id=kwargs["trace_id"],
            trigger_type=kwargs["trigger_type"],
            status=None,
            phase=MemoryTaskPhase.ACCEPTED,
            source_ref=kwargs["source_ref"],
            archive_ref=kwargs["archive_ref"],
        )

    def _fake_publish_task(task):
        return MemoryWriteTaskView(
            task_id=task.task_id,
            trace_id="trace-queued",
            trigger_type="memory_api",
            status=None,
            phase=MemoryTaskPhase.ACCEPTED,
            source_ref=captured["source_ref"],
            archive_ref=None,
        )

    monkeypatch.setattr(MemoryWriteTaskService, "create_task", staticmethod(_fake_create_task))
    monkeypatch.setattr(MemoryWriteTaskService, "_publish_task", staticmethod(_fake_publish_task))

    accepted = await MemoryWriteTaskService.accept_task_request(command)

    assert accepted.archive_ref is None
    assert accepted.source_ref.path is None
    assert accepted.source_ref.conversation_id == "codex:sess-1"


@pytest.mark.anyio
async def test_accept_task_request_rejects_missing_conversation_source(monkeypatch: pytest.MonkeyPatch) -> None:
    request = TaskCreateRequest(
        user_id="u1",
        agent_id="a1",
        project_id="p1",
        trigger_type="memory_api",
        source_ref={
            "type": "conversation",
            "conversation_id": "codex:sess-1",
        },
    )
    command = task_create_request_to_command(request)

    monkeypatch.setattr(
        ConversationRepository,
        "get_conversation",
        staticmethod(lambda **_: None),
    )

    with pytest.raises(MemoryValidationError, match="not found"):
        await MemoryWriteTaskService.accept_task_request(command)


@pytest.mark.anyio
async def test_accept_task_request_rejects_conversation_agent_scope_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = TaskCreateRequest(
        user_id="u1",
        agent_id="a1",
        project_id="p1",
        trigger_type="memory_api",
        source_ref={
            "type": "conversation",
            "conversation_id": "codex:sess-1",
        },
    )
    command = task_create_request_to_command(request)

    monkeypatch.setattr(
        ConversationRepository,
        "get_conversation",
        staticmethod(
            lambda **_: type(
                "ConversationView",
                (),
                {
                    "conversation_id": "codex:sess-1",
                    "agent_id": "other-agent",
                    "project_id": "p1",
                },
            )()
        ),
    )

    with pytest.raises(MemoryValidationError, match="agent_id"):
        await MemoryWriteTaskService.accept_task_request(command)
