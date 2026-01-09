"""
Prometheus metrics exporter for AI Beast.

Provides comprehensive metrics collection and HTTP server for Prometheus scraping.
Tracks model downloads, Ollama requests, RAG operations, and system health.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from functools import wraps
from threading import Lock
from typing import Any, Callable, TypeVar

from modules.logging_config import get_logger

logger = get_logger(__name__)

# Type variable for decorators
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Metric Classes
# =============================================================================


class Counter:
    """Simple counter metric."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = Lock()

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment counter."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def labels(self, **labels) -> "LabeledMetric":
        """Get labeled metric instance."""
        return LabeledMetric(self, labels)

    def get_metrics(self) -> list[tuple[dict, float]]:
        """Get all metric values."""
        with self._lock:
            return [
                (dict(zip(self.label_names, key)), value)
                for key, value in self._values.items()
            ]


class Gauge:
    """Simple gauge metric."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = Lock()

    def set(self, value: float, **labels) -> None:
        """Set gauge value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment gauge."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def dec(self, value: float = 1.0, **labels) -> None:
        """Decrement gauge."""
        self.inc(-value, **labels)

    def labels(self, **labels) -> "LabeledMetric":
        """Get labeled metric instance."""
        return LabeledMetric(self, labels)

    def get_metrics(self) -> list[tuple[dict, float]]:
        """Get all metric values."""
        with self._lock:
            return [
                (dict(zip(self.label_names, key)), value)
                for key, value in self._values.items()
            ]


class Histogram:
    """Simple histogram metric."""

    # Default buckets (latency-oriented)
    DEFAULT_BUCKETS = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0,
        2.5, 5.0, 10.0, 30.0, 60.0, float("inf"),
    )

    def __init__(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: dict[tuple, dict[float, int]] = {}
        self._sums: dict[tuple, float] = {}
        self._totals: dict[tuple, int] = {}
        self._lock = Lock()

    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            if key not in self._counts:
                self._counts[key] = {b: 0 for b in self.buckets}
                self._sums[key] = 0.0
                self._totals[key] = 0

            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

            self._sums[key] += value
            self._totals[key] += 1

    def labels(self, **labels) -> "LabeledMetric":
        """Get labeled metric instance."""
        return LabeledMetric(self, labels)

    @contextmanager
    def time(self, **labels):
        """Context manager for timing operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(time.perf_counter() - start, **labels)

    def get_metrics(self) -> list[tuple[dict, dict]]:
        """Get all metric values with buckets."""
        with self._lock:
            results = []
            for key, buckets in self._counts.items():
                labels = dict(zip(self.label_names, key))
                results.append((
                    labels,
                    {
                        "buckets": buckets,
                        "sum": self._sums.get(key, 0.0),
                        "count": self._totals.get(key, 0),
                    }
                ))
            return results


class LabeledMetric:
    """Helper class for labeled metrics."""

    def __init__(self, metric: Counter | Gauge | Histogram, labels: dict):
        self._metric = metric
        self._labels = labels

    def inc(self, value: float = 1.0) -> None:
        """Increment."""
        self._metric.inc(value, **self._labels)

    def dec(self, value: float = 1.0) -> None:
        """Decrement (for Gauge)."""
        if hasattr(self._metric, "dec"):
            self._metric.dec(value, **self._labels)

    def set(self, value: float) -> None:
        """Set value (for Gauge)."""
        if hasattr(self._metric, "set"):
            self._metric.set(value, **self._labels)

    def observe(self, value: float) -> None:
        """Observe value (for Histogram)."""
        if hasattr(self._metric, "observe"):
            self._metric.observe(value, **self._labels)

    @contextmanager
    def time(self):
        """Context manager for timing."""
        if hasattr(self._metric, "time"):
            with self._metric.time(**self._labels):
                yield
        else:
            yield


# =============================================================================
# AI Beast Metrics Registry
# =============================================================================


class MetricsRegistry:
    """Central registry for all AI Beast metrics."""

    def __init__(self):
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}

        # Model metrics
        self.model_downloads = Counter(
            "ai_beast_model_downloads_total",
            "Total number of model downloads",
            ["model_name", "location"],
        )
        self._metrics["model_downloads"] = self.model_downloads

        self.model_download_bytes = Histogram(
            "ai_beast_model_download_bytes",
            "Size of downloaded models in bytes",
            ["model_name"],
            buckets=(1e6, 1e7, 1e8, 5e8, 1e9, 2e9, 5e9, 1e10, float("inf")),
        )
        self._metrics["model_download_bytes"] = self.model_download_bytes

        self.model_download_duration = Histogram(
            "ai_beast_model_download_duration_seconds",
            "Duration of model downloads",
            ["model_name"],
        )
        self._metrics["model_download_duration"] = self.model_download_duration

        self.active_models = Gauge(
            "ai_beast_active_models",
            "Number of active models",
            ["location", "type"],
        )
        self._metrics["active_models"] = self.active_models

        # Ollama metrics
        self.ollama_requests = Counter(
            "ai_beast_ollama_requests_total",
            "Total Ollama API requests",
            ["endpoint", "status"],
        )
        self._metrics["ollama_requests"] = self.ollama_requests

        self.ollama_request_duration = Histogram(
            "ai_beast_ollama_request_duration_seconds",
            "Ollama request duration",
            ["endpoint"],
        )
        self._metrics["ollama_request_duration"] = self.ollama_request_duration

        self.ollama_tokens_generated = Counter(
            "ai_beast_ollama_tokens_total",
            "Total tokens generated by Ollama",
            ["model"],
        )
        self._metrics["ollama_tokens"] = self.ollama_tokens_generated

        # RAG metrics
        self.rag_ingestions = Counter(
            "ai_beast_rag_ingestions_total",
            "Total RAG document ingestions",
            ["collection", "status"],
        )
        self._metrics["rag_ingestions"] = self.rag_ingestions

        self.rag_chunks = Counter(
            "ai_beast_rag_chunks_total",
            "Total RAG chunks created",
            ["collection"],
        )
        self._metrics["rag_chunks"] = self.rag_chunks

        self.rag_queries = Counter(
            "ai_beast_rag_queries_total",
            "Total RAG queries",
            ["collection", "status"],
        )
        self._metrics["rag_queries"] = self.rag_queries

        self.rag_query_duration = Histogram(
            "ai_beast_rag_query_duration_seconds",
            "RAG query duration",
            ["collection"],
        )
        self._metrics["rag_query_duration"] = self.rag_query_duration

        # Agent metrics
        self.agent_tasks = Counter(
            "ai_beast_agent_tasks_total",
            "Total agent tasks executed",
            ["status"],
        )
        self._metrics["agent_tasks"] = self.agent_tasks

        self.agent_task_duration = Histogram(
            "ai_beast_agent_task_duration_seconds",
            "Agent task duration",
            [],
        )
        self._metrics["agent_task_duration"] = self.agent_task_duration

        # System metrics
        self.disk_usage = Gauge(
            "ai_beast_disk_usage_bytes",
            "Disk usage in bytes",
            ["path", "type"],
        )
        self._metrics["disk_usage"] = self.disk_usage

        self.service_health = Gauge(
            "ai_beast_service_health",
            "Service health status (1=healthy, 0=unhealthy)",
            ["service"],
        )
        self._metrics["service_health"] = self.service_health

    def format_prometheus(self) -> str:
        """Format all metrics in Prometheus text format."""
        lines: list[str] = []

        for metric in self._metrics.values():
            # Add help and type
            lines.append(f"# HELP {metric.name} {metric.description}")

            if isinstance(metric, Counter):
                lines.append(f"# TYPE {metric.name} counter")
                for labels, value in metric.get_metrics():
                    label_str = self._format_labels(labels)
                    lines.append(f"{metric.name}{label_str} {value}")

            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {metric.name} gauge")
                for labels, value in metric.get_metrics():
                    label_str = self._format_labels(labels)
                    lines.append(f"{metric.name}{label_str} {value}")

            elif isinstance(metric, Histogram):
                lines.append(f"# TYPE {metric.name} histogram")
                for labels, data in metric.get_metrics():
                    cumulative = 0
                    for bucket, count in sorted(data["buckets"].items()):
                        cumulative += count
                        bucket_labels = {**labels, "le": str(bucket) if bucket != float("inf") else "+Inf"}
                        label_str = self._format_labels(bucket_labels)
                        lines.append(f"{metric.name}_bucket{label_str} {cumulative}")

                    label_str = self._format_labels(labels)
                    lines.append(f"{metric.name}_sum{label_str} {data['sum']}")
                    lines.append(f"{metric.name}_count{label_str} {data['count']}")

            lines.append("")  # Empty line between metrics

        return "\n".join(lines)

    @staticmethod
    def _format_labels(labels: dict) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in labels.items() if v]
        return "{" + ",".join(parts) + "}" if parts else ""


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: MetricsRegistry | None = None
_registry_lock = Lock()


def get_registry() -> MetricsRegistry:
    """Get or create the global metrics registry."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = MetricsRegistry()
    return _registry


# =============================================================================
# Decorator Helpers
# =============================================================================


def track_duration(histogram_name: str, **static_labels):
    """Decorator to track function duration."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            registry = get_registry()
            metric = getattr(registry, histogram_name, None)
            if metric:
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    metric.observe(time.perf_counter() - start, **static_labels)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            registry = get_registry()
            metric = getattr(registry, histogram_name, None)
            if metric:
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    metric.observe(time.perf_counter() - start, **static_labels)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def track_counter(counter_name: str, **static_labels):
    """Decorator to increment counter on function call."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            registry = get_registry()
            metric = getattr(registry, counter_name, None)
            try:
                result = await func(*args, **kwargs)
                if metric:
                    metric.inc(**{**static_labels, "status": "success"})
                return result
            except Exception:
                if metric:
                    metric.inc(**{**static_labels, "status": "error"})
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            registry = get_registry()
            metric = getattr(registry, counter_name, None)
            try:
                result = func(*args, **kwargs)
                if metric:
                    metric.inc(**{**static_labels, "status": "success"})
                return result
            except Exception:
                if metric:
                    metric.inc(**{**static_labels, "status": "error"})
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# HTTP Server
# =============================================================================


class MetricsServer:
    """Simple HTTP server for Prometheus metrics endpoint."""

    def __init__(self, port: int = 9091, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self._server = None

    async def start(self):
        """Start the metrics server."""
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/health", self._handle_health)

        runner = web.AppRunner(app)
        await runner.setup()

        self._server = web.TCPSite(runner, self.host, self.port)
        await self._server.start()

        logger.info("metrics_server_started", host=self.host, port=self.port)

    async def _handle_metrics(self, request):
        """Handle /metrics endpoint."""
        from aiohttp import web

        registry = get_registry()
        content = registry.format_prometheus()
        return web.Response(
            text=content,
            content_type="text/plain; version=0.0.4",
        )

    async def _handle_health(self, request):
        """Handle /health endpoint."""
        from aiohttp import web
        return web.Response(text="OK")


# =============================================================================
# Convenience Functions
# =============================================================================


def record_model_download(
    model_name: str,
    location: str,
    size_bytes: int,
    duration_seconds: float,
) -> None:
    """Record a model download."""
    registry = get_registry()
    registry.model_downloads.inc(model_name=model_name, location=location)
    registry.model_download_bytes.observe(size_bytes, model_name=model_name)
    registry.model_download_duration.observe(duration_seconds, model_name=model_name)


def record_ollama_request(
    endpoint: str,
    status: str,
    duration_seconds: float,
    tokens: int = 0,
    model: str = "",
) -> None:
    """Record an Ollama request."""
    registry = get_registry()
    registry.ollama_requests.inc(endpoint=endpoint, status=status)
    registry.ollama_request_duration.observe(duration_seconds, endpoint=endpoint)
    if tokens > 0 and model:
        registry.ollama_tokens_generated.inc(tokens, model=model)


def record_rag_ingestion(
    collection: str,
    status: str,
    chunks: int = 0,
) -> None:
    """Record a RAG ingestion."""
    registry = get_registry()
    registry.rag_ingestions.inc(collection=collection, status=status)
    if chunks > 0:
        registry.rag_chunks.inc(chunks, collection=collection)


def update_service_health(service: str, healthy: bool) -> None:
    """Update service health status."""
    registry = get_registry()
    registry.service_health.set(1.0 if healthy else 0.0, service=service)
