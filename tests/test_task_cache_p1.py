"""
Integration tests for Task Cache API - P1 Enhanced Features
"""
import pytest
from models import get_db, TaskCache
from service.task_cache_service import TaskCacheService


class TestTaskCacheP1Features:
    """Test P1 enhanced features"""

    def test_batch_save_tasks(self):
        """Test batch saving multiple tasks"""
        tasks_data = [
            {
                "request": f"batch request {i}",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": f"output {i}",
                "duration_seconds": 1.0 + i * 0.1
            }
            for i in range(5)
        ]

        result = TaskCacheService.save_tasks_batch(tasks_data)

        assert result["total_processed"] == 5
        assert result["saved_count"] + result["updated_count"] == 5 - result["failed_count"]
        assert result["failed_count"] == 0
        assert len(result["task_ids"]) == 5

        # Clean up
        with get_db() as session:
            for task_id in result["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_batch_save_with_duplicates(self):
        """Test batch save handles duplicates correctly"""
        tasks_data = [
            {
                "request": "duplicate request",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": "first output"
            },
            {
                "request": "duplicate request",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": "second output (should update)"
            }
        ]

        result = TaskCacheService.save_tasks_batch(tasks_data)

        assert result["total_processed"] == 2
        # Should have 1 save and 1 update
        assert result["saved_count"] >= 1

        # Clean up
        with get_db() as session:
            for task_id in result["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_delete_task(self):
        """Test deleting a task"""
        # Create a task
        task = TaskCacheService.save_task(
            request="task to delete",
            mode="command",
            backend="claude",
            success=True,
            output="output"
        )
        task_id = task.id

        # Delete it
        success = TaskCacheService.delete_task(task_id)
        assert success is True

        # Verify it's deleted
        with get_db() as session:
            deleted_task = session.query(TaskCache).filter_by(id=task_id).first()
            assert deleted_task is None

    def test_delete_nonexistent_task(self):
        """Test deleting a non-existent task returns False"""
        success = TaskCacheService.delete_task(999999)
        assert success is False

    def test_clear_old_tasks(self):
        """Test clearing old tasks"""
        from datetime import datetime, timedelta

        # Create an old task by manipulating its created_at
        task = TaskCacheService.save_task(
            request="old task",
            mode="command",
            backend="claude",
            success=True,
            output="output"
        )

        # Manually set created_at to 60 days ago
        with get_db() as session:
            old_task = session.query(TaskCache).filter_by(id=task.id).first()
            old_task.created_at = datetime.now() - timedelta(days=60)
            session.commit()

        # Clear tasks older than 30 days
        deleted_count = TaskCacheService.clear_old_tasks(days=30)
        assert deleted_count >= 1

        # Verify task is deleted
        with get_db() as session:
            deleted_task = session.query(TaskCache).filter_by(id=task.id).first()
            assert deleted_task is None

    def test_export_tasks_json(self):
        """Test exporting tasks as JSON"""
        # Create some test tasks
        tasks = []
        for i in range(3):
            task = TaskCacheService.save_task(
                request=f"export test {i}",
                mode="command",
                backend="claude",
                success=True,
                output=f"output {i}"
            )
            tasks.append(task)

        # Export as JSON
        exported = TaskCacheService.export_tasks(format='json', limit=10)

        assert isinstance(exported, list)
        assert len(exported) >= 3

        # Verify structure
        if exported:
            assert 'id' in exported[0]
            assert 'request' in exported[0]
            assert 'mode' in exported[0]
            assert 'backend' in exported[0]

        # Clean up
        with get_db() as session:
            for task in tasks:
                session.delete(task)
            session.commit()

    def test_export_tasks_with_filters(self):
        """Test exporting tasks with filters"""
        # Create tasks with different modes
        task1 = TaskCacheService.save_task(
            request="command task",
            mode="command",
            backend="claude",
            success=True,
            output="output"
        )
        task2 = TaskCacheService.save_task(
            request="agent task",
            mode="agent",
            backend="gemini",
            success=True,
            output="output"
        )

        # Export only command mode
        exported = TaskCacheService.export_tasks(mode="command")
        assert all(t['mode'] == 'command' for t in exported if t['id'] in [task1.id, task2.id])

        # Export only gemini backend
        exported = TaskCacheService.export_tasks(backend="gemini")
        gemini_tasks = [t for t in exported if t['id'] == task2.id]
        assert all(t['backend'] == 'gemini' for t in gemini_tasks)

        # Clean up
        with get_db() as session:
            session.delete(task1)
            session.delete(task2)
            session.commit()

    def test_request_validation(self):
        """Test that invalid data is rejected"""
        # Test invalid mode
        with pytest.raises(ValueError, match="Mode must be one of"):
            from controllers.task_cache.task_cache import TaskDataRequest
            TaskDataRequest(
                request="test",
                mode="invalid_mode",
                backend="claude",
                success=True,
                output="output"
            )

        # Test invalid backend
        with pytest.raises(ValueError, match="Backend must be one of"):
            from controllers.task_cache.task_cache import TaskDataRequest
            TaskDataRequest(
                request="test",
                mode="command",
                backend="invalid_backend",
                success=True,
                output="output"
            )

    def test_duration_validation(self):
        """Test duration field validation"""
        from controllers.task_cache.task_cache import TaskDataRequest
        from pydantic import ValidationError

        # Valid duration
        valid_request = TaskDataRequest(
            request="test",
            mode="command",
            backend="claude",
            success=True,
            output="output",
            duration_seconds=10.5
        )
        assert valid_request.duration_seconds == 10.5

        # Negative duration should fail
        with pytest.raises(ValidationError):
            TaskDataRequest(
                request="test",
                mode="command",
                backend="claude",
                success=True,
                output="output",
                duration_seconds=-1.0
            )

        # Duration > 1 hour (3600s) should fail
        with pytest.raises(ValidationError):
            TaskDataRequest(
                request="test",
                mode="command",
                backend="claude",
                success=True,
                output="output",
                duration_seconds=4000
            )

    def test_batch_request_size_limit(self):
        """Test batch request size limits"""
        from controllers.task_cache.task_cache import BatchTaskDataRequest, TaskDataRequest
        from pydantic import ValidationError

        # Valid batch (within limit)
        tasks = [
            TaskDataRequest(
                request=f"task {i}",
                mode="command",
                backend="claude",
                success=True,
                output="output"
            )
            for i in range(50)
        ]
        batch = BatchTaskDataRequest(tasks=tasks)
        assert len(batch.tasks) == 50

        # Empty batch should fail
        with pytest.raises(ValidationError):
            BatchTaskDataRequest(tasks=[])

        # Batch > 100 should fail
        with pytest.raises(ValidationError):
            tasks_too_many = [
                TaskDataRequest(
                    request=f"task {i}",
                    mode="command",
                    backend="claude",
                    success=True,
                    output="output"
                )
                for i in range(101)
            ]
            BatchTaskDataRequest(tasks=tasks_too_many)

    def test_performance_with_large_batch(self):
        """Test performance with larger batch"""
        import time

        tasks_data = [
            {
                "request": f"perf test {i}",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": f"output {i}"
            }
            for i in range(50)
        ]

        start_time = time.time()
        result = TaskCacheService.save_tasks_batch(tasks_data)
        duration = time.time() - start_time

        assert result["total_processed"] == 50
        assert duration < 5.0  # Should complete within 5 seconds

        # Clean up
        with get_db() as session:
            for task_id in result["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
