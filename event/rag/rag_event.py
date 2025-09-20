from event.event_manager import event_manager_context
from models import ConversationMessage
from service import KnowledgeBaseService

event_manager = event_manager_context.get()


@event_manager.subscribe(event="paragraph_rag_from_web_memo")
async def paragraph_rag_from_web_memo(crawl_text: str, crawl_type: str) -> None:
    """
    Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
    """
    await KnowledgeBaseService.paragraph_rag_from_web_memo(crawl_text, crawl_type)


@event_manager.subscribe(event="qa_rag_from_conversation_message")
async def qa_rag_from_conversation_message(message: ConversationMessage) -> None:
    """
    Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
    """
    from service import ConversationMessageService
    ConversationMessageService.add_conversation_message(message)
    if message.role == 'assistant' and message.state == 'success' and len(message.content.strip()) > 0:
        await KnowledgeBaseService.qa_rag_from_conversation_message()
