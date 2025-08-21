from typing import Optional

from models import ConversationMessage
from models.engine import get_session


class ConversationMessageService:

    @staticmethod
    def add_conversation_message(message:ConversationMessage) -> ConversationMessage:
        """
        Add a conversation message to the database.
        :param message: ConversationMessage object to be added.
        :return: The added ConversationMessage object.
        """
        with get_session() as session:
            session.add(message)
            session.commit()
            session.refresh(message)
        return message

    @staticmethod
    def search_conversation_message(self,search_text:str):
        pass

    @staticmethod
    def update_conversation_message_state(message_id, state:str) -> None:
        with get_session() as session:
            message = session.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
            if not message:
                raise ValueError(f"Message with id {message_id} not found.")
            message.state = state
            session.commit()
            session.refresh(message)
