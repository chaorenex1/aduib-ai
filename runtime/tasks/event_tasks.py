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
    """Persist RetrievalTrace to memory_retrieval_log + memory_retrieval_result."""
    import uuid

    from models.engine import get_db
    from models.memory_retrieval_log import MemoryRetrievalLog, MemoryRetrievalResult

    result_details: list[dict] = trace.get("result_details", [])
    has_results = trace.get("final_count", 0) > 0

    with get_db() as session:
        log_row = MemoryRetrievalLog(
            user_id=trace.get("user_id", ""),
            agent_id=trace.get("agent_id"),
            project_id=trace.get("project_id"),
            retrieve_type=trace.get("retrieve_type", "llm"),
            top_k=trace.get("top_k", 5),
            query_hash=trace.get("query_hash", ""),
            ms_domain_count=trace.get("ms_domain_count", 0),
            ms_topic_count=trace.get("ms_topic_count", 0),
            latency_step0_ms=trace.get("latency_step0_ms", 0),
            latency_step1_ms=trace.get("latency_step1_ms", 0),
            candidate_total_raw=trace.get("candidate_total_raw", 0),
            candidate_total_unique=trace.get("candidate_total_unique", 0),
            latency_step2_ms=trace.get("latency_step2_ms", 0),
            judge_input_count=trace.get("judge_input_count", 0),
            judge_output_count=trace.get("judge_output_count", 0),
            judge_selection_rate=trace.get("judge_selection_rate") if has_results else None,
            judge_failed=trace.get("judge_failed", False),
            judge_score_weights=trace.get("judge_score_weights") or None,
            judge_weight_reason=trace.get("judge_weight_reason") or None,
            latency_step3_ms=trace.get("latency_step3_ms", 0),
            react_enabled=trace.get("react_enabled", False),
            react_step_count=trace.get("react_step_count", 0),
            react_stop_reason=trace.get("react_stop_reason") or None,
            react_repeated_action_count=trace.get("react_repeated_action_count", 0),
            react_total_new_candidates=trace.get("react_total_new_candidates", 0),
            react_unique_action_query_count=trace.get("react_unique_action_query_count", 0),
            react_steps=trace.get("react_steps") or None,
            final_count=trace.get("final_count", 0),
            final_score_avg=trace.get("final_score_avg") if has_results else None,
            final_score_p50=trace.get("final_score_p50") if has_results else None,
            final_score_p10=trace.get("final_score_p10") if has_results else None,
            domain_dist=trace.get("domain_dist") or None,
            source_dist=trace.get("source_dist") or None,
            type_dist=trace.get("type_dist") or None,
            latency_total_ms=trace.get("latency_total_ms", 0),
        )
        session.add(log_row)
        session.flush()  # 获取 log_row.id，用于 result 外键

        for detail in result_details:
            try:
                mem_uuid = uuid.UUID(detail["memory_id"])
            except (ValueError, KeyError, TypeError):
                continue
            session.add(
                MemoryRetrievalResult(
                    log_id=log_row.id,
                    memory_id=mem_uuid,
                    hit_count=detail.get("hit_count", 1),
                    evidence_count=detail.get("evidence_count", 1),
                    rag_score=detail.get("rag_score") or None,
                    from_expansion=detail.get("from_expansion", False),
                    judge_rank=detail.get("judge_rank"),
                    final_score=detail.get("final_score") or None,
                    final_rank=detail.get("final_rank"),
                    memory_domain=detail.get("memory_domain", ""),
                    memory_type=detail.get("memory_type", ""),
                    memory_source=detail.get("memory_source", ""),
                    retrieval_sources=detail.get("retrieval_sources") or None,
                    access_count_at_query=detail.get("access_count_at_query", 0),
                )
            )

        session.commit()

    logger.info(
        "Retrieval trace persisted: log_id=%s user=%s type=%s results=%d latency=%dms",
        log_row.id,
        trace.get("user_id"),
        trace.get("retrieve_type"),
        len(result_details),
        trace.get("latency_total_ms", 0),
    )


@celery_app.task(
    bind=True,
    name="event.memory_learning_cycle",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def memory_learning_cycle_task(self, user_id: str) -> None:
    """Run the full 4-phase memory learning cycle for a single user."""
    if not user_id:
        return
    from runtime.memory.learning.engine import MemoryLearningEngine

    result = asyncio.run(MemoryLearningEngine(user_id).run_learning_cycle())
    if result.error:
        logger.info("Learning cycle skipped for user %s: %s", user_id, result.error)
    else:
        logger.info(
            "Learning cycle complete for user %s: scored=%d insights=%d merges=%d pruned=%d elapsed=%.2fs",
            user_id,
            result.quality_scored,
            result.insights_created,
            result.merges_performed,
            result.memories_pruned,
            result.elapsed_seconds,
        )


@celery_app.task(
    bind=True,
    name="event.memory_learning_scan",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def memory_learning_scan_task(self) -> None:
    """Daily scan: find users with new memories in last 24h and trigger learning."""
    from datetime import timedelta

    from models.engine import get_db
    from models.memory import MemoryBase, MemoryRecord

    cutoff = datetime.datetime.now(datetime.UTC) - timedelta(hours=24)
    cutoff_naive = cutoff.replace(tzinfo=None)

    with get_db() as session:
        rows = (
            session.query(MemoryBase.user_id)
            .join(MemoryRecord, MemoryRecord.memory_base_id == MemoryBase.id)
            .filter(MemoryRecord.created_at >= cutoff_naive)
            .filter(MemoryRecord.deleted == 0)
            .distinct()
            .all()
        )

    dispatched = 0
    for (user_id,) in rows:
        if user_id:
            memory_learning_cycle_task.delay(user_id)
            dispatched += 1

    logger.info("memory_learning_scan: dispatched learning cycle for %d users", dispatched)


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
