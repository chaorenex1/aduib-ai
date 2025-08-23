from models import ConversationMessage
from models.engine import get_session


class ConversationMessageService:

    @classmethod
    def add_conversation_message(cls,message:ConversationMessage) -> ConversationMessage:
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

    @classmethod
    def search_conversation_message(cls,search_text:str):
        pass

    @classmethod
    def update_conversation_message_state(cls,message_id, state:str) -> None:
        """
        Update the state of a conversation message by its ID.
        :param message_id: The ID of the conversation message to update.
        :param state: The new state to set for the conversation message.
        :raises ValueError: If the message with the given ID does not exist.
        :return: None
        """
        with get_session() as session:
            message = session.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
            if not message:
                raise ValueError(f"Message with id {message_id} not found.")
            message.state = state
            session.commit()
            session.refresh(message)
