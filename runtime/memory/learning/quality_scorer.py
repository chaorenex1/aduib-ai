from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from models.engine import get_db
from models.memory import MemoryBase, MemoryRecord

logger = logging.getLogger(__name__)


class QualityScorer:
    RECENCY_HALF_LIFE_DAYS: float = 30.0
    MAX_ACCESS_SATURATION: int = 10
    MAX_TAG_SATURATION: int = 5

    def __init__(self, params: dict | None = None) -> None:
        p = params or {}
        self.recency_half_life_days: float = p.get("recency_half_life_days", self.RECENCY_HALF_LIFE_DAYS)
        self.max_access_saturation: int = int(p.get("max_access_saturation", self.MAX_ACCESS_SATURATION))
        self.max_tag_saturation: int = int(p.get("max_tag_saturation", self.MAX_TAG_SATURATION))
        self.weight_recency: float = p.get("weight_recency", 0.5)
        self.weight_usage: float = p.get("weight_usage", 0.3)
        self.weight_richness: float = p.get("weight_richness", 0.2)

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def score_record(self, record: MemoryRecord, now: datetime | None = None) -> float:
        if now is None:
            now_utc = datetime.now(UTC)
        else:
            now_utc = self._to_utc(now)

        if record.accessed_at is None:
            days_since_access = 999.0
        else:
            accessed_at = self._to_utc(record.accessed_at)
            days_since_access = (now_utc - accessed_at).total_seconds() / 86400

        recency = math.exp(-days_since_access / self.recency_half_life_days)
        usage = min(1.0, (record.access_count or 0) / self.max_access_saturation)
        richness = min(1.0, len(record.tags or []) / self.max_tag_saturation)
        quality = round(self.weight_recency * recency + self.weight_usage * usage + self.weight_richness * richness, 6)
        return quality

    async def score_all(self, user_id: str) -> int:
        with get_db() as session:
            records = (
                session.query(MemoryRecord)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == user_id,
                    MemoryRecord.deleted == 0,
                )
                .all()
            )

            if not records:
                logger.info("QualityScorer: scored 0 records for user %s", user_id)
                return 0

            now_utc = datetime.now(UTC)
            updates = [
                {"id": record.id, "quality_score": self.score_record(record, now=now_utc)} for record in records
            ]  # score_record is now an instance method using self.* params

            session.bulk_update_mappings(MemoryRecord, updates)
            session.commit()

            logger.info("QualityScorer: scored %d records for user %s", len(updates), user_id)
            return len(updates)
