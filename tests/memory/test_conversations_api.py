from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllers.memory.conversations import (
    append_conversation_message as append_conversation_message_endpoint,
)
from controllers.memory.conversations import create_conversation as create_conversation_endpoint
from controllers.memory.conversations import get_conversation as get_conversation_endpoint
from controllers.memory.schemas import ConversationAppendMessageRequest, ConversationCreateRequest, ConversationGetQuery
from service.memory import ConversationSourceNotFoundError, ConversationSourceService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_conversation_endpoint_returns_created_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ConversationSourceService,
        "create_conversation",
        staticmethod(
            lambda _command: {
                "conversation_id": "codex:sess_1",
                "type": "conversation",
                "title": "Design session",
                "user_id": "u1",
                "agent_id": "a1",
                "project_id": "proj-1",
                "external_source": "codex",
                "external_session_id": "sess_1",
                "message_ref": {
                    "type": "jsonl",
                    "uri": "memory_pipeline/users/u1/sources/conversations/codex__sess_1.jsonl",
                    "path": "memory_pipeline/users/u1/sources/conversations/codex__sess_1.jsonl",
                    "sha256": "sha256-1",
                },
                "message_count": 2,
                "modalities": ["text"],
                "version": 1,
                "created_at": "2026-04-18T10:00:00Z",
                "updated_at": "2026-04-18T10:00:05Z",
            }
        ),
    )

    response = await create_conversation_endpoint(
        ConversationCreateRequest(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            conversation={
                "external_source": "codex",
                "external_session_id": "sess_1",
                "title": "Design session",
                "messages": [
                    {"role": "user", "content_parts": [{"type": "text", "text": "hello"}], "created_at": "2026-04-18T10:00:00Z"}
                ],
            },
            metadata={"language": "zh", "tags": ["conversation"]},
        )
    )

    body = json.loads(response.body)
    assert response.status_code == 201
    assert body["success"] is True
    assert body["data"]["conversation_id"] == "codex:sess_1"


@pytest.mark.anyio
async def test_append_conversation_message_endpoint_returns_created_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ConversationSourceService,
        "append_message",
        staticmethod(
            lambda _command: {
                "conversation_id": "codex:sess_1",
                "appended": True,
                "message_count": 3,
                "version": 2,
                "updated_at": "2026-04-18T10:00:20Z",
            }
        ),
    )

    response = await append_conversation_message_endpoint(
        "codex:sess_1",
        ConversationAppendMessageRequest(
            user_id="u1",
            agent_id="a1",
            project_id="proj-1",
            message={
                "role": "assistant",
                "content_parts": [{"type": "text", "text": "hello"}],
                "created_at": "2026-04-18T10:00:20Z",
            },
        ),
    )

    body = json.loads(response.body)
    assert response.status_code == 201
    assert body["success"] is True
    assert body["data"]["message_count"] == 3


@pytest.mark.anyio
async def test_get_conversation_endpoint_returns_serialized_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ConversationSourceService,
        "get_conversation",
        staticmethod(
            lambda _query: {
                "conversation_id": "codex:sess_1",
                "type": "conversation",
                "title": "Design session",
                "user_id": "u1",
                "agent_id": "a1",
                "project_id": "proj-1",
                "external_source": "codex",
                "external_session_id": "sess_1",
                "message_ref": {
                    "type": "jsonl",
                    "uri": "memory_pipeline/users/u1/sources/conversations/codex__sess_1.jsonl",
                    "path": "memory_pipeline/users/u1/sources/conversations/codex__sess_1.jsonl",
                    "sha256": "sha256-1",
                },
                "message_count": 2,
                "modalities": ["text"],
                "version": 1,
                "created_at": "2026-04-18T10:00:00Z",
                "updated_at": "2026-04-18T10:00:05Z",
            }
        ),
    )

    response = await get_conversation_endpoint("codex:sess_1", ConversationGetQuery(user_id="u1"))
    body = json.loads(response.body)
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["message_ref"]["uri"].endswith("codex__sess_1.jsonl")


@pytest.mark.anyio
async def test_get_conversation_endpoint_surfaces_service_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_query):
        raise ConversationSourceNotFoundError("missing", details={"conversation_id": "codex:sess_1"})

    monkeypatch.setattr(ConversationSourceService, "get_conversation", staticmethod(_raise))

    response = await get_conversation_endpoint("codex:sess_1", ConversationGetQuery(user_id="u1"))
    body = json.loads(response.body)
    assert response.status_code == 404
    assert body["success"] is False
    assert body["error"]["code"] == "conversation_source_not_found"
