from pathlib import Path

from modules.monitoring.tracer import Tracer


def test_tracer_writes_span(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer(service_name="ai_beast_test", otel_enabled=False)
    with tracer.trace_operation("unit", {"ok": True}):
        pass
    trace_file = Path("outputs/traces/ai_beast_test_traces.jsonl")
    assert trace_file.exists()
    content = trace_file.read_text(encoding="utf-8")
    assert "unit" in content
