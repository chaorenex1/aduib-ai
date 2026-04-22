from __future__ import annotations

from models import ConversationMessage, get_db


class SessionMessageRepository:
    @staticmethod
    def list_session_messages(
        *,
        agent_session_id: int,
        user_id: str,
        agent_id: str | None,
    ) -> list[dict[str, object]]:
        with get_db() as session:
            query = session.query(ConversationMessage).filter(
                ConversationMessage.agent_session_id == agent_session_id,
                ConversationMessage.deleted == 0,
            )
            if user_id:
                query = query.filter(ConversationMessage.user_id == user_id)
            if agent_id and str(agent_id).isdigit():
                query = query.filter(ConversationMessage.agent_id == int(agent_id))
            messages = query.order_by(ConversationMessage.created_at.asc()).all()

        return [
            {
                "message_id": message.message_id,
                "role": message.role,
                "content": message.content,
                "user_id": message.user_id,
                "agent_id": message.agent_id,
                "agent_session_id": message.agent_session_id,
                "model_name": message.model_name,
                "provider_name": message.provider_name,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in messages
        ]
