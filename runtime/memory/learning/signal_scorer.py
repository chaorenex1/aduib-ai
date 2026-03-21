from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from models.engine import get_db
from models.memory import MemoryBase, MemoryRecord
from runtime.memory.types import MemorySignalType

logger = logging.getLogger(__name__)

ALPHA = 0.3  # blend weight for new signal quality


@dataclass
class SignalScorerResult:
    signals_processed: int = 0
    memories_updated: int = 0


class SignalScorer:
    """Phase 5 of learning cycle: blend adoption signals into MemoryRecord.quality_score."""

    def __init__(self, lookback_days: int = 30) -> None:
        # Only consider signals from the last `lookback_days` days
        self.lookback_days = lookback_days

    async def score_all(self, user_id: str) -> SignalScorerResult:
        """
        1. Query LearningSignal(user_id=user_id, signal_type="memory_adoption",
                                created_at >= now - lookback_days)
        2. Group by source_id → compute mean(value)
        3. For each source_id that is a valid UUID and maps to an existing MemoryRecord:
             normalized = (mean_value + 1.0) / 2.0
             new_quality = 0.7 * (record.quality_score or 0.5) + 0.3 * normalized
             clamp to [0.0, 1.0]
        4. bulk_update_mappings MemoryRecord
        5. Return SignalScorerResult(signals_processed, memories_updated)
        """
        from models.learning_signal import LearningSignal

        cutoff = datetime.utcnow() - timedelta(days=self.lookback_days)

        # Step 1: load signals
        with get_db() as session:
            rows = (
                session.query(LearningSignal.source_id, LearningSignal.value)
                .filter(
                    LearningSignal.user_id == user_id,
                    LearningSignal.signal_type == MemorySignalType.MEMORY_ADOPTION.value,
                    LearningSignal.source_id.isnot(None),
                    LearningSignal.created_at >= cutoff,
                )
                .all()
            )

        if not rows:
            return SignalScorerResult()

        signals_processed = len(rows)

        # Step 2: group by source_id → mean(value)
        sums: dict[str, list[float]] = {}
        for source_id, value in rows:
            sums.setdefault(source_id, []).append(float(value))

        mean_by_id: dict[str, float] = {sid: sum(vals) / len(vals) for sid, vals in sums.items()}

        # Step 3: fetch matching MemoryRecords and compute new quality
        valid_uuids: list[uuid.UUID] = []
        uuid_map: dict[str, uuid.UUID] = {}
        for sid in mean_by_id:
            try:
                u = uuid.UUID(sid)
                valid_uuids.append(u)
                uuid_map[sid] = u
            except (ValueError, AttributeError):
                pass

        if not valid_uuids:
            return SignalScorerResult(signals_processed=signals_processed)

        with get_db() as session:
            records = (
                session.query(MemoryRecord)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == user_id,
                    MemoryRecord.id.in_(valid_uuids),
                    MemoryRecord.deleted == 0,
                )
                .all()
            )

            if not records:
                return SignalScorerResult(signals_processed=signals_processed)

            updates = []
            for record in records:
                sid = str(record.id)
                mean_val = mean_by_id.get(sid)
                if mean_val is None:
                    continue
                normalized = (mean_val + 1.0) / 2.0
                old_quality = record.quality_score if record.quality_score is not None else 0.5
                new_quality = round(max(0.0, min(1.0, (1.0 - ALPHA) * old_quality + ALPHA * normalized)), 6)
                updates.append({"id": record.id, "quality_score": new_quality})

            if updates:
                session.bulk_update_mappings(MemoryRecord, updates)
                session.commit()

        logger.info(
            "SignalScorer: user=%s signals=%d memories_updated=%d",
            user_id,
            signals_processed,
            len(updates),
        )
        return SignalScorerResult(
            signals_processed=signals_processed,
            memories_updated=len(updates),
        )
