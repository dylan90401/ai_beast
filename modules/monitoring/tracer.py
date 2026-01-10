"""
AI Beast Tracing Module

Implements distributed tracing following AI Toolkit best practices.
Integrates with OpenTelemetry collector when enabled.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        self.otel_enabled = otel_enabled
        self.otel_endpoint = otel_endpoint

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
        self._otel_headers = {
            "Content-Type": "application/json",
            "User-Agent": "ai-beast-tracer/1.0",
        }
        logger.info(f"OTEL endpoint configured: {self.otel_endpoint}")

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

        try:
            logger.debug(f"Starting trace: {trace_id}")
            yield span

            span["status"] = "success"
            span["duration_ms"] = (time.time() - start_time) * 1000

        except Exception as e:
            span["status"] = "error"
            span["error"] = str(e)
            span["duration_ms"] = (time.time() - start_time) * 1000
            raise

        finally:
            self._record_span(span)

    def _record_span(self, span: dict[str, Any]):
        """Record span to storage."""
        trace_file = self.trace_dir / f"{self.service_name}_traces.jsonl"
        with open(trace_file, "a") as f:
            f.write(json.dumps(span) + "\n")

        if self.otel_enabled and self.otel_endpoint:
            self._export_to_otel(span)

    def _export_to_otel(self, span: dict[str, Any]):
        """Export span to OTEL collector (best-effort JSON)."""
        payload = {
            "service": self.service_name,
            "span": span,
        }
        data = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.otel_endpoint,
                data=data,
                headers=self._otel_headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status >= 400:
                    logger.warning("OTEL export failed: HTTP %s", resp.status)
        except urllib.error.URLError as exc:
            logger.warning("OTEL export failed: %s", exc)


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
