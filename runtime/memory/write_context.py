from __future__ import annotations

from service.memory.base.contracts import MemoryWritePipelineContext


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
