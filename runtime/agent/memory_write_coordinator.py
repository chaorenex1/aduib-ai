from __future__ import annotations

from runtime.memory.base.contracts import MemorySourceRef, MemoryTaskCreateCommand
from runtime.memory.base.enums import MemoryTriggerType
from service.memory.write_task_service import MemoryWriteTaskService


class MemoryWriteCoordinator:
    @classmethod
    async def maybe_schedule_write(
        cls,
        *,
        mode: str,
        session_id: int,
        user_id: str | None,
        agent_id: int,
        agent_enabled_memory: bool,
    ) -> str | None:
        if mode != "agent" or not agent_enabled_memory or not user_id:
            return None
        accepted = await MemoryWriteTaskService.accept_task_request(
            MemoryTaskCreateCommand(
                trigger_type=MemoryTriggerType.SESSION_COMMIT,
                user_id=str(user_id),
                agent_id=str(agent_id),
                source_ref=MemorySourceRef(type="conversation", external_session_id=str(session_id)),
            )
        )
        return accepted.task_id
