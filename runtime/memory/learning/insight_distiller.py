from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func

from models.document import KnowledgeDocument
from models.engine import get_db
from models.memory import MemoryBase, MemoryRecord
from runtime.generator.generator import LLMGenerator
from runtime.memory.manager import MemoryManager
from runtime.memory.types import Memory, MemoryClassType

logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    topics_processed: int = 0
    insights_created: int = 0
    skipped: int = 0


class InsightDistiller:
    MIN_EPISODIC_COUNT: int = 3
    MAX_TOPICS_PER_RUN: int = 10

    def __init__(self, params: dict | None = None) -> None:
        p = params or {}
        self.min_episodic_count: int = int(p.get("min_episodic_count", self.MIN_EPISODIC_COUNT))
        self.max_topics_per_run: int = int(p.get("max_topics_per_run", self.MAX_TOPICS_PER_RUN))

    async def distill(self, user_id: str) -> DistillationResult:
        result = DistillationResult()

        with get_db() as session:
            episodic_counts = (
                session.query(MemoryRecord.domain, MemoryRecord.topic, func.count().label("cnt"))
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == user_id,
                    MemoryRecord.type == MemoryClassType.EPISODIC.value,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.topic.isnot(None),
                    MemoryRecord.topic != "",
                )
                .group_by(MemoryRecord.domain, MemoryRecord.topic)
                .having(func.count() >= self.min_episodic_count)
                .all()
            )
            topic_keys = [(row.domain or "", row.topic) for row in episodic_counts if row.topic]

            if not topic_keys:
                return result

            semantic_topic_keys = {
                (row.domain or "", row.topic)
                for row in session.query(MemoryRecord.domain, MemoryRecord.topic)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == user_id,
                    MemoryRecord.type == MemoryClassType.SEMANTIC.value,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.topic.isnot(None),
                    MemoryRecord.topic != "",
                )
                .all()
            }
            eligible_topic_keys = [topic_key for topic_key in topic_keys if topic_key not in semantic_topic_keys][
                : self.max_topics_per_run
            ]

        for topic_domain, topic_name in eligible_topic_keys:
            result.topics_processed += 1
            episodic_contents = self._load_episodic_contents(topic_domain, topic_name)
            if not episodic_contents:
                result.skipped += 1
                continue

            insight = LLMGenerator.distill_semantic_insight(topic_name, episodic_contents)
            if not insight:
                result.skipped += 1
                continue

            semantic_memory = Memory(
                type=MemoryClassType.SEMANTIC,
                content=insight,
                user_id=user_id,
                domain=topic_domain or "",
                source="distillation",
                topic=topic_name,
                tags=[],
            )
            manager = MemoryManager(user_id=user_id)
            await manager.store(semantic_memory)
            logger.info("InsightDistiller: created insight for topic %s/%s", topic_domain, topic_name)
            result.insights_created += 1

        return result

    def _load_episodic_contents(self, topic_domain: str, topic_name: str) -> list[str]:
        with get_db() as session:
            records = (
                session.query(MemoryRecord)
                .filter(
                    MemoryRecord.domain == topic_domain,
                    MemoryRecord.topic == topic_name,
                    MemoryRecord.type == MemoryClassType.EPISODIC.value,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.kb_doc_id.isnot(None),
                )
                .order_by(MemoryRecord.created_at.asc())
                .limit(20)
                .all()
            )
            kb_doc_ids = [record.kb_doc_id for record in records]
            if not kb_doc_ids:
                return []
            docs = (
                session.query(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.id.in_(kb_doc_ids),
                    KnowledgeDocument.deleted == 0,
                )
                .all()
            )
            return [doc.content for doc in docs if doc.content]
