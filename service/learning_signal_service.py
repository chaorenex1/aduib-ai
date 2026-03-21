import asyncio
import datetime
import logging
import uuid
from collections.abc import Iterable
from typing import Any, Optional

from runtime.memory.types import MemorySignalType

logger = logging.getLogger(__name__)


class LearningSignalService:
    """Fire-and-forget service for emitting learning signals.

    Uses event_manager to dispatch Celery tasks asynchronously,
    never blocking the Agent execution main path.
    Falls back to direct DB write if event_manager is unavailable.
    """

    @staticmethod
    def _normalize_signal_type(signal_type: str | MemorySignalType) -> str:
        if isinstance(signal_type, MemorySignalType):
            return signal_type.value
        return str(signal_type)

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["signal_type"] = cls._normalize_signal_type(normalized.get("signal_type", ""))
        normalized["agent_id"] = normalized.get("agent_id") or ""
        normalized["value"] = float(normalized.get("value", 0.0))
        normalized["context"] = normalized.get("context") or {}
        return normalized

    @classmethod
    async def emit(
        cls,
        user_id: str,
        signal_type: str | MemorySignalType,
        source_id: Optional[str] = None,
        value: float = 0.0,
        context: Optional[dict] = None,
    ) -> None:
        """Emit a single learning signal (fire-and-forget).

        Dispatches via event_manager -> Celery task.
        Falls back to direct DB write if dispatch fails.
        """
        # Build payload
        payload = cls._normalize_payload(
            {
                "user_id": user_id,
                "signal_type": signal_type,
                "source_id": source_id,
                "value": float(value),
                "context": context or {},
            }
        )
        try:
            from event.event_manager import event_manager_context

            em = event_manager_context.get()
            if em is not None:
                await em.emit_async("learning_signal_persist", **payload)
                return
        except Exception as exc:
            logger.debug(
                "LearningSignalService.emit: event_manager dispatch failed (%s), falling back to direct write", exc
            )

        # Fallback: direct DB write in background thread
        asyncio.create_task(_write_signal_direct(payload))

    @classmethod
    async def emit_batch(cls, signals: list[dict]) -> None:
        """Emit multiple learning signals at once (fire-and-forget).

        Each dict must have: user_id (str), signal_type (str).
        Optional: source_id, value, context, agent_id.
        Dispatches as a single batch Celery task.
        Falls back to individual direct writes.
        """
        normalized_signals = [cls._normalize_payload(sig) for sig in signals if isinstance(sig, dict)]
        if not normalized_signals:
            return
        try:
            from event.event_manager import event_manager_context

            em = event_manager_context.get()
            if em is not None:
                await em.emit_async("learning_signal_persist_batch", signals=normalized_signals)
                return
        except Exception as exc:
            logger.debug("LearningSignalService.emit_batch: event_manager dispatch failed (%s), falling back", exc)

        # Fallback: write each directly
        for sig in normalized_signals:
            asyncio.create_task(_write_signal_direct(sig))

    @classmethod
    async def emit_memory_signals(
        cls,
        user_id: str,
        signal_type: str | MemorySignalType,
        memory_ids: Iterable[str],
        *,
        context: Optional[dict[str, Any]] = None,
        value: float = 0.0,
        value_by_source: Optional[dict[str, float]] = None,
    ) -> None:
        signals: list[dict[str, Any]] = []
        for memory_id in memory_ids:
            if not memory_id:
                continue
            signals.append(
                {
                    "user_id": user_id,
                    "signal_type": signal_type,
                    "source_id": memory_id,
                    "value": (
                        float(value_by_source[memory_id])
                        if value_by_source and memory_id in value_by_source
                        else float(value)
                    ),
                    "context": dict(context or {}),
                }
            )
        await cls.emit_batch(signals)


async def _write_signal_direct(payload: dict) -> None:
    """Background coroutine: write a single LearningSignal record directly to DB."""
    try:
        from models import LearningSignal

        record = LearningSignal(
            id=uuid.uuid4(),
            user_id=payload.get("user_id", ""),
            signal_type=payload.get("signal_type", ""),
            source_id=payload.get("source_id") or None,
            value=float(payload.get("value", 0.0)),
            context=payload.get("context") or {},
            created_at=datetime.datetime.now(),
        )
        await asyncio.to_thread(_db_insert, record)
    except Exception as exc:
        logger.warning("LearningSignalService._write_signal_direct failed: %s", exc)


def _db_insert(record) -> None:
    """Sync DB insert helper called via asyncio.to_thread."""
    from models import get_db

    with get_db() as session:
        session.add(record)
        session.commit()
