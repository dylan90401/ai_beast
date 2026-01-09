def test_check_service_health_open_port(monkeypatch):
    from modules.monitoring import check_service_health

    class FakeSocket:
        def settimeout(self, _):
            return None

        def connect_ex(self, _):
            return 0

        def close(self):
            return None

    monkeypatch.setattr("socket.socket", lambda *a, **k: FakeSocket())
    result = check_service_health("TestSvc", 1234)
    assert result["healthy"] is True


def test_check_service_health_closed_port(monkeypatch):
    from modules.monitoring import check_service_health

    class FakeSocket:
        def settimeout(self, _):
            return None

        def connect_ex(self, _):
            return 1

        def close(self):
            return None

    monkeypatch.setattr("socket.socket", lambda *a, **k: FakeSocket())
    result = check_service_health("TestSvc", 1234)
    assert result["healthy"] is False


def test_collect_metrics_has_timestamp(tmp_path):
    from modules.monitoring import collect_metrics

    metrics = collect_metrics(tmp_path)
    assert "timestamp" in metrics
    assert "disk_usage" in metrics


def test_tools_cli_collect_diagnostics_writes_file(tmp_path, monkeypatch):
    from tools.cli import collect_diagnostics

    fake_metrics = {"timestamp": "now", "disk_usage": {"total_gb": 1}}

    def fake_collect_metrics(_base):
        return fake_metrics

    monkeypatch.setattr("modules.monitoring.collect_metrics", fake_collect_metrics)

    code = collect_diagnostics(tmp_path)
    assert code == 0
    output = tmp_path / ".cache" / "diagnostics.json"
    assert output.exists()
    assert "timestamp" in output.read_text(encoding="utf-8")


def test_tools_cli_verify_security_no_issues(tmp_path):
    from tools.cli import verify_security

    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True)
    cfg = cfg_dir / "ai-beast.env"
    cfg.write_text("PASSWORD=your_password_here\n", encoding="utf-8")
    cfg.chmod(0o600)

    code = verify_security(tmp_path)
    assert code == 0
