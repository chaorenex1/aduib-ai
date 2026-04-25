from __future__ import annotations

import datetime

from models import MemoryWriteTask, get_db
from service.error.base import RepositoryBase


class MemoryWriteTaskRepository(RepositoryBase):
    @staticmethod
    def get_by_idempotency_key(idempotency_key: str) -> MemoryWriteTask | None:
        with get_db() as session:
            return (
                session.query(MemoryWriteTask)
                .filter(MemoryWriteTask.idempotency_key == idempotency_key)
                .order_by(MemoryWriteTask.created_at.desc())
                .first()
            )

    @staticmethod
    def create(task: MemoryWriteTask) -> MemoryWriteTask:
        with get_db() as session:
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    @staticmethod
    def get_by_task_id(task_id: str) -> MemoryWriteTask | None:
        with get_db() as session:
            return session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()

    @staticmethod
    def update_task(
        task_id: str,
        *,
        mutate,
    ) -> MemoryWriteTask | None:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if task is None:
                return None
            mutate(task)
            task.updated_at = datetime.datetime.now()
            session.commit()
            session.refresh(task)
            return task