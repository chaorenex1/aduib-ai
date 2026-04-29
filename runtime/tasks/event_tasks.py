from __future__ import annotations

import asyncio
import datetime
import json

from celery.utils.log import get_task_logger

from runtime.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


def _build_conversation_message(message_dict: dict):
    """Reconstruct a ConversationMessage from a plain dict (not persisted to DB)."""
    from models import ConversationMessage

    return ConversationMessage(
        message_id=message_dict.get("message_id"),
        agent_id=message_dict.get("agent_id"),
        agent_session_id=message_dict.get("agent_session_id"),
        model_name=message_dict.get("model_name", ""),
        provider_name=message_dict.get("provider_name", ""),
        model_parameters=message_dict.get("model_parameters"),
        role=message_dict.get("role", ""),
        content=message_dict.get("content", ""),
        system_prompt=message_dict.get("system_prompt"),
        usage=message_dict.get("usage"),
        state=message_dict.get("state", "success"),
        user_id=message_dict.get("user_id"),
    )


def _sync_to_clickhouse(message) -> None:
    """Write conversation_message and message_token_usage rows to ClickHouse."""
    try:
        from component.clickhouse.client import get_ch_client

        client = get_ch_client()
    except RuntimeError:
        # ClickHouse disabled or not initialized
        return

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
        logger.exception("Failed to sync conversation_message to ClickHouse (message_id=%s)", message.message_id)

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
        logger.exception("Failed to sync message_token_usage to ClickHouse (message_id=%s)", message.message_id)


@celery_app.task(
    bind=True,
    name="event.paragraph_rag_from_web_memo",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def paragraph_rag_from_web_memo_task(self, crawl_text: str, crawl_type: str) -> None:
    from service import KnowledgeBaseService

    asyncio.run(KnowledgeBaseService.paragraph_rag_from_web_memo(crawl_text, crawl_type))


@celery_app.task(
    bind=True,
    name="event.qa_rag_from_conversation_message",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def qa_rag_from_conversation_message_task(self, message_dict: dict) -> None:
    from service import ConversationMessageService

    message = _build_conversation_message(message_dict)
    ConversationMessageService.add_conversation_message(message)
    _sync_to_clickhouse(message)


@celery_app.task(
    bind=True,
    name="event.memory_retrieval_logged",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def memory_retrieval_logged_task(self, trace: dict) -> None:
    # Legacy runtime memory retrieval logging depended on deleted ORM models and
    # retrieval pipeline files. Keep the old task entrypoint in place only to
    # avoid accidental dispatch failures while business callers are being cleaned
    # up elsewhere.
    logger.info("memory_retrieval_logged_task skipped because legacy memory retrieval logging was retired")


@celery_app.task(
    bind=True,
    name="event.memory_learning_cycle",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def memory_learning_cycle_task(self, user_id: str) -> None:
    # Legacy memory learning depended on deleted runtime.memory.learning files.
    logger.info("memory_learning_cycle_task skipped because the legacy memory learning pipeline was retired")


@celery_app.task(
    bind=True,
    name="event.memory_learning_scan",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def memory_learning_scan_task(self) -> None:
    # Legacy memory learning scans depended on deleted ORM/runtime files.
    logger.info("memory_learning_scan_task skipped because the legacy memory learning scan was retired")


@celery_app.task(
    bind=True,
    name="event.learning_signal_persist",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def learning_signal_persist_task(
    self,
    user_id: str,
    agent_id: str = "",
    signal_type: str = "",
    source_id: str | None = None,
    value: float = 0.0,
    context: dict | None = None,
) -> None:
    """Persist a single LearningSignal record to the database."""
    import datetime
    import uuid

    from models import LearningSignal, get_db

    record = LearningSignal(
        id=uuid.uuid4(),
        user_id=user_id,
        agent_id=agent_id or None,
        signal_type=signal_type,
        source_id=source_id or None,
        value=float(value),
        context=context or {},
        created_at=datetime.datetime.now(),
    )
    with get_db() as session:
        session.add(record)
        session.commit()
    logger.info(
        "learning_signal persisted: user=%s type=%s source=%s value=%.2f",
        user_id,
        signal_type,
        source_id,
        value,
    )


@celery_app.task(
    bind=True,
    name="event.learning_signal_persist_batch",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def learning_signal_persist_batch_task(self, signals: list) -> None:
    """Persist a batch of LearningSignal records in a single DB transaction."""
    import datetime
    import uuid

    from models import LearningSignal, get_db

    if not signals:
        return

    records = []
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        records.append(
            LearningSignal(
                id=uuid.uuid4(),
                user_id=sig.get("user_id", ""),
                agent_id=sig.get("agent_id") or None,
                signal_type=sig.get("signal_type", ""),
                source_id=sig.get("source_id") or None,
                value=float(sig.get("value", 0.0)),
                context=sig.get("context") or {},
                created_at=datetime.datetime.now(),
            )
        )

    with get_db() as session:
        session.bulk_save_objects(records)
        session.commit()
    logger.info("learning_signal_persist_batch: wrote %d signals", len(records))
