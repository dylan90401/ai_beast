"""
Simple polling-based file watcher.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path


class FileWatcher:
    def __init__(self, path: Path, callback: Callable[[Path], None], interval: float = 2.0) -> None:
        self.path = path
        self.callback = callback
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_mtime = self._mtime()

    def _mtime(self) -> float:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval * 2)

    def _run(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.interval)
            mtime = self._mtime()
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                self.callback(self.path)
