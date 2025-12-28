from typing import Any

from runtime.tool.mcp.fast_mcp_instance import fast_mcp
from service import QAMemoryService


@fast_mcp.tool(name="retrieve_qa_kb", description="Retrieve QA memory matches for a project query")
def retrieve_qa_memory(project_id: str, query: str, limit: int = 6, min_score: float = 0.2):
    matches = QAMemoryService.search(
        project_id=project_id,
        query=query,
        limit=limit,
        min_score=min_score,
    )
    return {"items": matches}


@fast_mcp.tool(name="qa_memory_candidate", description="Store a new QA memory candidate")
def qa_memory_candidate(
    project_id: str,
    question: str,
    answer: str,
    summary: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    author: str | None = None,
    confidence: float = 0.5,
):
    record = QAMemoryService.create_candidate(
        project_id=project_id,
        question=question,
        answer=answer,
        summary=summary,
        tags=tags or [],
        metadata=metadata or {},
        source=source,
        author=author,
        confidence=confidence,
    )
    return {
        "qa_id": str(record.id),
        "status": record.status,
        "level": record.level,
    }


@fast_mcp.tool(name="qa_memory_hit", description="Report QA memory hit/exposure metrics")
def qa_memory_hit(project_id: str, references: list[dict[str, Any]]):
    QAMemoryService.record_hits(project_id, references or [])
    return {"project_id": project_id, "reported": len(references or [])}


@fast_mcp.tool(name="qa_memory_validate", description="Report QA memory validation signal")
def qa_memory_validate(
    project_id: str,
    qa_id: str,
    result: str | None = None,
    signal_strength: str | None = None,
    success: bool | None = None,
    strong_signal: bool = False,
    payload: dict[str, Any] | None = None,
):
    if result:
        normalized_result = result
    elif success is not None:
        normalized_result = "pass" if success else "fail"
    else:
        return {"status": "invalid_request", "message": "Missing validation result"}

    if signal_strength:
        normalized_strength = signal_strength
    else:
        normalized_strength = "strong" if strong_signal else "weak"

    record = QAMemoryService.record_validation(
        project_id=project_id,
        qa_id=qa_id,
        result=normalized_result,
        signal_strength=normalized_strength,
        payload=payload,
    )
    if not record:
        return {"status": "not_found", "qa_id": qa_id}
    return {
        "qa_id": str(record.id),
        "status": record.status,
        "level": record.level,
        "validation_level": int(record.level[1:]) if record.level.startswith("L") else 0,
        "trust_score": record.trust_score,
    }
