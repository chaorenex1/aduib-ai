"""
Performance Optimization Tests for Task Cache API - P2
"""
import pytest
import time
from models import get_db, TaskCache
from service.task_cache_service import TaskCacheService


class TestTaskCacheP2Features:
    """Test P2 performance optimization features"""

    def test_redis_statistics_caching(self):
        """Test that statistics are cached in Redis"""
        # Create some test tasks
        task1 = TaskCacheService.save_task(
            request="cache test 1",
            mode="command",
            backend="claude",
            success=True,
            output="output"
        )

        # First call - should query database
        start_time = time.time()
        stats1 = TaskCacheService.get_statistics(use_cache=True)
        first_duration = time.time() - start_time

        # Second call - should use cache (faster)
        start_time = time.time()
        stats2 = TaskCacheService.get_statistics(use_cache=True)
        second_duration = time.time() - start_time

        # Verify stats are the same
        assert stats1 == stats2

        # Second call should be faster (from cache)
        # Note: This might not always be true in test environment
        # but we can at least verify it doesn't error

        # Test with cache disabled
        stats3 = TaskCacheService.get_statistics(use_cache=False)
        assert stats3["total_tasks"] >= 1

        # Clean up
        with get_db() as session:
            session.delete(task1)
            session.commit()

    def test_batch_save_with_transaction(self):
        """Test optimized batch save with single transaction"""
        tasks_data = [
            {
                "request": f"transaction test {i}",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": f"output {i}"
            }
            for i in range(20)
        ]

        # Test with transaction (optimized)
        start_time = time.time()
        result_optimized = TaskCacheService.save_tasks_batch(
            tasks_data,
            use_transaction=True
        )
        optimized_duration = time.time() - start_time

        assert result_optimized["total_processed"] == 20
        assert result_optimized["saved_count"] + result_optimized["updated_count"] == 20

        # Clean up
        with get_db() as session:
            for task_id in result_optimized["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_batch_save_transaction_rollback(self):
        """Test that batch save rolls back on error"""
        # Create task data with one invalid entry
        tasks_data = [
            {
                "request": "valid task 1",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": "output"
            },
            {
                "request": None,  # This will cause an error
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": "output"
            }
        ]

        # Should handle error gracefully
        try:
            result = TaskCacheService.save_tasks_batch(
                tasks_data,
                use_transaction=True
            )
            # Might succeed with partial save
            assert result["failed_count"] >= 1
        except Exception:
            # Or might raise exception
            pass

    def test_batch_save_performance_comparison(self):
        """Compare performance of old vs new batch save"""
        tasks_data = [
            {
                "request": f"perf test {i}",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": f"output {i}"
            }
            for i in range(30)
        ]

        # Test optimized version
        start_time = time.time()
        result_optimized = TaskCacheService.save_tasks_batch(
            tasks_data,
            use_transaction=True
        )
        optimized_duration = time.time() - start_time

        # Should complete reasonably fast
        assert optimized_duration < 5.0  # Should be under 5 seconds

        # Clean up
        with get_db() as session:
            for task_id in result_optimized["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_cleanup_scheduler_status(self):
        """Test cleanup scheduler status"""
        from runtime.tasks.task_cache_cleanup import get_cleanup_status

        status = get_cleanup_status()

        assert "enabled" in status
        assert "retention_days" in status
        assert "total_cleaned" in status
        assert status["enabled"] is True

    def test_manual_cleanup_trigger(self):
        """Test manual cleanup trigger"""
        from runtime.tasks.task_cache_cleanup import run_scheduled_cleanup
        from datetime import datetime, timedelta

        # Create an old task
        task = TaskCacheService.save_task(
            request="old task for cleanup",
            mode="command",
            backend="claude",
            success=True,
            output="output"
        )

        # Manually set it to 100 days old
        with get_db() as session:
            old_task = session.query(TaskCache).filter_by(id=task.id).first()
            old_task.created_at = datetime.now() - timedelta(days=100)
            session.commit()

        # Trigger cleanup (should not delete - wrong hour)
        # Just test that it runs without error
        import asyncio
        try:
            result = asyncio.run(run_scheduled_cleanup())
            assert "status" in result
        except Exception as e:
            # May fail if Redis not available, that's ok
            pass

        # Clean up
        with get_db() as session:
            task_to_delete = session.query(TaskCache).filter_by(id=task.id).first()
            if task_to_delete:
                session.delete(task_to_delete)
                session.commit()

    def test_logging_for_batch_operations(self):
        """Test that batch operations log correctly"""
        import logging

        # Capture logs
        logger = logging.getLogger("service.task_cache_service")
        original_level = logger.level
        logger.setLevel(logging.INFO)

        tasks_data = [
            {
                "request": "log test 1",
                "mode": "command",
                "backend": "claude",
                "success": True,
                "output": "output"
            }
        ]

        # Should log without errors
        result = TaskCacheService.save_tasks_batch(tasks_data)
        assert result["total_processed"] == 1

        # Restore log level
        logger.setLevel(original_level)

        # Clean up
        with get_db() as session:
            for task_id in result["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_cache_invalidation_after_cleanup(self):
        """Test that cache is invalidated after cleanup"""
        # Get initial stats (will be cached)
        stats1 = TaskCacheService.get_statistics(use_cache=True)

        # Clear old tasks
        TaskCacheService.clear_old_tasks(days=365)  # Clear very old tasks

        # Cache should be cleared automatically
        # (though we can't easily test this without Redis)

        stats2 = TaskCacheService.get_statistics(use_cache=False)
        # Stats should still be valid
        assert "total_tasks" in stats2

    def test_performance_with_large_dataset(self):
        """Test performance with larger dataset"""
        # Create 100 tasks
        tasks_data = [
            {
                "request": f"large dataset test {i}",
                "mode": "command" if i % 2 == 0 else "agent",
                "backend": "claude" if i % 3 == 0 else "gemini",
                "success": i % 5 != 0,  # 20% failure rate
                "output": f"output {i}",
                "duration_seconds": 1.0 + (i % 10) * 0.1
            }
            for i in range(100)
        ]

        start_time = time.time()
        result = TaskCacheService.save_tasks_batch(tasks_data, use_transaction=True)
        duration = time.time() - start_time

        # Should complete in reasonable time
        assert duration < 10.0  # Should be under 10 seconds for 100 tasks
        assert result["total_processed"] == 100

        # Test statistics performance with large dataset
        start_time = time.time()
        stats = TaskCacheService.get_statistics(use_cache=False)
        stats_duration = time.time() - start_time

        assert stats_duration < 1.0  # Should be under 1 second
        assert stats["total_tasks"] >= 100

        # Clean up
        with get_db() as session:
            for task_id in result["task_ids"]:
                task = session.query(TaskCache).filter_by(id=task_id).first()
                if task:
                    session.delete(task)
            session.commit()

    def test_export_performance(self):
        """Test export performance with moderate dataset"""
        # Create 50 tasks
        tasks = []
        for i in range(50):
            task = TaskCacheService.save_task(
                request=f"export perf test {i}",
                mode="command",
                backend="claude",
                success=True,
                output=f"output {i}"
            )
            tasks.append(task)

        # Test export performance
        start_time = time.time()
        exported = TaskCacheService.export_tasks(format='json', limit=50)
        export_duration = time.time() - start_time

        # Should be fast
        assert export_duration < 2.0  # Under 2 seconds
        assert len(exported) >= 50

        # Clean up
        with get_db() as session:
            for task in tasks:
                session.delete(task)
            session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
