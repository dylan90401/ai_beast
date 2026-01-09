import types

from modules.queue.rq_queue import _resolve_task, cleanup_jobs, delete_job, enqueue_task, list_jobs, retry_job


def test_resolve_task_rejects_invalid():
    try:
        _resolve_task("os.system")
    except ValueError as exc:
        assert "modules.queue.tasks" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_enqueue_task_handles_missing_redis(monkeypatch):
    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no redis")))
    result = enqueue_task("modules.queue.tasks.heartbeat", "hi")
    assert not result["ok"]


def test_list_jobs_handles_missing_redis(monkeypatch):
    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no redis")))
    assert list_jobs() == []


def test_retry_delete_missing_job(monkeypatch):
    class DummyQueue:
        def fetch_job(self, _):
            return None

    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: DummyQueue())
    assert retry_job("abc")["ok"] is False
    assert delete_job("abc")["ok"] is False


def test_list_jobs_filters_status(monkeypatch):
    class DummyJob:
        def __init__(self, job_id, status):
            self.id = job_id
            self._status = status
            self.created_at = None
            self.func_name = "modules.queue.tasks.heartbeat"
            self.origin = "default"
            self.args = ["hi"]
            self.kwargs = {}

        def get_status(self):
            return self._status

    class DummyQueue:
        def __init__(self):
            self.queued = [DummyJob("job-q", "queued")]
            self.finished = DummyJob("job-f", "finished")

        def get_jobs(self):
            return list(self.queued)

        def fetch_job(self, job_id):
            return self.finished if job_id == "job-f" else None

    class DummyRegistry:
        def __init__(self, queue=None):
            self.queue = queue

        def get_job_ids(self):
            return ["job-f"]

    registry = types.SimpleNamespace(
        FinishedJobRegistry=DummyRegistry,
        FailedJobRegistry=DummyRegistry,
        StartedJobRegistry=DummyRegistry,
    )
    monkeypatch.setitem(__import__("sys").modules, "rq.registry", registry)
    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: DummyQueue())

    queued_only = list_jobs(limit=10, status="queued")
    assert len(queued_only) == 1
    assert queued_only[0]["id"] == "job-q"

    finished_only = list_jobs(limit=10, status="finished")
    assert len(finished_only) == 1
    assert finished_only[0]["id"] == "job-f"


def test_cleanup_jobs(monkeypatch):
    class DummyJob:
        def __init__(self, job_id):
            self.id = job_id
            self.deleted = False

        def delete(self):
            self.deleted = True

    class DummyQueue:
        def __init__(self):
            self.queued = [DummyJob("job-q1"), DummyJob("job-q2")]
            self.finished = {job.id: job for job in [DummyJob("job-f1")]}

        def get_jobs(self):
            return list(self.queued)

        def fetch_job(self, job_id):
            return self.finished.get(job_id)

    class DummyRegistry:
        def __init__(self, queue=None):
            self.queue = queue

        def get_job_ids(self):
            return list(self.queue.finished.keys())

    registry = types.SimpleNamespace(
        FinishedJobRegistry=DummyRegistry,
        FailedJobRegistry=DummyRegistry,
        StartedJobRegistry=DummyRegistry,
    )
    monkeypatch.setitem(__import__("sys").modules, "rq.registry", registry)
    dummy_queue = DummyQueue()
    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: dummy_queue)

    queued = cleanup_jobs(status="queued", limit=10)
    assert queued["ok"] is True
    assert queued["count"] == 2

    finished = cleanup_jobs(status="finished", limit=10)
    assert finished["ok"] is True
    assert finished["count"] == 1
