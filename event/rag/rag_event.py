from event.event_manager import event_manager_context
from service import KnowledgeBaseService

event_manager = event_manager_context.get()


@event_manager.subscribe(event="paragraph_rag_from_web_memo")
async def paragraph_rag_from_web_memo(crawl_text: str, crawl_type: str) -> None:
    """
    Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
    """
    await KnowledgeBaseService.paragraph_rag_from_web_memo(crawl_text, crawl_type)
