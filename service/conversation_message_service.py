import json

from models import ConversationMessage
from models.engine import get_db
from models.message import MessageTokenUsage
from runtime.entities import LLMUsage


class ConversationMessageService:
    @classmethod
    def add_conversation_message(cls, message: ConversationMessage) -> ConversationMessage:
        """
        Add a conversation message to the database.
        :param message: ConversationMessage object to be added.
        :return: The added ConversationMessage object.
        """
        with get_db() as session:
            session.add(message)
            session.commit()

            if message.usage:
                with get_db() as session2:
                    llm_usage = LLMUsage.model_validate(obj=json.loads(message.usage))
                    usage = MessageTokenUsage(
                        agent_id=message.agent_id,
                        agent_session_id=message.agent_session_id,
                        message_id=message.message_id,
                        model_name=message.model_name,
                        provider_name=message.provider_name,
                        prompt_tokens=llm_usage.prompt_tokens,
                        completion_tokens=llm_usage.completion_tokens,
                        total_tokens=llm_usage.total_tokens,
                        prompt_unit_price=llm_usage.prompt_unit_price,
                        prompt_price=llm_usage.prompt_price,
                        completion_unit_price=llm_usage.completion_unit_price,
                        completion_price=llm_usage.completion_price,
                        total_price=llm_usage.total_price,
                    )
                    session2.add(usage)
                    session2.commit()
        return message

    @classmethod
    def search_conversation_message(cls, search_text: str):
        pass

    @classmethod
    def update_conversation_message_state(cls, message_id, state: str) -> None:
        """
        Update the state of a conversation message by its ID.
        :param message_id: The ID of the conversation message to update.
        :param state: The new state to set for the conversation message.
        :raises ValueError: If the message with the given ID does not exist.
        :return: None
        """
        with get_db() as session:
            message = session.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
            if not message:
                raise ValueError(f"Message with id {message_id} not found.")
            message.state = state
            session.commit()
            session.refresh(message)

    @classmethod
    def get_context_length(cls, agent_id, session_id):
        with get_db() as session:
            messages = (
                session.query(MessageTokenUsage)
                .filter(MessageTokenUsage.agent_id == agent_id, MessageTokenUsage.agent_session_id == session_id)
                .all()
            )
            total_tokens = sum(message.prompt_tokens for message in messages)
            return total_tokens

    @classmethod
    def get_prev_message_id(cls, agent_id, session_id, message_id):
        with get_db() as session:
            # 取出不等于当前message_id的最后一条消息
            message = (
                session.query(ConversationMessage)
                .filter(
                    ConversationMessage.agent_id == agent_id,
                    ConversationMessage.agent_session_id == session_id,
                    ConversationMessage.message_id != message_id,
                )
                .order_by(ConversationMessage.created_at.desc())
                .first()
            )
            if message:
                return message.message_id
            return None
