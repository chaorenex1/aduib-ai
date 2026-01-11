import datetime
import hashlib
import json
from typing import Any, Iterable, Sequence

from sqlalchemy import select

from component.vdb.vector_factory import Vector
from controllers.params import TaskGradeResult
from models import (
    KnowledgeBase,
    QaMemoryEvent,
    QaMemoryLevel,
    QaMemoryRecord,
    QaMemoryStatus,
    get_db, TaskGradeRecord,
)
from runtime.entities.document_entities import Document
from runtime.generator.generator import LLMGenerator
from runtime.rag.rag_type import RagType


class QAMemoryService:
    """Service layer for QA memory lifecycle management."""

    BASE_TTL_DAYS = 14
    MAX_TTL_DAYS = 180
    STRONG_PASS_TTL_BONUS_DAYS = 30
    STRONG_FAIL_MIN_TTL_DAYS = 7
    FRESHNESS_WINDOW_DAYS = 30
    LEVEL_MIN_VALIDATIONS = {
        1: 2,
        2: 4,
        3: 6,
    }
    LEVEL_MIN_STRONG_PASSES = {
        2: 1,
        3: 2,
    }
    LEVEL_TRUST_THRESHOLDS = {
        1: 0.40,
        2: 0.65,
        3: 0.80,
    }

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
        stats = cls._init_stats()
        trust_score = cls._compute_trust_score(stats)
        metadata.setdefault("stats", stats)
        metadata.setdefault(
            "score",
            {
                "trust_score": trust_score,
                "validation_level": 0,
            },
        )
        metadata.setdefault(
            "ttl",
            {"expires_at": (now + datetime.timedelta(days=cls.BASE_TTL_DAYS)).isoformat()},
        )

        kb_id: str
        summary = summary if summary else LLMGenerator.generate_doc_research(f"Q: {question}\nA: {answer}")
        if metadata.get("summary") != summary:
            metadata["summary"] = summary
        with get_db() as session:
            kb = cls._ensure_default_kb(session)
            kb_id = str(kb.id)
            record = QaMemoryRecord(
                project_id=project_id,
                knowledge_base_id=kb.id,
                rag_type=RagType.QA,
                question=question.strip(),
                answer=answer.strip(),
                summary=summary,
                tags=tags,
                meta=metadata,
                status=QaMemoryStatus.CANDIDATE.value,
                level=QaMemoryLevel.L0.value,
                confidence=max(0.0, min(1.0, confidence)),
                trust_score=max(0.0, min(1.0, trust_score)),
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
        if len(documents) == 0:
            documents=vector.search_by_full_text(query, top_k=limit * 2, score_threshold=min_score)
        else:
            new_documents=vector.search_by_full_text(query, top_k=limit * 2, score_threshold=min_score)
            if len(new_documents) > 0:
                documents.extend(new_documents)
                # deduplicate documents by id
                doc_map = {}
                for doc in documents:
                    doc_id = (doc.metadata or {}).get("doc_id")
                    if doc_id and doc_id not in doc_map:
                        doc_map[doc_id] = doc
                documents = list(doc_map.values())

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
            relevance = raw_distance
            trust = cls._compute_trust(record)
            freshness = cls._compute_freshness(record, now)
            level_value = cls._parse_level(record.level)
            level_boost = min(0.08, 0.02 * level_value)
            final_score = 0.55 * relevance + 0.30 * trust + 0.15 * freshness + level_boost
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
                    "validation_level": level_value,
                    "level": record.level,
                    "status": record.status,
                    "metadata": record.meta,
                    "tags": record.tags,
                    "expiry_at": record.ttl_expire_at.isoformat() if record.ttl_expire_at else None,
                    "source": record.source,
                    "confidence": record.confidence,
                }
            )

        if any(match["validation_level"] > 0 for match in matches):
            matches = [match for match in matches if match["validation_level"] > 0]

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
        result: str,
        signal_strength: str = "weak",
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
            stats = cls._get_stats(record)
            normalized_result = "pass" if result == "pass" else "fail"
            normalized_strength = cls._normalize_signal_strength(signal_strength)
            ignored = cls._should_ignore_signal(stats, normalized_result, normalized_strength)
            if not ignored:
                cls._update_stats(stats, normalized_result, normalized_strength, now)
            else:
                stats["last_validated_at"] = now.isoformat()
            cls._sync_counts(record, stats)
            record.trust_score = cls._compute_trust_score(stats)
            validation_level = cls._compute_validation_level(stats)
            record.level = cls._format_level(validation_level)
            if normalized_result == "pass":
                record.status = QaMemoryStatus.ACTIVE.value
            elif stats["consecutive_fail"] >= 3:
                record.status = QaMemoryStatus.DEPRECATED.value
            elif stats["consecutive_fail"] >= 2:
                record.status = QaMemoryStatus.STALE.value
            cls._adjust_ttl(record, normalized_result, normalized_strength, now)
            cls._store_meta_stats(record, stats, validation_level)

            session.add(
                QaMemoryEvent(
                    qa_id=record.id,
                    project_id=project_id,
                    event_type="validate",
                    payload={
                        "result": normalized_result,
                        "signal_strength": normalized_strength,
                        "ignored": ignored,
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
    def _parse_level(cls, level: str | None) -> int:
        if not level:
            return 0
        if level.startswith("L"):
            try:
                return int(level[1:])
            except ValueError:
                return 0
        return 0

    @classmethod
    def _init_stats(cls) -> dict[str, Any]:
        return {
            "total_pass": 0,
            "total_fail": 0,
            "strong_pass": 0,
            "strong_fail": 0,
            "medium_pass": 0,
            "medium_fail": 0,
            "weak_pass": 0,
            "weak_fail": 0,
            "consecutive_fail": 0,
            "last_result": None,
            "last_validated_at": None,
        }

    @classmethod
    def _get_stats(cls, record: QaMemoryRecord) -> dict[str, Any]:
        meta = record.meta or {}
        stats = meta.get("stats") or {}
        defaults = cls._init_stats()
        defaults.update({k: v for k, v in stats.items() if k in defaults})
        return defaults

    @classmethod
    def _normalize_signal_strength(cls, signal_strength: str) -> str:
        normalized = (signal_strength or "weak").lower()
        if normalized not in {"strong", "medium", "weak"}:
            return "weak"
        return normalized

    @classmethod
    def _should_ignore_signal(cls, stats: dict[str, Any], result: str, strength: str) -> bool:
        if strength != "weak" or result != "fail":
            return False
        strong_pass = int(stats.get("strong_pass", 0))
        strong_fail = int(stats.get("strong_fail", 0))
        return strong_pass >= 2 and strong_pass > strong_fail

    @classmethod
    def _update_stats(
        cls,
        stats: dict[str, Any],
        result: str,
        strength: str,
        now: datetime.datetime,
    ) -> None:
        if result == "pass":
            stats["total_pass"] += 1
        else:
            stats["total_fail"] += 1
        key = f"{strength}_{result}"
        stats[key] += 1
        if result == "fail":
            stats["consecutive_fail"] += 1
        else:
            stats["consecutive_fail"] = 0
        stats["last_result"] = result
        stats["last_validated_at"] = now.isoformat()

    @classmethod
    def _sync_counts(cls, record: QaMemoryRecord, stats: dict[str, Any]) -> None:
        record.success_count = int(stats.get("total_pass", 0))
        record.failure_count = int(stats.get("total_fail", 0))
        record.strong_signal_count = int(stats.get("strong_pass", 0))

    @classmethod
    def _compute_trust_score(cls, stats: dict[str, Any]) -> float:
        sp = stats.get("strong_pass", 0)
        sf = stats.get("strong_fail", 0)
        mp = stats.get("medium_pass", 0)
        mf = stats.get("medium_fail", 0)
        wp = stats.get("weak_pass", 0)
        wf = stats.get("weak_fail", 0)
        cf = stats.get("consecutive_fail", 0)
        score = 0.0
        score += 0.25 * sp
        score -= 0.35 * sf
        score += 0.10 * mp
        score -= 0.15 * mf
        score += 0.02 * wp
        score -= 0.05 * wf
        score -= 0.5 * min(cf, 3)
        score = max(-2.0, min(score, 3.0))
        return (score + 2.0) / 5.0

    @classmethod
    def _compute_validation_level(cls, stats: dict[str, Any]) -> int:
        if int(stats.get("consecutive_fail", 0)) >= 3:
            return 0
        total = int(stats.get("total_pass", 0)) + int(stats.get("total_fail", 0))
        trust_score = cls._compute_trust_score(stats)
        strong_pass = int(stats.get("strong_pass", 0))
        strong_fail = int(stats.get("strong_fail", 0))
        if (
            total >= cls.LEVEL_MIN_VALIDATIONS[3]
            and trust_score >= cls.LEVEL_TRUST_THRESHOLDS[3]
            and strong_pass >= cls.LEVEL_MIN_STRONG_PASSES[3]
            and strong_fail == 0
        ):
            return 3
        if (
            total >= cls.LEVEL_MIN_VALIDATIONS[2]
            and trust_score >= cls.LEVEL_TRUST_THRESHOLDS[2]
            and strong_pass >= cls.LEVEL_MIN_STRONG_PASSES[2]
        ):
            return 2
        if total >= cls.LEVEL_MIN_VALIDATIONS[1] and trust_score >= cls.LEVEL_TRUST_THRESHOLDS[1]:
            return 1
        return 0

    @classmethod
    def _format_level(cls, level: int) -> str:
        return f"L{max(0, min(level, 3))}"

    @classmethod
    def _adjust_ttl(
        cls,
        record: QaMemoryRecord,
        result: str,
        strength: str,
        now: datetime.datetime,
    ) -> None:
        if strength == "strong" and result == "pass":
            base = record.ttl_expire_at if record.ttl_expire_at and record.ttl_expire_at > now else now
            updated = base + datetime.timedelta(days=cls.STRONG_PASS_TTL_BONUS_DAYS)
            cap = now + datetime.timedelta(days=cls.MAX_TTL_DAYS)
            record.ttl_expire_at = min(updated, cap)
            return
        if strength == "strong" and result == "fail":
            record.ttl_expire_at = now + datetime.timedelta(days=cls.STRONG_FAIL_MIN_TTL_DAYS)

    @classmethod
    def _store_meta_stats(cls, record: QaMemoryRecord, stats: dict[str, Any], level: int) -> None:
        meta = dict(record.meta or {})
        meta["stats"] = stats
        meta["score"] = {"trust_score": record.trust_score, "validation_level": level}
        meta["ttl"] = {
            "expires_at": record.ttl_expire_at.isoformat() if record.ttl_expire_at else None,
        }
        record.meta = meta

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

    @classmethod
    def grade_task(cls, prompt: str) -> TaskGradeResult:
        from runtime.tasks.task_grade import TaskGrader
        result: dict[str, Any] = TaskGrader.grade_task(prompt)
        return TaskGradeResult(
            task_level=result.get("task_level", "unknown"),
            reason=result.get("reason", ""),
            recommended_model=result.get("recommended_model", "default-model"),
            recommended_model_provider=result.get("recommended_model_provider", "default-provider"),
            confidence=result.get("confidence"),
        )

