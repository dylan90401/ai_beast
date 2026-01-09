#!/usr/bin/env python3
"""
Back-compat wrapper for v23: `kryptos_agent_multi.py` now delegates to kryptos_agent_hub.py.

Usage:
  python apps/agent/kryptos_agent_multi.py [--apply] [--pipeline build|harden|docs] "task..."
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    base = Path.cwd().resolve()
    hub = base / "apps" / "agent" / "kryptos_agent_hub.py"
    if not hub.exists():
        print(f"Missing hub: {hub}", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(hub)]
    # pass-through args
    cmd += sys.argv[1:]
    p = subprocess.run(cmd, cwd=str(base), check=False)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
