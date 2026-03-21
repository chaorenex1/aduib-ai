import json
import logging

from event.event_manager import event_manager_context
from models import ConversationMessage
from service import KnowledgeBaseService

log = logging.getLogger(__name__)

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
    Persist conversation message to PostgreSQL, then sync to ClickHouse for analytics.
    """
    from service import ConversationMessageService

    ConversationMessageService.add_conversation_message(message)
    _sync_to_clickhouse(message)


def _sync_to_clickhouse(message: ConversationMessage) -> None:
    """
    Write conversation_message and message_token_usage rows to ClickHouse.
    Uses ReplacingMergeTree — re-inserting with the same message_id and a
    newer updated_at will replace the old row during background merges
    (query with FINAL to get deduplicated results immediately).
    """
    try:
        from component.clickhouse.client import get_ch_client

        client = get_ch_client()
    except RuntimeError:
        # ClickHouse disabled or not initialized
        return

    import datetime

    now = datetime.datetime.now()

    try:
        client.insert(
            "conversation_message",
            [
                [
                    message.message_id or "",
                    message.agent_id or 0,
                    message.agent_session_id or 0,
                    message.model_name or "",
                    message.provider_name or "",
                    message.role or "",
                    message.content or "",
                    message.state or "",
                    message.user_id or "",
                    message.created_at or now,
                    message.updated_at or now,
                ]
            ],
            column_names=[
                "message_id",
                "agent_id",
                "agent_session_id",
                "model_name",
                "provider_name",
                "role",
                "content",
                "state",
                "user_id",
                "created_at",
                "updated_at",
            ],
        )
    except Exception:
        log.exception("Failed to sync conversation_message to ClickHouse (message_id=%s)", message.message_id)

    if not message.usage:
        return

    try:
        from runtime.entities import LLMUsage

        llm_usage = LLMUsage.model_validate(obj=json.loads(message.usage))
        client.insert(
            "message_token_usage",
            [
                [
                    message.message_id or "",
                    message.agent_id or 0,
                    message.agent_session_id or 0,
                    message.model_name or "",
                    message.provider_name or "",
                    llm_usage.prompt_tokens,
                    llm_usage.cached_tokens or 0,
                    llm_usage.completion_tokens,
                    llm_usage.thinking_tokens or 0,
                    llm_usage.total_tokens,
                    llm_usage.total_price,
                    llm_usage.cache_price or 0,
                    llm_usage.thinking_price or 0,
                    message.created_at or now,
                    now,
                ]
            ],
            column_names=[
                "message_id",
                "agent_id",
                "agent_session_id",
                "model_name",
                "provider_name",
                "prompt_tokens",
                "cached_prompt_tokens",
                "completion_tokens",
                "thinking_tokens",
                "total_tokens",
                "total_price",
                "cache_price",
                "thinking_price",
                "created_at",
                "updated_at",
            ],
        )
    except Exception:
        log.exception("Failed to sync message_token_usage to ClickHouse (message_id=%s)", message.message_id)
