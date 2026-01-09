from modules.monitoring.prometheus import build_prometheus_metrics


def test_prometheus_metrics_includes_db():
    metrics = {
        "disk_usage": {"total_gb": 1, "used_gb": 0.5, "free_gb": 0.5},
        "memory": {"total_gb": 2, "used_gb": 1},
        "metadata_db": {"ok": True, "backend": "postgres"},
    }
    text = build_prometheus_metrics(metrics)
    assert "ai_beast_metadata_db_up" in text
    assert "backend=\"postgres\"" in text
