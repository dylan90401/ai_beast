#!/usr/bin/env python3
"""AI Beast Dashboard - Async WebSocket Server.

This module provides WebSocket support for real-time dashboard updates.
It can run alongside the main dashboard or as a standalone server.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quart import Quart, send_file, websocket
from quart_cors import cors


def resolve_base_dir() -> Path:
    """Resolve the base directory."""
    bd = os.environ.get("BASE_DIR")
    if bd:
        return Path(bd)
    here = Path(__file__).resolve()
    if here.parent.name == "_template":
        return here.parents[3]
    return here.parents[2]


BASE_DIR = resolve_base_dir()
STATIC_DIR = BASE_DIR / "apps" / "dashboard" / "static"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Create Quart app
app = Quart(__name__, static_folder=str(STATIC_DIR))
app = cors(app)

# Connected WebSocket clients
connected_clients: set[Any] = set()

# Logger (lazy import to avoid circular imports)
_logger = None


def get_logger():
    """Get logger instance."""
    global _logger
    if _logger is None:
        try:
            from modules.logging_config import get_logger as get_structlog_logger

            _logger = get_structlog_logger(__name__)
        except ImportError:
            import logging

            _logger = logging.getLogger(__name__)
    return _logger


def get_llm_manager():
    """Get LLM manager instance."""
    try:
        from modules.llm import LLMManager

        return LLMManager(BASE_DIR)
    except ImportError:
        return None


def load_metrics() -> dict[str, Any]:
    """Load system metrics."""
    metrics: dict[str, Any] = {}
    try:
        from modules.monitoring import collect_metrics

        metrics = collect_metrics(BASE_DIR)
    except Exception as ex:
        metrics["error"] = str(ex)

    # Add memory info
    try:
        metrics["memory"] = _memory_info()
    except Exception:
        pass

    return metrics


def _memory_info() -> dict[str, float]:
    """Get memory information."""
    import subprocess

    info: dict[str, float] = {}

    if sys.platform == "darwin":
        try:
            total = int(
                subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"])
                .decode()
                .strip()
            )
            vm = subprocess.check_output(["/usr/bin/vm_stat"]).decode()
            page_size = 4096
            for line in vm.splitlines():
                if "page size of" in line:
                    page_size = int(line.split("page size of")[1].split("bytes")[0])

            pages: dict[str, int] = {}
            for line in vm.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip().lower().replace(" ", "_")
                v = v.strip().strip(".")
                if v.isdigit():
                    pages[k] = int(v)

            free_pages = (
                pages.get("pages_free", 0)
                + pages.get("pages_inactive", 0)
                + pages.get("pages_speculative", 0)
            )
            free = free_pages * page_size
            used = max(total - free, 0)
            info = {
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "percent_used": round((used / total) * 100, 2) if total else 0.0,
            }
        except Exception:
            pass

    elif sys.platform.startswith("linux"):
        try:
            total_kb = 0
            avail_kb = 0
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
            total = total_kb * 1024
            free = avail_kb * 1024
            used = max(total - free, 0)
            info = {
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "percent_used": round((used / total) * 100, 2) if total else 0.0,
            }
        except Exception:
            pass

    return info


# ==================== Routes ====================


@app.route("/")
async def index():
    """Serve the main dashboard page."""
    return await send_file(STATIC_DIR / "index.html")


@app.route("/api/health")
async def api_health():
    """Health check endpoint."""
    return {"ok": True, "base_dir": str(BASE_DIR), "websocket": True}


# ==================== WebSocket ====================


@app.websocket("/ws/updates")
async def ws_updates():
    """WebSocket endpoint for real-time updates."""
    logger = get_logger()
    client = websocket._get_current_object()
    connected_clients.add(client)
    logger.info("websocket_connected", clients=len(connected_clients))

    try:
        # Send initial state
        await client.send_json(
            {
                "type": "connected",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {"message": "Connected to AI Beast Dashboard"},
            }
        )

        while True:
            # Send periodic updates every 5 seconds
            await asyncio.sleep(5)

            try:
                # Collect current status
                metrics = load_metrics()
                mgr = get_llm_manager()
                models_status = {
                    "ollama_running": mgr.ollama_running() if mgr else False,
                }

                await client.send_json(
                    {
                        "type": "update",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "data": {
                            "metrics": metrics,
                            "models": models_status,
                        },
                    }
                )
            except Exception as e:
                logger.error("websocket_update_failed", error=str(e))

    except asyncio.CancelledError:
        pass
    finally:
        connected_clients.discard(client)
        logger.info("websocket_disconnected", clients=len(connected_clients))


async def broadcast_update(data: dict[str, Any]) -> None:
    """Broadcast update to all connected clients.

    Args:
        data: Data to broadcast
    """
    logger = get_logger()
    message = {
        "type": "broadcast",
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }

    for client in connected_clients.copy():
        try:
            await client.send_json(message)
        except Exception:
            connected_clients.discard(client)
            logger.warning("broadcast_client_removed")


async def send_notification(message: str, level: str = "info") -> None:
    """Send notification to all connected clients.

    Args:
        message: Notification message
        level: Notification level (info, success, warning, error)
    """
    await broadcast_update(
        {
            "type": "notification",
            "message": message,
            "level": level,
        }
    )


async def send_log(message: str, level: str = "INFO") -> None:
    """Send log message to all connected clients.

    Args:
        message: Log message
        level: Log level
    """
    await broadcast_update(
        {
            "type": "log",
            "message": message,
            "level": level,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


# ==================== Main ====================


def run_dashboard(host: str = "127.0.0.1", port: int = 8787) -> None:
    """Run the dashboard server.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    app.run(host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Beast Dashboard WebSocket Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8788, help="Port to listen on")
    args = parser.parse_args()

    print(f"Starting WebSocket server on {args.host}:{args.port}")
    run_dashboard(host=args.host, port=args.port)
