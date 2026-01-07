# otel_collector (stub)

Minimal OpenTelemetry Collector surface area.

- Service name: `otel-collector`
- Role: receive OTLP (gRPC/HTTP) from services and (later) export to a backend.
- Current version: **minimal collector** that accepts OTLP and logs spans/metrics to stdout.

This is "stub" in the sense that nothing is instrumented yet.
