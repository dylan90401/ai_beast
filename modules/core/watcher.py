"""
File system watcher using polling.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable


class FileWatcher:
    def __init__(self, path: Path, interval: float = 2.0) -> None:
        self.path = Path(path)
        self.interval = max(0.2, float(interval))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_mtime: float | None = None

    def start(self, on_change: Callable[[Path], None]) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _run() -> None:
            while not self._stop.is_set():
                try:
                    mtime = self.path.stat().st_mtime
                except FileNotFoundError:
                    mtime = None
                if self._last_mtime is None:
                    self._last_mtime = mtime
                elif mtime is not None and mtime != self._last_mtime:
                    self._last_mtime = mtime
                    on_change(self.path)
                time.sleep(self.interval)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
