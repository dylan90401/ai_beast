"""
Monitoring module for AI Beast.

Provides observability, metrics collection, and health monitoring.
"""

from pathlib import Path


def check_service_health(service_name: str, port: int) -> dict:
    """
    Check if a service is healthy.

    Args:
        service_name: Name of the service
        port: Port the service is listening on

    Returns:
        Dict with 'healthy' bool and 'message' string
    """
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()

        if result == 0:
            return {
                "healthy": True,
                "message": f"{service_name} is responding on port {port}",
            }
        else:
            return {
                "healthy": False,
                "message": f"{service_name} not responding on port {port}",
            }
    except Exception as e:
        return {"healthy": False, "message": f"Error checking {service_name}: {e}"}


def collect_metrics(base_dir: Path) -> dict:
    """
    Collect system and application metrics.

    Args:
        base_dir: Base directory of the installation

    Returns:
        Dict with various metrics
    """
    import shutil

    metrics = {"disk_usage": {}, "service_status": {}, "timestamp": None}

    try:
        from datetime import datetime

        metrics["timestamp"] = datetime.utcnow().isoformat()

        # Disk usage
        if base_dir.exists():
            usage = shutil.disk_usage(base_dir)
            metrics["disk_usage"] = {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": round((usage.used / usage.total) * 100, 2),
            }
    except Exception as e:
        metrics["error"] = str(e)

    return metrics
