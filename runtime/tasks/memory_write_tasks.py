from __future__ import annotations

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


def _build_phase_payload(task_id: str, phase: str, task) -> dict:
    archive_ref = task.archive_ref.model_dump(mode="python", exclude_none=True) if task.archive_ref else None
    source_ref = task.source_ref.model_dump(mode="python", exclude_none=True)

    if phase == "prepare_extract_context":
        return {
            "skeleton": True,
            "task_id": task_id,
            "phase": phase,
            "source_ref": source_ref,
            "archive_ref": archive_ref,
            "message": "Prepared archived source and queue context for downstream extraction.",
        }
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
