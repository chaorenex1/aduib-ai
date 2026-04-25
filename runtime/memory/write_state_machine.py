from __future__ import annotations

import json

from pydantic import BaseModel

from runtime.memory.apply.resolve_operations import resolve_operations

from .apply.file_commit import apply_memory_files
from .apply.metadata_refresh import refresh_metadata
from .apply.navigation_refresh import refresh_navigation
from .apply.staged_write import build_staged_write_set
from .base.contracts import MemoryWritePipelineContext
from .base.enums import MemoryTaskFinalStatus, MemoryTaskPhase
from .extract.orchestrator import run_memory_react_orchestrator
from .navigation.generate_summary import generate_navigation_summary
from .prepare_context.prepare_context import prepare_extract_context

MEMORY_WRITE_STATE_TRANSITIONS = {
    MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT: MemoryTaskPhase.EXTRACT_OPERATIONS,
    MemoryTaskPhase.EXTRACT_OPERATIONS: MemoryTaskPhase.RESOLVE_OPERATIONS,
    MemoryTaskPhase.RESOLVE_OPERATIONS: MemoryTaskPhase.BUILD_STAGED_WRITE_SET,
    MemoryTaskPhase.BUILD_STAGED_WRITE_SET: MemoryTaskPhase.APPLY_MEMORY_FILES,
    MemoryTaskPhase.APPLY_MEMORY_FILES: MemoryTaskPhase.GENERATE_NAVIGATION_SUMMARY,
    MemoryTaskPhase.GENERATE_NAVIGATION_SUMMARY: MemoryTaskPhase.REFRESH_NAVIGATION,
    MemoryTaskPhase.REFRESH_NAVIGATION: MemoryTaskPhase.REFRESH_METADATA,
    MemoryTaskPhase.REFRESH_METADATA: MemoryTaskPhase.COMMITTED,
}

PHASE_HANDLERS = {
    MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT: prepare_extract_context,
    MemoryTaskPhase.EXTRACT_OPERATIONS: run_memory_react_orchestrator,
    MemoryTaskPhase.RESOLVE_OPERATIONS: resolve_operations,
    MemoryTaskPhase.BUILD_STAGED_WRITE_SET: build_staged_write_set,
    MemoryTaskPhase.APPLY_MEMORY_FILES: apply_memory_files,
    MemoryTaskPhase.GENERATE_NAVIGATION_SUMMARY: generate_navigation_summary,
    MemoryTaskPhase.REFRESH_NAVIGATION: refresh_navigation,
    MemoryTaskPhase.REFRESH_METADATA: refresh_metadata,
}


def build_memory_write_pipeline_context(*, task_id: str, phase: str, task, phase_results: dict[str, dict]):
    return MemoryWritePipelineContext(
        task_id=task_id,
        trace_id=task.trace_id,
        trigger_type=task.trigger_type,
        user_id=getattr(task, "user_id", None),
        agent_id=getattr(task, "agent_id", None),
        project_id=getattr(task, "project_id", None),
        phase=phase,
        source_ref=task.source_ref,
        archive_ref=task.archive_ref,
        phase_results=phase_results,
    )

class MemoryStateMachineRuntime:

    @classmethod
    def run_memory_write_phase(cls,context: MemoryWritePipelineContext) -> dict:
        phase = MemoryTaskPhase(str(context.phase))
        handler = PHASE_HANDLERS.get(phase)
        if handler is None:
            raise ValueError(f"unsupported memory write phase: {phase}")
        result = handler(context)
        if isinstance(result, BaseModel):
            return result.model_dump(mode="python", exclude_none=True)
        return result

    @classmethod
    def run_memory_write_task_phase(cls,*, task_id: str, phase: str, task, phase_results: dict[str, dict]) -> dict:

        context = build_memory_write_pipeline_context(
            task_id=task_id,
            phase=phase,
            task=task,
            phase_results=phase_results,
        )
        return cls.run_memory_write_phase(context)

    @classmethod
    def execute_memory_write_task(cls,task_id: str, *, worker_task_id: str | None = None) -> dict:
        archive_ref = None
        try:
            archive_ref = cls._materialize_worker_archive(task_id=task_id, worker_task_id=worker_task_id)
            return cls._advance_memory_write_state(
                task_id=task_id,
                phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
                phase_results={},
                worker_task_id=worker_task_id,
            )
        finally:
            cls._cleanup_worker_archive(task_id=task_id, archive_ref=archive_ref)

    @classmethod
    def _advance_memory_write_state(
        cls,
        *,
        task_id: str,
        phase: MemoryTaskPhase,
        phase_results: dict[str, dict],
        worker_task_id: str | None,
    ) -> dict:
        if phase == MemoryTaskPhase.COMMITTED:
            return cls._commit_memory_write_task(task_id=task_id, phase_results=phase_results)

        from service.memory import MemoryWriteTaskService

        current_phase = str(phase)
        try:
            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            checkpoint = cls.run_memory_write_task_phase(
                task_id=task_id,
                phase=current_phase,
                task=task,
                phase_results=phase_results,
            )
            phase_results[current_phase] = checkpoint
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
                result_ref=checkpoint,
                operator_notes=f"Worker completed {current_phase}.",
            )
        except Exception as exc:
            journal_ref, rollback_metadata = cls._build_recovery_artifacts_from_failure(
                exc=exc,
                phase_results=phase_results,
                worker_task_id=worker_task_id,
            )
            MemoryWriteTaskService.mark_needs_manual_recovery(
                task_id,
                phase=current_phase,
                error=str(exc),
                rollback_metadata=rollback_metadata,
                journal_ref=journal_ref,
            )
            raise

        next_phase = MEMORY_WRITE_STATE_TRANSITIONS[phase]
        return cls._advance_memory_write_state(
            task_id=task_id,
            phase=next_phase,
            phase_results=phase_results,
            worker_task_id=worker_task_id,
        )


    @classmethod
    def _commit_memory_write_task(cls,*, task_id: str, phase_results: dict[str, dict]) -> dict:
        from service.memory import MemoryWriteTaskService

        final_result = {
            "task_id": task_id,
            "status": str(MemoryTaskFinalStatus.SUCCESS),
            "final_phase": str(MemoryTaskPhase.COMMITTED),
            "phase_results": phase_results,
        }
        journal_ref, _rollback_metadata = cls._extract_recovery_artifacts(phase_results=phase_results)
        if journal_ref:
            final_result["journal_ref"] = journal_ref
        MemoryWriteTaskService.mark_committed(
            task_id,
            result_ref=final_result,
            operator_notes="Worker completed runtime state machine through committed.",
            journal_ref=journal_ref,
        )
        return final_result


    @classmethod
    def _extract_recovery_artifacts(cls,*, phase_results: dict[str, dict]) -> tuple[str | None, dict]:
        journal_ref = None
        rollback_metadata: dict = {}
        for result in phase_results.values():
            if not isinstance(result, dict):
                continue
            if result.get("journal_ref"):
                journal_ref = result["journal_ref"]
            result_rollback_metadata = result.get("rollback_metadata")
            if isinstance(result_rollback_metadata, dict):
                rollback_metadata = {**rollback_metadata, **result_rollback_metadata}
        return journal_ref, rollback_metadata


    @classmethod
    def _build_recovery_artifacts_from_failure(
        cls,
        *,
        exc: Exception,
        phase_results: dict[str, dict],
        worker_task_id: str | None,
    ) -> tuple[str | None, dict]:
        journal_ref, rollback_metadata = cls._extract_recovery_artifacts(phase_results=phase_results)
        if worker_task_id:
            rollback_metadata = {"worker_task_id": worker_task_id, **rollback_metadata}
        try:
            parsed_error = json.loads(str(exc))
        except json.JSONDecodeError:
            parsed_error = None
        if isinstance(parsed_error, dict):
            if parsed_error.get("journal_ref") and not journal_ref:
                journal_ref = parsed_error["journal_ref"]
            parsed_rollback_metadata = parsed_error.get("rollback_metadata")
            if isinstance(parsed_rollback_metadata, dict):
                rollback_metadata = {**rollback_metadata, **parsed_rollback_metadata}
        return journal_ref, rollback_metadata


    @classmethod
    def _materialize_worker_archive(cls,*, task_id: str, worker_task_id: str | None) -> object:
        from runtime.memory.source_archive import MemorySourceArchiveRuntime
        from service.memory import MemoryWriteTaskService
        from service.memory.base.enums import MemoryTriggerType

        task = MemoryWriteTaskService.get_task(task_id)
        if task.trigger_type != MemoryTriggerType.MEMORY_API or task.source_ref.type != "conversation":
            return None

        try:
            archive_ref = MemorySourceArchiveRuntime.freeze_memory_api_conversation_source(task)
            MemoryWriteTaskService.attach_archive_ref(task_id, archive_ref=archive_ref)
            return archive_ref
        except Exception as exc:
            rollback_metadata = {"worker_task_id": worker_task_id} if worker_task_id else None
            MemoryWriteTaskService.mark_needs_manual_recovery(
                task_id,
                phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
                error=str(exc),
                rollback_metadata=rollback_metadata,
            )
            raise


    @classmethod
    def _cleanup_worker_archive(cls,*, task_id: str, archive_ref) -> None:
        if archive_ref is None:
            return

        from runtime.memory.source_archive import MemorySourceArchiveRuntime
        from service.memory import MemoryWriteTaskService

        try:
            MemorySourceArchiveRuntime.delete_archive(archive_ref)
        except Exception:
            return

        try:
            MemoryWriteTaskService.clear_archive_ref(task_id)
        except Exception:
            return
