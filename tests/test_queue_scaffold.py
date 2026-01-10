from modules.queue.rq_queue import (
    _resolve_task,
    cleanup_jobs,
    delete_job,
    enqueue_task,
    list_jobs,
    retry_job,
)


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


def test_cleanup_jobs_invalid_status(monkeypatch):
    class DummyQueue:
        pass

    monkeypatch.setattr("modules.queue.rq_queue.get_queue", lambda *a, **k: DummyQueue())
    result = cleanup_jobs(status="unknown", limit=10)
    assert result["ok"] is False
