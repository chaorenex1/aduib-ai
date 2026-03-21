from __future__ import annotations

import datetime
import logging
import threading

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class CronScheduler:
    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._scheduler and self._scheduler.running:
                return
            self._scheduler = BackgroundScheduler(timezone="UTC")
            self._scheduler.start()
        self.reload()

    def stop(self) -> None:
        with self._lock:
            if self._scheduler is None:
                return
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def reload(self) -> None:
        from models import CronJob, get_db

        with get_db() as session:
            cron_ids = [row.id for row in session.query(CronJob.id).filter(CronJob.enabled.is_(True)).all()]
        for cron_id in cron_ids:
            self.register_cron(cron_id)

    def register_cron(self, cron_id: int) -> datetime.datetime | None:
        from service.cron_job_service import CronJobService

        cron_job = CronJobService.get_record(cron_id)
        if cron_job is None or not cron_job.enabled:
            self.remove_cron(cron_id)
            return None

        next_run = CronJobService.compute_next_run(cron_job.schedule, cron_job.timezone)
        scheduler = self._scheduler
        if scheduler is None:
            return next_run

        trigger = CronTrigger.from_crontab(cron_job.schedule, timezone=cron_job.timezone)
        scheduler.add_job(
            self._dispatch_cron,
            trigger=trigger,
            args=[cron_id],
            id=self._job_id(cron_id),
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=60,
        )
        job = scheduler.get_job(self._job_id(cron_id))
        if job and job.next_run_time:
            next_run = self._normalize_datetime(job.next_run_time)
        CronJobService.update_next_run(cron_id, next_run)
        return next_run

    def remove_cron(self, cron_id: int) -> None:
        scheduler = self._scheduler
        if scheduler is None:
            return
        try:
            scheduler.remove_job(self._job_id(cron_id))
        except JobLookupError:
            return

    def _dispatch_cron(self, cron_id: int) -> None:
        from service.cron_job_service import CronJobService
        from service.task_job_service import TaskJobService

        cron_job = CronJobService.get_record(cron_id)
        if cron_job is None or not cron_job.enabled:
            self.remove_cron(cron_id)
            return

        try:
            task = TaskJobService.create_from_cron(cron_job)
            next_run_at = None
            scheduler = self._scheduler
            if scheduler:
                job = scheduler.get_job(self._job_id(cron_id))
                next_run_at = self._normalize_datetime(job.next_run_time) if job else None
            CronJobService.mark_triggered(
                cron_id,
                last_task_id=task["id"],
                last_run_at=datetime.datetime.now(),
                next_run_at=next_run_at,
            )
        except Exception as exc:
            logger.error("Cron job %s dispatch failed: %s", cron_id, exc, exc_info=True)

    @staticmethod
    def _job_id(cron_id: int) -> str:
        return f"cron_job:{cron_id}"

    @staticmethod
    def _normalize_datetime(value: datetime.datetime | None) -> datetime.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(datetime.UTC).replace(tzinfo=None)


cron_scheduler = CronScheduler()
