from typing import Any, Dict, List, Optional

from aduib_rpc.server.rpc_execution.service_call import service

from service import QAMemoryService


def _serialize_record(record) -> dict[str, Any]:
    meta = record.meta or {}
    return {
        "qa_id": str(record.id),
        "project_id": record.project_id,
        "question": record.question,
        "answer": record.answer,
        "summary": record.summary,
        "tags": record.tags,
        "metadata": meta,
        "scope": meta.get("scope", {}),
        "evidence_refs": meta.get("evidence_refs", []),
        "time_sensitivity": meta.get("time_sensitivity"),
        "resource_uri": meta.get("resource_uri"),
        "status": record.status,
        "level": record.level,
        "trust_score": record.trust_score,
        "confidence": record.confidence,
        "usage_count": record.usage_count,
        "success_count": record.success_count,
        "failure_count": record.failure_count,
        "strong_signal_count": record.strong_signal_count,
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "last_validated_at": record.last_validated_at.isoformat() if record.last_validated_at else None,
        "ttl_expire_at": record.ttl_expire_at.isoformat() if record.ttl_expire_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@service(service_name="QaMemoryService")
class QaMemoryService:
    schema_version = 1

    async def retrieve_qa_kb(
        self,
        query: str,
        namespace: str,
        top_k: int = 8,
        filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        matches = QAMemoryService.search(project_id=namespace, query=query, limit=top_k, min_score=0.0)
        results = [self._format_search_result(item=match) for match in matches]

        if results:
            references = [
                {
                    "qa_id": item["qa_id"],
                    "shown": True,
                    "used": False,
                    "client": None,
                }
                for item in results
            ]
            QAMemoryService.record_hits(namespace, references)

        return {
            "schema_version": self.schema_version,
            "results": results,
            "meta": {"count": len(results), "namespace": namespace, "filters": filters or []},
        }

    async def qa_record_hit(
        self,
        qa_id: str,
        namespace: str,
        used: bool = True,
        shown: bool = True,
        client: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reference = {
            "qa_id": qa_id,
            "shown": shown,
            "used": used,
            "client": client or {},
        }
        QAMemoryService.record_hits(namespace, [reference])
        return {"qa_id": qa_id, "namespace": namespace, "status": "recorded"}

    async def qa_upsert_candidate(
        self,
        question_raw: str,
        answer_raw: str,
        namespace: str,
        tags: Optional[List[str]] = None,
        scope: Optional[Dict[str, str]] = None,
        time_sensitivity: str = "medium",
        evidence_refs: Optional[List[str]] = None,
        client: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "scope": scope or {},
            "time_sensitivity": time_sensitivity,
            "evidence_refs": evidence_refs or [],
            "client": client or {},
        }
        record = QAMemoryService.create_candidate(
            project_id=namespace,
            question=question_raw,
            answer=answer_raw,
            summary=None,
            tags=tags or [],
            metadata=metadata,
            source="mcp",
            author=None,
            confidence=0.5,
        )
        return {"record": _serialize_record(record)}

    async def qa_validate_and_update(
        self,
        qa_id: str,
        namespace: str,
        result: str,
        signal_strength: str = "weak",
        reason: str = "",
        evidence_refs: Optional[List[str]] = None,
        execution: Optional[dict[str, Any]] = None,
        client: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_result = (result or "").lower()
        success = normalized_result == "pass"
        strong_signal = (signal_strength or "").lower() == "strong"
        payload = {
            "result": result,
            "reason": reason,
            "signal_strength": signal_strength,
            "evidence_refs": evidence_refs or [],
            "execution": execution or {},
            "client": client or {},
        }
        record = QAMemoryService.record_validation(
            project_id=namespace,
            qa_id=qa_id,
            success=success,
            strong_signal=strong_signal,
            payload=payload,
        )
        if not record:
            return {"status": "not_found", "qa_id": qa_id}
        return {"record": _serialize_record(record)}

    async def qa_expire(self, batch_size: int = 200) -> Dict[str, Any]:
        expired = QAMemoryService.expire_expired_memories(batch_size=batch_size)
        return {"expired": expired}

    async def qa_detail(self, namespace: str, qa_id: str) -> Dict[str, Any]:
        record = QAMemoryService.get_detail(project_id=namespace, qa_id=qa_id)
        if not record:
            return {"status": "not_found", "qa_id": qa_id}
        return {"record": _serialize_record(record)}

    @staticmethod
    def _format_search_result(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") or {}
        source_info: Dict[str, Any] = {}
        if item.get("source"):
            source_info["label"] = item["source"]
        if metadata.get("source"):
            source_info.update(metadata.get("source"))
        return {
            "qa_id": item["qa_id"],
            "question": item.get("question") or "",
            "answer": item.get("answer") or "",
            "validation_level": item.get("level"),
            "confidence": item.get("confidence") or item.get("trust"),
            "scope": metadata.get("scope", {}),
            "tags": item.get("tags") or [],
            "source": source_info,
            "expiry_at": item.get("expiry_at"),
            "relevance_score": item.get("score"),
            "evidence_refs": metadata.get("evidence_refs", []),
            "resource_uri": metadata.get("resource_uri"),
        }
