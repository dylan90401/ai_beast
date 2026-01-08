# otel_collector

Minimal OpenTelemetry Collector service.

- Service name: `otel-collector`
- Role: receive OTLP (gRPC/HTTP) from services and (later) export to a backend.
- Current version: accepts OTLP and logs spans/metrics to stdout.
