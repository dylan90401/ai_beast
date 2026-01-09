"""
RQ queue helpers for background tasks.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

from modules.core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_PREFIX = "modules.queue.tasks"


def get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")


def _resolve_task(dotted: str):
    if not dotted or not dotted.startswith(ALLOWED_PREFIX):
        raise ValueError("task must be in modules.queue.tasks")
    module_name, func_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, func_name, None)
    if not callable(fn):
        raise ValueError("task not found")
    return fn


def get_queue(name: str = "default"):
    from redis import Redis
    from rq import Queue

    conn = Redis.from_url(get_redis_url())
    return Queue(name, connection=conn)


def enqueue_task(
    dotted: str,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        fn = _resolve_task(dotted)
        q = get_queue()
        job = q.enqueue(fn, *args, **kwargs)
        return {"ok": True, "job_id": job.id}
    except Exception as exc:
        logger.warning("Queue enqueue failed", exc_info=exc)
        return {"ok": False, "error": str(exc)}


def list_jobs(limit: int = 25, status: str | None = None) -> list[dict[str, Any]]:
    try:
        from rq.registry import FinishedJobRegistry, FailedJobRegistry, StartedJobRegistry
    except Exception:
        return []

    limit = max(1, min(200, int(limit)))
    status_filter = (status or "").strip().lower()
    if status_filter in ("all", "any"):
        status_filter = ""
    q = get_queue()
    items: list[dict[str, Any]] = []
    if status_filter in ("", "queued"):
        for job in q.get_jobs()[:limit]:
            items.append(
                {
                    "id": job.id,
                    "status": job.get_status(),
                    "created_at": job.created_at.isoformat() if job.created_at else "",
                    "func_name": job.func_name,
                    "origin": job.origin,
                    "args": job.args,
                    "kwargs": job.kwargs,
                }
            )
    for registry, registry_status in (
        (StartedJobRegistry(queue=q), "started"),
        (FinishedJobRegistry(queue=q), "finished"),
        (FailedJobRegistry(queue=q), "failed"),
    ):
        if status_filter not in ("", registry_status):
            continue
        for job_id in registry.get_job_ids()[:limit]:
            job = q.fetch_job(job_id)
            if not job:
                continue
            items.append(
                {
                    "id": job.id,
                    "status": registry_status,
                    "created_at": job.created_at.isoformat() if job.created_at else "",
                    "func_name": job.func_name,
                    "origin": job.origin,
                    "args": job.args,
                    "kwargs": job.kwargs,
                }
            )
    seen = set()
    uniq = []
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        uniq.append(item)
    uniq.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    return uniq[:limit]


def retry_job(job_id: str) -> dict[str, Any]:
    if not job_id:
        return {"ok": False, "error": "job_id required"}
    q = get_queue()
    job = q.fetch_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    job.requeue()
    return {"ok": True}


def delete_job(job_id: str) -> dict[str, Any]:
    if not job_id:
        return {"ok": False, "error": "job_id required"}
    q = get_queue()
    job = q.fetch_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    job.delete()
    return {"ok": True}


def cleanup_jobs(status: str, limit: int = 200) -> dict[str, Any]:
    try:
        from rq.registry import FinishedJobRegistry, FailedJobRegistry, StartedJobRegistry
    except Exception:
        return {"ok": False, "error": "rq not available"}
    limit = max(1, min(500, int(limit)))
    q = get_queue()
    if status == "queued":
        jobs = q.get_jobs()[:limit]
        for job in jobs:
            job.delete()
        return {"ok": True, "count": len(jobs)}
    registry_map = {
        "started": StartedJobRegistry(queue=q),
        "finished": FinishedJobRegistry(queue=q),
        "failed": FailedJobRegistry(queue=q),
    }
    registry = registry_map.get(status)
    if not registry:
        return {"ok": False, "error": "invalid status"}
    ids = registry.get_job_ids()[:limit]
    for job_id in ids:
        job = q.fetch_job(job_id)
        if job:
            job.delete()
    return {"ok": True, "count": len(ids)}
