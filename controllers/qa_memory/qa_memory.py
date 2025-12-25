from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from controllers.common.base import BaseResponse, catch_exceptions
from service import QAMemoryService

router = APIRouter(tags=["qa_memory"])


class QASearchPayload(BaseModel):
    project_id: str = Field(..., description="Project/workspace identifier")
    query: str
    limit: int = Field(6, ge=1, le=20)
    min_score: float = Field(0.2, ge=0.0, le=1.0)


class QACandidatePayload(BaseModel):
    project_id: str
    question: str
    answer: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    author: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class QAReferencePayload(BaseModel):
    qa_id: str
    shown: bool = True
    used: bool = False
    message_id: str | None = None
    context: str | None = None


class QAHitsPayload(BaseModel):
    project_id: str
    references: list[QAReferencePayload] = Field(default_factory=list)


class QAValidationPayload(BaseModel):
    project_id: str
    qa_id: str
    success: bool
    strong_signal: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class QAExpirePayload(BaseModel):
    batch_size: int = Field(default=200, ge=1, le=1000)


def _serialize_record(record) -> dict[str, Any]:
    return {
        "qa_id": str(record.id),
        "project_id": record.project_id,
        "question": record.question,
        "answer": record.answer,
        "summary": record.summary,
        "tags": record.tags,
        "metadata": record.meta,
        "scope": (record.meta or {}).get("scope", {}),
        "resource_uri": (record.meta or {}).get("resource_uri"),
        "evidence_refs": (record.meta or {}).get("evidence_refs", []),
        "time_sensitivity": (record.meta or {}).get("time_sensitivity"),
        "status": record.status,
        "level": record.level,
        "trust_score": record.trust_score,
        "confidence": record.confidence,
        "usage_count": record.usage_count,
        "success_count": record.success_count,
        "failure_count": record.failure_count,
        "strong_signal_count": record.strong_signal_count,
        "last_used_at": record.last_used_at,
        "last_validated_at": record.last_validated_at,
        "ttl_expire_at": record.ttl_expire_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.post("/qa/search")
@catch_exceptions
async def qa_search(payload: QASearchPayload):
    matches = QAMemoryService.search(
        project_id=payload.project_id,
        query=payload.query,
        limit=payload.limit,
        min_score=payload.min_score,
    )
    return BaseResponse.ok({"items": matches})


@router.post("/qa/candidates")
@catch_exceptions
async def qa_candidate(payload: QACandidatePayload):
    record = QAMemoryService.create_candidate(
        project_id=payload.project_id,
        question=payload.question,
        answer=payload.answer,
        summary=payload.summary,
        tags=payload.tags,
        metadata=payload.metadata,
        source=payload.source,
        author=payload.author,
        confidence=payload.confidence,
    )
    return BaseResponse.ok({"record": _serialize_record(record)})


@router.post("/qa/hit")
@catch_exceptions
async def qa_hit(payload: QAHitsPayload):
    QAMemoryService.record_hits(payload.project_id, [ref.model_dump() for ref in payload.references])
    return BaseResponse.ok()


@router.post("/qa/validate")
@catch_exceptions
async def qa_validate(payload: QAValidationPayload):
    record = QAMemoryService.record_validation(
        project_id=payload.project_id,
        qa_id=payload.qa_id,
        success=payload.success,
        strong_signal=payload.strong_signal,
        payload=payload.payload,
    )
    if not record:
        return BaseResponse.error(404, "QA memory not found")
    return BaseResponse.ok({"record": _serialize_record(record)})


@router.post("/qa/expire")
@catch_exceptions
async def qa_expire(payload: QAExpirePayload):
    expired = QAMemoryService.expire_expired_memories(batch_size=payload.batch_size)
    return BaseResponse.ok({"expired": expired})


@router.get("/qa/{qa_id}")
@catch_exceptions
async def qa_detail(qa_id: str, project_id: str = Query(...)):
    record = QAMemoryService.get_detail(project_id=project_id, qa_id=qa_id)
    if not record:
        return BaseResponse.error(404, "QA memory not found")
    return BaseResponse.ok({"record": _serialize_record(record)})
