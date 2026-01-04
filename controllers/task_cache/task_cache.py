import csv
import io
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from controllers.common.base import catch_exceptions, BaseResponse
from controllers.params import CachedResultResponse, TaskDataRequest, TaskHistoryResponse, BatchTaskDataRequest
from service.task_cache_service import TaskCacheService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["task_cache"])


@router.get("/api/cache/query")
@catch_exceptions
async def query_cache(
    request_hash: str = Query(..., description="SHA256 hash of request:mode:backend"),
    mode: str = Query(..., description="Execution mode"),
    backend: str = Query(..., description="Backend type")
):
    """
    Query cache by request hash
    Returns cached result if found, 404 if not found
    Automatically increments hit_count on cache hit
    """
    cached_task = TaskCacheService.query_cache(request_hash, mode, backend)

    if cached_task is None:
        return BaseResponse.error(404, "Cache not found")

    result = CachedResultResponse(
        task_id=cached_task.id,
        output=cached_task.output,
        success=cached_task.success,
        created_at=cached_task.created_at.isoformat(),
        hit_count=cached_task.hit_count
    )

    return BaseResponse.ok(result.model_dump())


@router.post("/api/tasks/save")
@catch_exceptions
async def save_task(task_data: TaskDataRequest):
    """
    Save task execution result
    Creates new task or updates existing one based on request hash
    """
    saved_task = TaskCacheService.save_task(
        request=task_data.request,
        mode=task_data.mode,
        backend=task_data.backend,
        success=task_data.success,
        output=task_data.output,
        error=task_data.error,
        run_id=task_data.run_id,
        duration_seconds=task_data.duration_seconds
    )

    return BaseResponse.ok({
        "task_id": saved_task.id,
        "request_hash": saved_task.request_hash,
        "success": True
    })


@router.get("/api/tasks/history")
@catch_exceptions
async def get_task_history(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    mode: Optional[str] = Query(None, description="Filter by mode"),
    backend: Optional[str] = Query(None, description="Filter by backend")
):
    """
    Get task history with pagination and filtering
    """
    tasks = TaskCacheService.get_history(
        limit=limit,
        offset=offset,
        mode=mode,
        backend=backend
    )

    history = [
        TaskHistoryResponse(
            id=task.id,
            request=task.request,
            request_hash=task.request_hash,
            mode=task.mode,
            backend=task.backend,
            success=task.success,
            output=task.output,
            error=task.error,
            run_id=task.run_id,
            duration_seconds=task.duration_seconds,
            hit_count=task.hit_count,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat()
        ).model_dump()
        for task in tasks
    ]

    return BaseResponse.ok({
        "tasks": history,
        "total": len(history),
        "limit": limit,
        "offset": offset
    })


@router.get("/api/stats")
@catch_exceptions
async def get_stats():
    """
    Get cache and task statistics
    Returns:
        - total_tasks: Total number of tasks
        - cache_hit_rate: Cache hit rate percentage
        - success_rate: Task success rate percentage
        - backends: Distribution by backend
        - modes: Distribution by mode
    """
    stats = TaskCacheService.get_statistics()
    return BaseResponse.ok(stats)


@router.post("/api/tasks/batch")
@catch_exceptions
async def save_tasks_batch(batch_request: BatchTaskDataRequest):
    """
    Batch save multiple tasks
    Maximum 100 tasks per batch
    """
    tasks_data = [task.model_dump() for task in batch_request.tasks]
    result = TaskCacheService.save_tasks_batch(tasks_data)
    return BaseResponse.ok(result)


@router.delete("/api/tasks/{task_id}")
@catch_exceptions
async def delete_task(task_id: int):
    """
    Delete a task by ID
    """
    success = TaskCacheService.delete_task(task_id)
    if not success:
        return BaseResponse.error(404, f"Task {task_id} not found")
    return BaseResponse.ok({"deleted": True, "task_id": task_id})


@router.delete("/api/tasks/cleanup")
@catch_exceptions
async def cleanup_old_tasks(
    days: int = Query(30, ge=1, le=365, description="Delete tasks older than this many days")
):
    """
    Clean up old tasks
    Default: 30 days
    """
    deleted_count = TaskCacheService.clear_old_tasks(days)
    return BaseResponse.ok({
        "deleted_count": deleted_count,
        "days": days
    })


@router.get("/api/tasks/export")
@catch_exceptions
async def export_tasks(
    format: str = Query("json", description="Export format: json or csv"),
    mode: Optional[str] = Query(None, description="Filter by mode"),
    backend: Optional[str] = Query(None, description="Filter by backend"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of tasks")
):
    """
    Export tasks to JSON or CSV format
    """
    if format not in ['json', 'csv']:
        return BaseResponse.error(400, "Format must be 'json' or 'csv'")

    tasks_data = TaskCacheService.export_tasks(
        format=format,
        mode=mode,
        backend=backend,
        limit=limit
    )

    if format == 'json':
        return BaseResponse.ok({
            "format": "json",
            "count": len(tasks_data),
            "tasks": tasks_data
        })

    elif format == 'csv':
        # Generate CSV
        output = io.StringIO()
        if tasks_data:
            writer = csv.DictWriter(output, fieldnames=tasks_data[0].keys())
            writer.writeheader()
            writer.writerows(tasks_data)

        csv_content = output.getvalue()

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=tasks_export.csv"
            }
        )


@router.get("/api/tasks/cleanup/status")
@catch_exceptions
async def get_cleanup_status():
    """
    Get automatic cleanup scheduler status (P2)
    """
    from runtime.tasks.task_cache_cleanup import get_cleanup_status
    status = get_cleanup_status()
    return BaseResponse.ok(status)


@router.post("/api/tasks/cleanup/run")
@catch_exceptions
async def trigger_cleanup():
    """
    Manually trigger cleanup task (P2)
    """
    from runtime.tasks.task_cache_cleanup import run_scheduled_cleanup

    logger.info("Manual cleanup triggered")
    start_time = time.time()

    result = await run_scheduled_cleanup()

    duration = time.time() - start_time
    result["duration_seconds"] = round(duration, 2)

    logger.info(f"Manual cleanup completed: {result}")

    return BaseResponse.ok(result)


@router.get("/api/tasks/metrics")
@catch_exceptions
async def get_performance_metrics():
    """
    Get performance metrics and system status (P2)
    """
    from models import get_db, TaskCache
    from datetime import datetime, timedelta

    with get_db() as session:
        # Recent tasks (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        recent_count = session.query(func.count(TaskCache.id)).filter(
            TaskCache.created_at >= yesterday
        ).scalar() or 0

        # Recent hits (tasks with hit_count > 0 in last 24 hours)
        recent_hits = session.query(func.count(TaskCache.id)).filter(
            TaskCache.created_at >= yesterday,
            TaskCache.hit_count > 0
        ).scalar() or 0

        # Average duration
        avg_duration = session.query(func.avg(TaskCache.duration_seconds)).filter(
            TaskCache.duration_seconds.isnot(None)
        ).scalar() or 0

    metrics = {
        "recent_tasks_24h": recent_count,
        "recent_cache_hits_24h": recent_hits,
        "avg_task_duration_seconds": round(float(avg_duration), 2) if avg_duration else 0,
        "cache_enabled": True,
        "batch_optimization_enabled": True,
        "auto_cleanup_enabled": True,
        "timestamp": datetime.now().isoformat()
    }

    return BaseResponse.ok(metrics)
