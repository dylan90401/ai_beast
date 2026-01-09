"""
Background task queue worker and manager.

Provides a comprehensive task queue system using Redis and RQ for
handling long-running operations asynchronously.
"""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, TypeVar

from modules.logging_config import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Data Classes & Enums
# =============================================================================


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    DEFERRED = "deferred"
    SCHEDULED = "scheduled"
    CANCELED = "canceled"


@dataclass
class JobInfo:
    """Job information."""

    id: str
    status: JobStatus
    func_name: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    timeout: int = 3600
    retries: int = 0
    max_retries: int = 3

    @property
    def duration_seconds(self) -> float | None:
        """Get job duration if completed."""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "func_name": self.func_name,
            "args": list(self.args),
            "kwargs": self.kwargs,
            "result": self.result,
            "error": self.error,
            "enqueued_at": self.enqueued_at.isoformat() if self.enqueued_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "timeout": self.timeout,
            "retries": self.retries,
            "max_retries": self.max_retries,
        }


# =============================================================================
# Task Queue Manager
# =============================================================================


class TaskQueue:
    """
    Task queue manager for background job processing.

    Wraps Redis Queue (RQ) with additional features:
    - Job tracking and status queries
    - Multiple queue support (default, high, low priority)
    - Job scheduling
    - Retry handling
    """

    QUEUE_NAMES = ["high", "default", "low"]

    def __init__(
        self,
        redis_url: str | None = None,
        default_timeout: int = 3600,
        result_ttl: int = 86400,
    ):
        """
        Initialize task queue.

        Args:
            redis_url: Redis connection URL
            default_timeout: Default job timeout in seconds
            result_ttl: Result retention time in seconds
        """
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://127.0.0.1:6379/0"
        )
        self.default_timeout = default_timeout
        self.result_ttl = result_ttl
        self._redis = None
        self._queues: dict[str, Any] = {}

    @property
    def redis(self):
        """Get Redis connection."""
        if self._redis is None:
            from redis import Redis
            self._redis = Redis.from_url(self.redis_url)
        return self._redis

    def get_queue(self, name: str = "default"):
        """Get or create a queue by name."""
        if name not in self._queues:
            from rq import Queue
            self._queues[name] = Queue(name, connection=self.redis)
        return self._queues[name]

    # -------------------------------------------------------------------------
    # Job Submission
    # -------------------------------------------------------------------------

    def enqueue(
        self,
        func: Callable | str,
        *args,
        queue: str = "default",
        timeout: int | None = None,
        result_ttl: int | None = None,
        job_id: str | None = None,
        depends_on: str | list[str] | None = None,
        at_front: bool = False,
        meta: dict | None = None,
        **kwargs,
    ) -> JobInfo:
        """
        Enqueue a task for background execution.

        Args:
            func: Function to execute (callable or dotted path)
            *args: Function arguments
            queue: Queue name (default, high, low)
            timeout: Job timeout in seconds
            result_ttl: Result TTL in seconds
            job_id: Custom job ID
            depends_on: Job ID(s) this job depends on
            at_front: Add to front of queue
            meta: Additional metadata
            **kwargs: Function keyword arguments

        Returns:
            JobInfo with job details
        """
        from rq import Queue

        q = self.get_queue(queue)

        # Resolve function if string
        if isinstance(func, str):
            func = self._resolve_func(func)

        try:
            job = q.enqueue(
                func,
                *args,
                job_timeout=timeout or self.default_timeout,
                result_ttl=result_ttl or self.result_ttl,
                job_id=job_id,
                depends_on=depends_on,
                at_front=at_front,
                meta=meta or {},
                **kwargs,
            )

            logger.info(
                "job_enqueued",
                job_id=job.id,
                func=func.__name__ if callable(func) else str(func),
                queue=queue,
            )

            return JobInfo(
                id=job.id,
                status=JobStatus.QUEUED,
                func_name=job.func_name or str(func),
                args=args,
                kwargs=kwargs,
                enqueued_at=job.enqueued_at,
                timeout=timeout or self.default_timeout,
            )

        except Exception as e:
            logger.error("job_enqueue_failed", error=str(e))
            raise

    def enqueue_at(
        self,
        scheduled_time: datetime,
        func: Callable | str,
        *args,
        queue: str = "default",
        **kwargs,
    ) -> JobInfo:
        """
        Schedule a job for future execution.

        Args:
            scheduled_time: When to execute the job
            func: Function to execute
            *args: Function arguments
            queue: Queue name
            **kwargs: Additional enqueue options

        Returns:
            JobInfo with scheduled job details
        """
        from rq_scheduler import Scheduler

        scheduler = Scheduler(connection=self.redis, queue_name=queue)

        if isinstance(func, str):
            func = self._resolve_func(func)

        job = scheduler.enqueue_at(scheduled_time, func, *args, **kwargs)

        logger.info(
            "job_scheduled",
            job_id=job.id,
            func=func.__name__ if callable(func) else str(func),
            scheduled_for=scheduled_time.isoformat(),
        )

        return JobInfo(
            id=job.id,
            status=JobStatus.SCHEDULED,
            func_name=job.func_name or str(func),
            args=args,
            kwargs=kwargs,
            enqueued_at=datetime.utcnow(),
        )

    def enqueue_in(
        self,
        delay_seconds: int,
        func: Callable | str,
        *args,
        **kwargs,
    ) -> JobInfo:
        """
        Schedule a job after a delay.

        Args:
            delay_seconds: Seconds to wait before execution
            func: Function to execute
            *args: Function arguments
            **kwargs: Additional enqueue options

        Returns:
            JobInfo with scheduled job details
        """
        from datetime import timedelta
        scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        return self.enqueue_at(scheduled_time, func, *args, **kwargs)

    # -------------------------------------------------------------------------
    # Job Management
    # -------------------------------------------------------------------------

    def get_job(self, job_id: str) -> JobInfo | None:
        """
        Get job information.

        Args:
            job_id: Job ID

        Returns:
            JobInfo or None if not found
        """
        from rq.job import Job

        try:
            job = Job.fetch(job_id, connection=self.redis)

            status_map = {
                "queued": JobStatus.QUEUED,
                "started": JobStatus.STARTED,
                "finished": JobStatus.FINISHED,
                "failed": JobStatus.FAILED,
                "deferred": JobStatus.DEFERRED,
                "scheduled": JobStatus.SCHEDULED,
                "canceled": JobStatus.CANCELED,
            }

            return JobInfo(
                id=job.id,
                status=status_map.get(job.get_status(), JobStatus.QUEUED),
                func_name=job.func_name or "",
                args=job.args or (),
                kwargs=job.kwargs or {},
                result=job.result if job.is_finished else None,
                error=str(job.exc_info) if job.is_failed else None,
                enqueued_at=job.enqueued_at,
                started_at=job.started_at,
                ended_at=job.ended_at,
            )

        except Exception:
            return None

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a queued job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if canceled successfully
        """
        from rq.job import Job

        try:
            job = Job.fetch(job_id, connection=self.redis)
            job.cancel()
            logger.info("job_canceled", job_id=job_id)
            return True
        except Exception as e:
            logger.error("job_cancel_failed", job_id=job_id, error=str(e))
            return False

    def requeue_job(self, job_id: str) -> bool:
        """
        Requeue a failed job.

        Args:
            job_id: Job ID to requeue

        Returns:
            True if requeued successfully
        """
        from rq.job import Job

        try:
            job = Job.fetch(job_id, connection=self.redis)
            job.requeue()
            logger.info("job_requeued", job_id=job_id)
            return True
        except Exception as e:
            logger.error("job_requeue_failed", job_id=job_id, error=str(e))
            return False

    def list_jobs(
        self,
        queue: str = "default",
        status: JobStatus | str | None = None,
        limit: int = 50,
    ) -> list[JobInfo]:
        """
        List jobs in a queue.

        Args:
            queue: Queue name
            status: Filter by status
            limit: Maximum jobs to return

        Returns:
            List of JobInfo
        """
        from rq.registry import (
            FinishedJobRegistry,
            FailedJobRegistry,
            StartedJobRegistry,
            DeferredJobRegistry,
        )

        q = self.get_queue(queue)
        jobs: list[JobInfo] = []

        # Convert status
        if isinstance(status, str):
            status = JobStatus(status) if status else None

        # Get jobs from appropriate registry
        registries = []
        if status is None or status == JobStatus.QUEUED:
            for job in q.get_jobs()[:limit]:
                info = self.get_job(job.id)
                if info:
                    jobs.append(info)

        registry_map = {
            JobStatus.STARTED: StartedJobRegistry,
            JobStatus.FINISHED: FinishedJobRegistry,
            JobStatus.FAILED: FailedJobRegistry,
            JobStatus.DEFERRED: DeferredJobRegistry,
        }

        for job_status, registry_class in registry_map.items():
            if status is None or status == job_status:
                registry = registry_class(queue=q)
                for job_id in registry.get_job_ids()[:limit]:
                    info = self.get_job(job_id)
                    if info:
                        jobs.append(info)

        return jobs[:limit]

    # -------------------------------------------------------------------------
    # Queue Management
    # -------------------------------------------------------------------------

    def get_queue_stats(self, queue: str = "default") -> dict[str, Any]:
        """
        Get queue statistics.

        Args:
            queue: Queue name

        Returns:
            Statistics dict
        """
        from rq.registry import (
            FinishedJobRegistry,
            FailedJobRegistry,
            StartedJobRegistry,
        )

        q = self.get_queue(queue)

        return {
            "name": queue,
            "queued": q.count,
            "started": StartedJobRegistry(queue=q).count,
            "finished": FinishedJobRegistry(queue=q).count,
            "failed": FailedJobRegistry(queue=q).count,
        }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all queues."""
        return {name: self.get_queue_stats(name) for name in self.QUEUE_NAMES}

    def clear_queue(self, queue: str = "default") -> int:
        """
        Clear all jobs from a queue.

        Args:
            queue: Queue name

        Returns:
            Number of jobs removed
        """
        q = self.get_queue(queue)
        count = q.count
        q.empty()
        logger.info("queue_cleared", queue=queue, count=count)
        return count

    # -------------------------------------------------------------------------
    # Worker Management
    # -------------------------------------------------------------------------

    def start_worker(
        self,
        queues: list[str] | None = None,
        burst: bool = False,
        with_scheduler: bool = False,
    ):
        """
        Start a worker process.

        Args:
            queues: Queues to process (default: all)
            burst: Exit after all jobs processed
            with_scheduler: Run scheduler alongside worker
        """
        from rq import Worker

        queues = queues or self.QUEUE_NAMES
        queue_objs = [self.get_queue(q) for q in queues]

        worker = Worker(queue_objs, connection=self.redis)

        logger.info(
            "worker_starting",
            queues=queues,
            burst=burst,
        )

        worker.work(burst=burst, with_scheduler=with_scheduler)

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _resolve_func(self, dotted: str) -> Callable:
        """Resolve dotted function path to callable."""
        import importlib

        # Security: Only allow functions from approved modules
        allowed_prefixes = ["modules.queue.tasks", "modules."]

        if not any(dotted.startswith(p) for p in allowed_prefixes):
            raise ValueError(f"Function not allowed: {dotted}")

        module_name, func_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_name)
        func = getattr(module, func_name, None)

        if not callable(func):
            raise ValueError(f"Function not found: {dotted}")

        return func


# =============================================================================
# Global Instance
# =============================================================================

_task_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


# =============================================================================
# Decorator
# =============================================================================


def background_task(
    queue: str = "default",
    timeout: int = 3600,
    retries: int = 0,
):
    """
    Decorator to mark a function as a background task.

    Args:
        queue: Default queue for this task
        timeout: Default timeout in seconds
        retries: Number of retry attempts on failure

    Usage:
        @background_task(queue="high", timeout=7200)
        def my_task(arg1, arg2):
            ...

        # Enqueue:
        my_task.delay(arg1, arg2)
    """
    def decorator(func: F) -> F:
        func._task_queue = queue
        func._task_timeout = timeout
        func._task_retries = retries

        def delay(*args, **kwargs) -> JobInfo:
            tq = get_task_queue()
            return tq.enqueue(
                func,
                *args,
                queue=queue,
                timeout=timeout,
                **kwargs,
            )

        func.delay = delay  # type: ignore
        return func

    return decorator
