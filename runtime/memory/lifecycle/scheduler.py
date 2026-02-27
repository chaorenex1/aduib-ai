"""记忆生命周期调度任务实现。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel

from .consolidation import Consolidation
from .promotion import MemoryPromotion
from .forgetting import Forgetting
from ..storage.adapter import StorageAdapter
from ..types.base import MemoryLifecycle

logger = logging.getLogger(__name__)


class ScheduleType(StrEnum):
    """调度类型枚举。"""

    SESSION_END = "session_end"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskType(StrEnum):
    """任务类型枚举。"""

    CONSOLIDATION = "consolidation"
    PROMOTION = "promotion"
    FORGETTING = "forgetting"
    CLEANUP = "cleanup"


class ScheduledTask(BaseModel):
    """调度任务配置。"""

    name: str
    task_type: TaskType
    schedule_type: ScheduleType
    cron: Optional[str] = None
    params: dict[str, Any] = {}
    enabled: bool = True


class TaskExecutionResult(BaseModel):
    """任务执行结果。"""

    task_name: str
    task_type: TaskType
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = True
    error: Optional[str] = None
    details: dict[str, Any] = {}


class MemoryLifecycleScheduler:
    """记忆生命周期调度器。"""

    DEFAULT_SCHEDULES: list[ScheduledTask] = [
        # 会话结束时
        ScheduledTask(
            name="session_end",
            task_type=TaskType.CONSOLIDATION,
            schedule_type=ScheduleType.SESSION_END,
        ),
        # 每日任务
        ScheduledTask(
            name="daily_promotion",
            task_type=TaskType.PROMOTION,
            schedule_type=ScheduleType.DAILY,
            cron="0 3 * * *",
            params={"levels": ["transient"]},
        ),
        ScheduledTask(
            name="daily_forgetting",
            task_type=TaskType.FORGETTING,
            schedule_type=ScheduleType.DAILY,
            cron="0 4 * * *",
            params={"levels": ["transient", "short"]},
        ),
        # 每周任务
        ScheduledTask(
            name="weekly_promotion",
            task_type=TaskType.PROMOTION,
            schedule_type=ScheduleType.WEEKLY,
            cron="0 3 * * 0",
            params={"levels": ["short"]},
        ),
        ScheduledTask(
            name="weekly_forgetting",
            task_type=TaskType.FORGETTING,
            schedule_type=ScheduleType.WEEKLY,
            cron="0 4 * * 0",
            params={"levels": ["short"]},
        ),
        # 每月任务
        ScheduledTask(
            name="monthly_promotion",
            task_type=TaskType.PROMOTION,
            schedule_type=ScheduleType.MONTHLY,
            cron="0 3 1 * *",
            params={"levels": ["long"]},
        ),
        ScheduledTask(
            name="monthly_cleanup",
            task_type=TaskType.CLEANUP,
            schedule_type=ScheduleType.MONTHLY,
            cron="0 5 1 * *",
            params={"older_than_days": 180},
        ),
    ]

    def __init__(
        self,
        consolidation: Consolidation,
        promotion: MemoryPromotion,
        forgetting: Forgetting,
        storage: StorageAdapter,
    ):
        """初始化调度器。"""
        self.consolidation = consolidation
        self.promotion = promotion
        self.forgetting = forgetting
        self.storage = storage

        # 复制默认调度配置以允许运行时修改
        self._schedules = [task.model_copy() for task in self.DEFAULT_SCHEDULES]

    async def on_session_end(self, session_id: str) -> TaskExecutionResult:
        """处理会话结束事件 - 整合工作记忆。"""
        started_at = datetime.now(timezone.utc)

        try:
            await self.consolidation.consolidate_session(session_id)

            return TaskExecutionResult(
                task_name="session_end",
                task_type=TaskType.CONSOLIDATION,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                success=True,
            )
        except Exception as e:
            logger.error(f"Session end consolidation failed: {e}")
            return TaskExecutionResult(
                task_name="session_end",
                task_type=TaskType.CONSOLIDATION,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                success=False,
                error=str(e),
            )

    async def run_daily_tasks(self) -> list[TaskExecutionResult]:
        """运行每日调度任务。"""
        daily_tasks = [
            task for task in self._schedules
            if task.schedule_type == ScheduleType.DAILY and task.enabled
        ]

        results = []
        for task in daily_tasks:
            result = await self.run_task(task)
            results.append(result)

        return results

    async def run_weekly_tasks(self) -> list[TaskExecutionResult]:
        """运行每周调度任务。"""
        weekly_tasks = [
            task for task in self._schedules
            if task.schedule_type == ScheduleType.WEEKLY and task.enabled
        ]

        results = []
        for task in weekly_tasks:
            result = await self.run_task(task)
            results.append(result)

        return results

    async def run_monthly_tasks(self) -> list[TaskExecutionResult]:
        """运行每月调度任务。"""
        monthly_tasks = [
            task for task in self._schedules
            if task.schedule_type == ScheduleType.MONTHLY and task.enabled
        ]

        results = []
        for task in monthly_tasks:
            result = await self.run_task(task)
            results.append(result)

        return results

    async def run_task(self, task: ScheduledTask) -> TaskExecutionResult:
        """执行单个调度任务。"""
        started_at = datetime.now(timezone.utc)

        try:
            if task.task_type == TaskType.CONSOLIDATION:
                # 整合任务 - 需要 session_id，这里通过 params 传递
                session_id = task.params.get("session_id", "")
                await self.consolidation.consolidate_session(session_id)

            elif task.task_type == TaskType.PROMOTION:
                # 升级任务 - 获取指定生命周期的记忆
                levels = task.params.get("levels", [])
                memories = await self._get_memories_by_levels(levels)
                await self.promotion.run_promotion_batch(memories)

            elif task.task_type == TaskType.FORGETTING:
                # 遗忘任务 - 获取指定生命周期的记忆
                levels = task.params.get("levels", [])
                memories = await self._get_memories_by_levels(levels)
                await self.forgetting.run_forgetting_batch(memories)

            elif task.task_type == TaskType.CLEANUP:
                # 清理任务
                older_than_days = task.params.get("older_than_days", 180)
                await self.cleanup_archived(older_than_days)

            return TaskExecutionResult(
                task_name=task.name,
                task_type=task.task_type,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                success=True,
            )

        except Exception as e:
            logger.error(f"Task {task.name} failed: {e}")
            return TaskExecutionResult(
                task_name=task.name,
                task_type=task.task_type,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                success=False,
                error=str(e),
            )

    async def cleanup_archived(self, older_than_days: int = 180) -> int:
        """清理归档记忆（stub 实现）。"""
        # TODO: 实现真正的清理逻辑，需要存储层支持更复杂的查询
        logger.warning(
            f"cleanup_archived is not fully implemented. "
            f"Would clean memories archived more than {older_than_days} days ago."
        )
        return 0

    async def _get_memories_by_levels(self, levels: list[str]) -> list:
        """根据生命周期级别获取记忆（简化实现）。"""
        # 由于 StorageAdapter 不支持按生命周期查询，这里返回空列表
        # 在真实场景中，需要扩展存储接口或在调用方提供记忆列表
        logger.warning(f"_get_memories_by_levels is simplified. Levels: {levels}")
        return []

    def get_schedules(self) -> list[ScheduledTask]:
        """获取所有配置的调度任务。"""
        return self._schedules.copy()

    def enable_task(self, task_name: str) -> None:
        """启用指定任务。"""
        for task in self._schedules:
            if task.name == task_name:
                task.enabled = True
                break

    def disable_task(self, task_name: str) -> None:
        """禁用指定任务。"""
        for task in self._schedules:
            if task.name == task_name:
                task.enabled = False
                break