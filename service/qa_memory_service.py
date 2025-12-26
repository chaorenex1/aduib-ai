import datetime
from typing import Any, Iterable, Sequence

from sqlalchemy import select

from component.vdb.vector_factory import Vector
from models import (
    KnowledgeBase,
    QaMemoryEvent,
    QaMemoryLevel,
    QaMemoryRecord,
    QaMemoryStatus,
    get_db,
)
from runtime.entities.document_entities import Document
from runtime.rag.rag_type import RagType


class QAMemoryService:
    """Service layer for QA memory lifecycle management."""

    BASE_TTL_DAYS = 14
    FRESHNESS_WINDOW_DAYS = 30

    @classmethod
    def create_candidate(
        cls,
        project_id: str,
        question: str,
        answer: str,
        summary: str | None = None,
        tags: Sequence[str] | None = None,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        author: str | None = None,
        confidence: float = 0.5,
    ) -> QaMemoryRecord:
        tags = list(tags or [])
        metadata = metadata or {}
        now = datetime.datetime.utcnow()

        kb_id: str
        with get_db() as session:
            kb = cls._ensure_default_kb(session)
            kb_id = str(kb.id)
            record = QaMemoryRecord(
                project_id=project_id,
                knowledge_base_id=kb.id,
                rag_type=RagType.QA,
                question=question.strip(),
                answer=answer.strip(),
                summary=summary or "",
                tags=tags,
                meta=metadata,
                status=QaMemoryStatus.CANDIDATE.value,
                level=QaMemoryLevel.L1.value,
                confidence=max(0.0, min(1.0, confidence)),
                trust_score=max(0.0, min(1.0, confidence)),
                ttl_expire_at=now + datetime.timedelta(days=cls.BASE_TTL_DAYS),
                source=source,
                author=author,
            )
            session.add(record)
            session.flush()
            cls._log_event(session, record.id, project_id, "candidate", {"source": source})
            session.commit()
            session.refresh(record)

        # Important: don't pass ORM instances outside the session.
        cls._upsert_vector_entry(record, kb_id)
        return record

    @classmethod
    def search(cls, project_id: str, query: str, limit: int = 6, min_score: float = 0.2) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        kb_id = cls._get_default_kb_id()
        if kb_id is None:
            return []

        vector = cls._vector_from_kb_id(kb_id)
        documents = vector.search_by_vector(query, top_k=limit * 2, score_threshold=min_score)

        qa_ids: set[str] = set()
        doc_map = {}
        for doc in documents:
            metadata = doc.metadata or {}
            doc_project = metadata.get("project_id")
            allowed_projects = set(metadata.get("shared_projects") or [])
            if doc_project not in (project_id, "global") and project_id not in allowed_projects:
                continue
            qa_id = metadata.get("qa_id") or metadata.get("doc_id")
            if not qa_id:
                continue
            qa_ids.add(qa_id)
            doc_map[qa_id] = doc

        if not qa_ids:
            return []

        with get_db() as session:
            rows = (
                session.execute(
                    select(QaMemoryRecord).where(
                        QaMemoryRecord.id.in_(qa_ids),
                        QaMemoryRecord.status != QaMemoryStatus.DEPRECATED.value,
                    )
                )
                .scalars()
                .all()
            )

        now = datetime.datetime.utcnow()
        matches = []
        for record in rows:
            doc = doc_map.get(str(record.id))
            if not doc:
                continue
            raw_distance = float((doc.metadata or {}).get("score", 0.0))
            relevance = cls._compute_relevance(raw_distance)
            trust = cls._compute_trust(record)
            freshness = cls._compute_freshness(record, now)
            final_score = 0.55 * relevance + 0.30 * trust + 0.15 * freshness
            matches.append(
                {
                    "qa_id": str(record.id),
                    "project_id": record.project_id,
                    "question": record.question,
                    "answer": record.answer,
                    "summary": record.summary,
                    "score": final_score,
                    "relevance": relevance,
                    "trust": trust,
                    "freshness": freshness,
                    "level": record.level,
                    "status": record.status,
                    "metadata": record.meta,
                    "tags": record.tags,
                    "expiry_at": record.ttl_expire_at.isoformat() if record.ttl_expire_at else None,
                    "source": record.source,
                    "confidence": record.confidence,
                }
            )

        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:limit]

    @classmethod
    def record_hits(cls, project_id: str, references: Iterable[dict[str, Any]]):
        if not references:
            return

        qa_ids = [ref["qa_id"] for ref in references if ref.get("qa_id")]
        if not qa_ids:
            return

        with get_db() as session:
            rows = (
                session.execute(
                    select(QaMemoryRecord)
                    .where(QaMemoryRecord.project_id == project_id)
                    .where(QaMemoryRecord.id.in_(qa_ids))
                )
                .scalars()
                .all()
            )
            now = datetime.datetime.utcnow()
            for record in rows:
                ref_meta = next((ref for ref in references if ref.get("qa_id") == str(record.id)), None)
                if not ref_meta:
                    continue
                shown = bool(ref_meta.get("shown", True))
                used = bool(ref_meta.get("used", False))
                if shown:
                    record.usage_count += 1
                if used:
                    record.last_used_at = now
                cls._log_event(
                    session,
                    record.id,
                    project_id,
                    "hit",
                    {
                        "shown": shown,
                        "used": used,
                        "context": ref_meta.get("context"),
                        "message_id": ref_meta.get("message_id"),
                        "client": ref_meta.get("client"),
                    },
                )
            session.commit()

    @classmethod
    def record_validation(
        cls,
        project_id: str,
        qa_id: str,
        success: bool,
        strong_signal: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> QaMemoryRecord | None:
        payload = payload or {}
        with get_db() as session:
            record: QaMemoryRecord | None = (
                session.execute(
                    select(QaMemoryRecord)
                    .where(QaMemoryRecord.project_id == project_id)
                    .where(QaMemoryRecord.id == qa_id)
                )
                .scalars()
                .first()
            )
            if not record:
                return None

            now = datetime.datetime.utcnow()
            record.last_validated_at = now
            if success:
                record.success_count += 1
                record.failure_count = 0
                record.trust_score = min(1.0, record.trust_score + (0.1 if strong_signal else 0.05))
                record.status = QaMemoryStatus.ACTIVE.value
                record.ttl_expire_at = now + datetime.timedelta(days=cls.BASE_TTL_DAYS)
                if strong_signal and record.level == QaMemoryLevel.L1.value:
                    record.level = QaMemoryLevel.L2.value
                if strong_signal:
                    record.strong_signal_count += 1
            else:
                record.failure_count += 1
                record.trust_score = max(0.0, record.trust_score - 0.1)
                if record.failure_count >= 3:
                    record.status = QaMemoryStatus.DEPRECATED.value
                elif record.failure_count >= 2:
                    record.status = QaMemoryStatus.STALE.value

            session.add(
                QaMemoryEvent(
                    qa_id=record.id,
                    project_id=project_id,
                    event_type="validate",
                    payload={
                        "success": success,
                        "strong_signal": strong_signal,
                        **payload,
                    },
                )
            )
            session.commit()
            session.refresh(record)

        kb_id = cls._get_default_kb_id()
        if kb_id:
            cls._upsert_vector_entry(record, kb_id)
        return record

    @classmethod
    def expire_expired_memories(cls, batch_size: int = 200) -> int:
        """
        Downgrade or remove QA memories whose TTL has elapsed.
        """
        now = datetime.datetime.utcnow()
        processed_ids: list[str] = []
        with get_db() as session:
            records = (
                session.execute(
                    select(QaMemoryRecord)
                    .where(QaMemoryRecord.ttl_expire_at.isnot(None))
                    .where(QaMemoryRecord.ttl_expire_at <= now)
                    .where(QaMemoryRecord.status != QaMemoryStatus.DEPRECATED.value)
                    .limit(batch_size)
                )
                .scalars()
                .all()
            )
            if not records:
                return 0

            processed = 0
            for record in records:
                if record.status == QaMemoryStatus.ACTIVE.value:
                    record.status = QaMemoryStatus.STALE.value
                    record.ttl_expire_at = now + datetime.timedelta(days=max(1, cls.BASE_TTL_DAYS // 2))
                else:
                    record.status = QaMemoryStatus.DEPRECATED.value
                    record.ttl_expire_at = None
                cls._log_event(
                    session,
                    record.id,
                    record.project_id,
                    "expire",
                    {"status": record.status},
                )
                processed += 1
                processed_ids.append(str(record.id))
            session.commit()

        if not processed_ids:
            return 0

        kb_id = cls._get_default_kb_id()
        if kb_id:
            with get_db() as session:
                refreshed = (
                    session.execute(select(QaMemoryRecord).where(QaMemoryRecord.id.in_(processed_ids)))
                    .scalars()
                    .all()
                )
            for record in refreshed:
                cls._upsert_vector_entry(record, kb_id)
        return processed

    @classmethod
    def get_detail(cls, project_id: str, qa_id: str) -> QaMemoryRecord | None:
        with get_db() as session:
            return (
                session.execute(
                    select(QaMemoryRecord)
                    .where(QaMemoryRecord.project_id == project_id)
                    .where(QaMemoryRecord.id == qa_id)
                )
                .scalars()
                .first()
            )

    @classmethod
    def _ensure_default_kb(cls, session) -> KnowledgeBase:
        kb: KnowledgeBase | None = (
            session.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.rag_type == RagType.QA.value)
                .where(KnowledgeBase.default_base == 1)
            )
            .scalars()
            .first()
        )
        if kb:
            return kb
        from service.knowledge_base_service import KnowledgeBaseService

        KnowledgeBaseService.create_knowledge_base("Default QA KB", RagType.QA, 1)
        kb = (
            session.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.rag_type == RagType.QA.value)
                .where(KnowledgeBase.default_base == 1)
            )
            .scalars()
            .first()
        )
        if not kb:
            raise RuntimeError("Failed to initialize default QA knowledge base")
        return kb

    @classmethod
    def _get_default_kb_id(cls) -> str | None:
        """Return the default QA KnowledgeBase id without leaking detached ORM instances."""
        with get_db() as session:
            return (
                session.execute(
                    select(KnowledgeBase.id)
                    .where(KnowledgeBase.rag_type == RagType.QA.value)
                    .where(KnowledgeBase.default_base == 1)
                )
                .scalars()
                .first()
            )

    @classmethod
    def _vector_from_kb_id(cls, kb_id: str) -> Vector:
        """Create a Vector using a KnowledgeBase loaded inside an active session."""
        with get_db() as session:
            kb = session.get(KnowledgeBase, kb_id)
            if not kb:
                raise RuntimeError(f"KnowledgeBase not found: {kb_id}")
            # Make it explicit that we don't want this instance to be used for lazy loads later.
            session.expunge(kb)
        return Vector(kb)

    @classmethod
    def _upsert_vector_entry(cls, record: QaMemoryRecord, knowledge_base_id: str):
        document = Document(
            content=cls._compose_content(record),
            metadata=cls._build_metadata(record),
        )
        vector = cls._vector_from_kb_id(knowledge_base_id)
        vector.delete_by_ids([str(record.id)])
        vector.add_texts([document])

    @staticmethod
    def _compose_content(record: QaMemoryRecord) -> str:
        summary = record.summary or ""
        return f"Question:\n{record.question}\n\nAnswer:\n{record.answer}\n\nSummary:\n{summary}"

    @staticmethod
    def _build_metadata(record: QaMemoryRecord) -> dict[str, Any]:
        metadata = dict(record.meta or {})
        metadata.update(
            {
                "qa_id": str(record.id),
                "doc_id": str(record.id),
                "project_id": record.project_id,
                "status": record.status,
                "level": record.level,
                "tags": record.tags,
            }
        )
        return metadata

    @classmethod
    def _compute_relevance(cls, distance: float) -> float:
        score = max(0.0, 1.0 - distance)
        return min(1.0, score)

    @classmethod
    def _compute_trust(cls, record: QaMemoryRecord) -> float:
        value = record.trust_score
        if record.status == QaMemoryStatus.STALE.value:
            value *= 0.7
        if record.status == QaMemoryStatus.DEPRECATED.value:
            value *= 0.3
        return max(0.0, min(1.0, value))

    @classmethod
    def _compute_freshness(cls, record: QaMemoryRecord, now: datetime.datetime) -> float:
        anchor = record.last_used_at or record.last_validated_at or record.created_at or now
        age_days = (now - anchor).total_seconds() / 86400
        freshness = max(0.0, 1 - age_days / cls.FRESHNESS_WINDOW_DAYS)
        return min(1.0, freshness)

    @classmethod
    def _log_event(cls, session, qa_id, project_id, event_type: str, payload: dict[str, Any] | None):
        session.add(
            QaMemoryEvent(
                qa_id=qa_id,
                project_id=project_id,
                event_type=event_type,
                payload=payload or {},
            )
        )
