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
from controllers.memory.schemas import MemoryCreateRequest
from runtime.memory.source_archive import MemorySourceArchiveRuntime
from service.memory import ConversationRepository
from service.memory.base.contracts import MemorySourceRef, MemoryWriteTaskView
from service.memory.base.enums import MemoryTaskPhase, MemoryTriggerType
from service.memory.base.mappers import memory_create_request_to_command


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


def test_freeze_conversation_source_writes_frozen_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    live_uri = "memory_pipeline/users/user-1/sources/conversations/codex__sess-1.jsonl"
    live_content = "\n".join(
        [
            json.dumps(
                {
                    "conversation_id": "codex:sess-1",
                    "role": "user",
                    "content_parts": [{"type": "text", "text": "hi"}],
                }
            ),
            json.dumps(
                {
                    "conversation_id": "codex:sess-1",
                    "role": "assistant",
                    "content_parts": [{"type": "text", "text": "yo"}],
                }
            ),
        ]
    ) + "\n"
    storage.write_text_atomic(live_uri, live_content)

    monkeypatch.setattr(
        ConversationRepository,
        "get_conversation",
        staticmethod(
            lambda **_: type(
                "ConversationView",
                (),
                {
                    "conversation_id": "codex:sess-1",
                    "message_ref": type("MessageRef", (), {"uri": live_uri})(),
                },
            )()
        ),
    )

    task = MemoryWriteTaskView(
        task_id="task-123",
        trace_id="trace-456",
        trigger_type=MemoryTriggerType.MEMORY_API,
        user_id="user-1",
        agent_id="agent-1",
        project_id="proj-1",
        status=None,
        phase=MemoryTaskPhase.ACCEPTED,
        source_ref=MemorySourceRef(type="conversation", conversation_id="codex:sess-1"),
        archive_ref=None,
    )

    archive_ref = MemorySourceArchiveRuntime.freeze_memory_api_conversation_source(task)

    assert archive_ref.type == "application/x-ndjson"
    assert archive_ref.path.endswith(
        "memory_pipeline/users/user-1/sources/memory_api/conversations/codex__sess-1__task-123.jsonl"
    )
    assert storage.read_text(archive_ref.path) == live_content


def test_delete_archive_removes_frozen_file(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    archive_path = "memory_pipeline/users/user-1/sources/memory_api/conversations/codex__sess-1__task-123.jsonl"
    storage.write_text_atomic(archive_path, "line-1\n")

    archive_ref = type(
        "ArchiveRef",
        (),
        {"path": archive_path},
    )()

    MemorySourceArchiveRuntime.delete_archive(archive_ref)

    assert storage.exists(archive_path) is False
