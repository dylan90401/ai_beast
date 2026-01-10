from pathlib import Path

from modules.monitoring import check_service_health, collect_metrics


def test_check_service_health_returns_fields():
    result = check_service_health("test", 9)
    assert "healthy" in result
    assert "message" in result


def test_collect_metrics(tmp_path: Path):
    metrics = collect_metrics(tmp_path)
    assert "disk_usage" in metrics
