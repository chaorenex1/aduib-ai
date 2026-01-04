"""
Test script for Task Cache API endpoints (P0 functionality)
"""
import pytest
import hashlib
from models import get_db, TaskCache
from service.task_cache_service import TaskCacheService


class TestTaskCacheService:
    """Test TaskCacheService business logic"""

    def test_compute_request_hash(self):
        """Test SHA256 hash computation"""
        request = "git status"
        mode = "command"
        backend = "claude"

        hash1 = TaskCacheService.compute_request_hash(request, mode, backend)
        hash2 = TaskCacheService.compute_request_hash(request, mode, backend)

        # Hash should be consistent
        assert hash1 == hash2
        # Hash should be SHA256 (64 chars)
        assert len(hash1) == 64
        # Hash should be hexadecimal
        assert all(c in '0123456789abcdef' for c in hash1)

        # Verify hash calculation
        expected = hashlib.sha256(f"{request}:{mode}:{backend}".encode('utf-8')).hexdigest()
        assert hash1 == expected

    def test_save_task(self):
        """Test saving task to cache"""
        task = TaskCacheService.save_task(
            request="test request",
            mode="command",
            backend="claude",
            success=True,
            output="test output",
            error=None,
            run_id="test-run-123",
            duration_seconds=2.5
        )

        assert task.id is not None
        assert task.request == "test request"
        assert task.mode == "command"
        assert task.backend == "claude"
        assert task.success is True
        assert task.output == "test output"
        assert task.run_id == "test-run-123"
        assert task.duration_seconds == 2.5
        assert task.hit_count == 0

        # Clean up
        with get_db() as session:
            session.delete(task)
            session.commit()

    def test_query_cache_not_found(self):
        """Test querying cache when not found"""
        result = TaskCacheService.query_cache(
            request_hash="nonexistent_hash",
            mode="command",
            backend="claude"
        )
        assert result is None

    def test_query_cache_found_and_increment(self):
        """Test querying cache when found and hit_count increment"""
        # First save a task
        task = TaskCacheService.save_task(
            request="cached request",
            mode="command",
            backend="claude",
            success=True,
            output="cached output"
        )

        initial_hit_count = task.hit_count
        request_hash = task.request_hash

        # Query the cache
        cached = TaskCacheService.query_cache(
            request_hash=request_hash,
            mode="command",
            backend="claude"
        )

        assert cached is not None
        assert cached.id == task.id
        assert cached.output == "cached output"
        assert cached.hit_count == initial_hit_count + 1

        # Query again
        cached2 = TaskCacheService.query_cache(
            request_hash=request_hash,
            mode="command",
            backend="claude"
        )
        assert cached2.hit_count == initial_hit_count + 2

        # Clean up
        with get_db() as session:
            session.delete(cached2)
            session.commit()

    def test_save_task_update_existing(self):
        """Test updating existing task with same hash"""
        # Save first task
        task1 = TaskCacheService.save_task(
            request="update test",
            mode="command",
            backend="claude",
            success=True,
            output="first output"
        )
        task1_id = task1.id

        # Save task with same request/mode/backend (should update)
        task2 = TaskCacheService.save_task(
            request="update test",
            mode="command",
            backend="claude",
            success=False,
            output="second output",
            error="Test error"
        )

        # Should be same ID
        assert task2.id == task1_id
        # Should have updated values
        assert task2.success is False
        assert task2.output == "second output"
        assert task2.error == "Test error"

        # Clean up
        with get_db() as session:
            session.delete(task2)
            session.commit()

    def test_get_history_pagination(self):
        """Test getting history with pagination"""
        # Create multiple tasks
        tasks = []
        for i in range(5):
            task = TaskCacheService.save_task(
                request=f"request {i}",
                mode="command",
                backend="claude",
                success=True,
                output=f"output {i}"
            )
            tasks.append(task)

        # Get first page
        history = TaskCacheService.get_history(limit=3, offset=0)
        assert len(history) >= 3

        # Get second page
        history2 = TaskCacheService.get_history(limit=3, offset=3)
        assert len(history2) >= 0

        # Clean up
        with get_db() as session:
            for task in tasks:
                session.delete(task)
            session.commit()

    def test_get_history_filtering(self):
        """Test getting history with filters"""
        # Create tasks with different modes and backends
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

        # Filter by mode
        command_tasks = TaskCacheService.get_history(mode="command")
        assert all(t.mode == "command" for t in command_tasks)

        # Filter by backend
        gemini_tasks = TaskCacheService.get_history(backend="gemini")
        assert all(t.backend == "gemini" for t in gemini_tasks)

        # Clean up
        with get_db() as session:
            session.delete(task1)
            session.delete(task2)
            session.commit()

    def test_get_statistics(self):
        """Test getting cache statistics"""
        # Create some test tasks
        tasks = []
        tasks.append(TaskCacheService.save_task(
            request="test 1",
            mode="command",
            backend="claude",
            success=True,
            output="output 1"
        ))
        tasks.append(TaskCacheService.save_task(
            request="test 2",
            mode="agent",
            backend="gemini",
            success=True,
            output="output 2"
        ))
        tasks.append(TaskCacheService.save_task(
            request="test 3",
            mode="command",
            backend="claude",
            success=False,
            output="output 3",
            error="error"
        ))

        # Add some hits
        TaskCacheService.query_cache(tasks[0].request_hash, "command", "claude")

        # Get statistics
        stats = TaskCacheService.get_statistics()

        assert "total_tasks" in stats
        assert "cache_hit_rate" in stats
        assert "success_rate" in stats
        assert "backends" in stats
        assert "modes" in stats

        assert stats["total_tasks"] >= 3
        assert isinstance(stats["backends"], dict)
        assert isinstance(stats["modes"], dict)

        # Clean up
        with get_db() as session:
            for task in tasks:
                session.delete(task)
            session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
