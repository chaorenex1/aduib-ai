from __future__ import annotations

import json

from runtime.memory.apply.memory_updater import MemoryUpdater
from runtime.memory.prepare_context.extract_context_runtime import ExtractContextRuntime

from .base.contracts import (
    ExtractOperationsPhaseResult,
    MemoryCommittedResult,
    MemoryUpdateContext,
    PreparedExtractContext,
)
from .base.enums import MemoryTaskPhase
from .extract.orchestrator import ReActOrchestrator


class MemoryStateMachineRuntime:
    APPLY_COORDINATION_PHASE = str(MemoryTaskPhase.MEMORY_UPDATER)

    @classmethod
    def execute_memory_write_task(cls, task_id: str) -> dict:
        archive_ref = None
        stage_results: dict[str, dict] = {}
        current_phase = str(MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT)
        try:
            archive_ref = cls._materialize_worker_archive(task_id=task_id)

            from service.memory import MemoryWriteTaskService

            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            prepared_context = cls._run_prepare_extract_context(task_id=task_id, task=task)
            prepared_payload = prepared_context.model_dump(mode="python", exclude_none=True)
            stage_results[current_phase] = prepared_payload
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
                result_ref=prepared_payload,
                operator_notes=f"Worker completed {current_phase}.",
            )

            current_phase = str(MemoryTaskPhase.EXTRACT_OPERATIONS)
            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            extract_result = cls._run_extract_operations(prepared_context)
            extract_payload = extract_result.model_dump(mode="python", exclude_none=True)
            stage_results[current_phase] = extract_payload
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
                result_ref=extract_payload,
                operator_notes=f"Worker completed {current_phase}.",
            )

            current_phase = cls.APPLY_COORDINATION_PHASE
            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            committed_result = cls._run_memory_updater(
                task=task,
                prepared_context=prepared_context,
                extract_result=extract_result,
            )
            committed_payload = committed_result.model_dump(mode="python", exclude_none=True)
            stage_results[current_phase] = committed_payload
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
                result_ref=committed_payload,
                operator_notes="Worker completed memory_updater.",
                journal_ref=committed_result.journal_ref,
                rollback_metadata=committed_result.rollback_metadata,
            )
            MemoryWriteTaskService.mark_committed(
                task_id,
                result_ref=committed_payload,
                operator_notes="Worker completed ExtractContext -> ReActOrchestrator -> MemoryUpdater.",
                journal_ref=committed_result.journal_ref,
            )
            return committed_payload
        except Exception as exc:
            from service.memory import MemoryWriteTaskService

            journal_ref, rollback_metadata = cls._build_recovery_artifacts_from_failure(
                exc=exc,
                stage_results=stage_results,
            )
            MemoryWriteTaskService.mark_needs_manual_recovery(
                task_id,
                phase=current_phase,
                error=str(exc),
                rollback_metadata=rollback_metadata,
                journal_ref=journal_ref,
            )
            raise
        finally:
            cls._cleanup_worker_archive(task_id=task_id, archive_ref=archive_ref)

    @classmethod
    def _run_prepare_extract_context(cls, *, task_id: str, task) -> PreparedExtractContext:
        return ExtractContextRuntime.prepare(task_id=task_id, task=task)

    @classmethod
    def _run_extract_operations(cls, prepared_context: PreparedExtractContext) -> ExtractOperationsPhaseResult:
        return ReActOrchestrator(prepared_context).run()

    @classmethod
    def _run_memory_updater(
        cls,
        *,
        task,
        prepared_context: PreparedExtractContext,
        extract_result: ExtractOperationsPhaseResult,
    ) -> MemoryCommittedResult:
        update_ctx = MemoryUpdateContext.from_task(
            task=task,
            prepared_context=prepared_context,
            extract_result=extract_result,
        )
        return MemoryUpdater(update_ctx).run()

    @classmethod
    def _extract_recovery_artifacts(cls, *, stage_results: dict[str, dict]) -> tuple[str | None, dict]:
        journal_ref = None
        rollback_metadata: dict = {}
        for result in stage_results.values():
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
        stage_results: dict[str, dict],
        worker_task_id: str | None,
    ) -> tuple[str | None, dict]:
        journal_ref, rollback_metadata = cls._extract_recovery_artifacts(stage_results=stage_results)
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
    def _materialize_worker_archive(cls, *, task_id: str) -> object:
        from runtime.memory.source_archive import MemorySourceArchiveRuntime
        from service.memory import MemoryWriteTaskService

        task = MemoryWriteTaskService.get_task(task_id)
        try:
            archive_ref = MemorySourceArchiveRuntime.freeze_memory_api_conversation_source(task)
            MemoryWriteTaskService.attach_archive_ref(task_id, archive_ref=archive_ref)
            return archive_ref
        except Exception as exc:
            MemoryWriteTaskService.mark_needs_manual_recovery(
                task_id,
                phase=MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT,
                error=str(exc),
                rollback_metadata={},
            )
            raise

    @classmethod
    def _cleanup_worker_archive(cls, *, task_id: str, archive_ref) -> None:
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
