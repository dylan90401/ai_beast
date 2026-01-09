"""
Task registry for RQ.
"""

from __future__ import annotations

import time


def heartbeat(label: str = "ok", delay: float = 0.0) -> dict[str, str]:
    if delay:
        time.sleep(delay)
    return {"status": "ok", "label": label}
