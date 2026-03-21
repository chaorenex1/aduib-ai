from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from models.document import KnowledgeDocument
from models.engine import get_db
from models.memory import MemoryBase, MemoryRecord

logger = logging.getLogger(__name__)


@dataclass
class PruneResult:
    evaluated: int = 0
    pruned: int = 0
    skipped: int = 0


class MemoryPruner:
    QUALITY_THRESHOLD: float = 0.2
    INACTIVE_DAYS: int = 60
    RETENTION_THRESHOLD: float = 0.1
    HALF_LIFE_HOURS: float = 168.0

    def __init__(self, params: dict | None = None) -> None:
        p = params or {}
        self.quality_threshold: float = p.get("quality_threshold", self.QUALITY_THRESHOLD)
        self.inactive_days: int = int(p.get("inactive_days", self.INACTIVE_DAYS))
        self.retention_threshold: float = p.get("retention_threshold", self.RETENTION_THRESHOLD)
        self.half_life_hours: float = p.get("half_life_hours", self.HALF_LIFE_HOURS)

    async def prune(self, user_id: str) -> PruneResult:
        result = PruneResult()
        cutoff = datetime.now(UTC) - timedelta(days=self.inactive_days)

        with get_db() as session:
            records = (
                session.query(MemoryRecord)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == user_id,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.quality_score < self.quality_threshold,
                )
                .filter(MemoryRecord.accessed_at < cutoff.replace(tzinfo=None))
                .all()
            )
            for record in records:
                session.expunge(record)

        now = datetime.now(UTC)
        to_prune: list[tuple[object, object | None]] = []

        for record in records:
            result.evaluated += 1
            accessed = record.accessed_at
            if accessed is None:
                result.skipped += 1
                continue
            if accessed.tzinfo is None:
                accessed = accessed.replace(tzinfo=UTC)
            hours_elapsed = (now - accessed).total_seconds() / 3600
            retention = math.exp(-hours_elapsed / self.half_life_hours)
            if retention >= self.retention_threshold:
                result.skipped += 1
                continue

            to_prune.append((record.id, record.kb_doc_id))
            logger.info(
                "MemoryPruner: pruned memory %s (retention=%.3f, quality=%.3f)",
                record.id,
                retention,
                record.quality_score if record.quality_score is not None else 0.0,
            )
            result.pruned += 1

        if to_prune:
            mem_ids = [item[0] for item in to_prune]
            doc_ids = [item[1] for item in to_prune if item[1] is not None]
            with get_db() as session:
                session.query(MemoryRecord).filter(MemoryRecord.id.in_(mem_ids)).update(
                    {MemoryRecord.deleted: 1}, synchronize_session=False
                )
                if doc_ids:
                    session.query(KnowledgeDocument).filter(KnowledgeDocument.id.in_(doc_ids)).update(
                        {KnowledgeDocument.deleted: 1}, synchronize_session=False
                    )
                session.commit()

        return result
