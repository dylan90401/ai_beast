"""
Built-in queue tasks.
"""

from __future__ import annotations

import time
from typing import Any


def heartbeat(source: str = "system", delay: float = 0.1) -> dict[str, Any]:
    time.sleep(max(0.0, float(delay)))
    return {"ok": True, "source": source}
