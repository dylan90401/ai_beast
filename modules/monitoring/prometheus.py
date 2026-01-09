"""
Prometheus metrics exporter.
"""

from __future__ import annotations

from typing import Any


def _line(metric: str, value: float, labels: dict[str, str] | None = None) -> str:
    if labels:
        parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = "{" + ",".join(parts) + "}"
    else:
        label_str = ""
    return f"{metric}{label_str} {value}"


def build_prometheus_metrics(metrics: dict[str, Any]) -> str:
    lines: list[str] = []
    disk = metrics.get("disk_usage") or {}
    mem = metrics.get("memory") or {}
    db = metrics.get("metadata_db") or {}

    lines.append("# HELP ai_beast_disk_total_bytes Disk total bytes.")
    lines.append("# TYPE ai_beast_disk_total_bytes gauge")
    if disk.get("total_gb") is not None:
        lines.append(_line("ai_beast_disk_total_bytes", float(disk.get("total_gb")) * 1024**3))

    lines.append("# HELP ai_beast_disk_used_bytes Disk used bytes.")
    lines.append("# TYPE ai_beast_disk_used_bytes gauge")
    if disk.get("used_gb") is not None:
        lines.append(_line("ai_beast_disk_used_bytes", float(disk.get("used_gb")) * 1024**3))

    lines.append("# HELP ai_beast_disk_free_bytes Disk free bytes.")
    lines.append("# TYPE ai_beast_disk_free_bytes gauge")
    if disk.get("free_gb") is not None:
        lines.append(_line("ai_beast_disk_free_bytes", float(disk.get("free_gb")) * 1024**3))

    lines.append("# HELP ai_beast_memory_used_bytes Memory used bytes.")
    lines.append("# TYPE ai_beast_memory_used_bytes gauge")
    if mem.get("used_gb") is not None:
        lines.append(_line("ai_beast_memory_used_bytes", float(mem.get("used_gb")) * 1024**3))

    lines.append("# HELP ai_beast_memory_total_bytes Memory total bytes.")
    lines.append("# TYPE ai_beast_memory_total_bytes gauge")
    if mem.get("total_gb") is not None:
        lines.append(_line("ai_beast_memory_total_bytes", float(mem.get("total_gb")) * 1024**3))

    lines.append("# HELP ai_beast_metadata_db_up Metadata DB status.")
    lines.append("# TYPE ai_beast_metadata_db_up gauge")
    lines.append(_line("ai_beast_metadata_db_up", 1.0 if db.get("ok") else 0.0))
    if db.get("backend"):
        lines.append(_line("ai_beast_metadata_db_backend_info", 1.0, {"backend": str(db.get("backend"))}))

    return "\n".join(lines) + "\n"
