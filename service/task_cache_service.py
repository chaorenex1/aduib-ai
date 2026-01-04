import hashlib
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import func, case

from models import get_db, TaskCache

logger = logging.getLogger(__name__)


class TaskCacheService:
    """Task cache service for Orchestrator integration"""

    @staticmethod
    def compute_request_hash(request: str, mode: str, backend: str) -> str:
        """
        Compute SHA256 hash for cache key

        Args:
            request: Original request content
            mode: Execution mode (command/agent/prompt/skill/backend)
            backend: Backend type (claude/gemini/codex)

        Returns:
            SHA256 hash string
        """
        content = f"{request}:{mode}:{backend}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @classmethod
    def query_cache(cls, request_hash: str, mode: str, backend: str) -> Optional[TaskCache]:
        """
        Query cache by request hash, mode, and backend
        If found, increment hit_count automatically

        Args:
            request_hash: SHA256 hash of request:mode:backend
            mode: Execution mode
            backend: Backend type

        Returns:
            TaskCache object if found, None otherwise
        """
        with get_db() as session:
            task = session.query(TaskCache).filter_by(
                request_hash=request_hash,
                mode=mode,
                backend=backend
            ).first()

            if task:
                # Increment hit count
                task.hit_count += 1
                session.commit()
                session.refresh(task)

            return task

    @classmethod
    def save_task(
        cls,
        request: str,
        mode: str,
        backend: str,
        success: bool,
        output: str,
        error: Optional[str] = None,
        run_id: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> TaskCache:
        """
        Save task execution result to cache
        If task with same hash exists, update it

        Args:
            request: Original request content
            mode: Execution mode
            backend: Backend type
            success: Whether execution succeeded
            output: Task output content
            error: Error message if failed
            run_id: Memex-CLI run ID
            duration_seconds: Execution duration in seconds

        Returns:
            Created or updated TaskCache object
        """
        request_hash = cls.compute_request_hash(request, mode, backend)

        with get_db() as session:
            # Check if task already exists
            existing_task = session.query(TaskCache).filter_by(
                request_hash=request_hash,
                mode=mode,
                backend=backend
            ).first()

            if existing_task:
                # Update existing task
                existing_task.request = request
                existing_task.success = success
                existing_task.output = output
                existing_task.error = error
                existing_task.run_id = run_id
                existing_task.duration_seconds = duration_seconds
                session.commit()
                session.refresh(existing_task)
                return existing_task
            else:
                # Create new task
                new_task = TaskCache(
                    request=request,
                    request_hash=request_hash,
                    mode=mode,
                    backend=backend,
                    success=success,
                    output=output,
                    error=error,
                    run_id=run_id,
                    duration_seconds=duration_seconds,
                    hit_count=0
                )
                session.add(new_task)
                session.commit()
                session.refresh(new_task)
                return new_task

    @classmethod
    def get_history(
        cls,
        limit: int = 50,
        offset: int = 0,
        mode: Optional[str] = None,
        backend: Optional[str] = None
    ) -> List[TaskCache]:
        """
        Get task history with pagination and filtering

        Args:
            limit: Maximum number of results (default 50)
            offset: Offset for pagination (default 0)
            mode: Filter by mode (optional)
            backend: Filter by backend (optional)

        Returns:
            List of TaskCache objects
        """
        with get_db() as session:
            query = session.query(TaskCache)

            # Apply filters
            if mode:
                query = query.filter_by(mode=mode)
            if backend:
                query = query.filter_by(backend=backend)

            # Order by created_at descending (newest first)
            query = query.order_by(TaskCache.created_at.desc())

            # Apply pagination
            query = query.limit(limit).offset(offset)

            return query.all()

    @classmethod
    def get_statistics(cls, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get cache statistics (with Redis caching support)

        Args:
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            Dictionary containing:
                - total_tasks: Total number of tasks
                - cache_hit_rate: Cache hit rate percentage
                - success_rate: Task success rate percentage
                - backends: Distribution of tasks by backend
                - modes: Distribution of tasks by mode
        """
        # Try to get from Redis cache first
        if use_cache:
            try:
                from component.cache.redis_cache import redis_client
                cache_key = "task_cache:statistics"
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.debug("Statistics cache hit")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}, falling back to database")

        # Calculate statistics from database
        with get_db() as session:
            # Total tasks
            total_tasks = session.query(func.count(TaskCache.id)).scalar() or 0

            if total_tasks == 0:
                return {
                    "total_tasks": 0,
                    "cache_hit_rate": 0.0,
                    "success_rate": 0.0,
                    "backends": {},
                    "modes": {}
                }

            # Cache hit rate (tasks with hit_count > 0)
            tasks_with_hits = session.query(func.count(TaskCache.id)).filter(
                TaskCache.hit_count > 0
            ).scalar() or 0
            cache_hit_rate = (tasks_with_hits / total_tasks * 100) if total_tasks > 0 else 0.0

            # Success rate
            successful_tasks = session.query(func.count(TaskCache.id)).filter(
                TaskCache.success == True
            ).scalar() or 0
            success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

            # Backend distribution
            backend_stats = session.query(
                TaskCache.backend,
                func.count(TaskCache.id).label('count')
            ).group_by(TaskCache.backend).all()
            backends = {stat.backend: stat.count for stat in backend_stats}

            # Mode distribution
            mode_stats = session.query(
                TaskCache.mode,
                func.count(TaskCache.id).label('count')
            ).group_by(TaskCache.mode).all()
            modes = {stat.mode: stat.count for stat in mode_stats}

            stats = {
                "total_tasks": total_tasks,
                "cache_hit_rate": round(cache_hit_rate, 2),
                "success_rate": round(success_rate, 2),
                "backends": backends,
                "modes": modes
            }

            # Cache the statistics in Redis
            if use_cache:
                try:
                    from component.cache.redis_cache import redis_client
                    cache_key = "task_cache:statistics"
                    # Cache for 5 minutes (300 seconds)
                    redis_client.setex(
                        cache_key,
                        300,
                        json.dumps(stats)
                    )
                    logger.debug("Statistics cached in Redis")
                except Exception as e:
                    logger.warning(f"Redis cache write failed: {e}")

            return stats

    @classmethod
    def save_tasks_batch(cls, tasks_data: List[Dict[str, Any]], use_transaction: bool = True) -> Dict[str, Any]:
        """
        Batch save multiple tasks (P2 optimized with single transaction)

        Args:
            tasks_data: List of task dictionaries containing:
                - request, mode, backend, success, output, error, run_id, duration_seconds
            use_transaction: Use single transaction for better performance (default: True)

        Returns:
            Dictionary with:
                - saved_count: Number of tasks saved
                - updated_count: Number of tasks updated
                - failed_count: Number of failed saves
                - task_ids: List of saved task IDs
        """
        if not use_transaction:
            # Old method - individual transactions
            return cls._save_tasks_batch_old(tasks_data)

        # P2 Optimized - Single transaction batch insert/update
        saved_count = 0
        updated_count = 0
        failed_count = 0
        task_ids = []

        with get_db() as session:
            try:
                for task_data in tasks_data:
                    try:
                        request_hash = cls.compute_request_hash(
                            task_data.get('request'),
                            task_data.get('mode'),
                            task_data.get('backend')
                        )

                        # Check if task exists
                        existing_task = session.query(TaskCache).filter_by(
                            request_hash=request_hash,
                            mode=task_data.get('mode'),
                            backend=task_data.get('backend')
                        ).first()

                        if existing_task:
                            # Update existing task
                            existing_task.request = task_data.get('request')
                            existing_task.success = task_data.get('success', True)
                            existing_task.output = task_data.get('output', '')
                            existing_task.error = task_data.get('error')
                            existing_task.run_id = task_data.get('run_id')
                            existing_task.duration_seconds = task_data.get('duration_seconds')
                            existing_task.updated_at = datetime.now()
                            task_ids.append(existing_task.id)
                            updated_count += 1
                        else:
                            # Create new task
                            new_task = TaskCache(
                                request=task_data.get('request'),
                                request_hash=request_hash,
                                mode=task_data.get('mode'),
                                backend=task_data.get('backend'),
                                success=task_data.get('success', True),
                                output=task_data.get('output', ''),
                                error=task_data.get('error'),
                                run_id=task_data.get('run_id'),
                                duration_seconds=task_data.get('duration_seconds'),
                                hit_count=0,
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            session.add(new_task)
                            session.flush()  # Get ID without committing
                            task_ids.append(new_task.id)
                            saved_count += 1

                    except Exception as e:
                        logger.error(f"Error processing task in batch: {e}")
                        failed_count += 1

                # Commit all changes in single transaction
                session.commit()
                logger.info(f"Batch saved {saved_count} new, updated {updated_count}, failed {failed_count}")

            except Exception as e:
                session.rollback()
                logger.error(f"Batch transaction failed: {e}")
                raise

        return {
            "saved_count": saved_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "total_processed": len(tasks_data),
            "task_ids": task_ids
        }

    @classmethod
    def _save_tasks_batch_old(cls, tasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Old batch save method (kept for compatibility)"""
        saved_count = 0
        updated_count = 0
        failed_count = 0
        task_ids = []

        for task_data in tasks_data:
            try:
                task = cls.save_task(
                    request=task_data.get('request'),
                    mode=task_data.get('mode'),
                    backend=task_data.get('backend'),
                    success=task_data.get('success', True),
                    output=task_data.get('output', ''),
                    error=task_data.get('error'),
                    run_id=task_data.get('run_id'),
                    duration_seconds=task_data.get('duration_seconds')
                )

                # Check if it was an update or new save
                request_hash = cls.compute_request_hash(
                    task_data.get('request'),
                    task_data.get('mode'),
                    task_data.get('backend')
                )

                with get_db() as session:
                    existing_count = session.query(func.count(TaskCache.id)).filter_by(
                        request_hash=request_hash
                    ).scalar()

                    if existing_count > 1:
                        updated_count += 1
                    else:
                        saved_count += 1

                task_ids.append(task.id)

            except Exception as e:
                logger.error(f"Error in old batch save: {e}")
                failed_count += 1

        return {
            "saved_count": saved_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "total_processed": len(tasks_data),
            "task_ids": task_ids
        }

    @classmethod
    def delete_task(cls, task_id: int) -> bool:
        """
        Delete a task by ID

        Args:
            task_id: Task ID to delete

        Returns:
            True if deleted, False if not found
        """
        with get_db() as session:
            task = session.query(TaskCache).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()
                return True
            return False

    @classmethod
    def clear_old_tasks(cls, days: int = 30) -> int:
        """
        Clear tasks older than specified days

        Args:
            days: Number of days (tasks older than this will be deleted)

        Returns:
            Number of tasks deleted
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        with get_db() as session:
            old_tasks = session.query(TaskCache).filter(
                TaskCache.created_at < cutoff_date
            ).all()

            count = len(old_tasks)

            for task in old_tasks:
                session.delete(task)

            session.commit()
            return count

    @classmethod
    def export_tasks(
        cls,
        format: str = 'json',
        mode: Optional[str] = None,
        backend: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Export tasks in specified format

        Args:
            format: Export format ('json' or 'csv')
            mode: Filter by mode
            backend: Filter by backend
            limit: Maximum number of tasks to export

        Returns:
            List of task dictionaries
        """
        tasks = cls.get_history(limit=limit, mode=mode, backend=backend)

        return [
            {
                "id": task.id,
                "request": task.request,
                "request_hash": task.request_hash,
                "mode": task.mode,
                "backend": task.backend,
                "success": task.success,
                "output": task.output,
                "error": task.error,
                "run_id": task.run_id,
                "duration_seconds": task.duration_seconds,
                "hit_count": task.hit_count,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }
            for task in tasks
        ]
