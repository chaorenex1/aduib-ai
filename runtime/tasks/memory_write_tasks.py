from __future__ import annotations

import hashlib
import json

from component.storage.base_storage import storage_manager
from runtime.tasks.celery_app import celery_app

PHASE_SEQUENCE = (
    "prepare_extract_context",
    "extract_operations",
    "resolve_operations",
    "build_staged_write_set",
    "apply_memory_files",
    "refresh_navigation",
    "refresh_metadata",
)


def _load_pg_jsonl_conversation_snapshot(source_ref: dict) -> dict:
    message_ref = source_ref.get("message_ref") or {}
    uri = str(message_ref.get("uri") or "").strip()
    if not uri:
        raise ValueError("conversation source_ref.message_ref.uri is required")

    raw_content = storage_manager.read_text(uri)
    actual_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    expected_sha256 = message_ref.get("sha256")
    if expected_sha256 and expected_sha256 != actual_sha256:
        raise ValueError("conversation source_ref.message_ref.sha256 does not match current content")

    messages: list[dict] = []
    for index, line in enumerate(raw_content.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"conversation jsonl contains invalid json at line {index}") from exc
        if not isinstance(message, dict):
            raise ValueError(f"conversation jsonl contains non-object row at line {index}")
        if message.get("conversation_id") != source_ref.get("id"):
            raise ValueError(f"conversation jsonl contains mismatched conversation_id at line {index}")
        messages.append(message)

    return {
        "storage": "pg_jsonl",
        "message_ref": {
            "type": message_ref.get("type", "jsonl"),
            "uri": uri,
            "sha256": actual_sha256,
        },
        "message_count": len(messages),
        "messages": messages,
    }


def _build_phase_payload(task_id: str, phase: str, task) -> dict:
    archive_ref = task.archive_ref.model_dump(mode="python", exclude_none=True) if task.archive_ref else None
    source_ref = task.source_ref.model_dump(mode="python", exclude_none=True)

    if phase == "prepare_extract_context":
        payload = {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "source_ref": source_ref,
            "archive_ref": archive_ref,
            "message": "Prepared archived source and queue context for downstream extraction.",
        }
        if source_ref.get("type") == "conversation" and source_ref.get("storage") == "pg_jsonl":
            payload["conversation_snapshot"] = _load_pg_jsonl_conversation_snapshot(source_ref)
            payload["message"] = "Prepared PG-backed conversation source and queue context for downstream extraction."
        return payload
    if phase == "extract_operations":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "structured_operations": [],
            "message": "Extraction scaffold executed; no planner implementation is wired yet.",
        }
    if phase == "resolve_operations":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "resolved_operations": [],
            "message": "Resolver scaffold executed; no path resolution implementation is wired yet.",
        }
    if phase == "build_staged_write_set":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "staging_manifest": {
                "memory_mutations": [],
                "navigation_mutations": [],
                "pg_mutations": [],
            },
            "message": "Staging scaffold executed; no write-set builder implementation is wired yet.",
        }
    if phase == "apply_memory_files":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "applied_memory_files": [],
            "message": "File-apply scaffold executed; no committed file writes occurred yet.",
        }
    if phase == "refresh_navigation":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "navigation_files": [],
            "message": "Navigation scaffold executed; no overview/summary refresh occurred yet.",
        }
    if phase == "refresh_metadata":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "metadata_scopes": [],
            "message": "Metadata scaffold executed; no PG projection refresh occurred yet.",
        }
    raise ValueError(f"unsupported memory write phase: {phase}")


@celery_app.task(name="runtime.tasks.memory_write.execute", bind=True)
def execute_memory_write(self, task_id: str) -> dict:
    from service.memory import MemoryWriteTaskService

    current_phase = "prepare_extract_context"
    try:
        phase_results: dict[str, dict] = {}
        for phase in PHASE_SEQUENCE:
            current_phase = phase
            task = MemoryWriteTaskService.mark_running(task_id, phase=phase)
            checkpoint = _build_phase_payload(task_id, phase, task)
            phase_results[phase] = checkpoint
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=phase,
                result_ref=checkpoint,
                operator_notes=f"Worker scaffold completed {phase}.",
            )

        final_result = {
            "task_id": task_id,
            "status": "committed",
            "final_phase": "committed",
            "phase_results": phase_results,
        }
        MemoryWriteTaskService.mark_committed(
            task_id,
            result_ref=final_result,
            operator_notes="Worker scaffold completed queue execution phases through committed.",
        )
        return final_result
    except Exception as exc:
        MemoryWriteTaskService.mark_needs_manual_recovery(
            task_id,
            phase=current_phase,
            error=str(exc),
            rollback_metadata={"worker_task_id": self.request.id},
        )
        raise
