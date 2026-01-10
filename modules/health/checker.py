"""
Health check system for all AI Beast services.

Provides detailed health status for monitoring and orchestration,
with support for multiple service types and aggregated reporting.

Features:
- HTTP endpoint health checks
- Service-specific health checkers (Ollama, Qdrant, Redis)
- System resource checks (disk space, memory)
- Aggregated health status
- Configurable thresholds
- Async execution for parallel checks

Example:
    from modules.health.checker import SystemHealthChecker, OllamaHealthChecker

    # Create system checker
    checker = SystemHealthChecker()
    checker.add_checker(OllamaHealthChecker())
    checker.add_checker(QdrantHealthChecker())

    # Run all checks
    health = await checker.check_all()
    print(f"Overall status: {health['status']}")

    # Check individual service
    ollama_check = await OllamaHealthChecker().check()
    print(f"Ollama: {ollama_check.status.value}")
"""

from __future__ import annotations

import asyncio
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

# Optional HTTP client
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def __lt__(self, other):
        """Allow comparison for determining worst status."""
        order = {
            HealthStatus.HEALTHY: 3,
            HealthStatus.DEGRADED: 2,
            HealthStatus.UNHEALTHY: 1,
            HealthStatus.UNKNOWN: 0,
        }
        return order[self] < order[other]


@dataclass
class HealthCheck:
    """
    Result of a health check.

    Contains status, timing, and detailed information about
    the health check performed.
    """

    name: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
        }

    @property
    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        """Check if status is degraded but functional."""
        return self.status == HealthStatus.DEGRADED

    @property
    def is_unhealthy(self) -> bool:
        """Check if status is unhealthy."""
        return self.status == HealthStatus.UNHEALTHY


class ServiceHealthChecker:
    """
    Base class for service health checkers.

    Subclass this to create custom health checkers for
    specific services.

    Example:
        class MyServiceChecker(ServiceHealthChecker):
            async def check(self) -> HealthCheck:
                # Implement health check logic
                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Service is running"
                )
    """

    def __init__(
        self,
        name: str,
        timeout: float = 5.0,
        critical: bool = True,
    ):
        """
        Initialize the health checker.

        Args:
            name: Service name for identification
            timeout: Timeout for health check in seconds
            critical: Whether this service is critical for overall health
        """
        self.name = name
        self.timeout = timeout
        self.critical = critical

    async def check(self) -> HealthCheck:
        """
        Perform health check.

        Override this method in subclasses.
        """
        raise NotImplementedError


class HTTPHealthChecker(ServiceHealthChecker):
    """
    Health checker for HTTP/HTTPS endpoints.

    Sends a GET request to the specified URL and checks
    the response status code.
    """

    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        timeout: float = 5.0,
        critical: bool = True,
        headers: dict[str, str] | None = None,
        verify_ssl: bool = True,
    ):
        """
        Initialize HTTP health checker.

        Args:
            name: Service name
            url: Health check URL
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds
            critical: Whether service is critical
            headers: Optional HTTP headers
            verify_ssl: Whether to verify SSL certificates
        """
        super().__init__(name, timeout, critical)
        self.url = url
        self.expected_status = expected_status
        self.headers = headers or {}
        self.verify_ssl = verify_ssl

    async def check(self) -> HealthCheck:
        """Check HTTP endpoint health."""
        if not HTTPX_AVAILABLE:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="httpx not installed",
                details={"error": "Install httpx: pip install httpx"},
            )

        start = time.time()

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(self.url, headers=self.headers)

            duration_ms = (time.time() - start) * 1000

            if response.status_code == self.expected_status:
                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"HTTP {response.status_code}",
                    details={
                        "url": self.url,
                        "status_code": response.status_code,
                        "response_time_ms": round(duration_ms, 2),
                    },
                    duration_ms=duration_ms,
                )
            else:
                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Unexpected status: {response.status_code}",
                    details={
                        "url": self.url,
                        "status_code": response.status_code,
                        "expected_status": self.expected_status,
                    },
                    duration_ms=duration_ms,
                )

        except httpx.TimeoutException:
            duration_ms = (time.time() - start) * 1000
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Request timeout after {self.timeout}s",
                details={"url": self.url, "timeout": self.timeout},
                duration_ms=duration_ms,
            )

        except httpx.ConnectError as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {e}",
                details={"url": self.url, "error": str(e)},
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {e}",
                details={"url": self.url, "error": str(e)},
                duration_ms=duration_ms,
            )


class OllamaHealthChecker(HTTPHealthChecker):
    """
    Health checker for Ollama service.

    Extends HTTP health check with Ollama-specific
    model verification.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        required_models: list[str] | None = None,
        timeout: float = 5.0,
    ):
        """
        Initialize Ollama health checker.

        Args:
            base_url: Ollama API base URL
            required_models: List of models that must be available
            timeout: Request timeout
        """
        super().__init__(
            name="ollama",
            url=f"{base_url}/api/tags",
            expected_status=200,
            timeout=timeout,
        )
        self.base_url = base_url
        self.required_models = required_models or []

    async def check(self) -> HealthCheck:
        """Check Ollama with model verification."""
        result = await super().check()

        if result.status != HealthStatus.HEALTHY:
            return result

        # Get model information
        if not HTTPX_AVAILABLE:
            return result

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                data = response.json()
                models = data.get("models", [])
                model_names = [m["name"] for m in models]

                result.details["model_count"] = len(models)
                result.details["models"] = model_names

                # Check for required models
                if self.required_models:
                    missing = [
                        m
                        for m in self.required_models
                        if m not in model_names and f"{m}:latest" not in model_names
                    ]
                    if missing:
                        result.status = HealthStatus.DEGRADED
                        result.message = f"Missing required models: {missing}"
                        result.details["missing_models"] = missing

                # Check if any models are loaded
                if len(models) == 0:
                    result.status = HealthStatus.DEGRADED
                    result.message = "No models loaded"

        except Exception as e:
            logger.warning(f"Failed to get Ollama model list: {e}")
            result.details["model_check_error"] = str(e)

        return result


class QdrantHealthChecker(HTTPHealthChecker):
    """
    Health checker for Qdrant vector database.

    Checks Qdrant health endpoint and collection status.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:6333",
        required_collections: list[str] | None = None,
        timeout: float = 5.0,
    ):
        """
        Initialize Qdrant health checker.

        Args:
            base_url: Qdrant API base URL
            required_collections: Collections that must exist
            timeout: Request timeout
        """
        # First check the readiness endpoint
        super().__init__(
            name="qdrant",
            url=f"{base_url}/readyz",  # Qdrant readiness endpoint
            expected_status=200,
            timeout=timeout,
        )
        self.base_url = base_url
        self.required_collections = required_collections or []

    async def check(self) -> HealthCheck:
        """Check Qdrant with collection verification."""
        result = await super().check()

        if result.status != HealthStatus.HEALTHY:
            # Try alternative health endpoint
            alt_checker = HTTPHealthChecker(
                name="qdrant",
                url=f"{self.base_url}/",
                expected_status=200,
                timeout=self.timeout,
            )
            result = await alt_checker.check()

        if result.status != HealthStatus.HEALTHY:
            return result

        # Check collections if required
        if not self.required_collections or not HTTPX_AVAILABLE:
            return result

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/collections")
                data = response.json()
                collections = [
                    c["name"] for c in data.get("result", {}).get("collections", [])
                ]

                result.details["collections"] = collections
                result.details["collection_count"] = len(collections)

                missing = [c for c in self.required_collections if c not in collections]
                if missing:
                    result.status = HealthStatus.DEGRADED
                    result.message = f"Missing required collections: {missing}"
                    result.details["missing_collections"] = missing

        except Exception as e:
            logger.warning(f"Failed to get Qdrant collections: {e}")
            result.details["collection_check_error"] = str(e)

        return result


class RedisHealthChecker(ServiceHealthChecker):
    """
    Health checker for Redis.

    Uses PING command to verify Redis is responsive.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        timeout: float = 5.0,
    ):
        """
        Initialize Redis health checker.

        Args:
            host: Redis host
            port: Redis port
            password: Optional Redis password
            timeout: Connection timeout
        """
        super().__init__(name="redis", timeout=timeout)
        self.host = host
        self.port = port
        self.password = password

    async def check(self) -> HealthCheck:
        """Check Redis health using PING."""
        start = time.time()

        try:
            import redis
        except ImportError:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="redis package not installed",
                details={"error": "Install redis: pip install redis"},
            )

        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                socket_timeout=self.timeout,
            )

            # PING returns True if successful
            if client.ping():
                duration_ms = (time.time() - start) * 1000

                # Get some info
                info = client.info("server")

                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="PONG",
                    details={
                        "host": self.host,
                        "port": self.port,
                        "redis_version": info.get("redis_version", "unknown"),
                        "uptime_seconds": info.get("uptime_in_seconds", 0),
                    },
                    duration_ms=duration_ms,
                )
            else:
                duration_ms = (time.time() - start) * 1000
                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="PING failed",
                    details={"host": self.host, "port": self.port},
                    duration_ms=duration_ms,
                )

        except redis.ConnectionError as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {e}",
                details={
                    "host": self.host,
                    "port": self.port,
                    "error": str(e),
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {e}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )


class DiskSpaceHealthChecker(ServiceHealthChecker):
    """
    Health checker for disk space.

    Monitors available disk space and reports status
    based on configurable thresholds.
    """

    def __init__(
        self,
        name: str,
        path: Path | str,
        warning_threshold: float = 0.2,  # 20% free
        critical_threshold: float = 0.1,  # 10% free
    ):
        """
        Initialize disk space checker.

        Args:
            name: Checker name (e.g., "disk_models")
            path: Path to check
            warning_threshold: Percentage free below which is warning
            critical_threshold: Percentage free below which is critical
        """
        super().__init__(name, critical=True)
        self.path = Path(path)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheck:
        """Check available disk space."""
        start = time.time()

        try:
            if not self.path.exists():
                return HealthCheck(
                    name=self.name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Path does not exist: {self.path}",
                    details={"path": str(self.path)},
                    duration_ms=(time.time() - start) * 1000,
                )

            total, used, free = shutil.disk_usage(self.path)
            free_pct = free / total if total > 0 else 0

            # Determine status based on thresholds
            if free_pct >= self.warning_threshold:
                status = HealthStatus.HEALTHY
                message = f"{free_pct:.1%} free ({free / (1024**3):.1f} GB)"
            elif free_pct >= self.critical_threshold:
                status = HealthStatus.DEGRADED
                message = f"Low disk space: {free_pct:.1%} free"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk space: {free_pct:.1%} free"

            duration_ms = (time.time() - start) * 1000

            return HealthCheck(
                name=self.name,
                status=status,
                message=message,
                details={
                    "path": str(self.path),
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "free_pct": round(free_pct, 4),
                    "warning_threshold": self.warning_threshold,
                    "critical_threshold": self.critical_threshold,
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check disk space: {e}",
                details={"path": str(self.path), "error": str(e)},
                duration_ms=(time.time() - start) * 1000,
            )


class MemoryHealthChecker(ServiceHealthChecker):
    """
    Health checker for system memory.

    Monitors available memory and reports status
    based on configurable thresholds.
    """

    def __init__(
        self,
        warning_threshold: float = 0.2,  # 20% free
        critical_threshold: float = 0.1,  # 10% free
    ):
        """
        Initialize memory checker.

        Args:
            warning_threshold: Percentage free below which is warning
            critical_threshold: Percentage free below which is critical
        """
        super().__init__(name="memory", critical=True)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    async def check(self) -> HealthCheck:
        """Check available system memory."""
        start = time.time()

        try:
            import psutil
        except ImportError:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="psutil not installed",
                details={"error": "Install psutil: pip install psutil"},
                duration_ms=(time.time() - start) * 1000,
            )

        try:
            memory = psutil.virtual_memory()
            free_pct = memory.available / memory.total if memory.total > 0 else 0

            if free_pct >= self.warning_threshold:
                status = HealthStatus.HEALTHY
                message = f"{free_pct:.1%} available"
            elif free_pct >= self.critical_threshold:
                status = HealthStatus.DEGRADED
                message = f"Low memory: {free_pct:.1%} available"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory: {free_pct:.1%} available"

            return HealthCheck(
                name=self.name,
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_pct": round(free_pct, 4),
                    "percent_used": memory.percent,
                },
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check memory: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start) * 1000,
            )


class SystemHealthChecker:
    """
    Aggregates health checks from multiple services.

    Runs all configured health checks in parallel and
    aggregates results into overall system health status.

    Example:
        checker = SystemHealthChecker()
        checker.add_checker(OllamaHealthChecker())
        checker.add_checker(QdrantHealthChecker())
        checker.add_checker(DiskSpaceHealthChecker("disk", Path.home()))

        health = await checker.check_all()
        print(f"Overall status: {health['status']}")

        for check in health['checks']:
            print(f"  {check['name']}: {check['status']}")
    """

    def __init__(self, name: str = "ai_beast"):
        """
        Initialize system health checker.

        Args:
            name: System name for identification
        """
        self.name = name
        self.checkers: list[ServiceHealthChecker] = []

    def add_checker(self, checker: ServiceHealthChecker):
        """
        Add a health checker.

        Args:
            checker: Service health checker to add
        """
        self.checkers.append(checker)
        logger.debug(f"Added health checker: {checker.name}")

    def remove_checker(self, name: str) -> bool:
        """
        Remove a health checker by name.

        Args:
            name: Name of checker to remove

        Returns:
            True if checker was found and removed
        """
        for i, checker in enumerate(self.checkers):
            if checker.name == name:
                self.checkers.pop(i)
                return True
        return False

    async def check_all(
        self,
        include_non_critical: bool = True,
    ) -> dict[str, Any]:
        """
        Run all health checks.

        Args:
            include_non_critical: Include non-critical services in checks

        Returns:
            Dict with overall status and individual check results
        """
        checkers = (
            self.checkers
            if include_non_critical
            else [c for c in self.checkers if c.critical]
        )

        if not checkers:
            return {
                "name": self.name,
                "status": HealthStatus.UNKNOWN.value,
                "message": "No health checkers configured",
                "timestamp": datetime.now().isoformat(),
                "checks": [],
            }

        # Run all checks in parallel
        start = time.time()
        results = await asyncio.gather(
            *[checker.check() for checker in checkers],
            return_exceptions=True,
        )
        total_duration = (time.time() - start) * 1000

        # Process results
        checks: list[HealthCheck] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed with exception: {result}")
                checks.append(
                    HealthCheck(
                        name=checkers[i].name,
                        status=HealthStatus.UNKNOWN,
                        message=f"Check failed: {result}",
                        details={"error": str(result)},
                    )
                )
            else:
                checks.append(result)

        # Determine overall status
        critical_checks = [
            check
            for check, checker in zip(checks, checkers, strict=True)
            if checker.critical
        ]

        if not critical_checks:
            critical_checks = checks

        statuses = [check.status for check in critical_checks]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
            message = "All services healthy"
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            unhealthy = [
                c.name for c in critical_checks if c.status == HealthStatus.UNHEALTHY
            ]
            overall = HealthStatus.UNHEALTHY
            message = f"Unhealthy services: {', '.join(unhealthy)}"
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            degraded = [
                c.name for c in critical_checks if c.status == HealthStatus.DEGRADED
            ]
            overall = HealthStatus.DEGRADED
            message = f"Degraded services: {', '.join(degraded)}"
        else:
            overall = HealthStatus.UNKNOWN
            message = "Unable to determine health status"

        return {
            "name": self.name,
            "status": overall.value,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "total_duration_ms": round(total_duration, 2),
            "checks": [check.to_dict() for check in checks],
        }

    async def check_service(self, name: str) -> HealthCheck | None:
        """
        Check a specific service by name.

        Args:
            name: Service name to check

        Returns:
            HealthCheck result or None if not found
        """
        for checker in self.checkers:
            if checker.name == name:
                return await checker.check()
        return None


def create_default_checker(
    base_dir: Path | None = None,
    ollama_url: str = "http://localhost:11434",
    qdrant_url: str = "http://localhost:6333",
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> SystemHealthChecker:
    """
    Create health checker with default configuration.

    Args:
        base_dir: Base directory for disk checks
        ollama_url: Ollama API URL
        qdrant_url: Qdrant API URL
        redis_host: Redis host
        redis_port: Redis port

    Returns:
        Configured SystemHealthChecker
    """
    checker = SystemHealthChecker(name="ai_beast")

    # Service checks
    checker.add_checker(OllamaHealthChecker(base_url=ollama_url))
    checker.add_checker(QdrantHealthChecker(base_url=qdrant_url))
    checker.add_checker(RedisHealthChecker(host=redis_host, port=redis_port))

    # WebUI check (optional)
    checker.add_checker(
        HTTPHealthChecker(
            name="webui",
            url="http://localhost:3000/health",
            critical=False,
        )
    )

    # System resource checks
    if base_dir:
        checker.add_checker(
            DiskSpaceHealthChecker(
                name="disk_base",
                path=base_dir,
            )
        )

        models_dir = base_dir / "heavy" / "llms"
        if models_dir.exists():
            checker.add_checker(
                DiskSpaceHealthChecker(
                    name="disk_models",
                    path=models_dir,
                )
            )

    # Memory check
    checker.add_checker(MemoryHealthChecker())

    return checker


# Convenience functions
async def quick_health_check(
    services: list[str] | None = None,
) -> dict[str, Any]:
    """
    Quick health check for common services.

    Args:
        services: List of services to check (default: all)

    Returns:
        Health check results
    """
    checker = create_default_checker()

    if services:
        # Filter to requested services
        checker.checkers = [c for c in checker.checkers if c.name in services]

    return await checker.check_all()


def health_check_sync(services: list[str] | None = None) -> dict[str, Any]:
    """
    Synchronous wrapper for health check.

    Args:
        services: List of services to check (default: all)

    Returns:
        Health check results
    """
    return asyncio.run(quick_health_check(services))
