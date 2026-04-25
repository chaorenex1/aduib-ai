from __future__ import annotations

import asyncio

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
    async def execute_memory_write_task(cls, task_id: str) -> dict:
        return await asyncio.to_thread(cls._execute_memory_write_task_sync, task_id)

    @classmethod
    def _execute_memory_write_task_sync(cls, task_id: str) -> dict:
        archive_ref = None
        current_phase = str(MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT)
        try:
            archive_ref = cls._materialize_worker_archive(task_id=task_id)

            from service.memory import MemoryWriteTaskService

            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            prepared_context = cls._run_prepare_extract_context(task_id=task_id, task=task)
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
            )

            current_phase = str(MemoryTaskPhase.EXTRACT_OPERATIONS)
            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            extract_result = cls._run_extract_operations(prepared_context)
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
            )

            current_phase = cls.APPLY_COORDINATION_PHASE
            task = MemoryWriteTaskService.mark_running(task_id, phase=current_phase)
            committed_result = cls._run_memory_updater(
                task=task,
                prepared_context=prepared_context,
                extract_result=extract_result,
            )
            committed_payload = committed_result.model_dump(mode="python", exclude_none=True)
            MemoryWriteTaskService.record_checkpoint(
                task_id,
                phase=current_phase,
            )
            MemoryWriteTaskService.mark_committed(task_id)
            return committed_payload
        except Exception as exc:
            from service.memory import MemoryWriteTaskService

            MemoryWriteTaskService.mark_needs_manual_recovery(
                task_id,
                phase=current_phase,
                error=str(exc),
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
