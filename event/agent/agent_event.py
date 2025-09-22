import logging

from event.event_manager import event_manager_context
from models import ConversationMessage
from runtime.agent.agent_type import Message
from runtime.agent_mamager import AgentMessageRecordCallback

event_manager = event_manager_context.get()

logger = logging.getLogger(__name__)


@event_manager.subscribe(event="agent_from_conversation_message")
async def agent_from_conversation_message(message: ConversationMessage,callback:AgentMessageRecordCallback) -> None:
    """
    Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
    """
    logger.debug(f"agent_from_conversation_message message: {message},callback:{callback}")
    from service import ConversationMessageService
    ConversationMessageService.add_conversation_message(message)
    if message.role == 'assistant' and message.state == 'success' and len(message.content.strip()) > 0:
        import time
        # 更新消息并添加到内存
        message_id = message.message_id
        message_content = message.content
        callback.agent_manager.get_or_create_memory(callback.agent, callback.session_id).add_interaction(Message(
            id=message_id,
            user_message=callback.user_message if hasattr(callback, 'user_message') else "",
            assistant_message=message_content,
            prev_message_id=ConversationMessageService.get_prev_message_id(agent_id=callback.agent.id,
                                                                           session_id=callback.session_id,
                                                                           message_id=message_id),
            meta={"timestamp": time.time()}
        ))