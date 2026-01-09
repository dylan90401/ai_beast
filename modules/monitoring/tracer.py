"""
AI Beast Tracing Module

Implements distributed tracing following AI Toolkit best practices.
Integrates with OpenTelemetry collector when enabled.
"""

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from modules.core.logging import get_logger

logger = get_logger(__name__)


class Tracer:
    """Distributed tracer for AI Beast operations."""

    def __init__(
        self,
        service_name: str = "ai_beast",
        otel_enabled: bool = False,
        otel_endpoint: str | None = None,
    ):
        """Initialize tracer."""
        self.service_name = service_name
        self.otel_enabled = otel_enabled or os.environ.get("OTEL_ENABLED") in ("1", "true", "True")
        self.otel_endpoint = otel_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        self._otel_tracer = None

        self.trace_dir = Path("outputs/traces")
        self.trace_dir.mkdir(parents=True, exist_ok=True)

        if self.otel_enabled and self.otel_endpoint:
            self._setup_otel()
        else:
            logger.info("OTEL disabled, using local trace storage")

    def _setup_otel(self):
        """Setup OpenTelemetry exporter (best-effort JSON export)."""
        if not self.otel_endpoint:
            self.otel_enabled = False
            return
        if not self.otel_endpoint.startswith(("http://", "https://")):
            logger.warning("OTEL endpoint must be http(s), disabling OTEL export")
            self.otel_enabled = False
            return
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except Exception as exc:
            logger.warning("OTEL dependencies missing, disabling OTEL export: %s", exc)
            self.otel_enabled = False
            return

        resource = Resource.create({"service.name": self.service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=self.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._otel_tracer = trace.get_tracer(self.service_name)
        logger.info("OTEL exporter configured: %s", self.otel_endpoint)

    @contextmanager
    def trace_operation(
        self, operation_name: str, attributes: dict[str, Any] | None = None
    ):
        """Context manager for tracing operations."""
        trace_id = f"{operation_name}_{int(time.time() * 1000)}"
        start_time = time.time()

        span = {
            "trace_id": trace_id,
            "operation": operation_name,
            "service": self.service_name,
            "start_time": start_time,
            "attributes": attributes or {},
        }

        otel_span = None
        if self._otel_tracer:
            otel_span = self._otel_tracer.start_span(operation_name)
            if attributes:
                for key, value in attributes.items():
                    otel_span.set_attribute(str(key), str(value))

        try:
            logger.debug("Starting trace: %s", trace_id)
            yield span

            span["status"] = "success"
            span["duration_ms"] = (time.time() - start_time) * 1000

        except Exception as e:
            span["status"] = "error"
            span["error"] = str(e)
            span["duration_ms"] = (time.time() - start_time) * 1000
            if otel_span:
                otel_span.record_exception(e)
            raise

        finally:
            if otel_span:
                if span.get("status") == "error":
                    otel_span.set_attribute("error", True)
                otel_span.end()
            self._record_span(span)

    def _record_span(self, span: dict[str, Any]):
        """Record span to storage."""
        trace_file = self.trace_dir / f"{self.service_name}_traces.jsonl"
        with open(trace_file, "a") as f:
            f.write(json.dumps(span) + "\n")


_tracer: Tracer | None = None


def get_tracer(
    service_name: str = "ai_beast",
    otel_enabled: bool = False,
    otel_endpoint: str | None = None,
) -> Tracer:
    """Get or create global tracer instance."""
    global _tracer

    if _tracer is None:
        _tracer = Tracer(
            service_name=service_name,
            otel_enabled=otel_enabled,
            otel_endpoint=otel_endpoint,
        )

    return _tracer
