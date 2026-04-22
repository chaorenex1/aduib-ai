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
from service.memory import MemorySourceArchiveService
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


@pytest.mark.anyio
async def test_archive_memory_api_writes_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    payload = MemoryCreateRequest(
        content="Remember to keep the write pipeline async.",
        project_id="proj-1",
        user_id="user-1",
        agent_id="agent-1",
        summary_enabled=False,
        memory_source="user_input",
    )
    command = await memory_create_request_to_command(payload)

    archive_ref = await MemorySourceArchiveService.archive_memory_api(
        command,
        task_id="task-123",
        trace_id="trace-456",
    )

    assert archive_ref.path.endswith("memory_pipeline/users/user-1/sources/memory_api/task-123.json")
    assert storage.exists(archive_ref.path) is True

    snapshot = json.loads(storage.read_text(archive_ref.path))
    assert snapshot["trigger_type"] == "memory_api"
    assert snapshot["task_id"] == "task-123"
    assert snapshot["trace_id"] == "trace-456"
    assert snapshot["scope"]["user_id"] == "user-1"
    assert snapshot["payload"]["content"] == "Remember to keep the write pipeline async."
