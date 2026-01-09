"""
Task queue module for background job processing.

Provides Redis-backed task queue with RQ for async task execution.
"""

from .rq_queue import enqueue_task, get_queue, get_redis_url, list_jobs
from .worker import (
    TaskQueue,
    JobInfo,
    JobStatus,
    get_task_queue,
    background_task,
)

__all__ = [
    # Legacy API
    "enqueue_task",
    "get_queue",
    "get_redis_url",
    "list_jobs",
    # New API
    "TaskQueue",
    "JobInfo",
    "JobStatus",
    "get_task_queue",
    "background_task",
]

