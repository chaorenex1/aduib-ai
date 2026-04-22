from __future__ import annotations

import json
import sys
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.storage.base_storage import BaseStorage, StorageEntry, storage_manager
from service.memory import (
    ConversationMessageRecord,
    ConversationRepository,
    ConversationSourceAppendCommand,
    ConversationSourceConflictError,
    ConversationSourceCorruptedError,
    ConversationSourceCreateCommand,
    ConversationSourceGetQuery,
    ConversationSourceMetadata,
    ConversationSourceNotFoundError,
    ConversationSourceService,
    build_conversation_id,
    build_conversation_source_path,
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


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _message(*, role: str, text: str, created_at: str, part_type: str = "text") -> ConversationMessageRecord:
    payload: dict[str, object]
    if part_type == "text":
        payload = {"type": "text", "text": text}
    else:
        payload = {"type": part_type, "file_id": "file-1", "mime_type": "image/png", "name": "diagram.png"}
    return ConversationMessageRecord(role=role, content_parts=[payload], created_at=created_at)


@pytest.fixture
def fake_conversation_repository(monkeypatch: pytest.MonkeyPatch):
    records: dict[tuple[str, str], dict[str, object]] = {}

    def _clone(record: dict[str, object]) -> SimpleNamespace:
        return json.loads(json.dumps(record), object_hook=lambda data: SimpleNamespace(**data))

    def _get_conversation(*, user_id: str, conversation_id: str):
        record = records.get((user_id, conversation_id))
        return _clone(record) if record else None

    def _create_conversation(**kwargs):
        record = {
            "conversation_id": kwargs["conversation_id"],
            "type": "conversation",
            "title": kwargs["title"],
            "user_id": kwargs["user_id"],
            "agent_id": kwargs["agent_id"],
            "project_id": kwargs["project_id"],
            "external_source": kwargs["external_source"],
            "external_session_id": kwargs["external_session_id"],
            "message_ref": {
                "type": "jsonl",
                "uri": kwargs["message_store_uri"],
                "path": kwargs["message_store_path"],
                "sha256": kwargs["content_sha256"],
            },
            "message_count": kwargs["message_count"],
            "modalities": kwargs["modalities"],
            "version": 1,
            "created_at": kwargs["first_message_at"].isoformat().replace("+00:00", "Z")
            if kwargs["first_message_at"]
            else None,
            "updated_at": kwargs["last_message_at"].isoformat().replace("+00:00", "Z")
            if kwargs["last_message_at"]
            else None,
        }
        records[(kwargs["user_id"], kwargs["conversation_id"])] = record
        return _clone(record)

    def _update_conversation_after_append(
        *,
        user_id: str,
        conversation_id: str,
        content_sha256: str,
        size_bytes: int,
        message_count: int,
        modalities: list[str],
        last_message_at,
    ):
        record = records[(user_id, conversation_id)]
        record["message_count"] = message_count
        record["modalities"] = modalities
        record["version"] = int(record["version"]) + 1
        record["updated_at"] = last_message_at.isoformat().replace("+00:00", "Z") if last_message_at else None
        record["message_ref"]["sha256"] = content_sha256
        return _clone(record)

    monkeypatch.setattr(ConversationRepository, "get_conversation", staticmethod(_get_conversation))
    monkeypatch.setattr(ConversationRepository, "create_conversation", staticmethod(_create_conversation))
    monkeypatch.setattr(
        ConversationRepository,
        "update_conversation_after_append",
        staticmethod(_update_conversation_after_append),
    )
    return records


@pytest.mark.anyio
async def test_create_conversation_writes_canonical_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    fake_conversation_repository = {}
    monkeypatch.setattr(ConversationRepository, "get_conversation", staticmethod(lambda **_: None))
    monkeypatch.setattr(
        ConversationRepository,
        "create_conversation",
        staticmethod(
            lambda **kwargs: SimpleNamespace(
                conversation_id=kwargs["conversation_id"],
                type="conversation",
                title=kwargs["title"],
                user_id=kwargs["user_id"],
                agent_id=kwargs["agent_id"],
                project_id=kwargs["project_id"],
                external_source=kwargs["external_source"],
                external_session_id=kwargs["external_session_id"],
                message_ref=SimpleNamespace(
                    type="jsonl",
                    uri=kwargs["message_store_uri"],
                    path=kwargs["message_store_path"],
                    sha256=kwargs["content_sha256"],
                ),
                message_count=kwargs["message_count"],
                modalities=kwargs["modalities"],
                version=1,
                created_at=kwargs["first_message_at"].isoformat().replace("+00:00", "Z")
                if kwargs["first_message_at"]
                else None,
                updated_at=kwargs["last_message_at"].isoformat().replace("+00:00", "Z")
                if kwargs["last_message_at"]
                else None,
            )
        ),
    )

    view = ConversationSourceService.create_conversation(
        ConversationSourceCreateCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            external_source="codex",
            external_session_id="sess_1",
            title="Design session",
            messages=[
                _message(role="user", text="hello", created_at="2026-04-18T10:00:00Z"),
                _message(role="assistant", text="world", created_at="2026-04-18T10:00:05Z"),
            ],
            metadata=ConversationSourceMetadata(language="zh", tags=["conversation"]),
        )
    )

    expected_path = build_conversation_source_path(
        user_id="u1",
        external_source="codex",
        external_session_id="sess_1",
    )
    assert view.conversation_id == build_conversation_id(external_source="codex", external_session_id="sess_1")
    assert view.message_ref.uri == expected_path
    assert view.message_count == 2
    assert view.modalities == ["text"]
    assert view.version == 1

    raw = storage.read_text(expected_path)
    lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["conversation_id"] == "codex:sess_1"
    assert lines[0]["role"] == "user"
    assert "metadata" not in lines[0]


@pytest.mark.anyio
async def test_append_message_rewrites_file_and_updates_modalities(
    monkeypatch: pytest.MonkeyPatch,
    fake_conversation_repository,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    ConversationSourceService.create_conversation(
        ConversationSourceCreateCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            external_source="codex",
            external_session_id="sess_1",
            title="Design session",
            messages=[_message(role="user", text="hello", created_at="2026-04-18T10:00:00Z")],
            metadata=ConversationSourceMetadata(language="zh", tags=["conversation"]),
        )
    )

    result = ConversationSourceService.append_message(
        ConversationSourceAppendCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            conversation_id="codex:sess_1",
            message=_message(
                role="assistant",
                text="diagram",
                created_at="2026-04-18T10:00:05Z",
                part_type="image",
            ),
        )
    )

    view = ConversationSourceService.get_conversation(
        ConversationSourceGetQuery(user_id="u1", conversation_id="codex:sess_1")
    )
    assert result.appended is True
    assert result.message_count == 2
    assert result.version == 2
    assert view.modalities == ["image", "text"]
    assert view.updated_at == "2026-04-18T10:00:05Z"


@pytest.mark.anyio
async def test_append_missing_conversation_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
    fake_conversation_repository,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    with pytest.raises(ConversationSourceNotFoundError):
        ConversationSourceService.append_message(
            ConversationSourceAppendCommand(
                user_id="u1",
                conversation_id="codex:missing",
                message=_message(role="user", text="hello", created_at="2026-04-18T10:00:00Z"),
            )
        )


@pytest.mark.anyio
async def test_append_conflicting_scope_raises_conflict(
    monkeypatch: pytest.MonkeyPatch,
    fake_conversation_repository,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    ConversationSourceService.create_conversation(
        ConversationSourceCreateCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            external_source="codex",
            external_session_id="sess_1",
            title="Design session",
            messages=[_message(role="user", text="hello", created_at="2026-04-18T10:00:00Z")],
        )
    )

    with pytest.raises(ConversationSourceConflictError):
        ConversationSourceService.append_message(
            ConversationSourceAppendCommand(
                user_id="u1",
                agent_id="another-agent",
                project_id="proj-1",
                conversation_id="codex:sess_1",
                message=_message(role="assistant", text="world", created_at="2026-04-18T10:00:05Z"),
            )
        )


@pytest.mark.anyio
async def test_get_conversation_reads_pg_metadata_without_scanning_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    fake_conversation_repository,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    ConversationSourceService.create_conversation(
        ConversationSourceCreateCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            external_source="codex",
            external_session_id="sess_1",
            title="Design session",
            messages=[_message(role="user", text="hello", created_at="2026-04-18T10:00:00Z")],
        )
    )

    path = build_conversation_source_path(user_id="u1", external_source="codex", external_session_id="sess_1")
    storage.write_text_atomic(path, "not valid jsonl anymore\n")

    view = ConversationSourceService.get_conversation(ConversationSourceGetQuery(user_id="u1", conversation_id="codex:sess_1"))
    assert view.conversation_id == "codex:sess_1"
    assert view.message_ref.uri == path


@pytest.mark.anyio
async def test_append_raises_corrupted_when_jsonl_mixed_ids(
    monkeypatch: pytest.MonkeyPatch,
    fake_conversation_repository,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)

    ConversationSourceService.create_conversation(
        ConversationSourceCreateCommand(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            external_source="codex",
            external_session_id="sess_1",
            title="Design session",
            messages=[_message(role="user", text="hello", created_at="2026-04-18T10:00:00Z")],
        )
    )

    path = build_conversation_source_path(user_id="u1", external_source="codex", external_session_id="sess_1")
    storage.write_text_atomic(
        path,
        "\n".join(
            [
                json.dumps({"conversation_id": "codex:sess_1", "role": "user", "content_parts": [{"type": "text", "text": "hello"}], "created_at": "2026-04-18T10:00:00Z"}),
                json.dumps({"conversation_id": "codex:other", "role": "assistant", "content_parts": [{"type": "text", "text": "world"}], "created_at": "2026-04-18T10:00:01Z"}),
            ]
        )
        + "\n",
    )

    with pytest.raises(ConversationSourceCorruptedError):
        ConversationSourceService.append_message(
            ConversationSourceAppendCommand(
                user_id="u1",
                conversation_id="codex:sess_1",
                message=_message(role="assistant", text="append", created_at="2026-04-18T10:00:05Z"),
            )
        )
