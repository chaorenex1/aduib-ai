from __future__ import annotations

from runtime.memory.write_state_machine import MemoryStateMachineRuntime

from .celery_app import celery_app


@celery_app.task(name="runtime.tasks.memory_write.execute", bind=True)
def execute_memory_write(self, task_id: str) -> dict:
    return MemoryStateMachineRuntime.execute_memory_write_task(task_id, worker_task_id=self.request.id)
