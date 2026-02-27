"""MemoryLifecycleScheduler 测试模块。"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from runtime.memory.lifecycle.scheduler import (
    ScheduleType,
    TaskType,
    ScheduledTask,
    TaskExecutionResult,
    MemoryLifecycleScheduler,
)
from runtime.memory.types.base import MemoryLifecycle


class TestScheduledTask:
    """ScheduledTask 测试类。"""

    def test_scheduled_task_creation(self):
        """测试创建 ScheduledTask 实例。"""
        task = ScheduledTask(
            name="daily_promotion",
            task_type=TaskType.PROMOTION,
            schedule_type=ScheduleType.DAILY,
            cron="0 3 * * *",
            params={"levels": ["transient"]},
        )

        assert task.name == "daily_promotion"
        assert task.task_type == TaskType.PROMOTION
        assert task.schedule_type == ScheduleType.DAILY
        assert task.cron == "0 3 * * *"
        assert task.params == {"levels": ["transient"]}
        assert task.enabled is True

    def test_scheduled_task_defaults(self):
        """测试 ScheduledTask 默认值。"""
        task = ScheduledTask(
            name="session_end",
            task_type=TaskType.CONSOLIDATION,
            schedule_type=ScheduleType.SESSION_END,
        )

        assert task.cron is None
        assert task.params == {}
        assert task.enabled is True


class TestTaskExecutionResult:
    """TaskExecutionResult 测试类。"""

    def test_task_execution_result_creation(self):
        """测试创建 TaskExecutionResult 实例。"""
        started_at = datetime.now(timezone.utc)
        result = TaskExecutionResult(
            task_name="daily_promotion",
            task_type=TaskType.PROMOTION,
            started_at=started_at,
        )

        assert result.task_name == "daily_promotion"
        assert result.task_type == TaskType.PROMOTION
        assert result.started_at == started_at
        assert result.completed_at is None
        assert result.success is True
        assert result.error is None
        assert result.details == {}


class TestMemoryLifecycleScheduler:
    """MemoryLifecycleScheduler 测试类。"""

    @pytest.fixture
    def mock_consolidation(self):
        """创建 Consolidation mock。"""
        consolidation = AsyncMock()
        consolidation.consolidate_session.return_value = []
        return consolidation

    @pytest.fixture
    def mock_promotion(self):
        """创建 MemoryPromotion mock。"""
        promotion = AsyncMock()
        promotion.run_promotion_batch.return_value = MagicMock(
            total_evaluated=10, total_promoted=2, errors=[]
        )
        return promotion

    @pytest.fixture
    def mock_forgetting(self):
        """创建 Forgetting mock。"""
        forgetting = AsyncMock()
        forgetting.run_forgetting_batch.return_value = MagicMock(
            total_evaluated=10, total_forgotten=1, errors=[]
        )
        return forgetting

    @pytest.fixture
    def mock_storage(self):
        """创建 StorageAdapter mock。"""
        storage = AsyncMock()
        storage.list_by_session.return_value = []
        return storage

    @pytest.fixture
    def scheduler(self, mock_consolidation, mock_promotion, mock_forgetting, mock_storage):
        """创建 MemoryLifecycleScheduler 实例。"""
        return MemoryLifecycleScheduler(
            consolidation=mock_consolidation,
            promotion=mock_promotion,
            forgetting=mock_forgetting,
            storage=mock_storage,
        )

    def test_default_schedules_exist(self, scheduler):
        """测试默认调度任务配置存在。"""
        schedules = scheduler.get_schedules()
        assert len(schedules) == 7

        # 验证任务名称
        task_names = {task.name for task in schedules}
        expected_names = {
            "session_end",
            "daily_promotion",
            "daily_forgetting",
            "weekly_promotion",
            "weekly_forgetting",
            "monthly_promotion",
            "monthly_cleanup",
        }
        assert task_names == expected_names

    @pytest.mark.asyncio
    async def test_on_session_end(self, scheduler, mock_consolidation):
        """测试会话结束事件处理。"""
        session_id = "test_session_123"

        result = await scheduler.on_session_end(session_id)

        # 验证调用 consolidation
        mock_consolidation.consolidate_session.assert_called_once_with(session_id)

        # 验证返回结果
        assert result.task_name == "session_end"
        assert result.task_type == TaskType.CONSOLIDATION
        assert result.success is True
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_daily_tasks(self, scheduler, mock_promotion, mock_forgetting):
        """测试每日任务执行。"""
        results = await scheduler.run_daily_tasks()

        assert len(results) == 2

        # 验证 promotion 任务
        promotion_result = next(r for r in results if r.task_name == "daily_promotion")
        assert promotion_result.task_type == TaskType.PROMOTION
        assert promotion_result.success is True

        # 验证 forgetting 任务
        forgetting_result = next(r for r in results if r.task_name == "daily_forgetting")
        assert forgetting_result.task_type == TaskType.FORGETTING
        assert forgetting_result.success is True

        # 验证调用了相应的方法
        mock_promotion.run_promotion_batch.assert_called_once()
        mock_forgetting.run_forgetting_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_weekly_tasks(self, scheduler, mock_promotion, mock_forgetting):
        """测试每周任务执行。"""
        results = await scheduler.run_weekly_tasks()

        assert len(results) == 2

        # 验证任务类型
        task_types = {result.task_type for result in results}
        assert TaskType.PROMOTION in task_types
        assert TaskType.FORGETTING in task_types

    @pytest.mark.asyncio
    async def test_run_monthly_tasks(self, scheduler):
        """测试每月任务执行。"""
        results = await scheduler.run_monthly_tasks()

        assert len(results) == 2

        # 验证包含 cleanup 任务
        task_types = {result.task_type for result in results}
        assert TaskType.PROMOTION in task_types
        assert TaskType.CLEANUP in task_types

    @pytest.mark.asyncio
    async def test_run_task_error_handling(self, scheduler, mock_consolidation):
        """测试任务执行错误处理。"""
        # 模拟异常
        mock_consolidation.consolidate_session.side_effect = Exception("Test error")

        task = ScheduledTask(
            name="test_task",
            task_type=TaskType.CONSOLIDATION,
            schedule_type=ScheduleType.SESSION_END,
        )

        result = await scheduler.run_task(task)

        assert result.success is False
        assert result.error == "Test error"
        assert result.completed_at is not None

    def test_enable_disable_task(self, scheduler):
        """测试启用/禁用任务。"""
        # 默认所有任务都是启用的
        schedules = scheduler.get_schedules()
        daily_promotion = next(task for task in schedules if task.name == "daily_promotion")
        assert daily_promotion.enabled is True

        # 禁用任务
        scheduler.disable_task("daily_promotion")
        schedules = scheduler.get_schedules()
        daily_promotion = next(task for task in schedules if task.name == "daily_promotion")
        assert daily_promotion.enabled is False

        # 启用任务
        scheduler.enable_task("daily_promotion")
        schedules = scheduler.get_schedules()
        daily_promotion = next(task for task in schedules if task.name == "daily_promotion")
        assert daily_promotion.enabled is True

    @pytest.mark.asyncio
    async def test_cleanup_archived_stub(self, scheduler):
        """测试清理归档记忆功能（stub 实现）。"""
        count = await scheduler.cleanup_archived(older_than_days=180)

        # Stub 实现应该返回 0
        assert count == 0