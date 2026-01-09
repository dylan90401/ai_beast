import threading
import time

from modules.core.watcher import FileWatcher


def test_file_watcher_detects_change(tmp_path):
    target = tmp_path / "watch.txt"
    target.write_text("a", encoding="utf-8")
    event = threading.Event()

    def on_change(path):
        if path == target:
            event.set()

    watcher = FileWatcher(target, interval=0.2)
    watcher.start(on_change)
    target.write_text("b", encoding="utf-8")
    assert event.wait(timeout=1.5)
    watcher.stop()
