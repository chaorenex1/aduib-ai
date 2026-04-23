from __future__ import annotations

from service.memory.base.contracts import MemoryWritePipelineContext
from service.memory.base.enums import MemoryTaskPhase

from .apply.file_commit import apply_memory_files
from .apply.metadata_refresh import refresh_metadata
from .apply.navigation_refresh import refresh_navigation
from .apply.staged_write import build_staged_write_set
from .extract.planner import extract_operations
from .extract.prepare_context import prepare_extract_context
from .resolve_operations import resolve_operations

PHASE_HANDLERS = {
    MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT: prepare_extract_context,
    MemoryTaskPhase.EXTRACT_OPERATIONS: extract_operations,
    MemoryTaskPhase.RESOLVE_OPERATIONS: resolve_operations,
    MemoryTaskPhase.BUILD_STAGED_WRITE_SET: build_staged_write_set,
    MemoryTaskPhase.APPLY_MEMORY_FILES: apply_memory_files,
    MemoryTaskPhase.REFRESH_NAVIGATION: refresh_navigation,
    MemoryTaskPhase.REFRESH_METADATA: refresh_metadata,
}


def run_memory_write_phase(context: MemoryWritePipelineContext) -> dict:
    phase = MemoryTaskPhase(str(context.phase))
    handler = PHASE_HANDLERS.get(phase)
    if handler is None:
        return _build_skeleton_phase_payload(context=context, phase=str(phase))
    return handler(context)


def run_memory_write_task_phase(*, task_id: str, phase: str, task, phase_results: dict[str, dict]) -> dict:
    from .write_context import build_memory_write_pipeline_context

    context = build_memory_write_pipeline_context(
        task_id=task_id,
        phase=phase,
        task=task,
        phase_results=phase_results,
    )
    return run_memory_write_phase(context)


def _build_skeleton_phase_payload(*, context: MemoryWritePipelineContext, phase: str) -> dict:
    raise ValueError(f"unsupported memory write phase: {phase}")
