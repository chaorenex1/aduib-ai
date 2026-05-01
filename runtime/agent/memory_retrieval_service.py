from __future__ import annotations

from controllers.memory.schemas import ContentPart, ConversationMessagePayload
from runtime.memory.find import MemoryFindRuntime
from runtime.memory.find_types import MemoryFindRequestDTO
from runtime.memory.search import MemorySearchRuntime
from runtime.memory.search_types import MemorySearchRequestDTO


class MemoryRetrievalService:
    @classmethod
    async def retrieve_for_turn(
        cls,
        *,
        mode: str,
        user_id: str,
        latest_user_text: str,
        session_messages,
    ) -> tuple[str | None, str]:
        query = " ".join(str(latest_user_text or "").split())
        if not query:
            return None, "none"
        if mode == "agent" and session_messages:
            payload = MemorySearchRequestDTO(
                query=query,
                session=cls._build_session_payload(session_messages),
            )
            response = MemorySearchRuntime.search_for_current_user(user_id, payload)
            return cls.build_memory_attachment(response.results), "search"
        payload = MemoryFindRequestDTO(query=query)
        response = MemoryFindRuntime.find_for_current_user(user_id, payload)
        return cls.build_memory_attachment(response.results), "find"

    @staticmethod
    def _build_session_payload(session_messages) -> list[ConversationMessagePayload]:
        payload: list[ConversationMessagePayload] = []
        for message in session_messages[-8:]:
            role = getattr(message, "role", None)
            if role not in {"user", "assistant"}:
                role = "assistant" if role == "assistant" else "user"
            payload.append(
                ConversationMessagePayload(
                    role=role,
                    content_parts=[ContentPart(type="text", text=str(message.content))],
                )
            )
        return payload

    @staticmethod
    def build_memory_attachment(results) -> str | None:
        if not results:
            return None
        parts = []
        for index, item in enumerate(results, start=1):
            score = getattr(item, "score", 0.0)
            memory_type = getattr(item, "memory_type", "unknown")
            abstract = getattr(item, "abstract", "")
            parts.append(f'<memory rank="{index}" score="{score:.3f}" type="{memory_type}">{abstract}</memory>')
        return "\n".join(parts)
