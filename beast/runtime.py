from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CmdResult:
    code: int
    out: str
    err: str


def run(cmd: Sequence[str], *, cwd: str | None = None, check: bool = True) -> CmdResult:
    p = subprocess.run(
        list(cmd),
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return CmdResult(p.returncode, p.stdout, p.stderr)


def which(bin_name: str) -> str | None:
    return shutil.which(bin_name)


def docker_compose_cmd() -> list[str]:
    # Prefer `docker compose` if available
    if which("docker") is None:
        raise RuntimeError("docker CLI not found")
    try:
        run(["docker", "compose", "version"], check=True)
        return ["docker", "compose"]
    except Exception:
        # fallback legacy
        if which("docker-compose") is None:
            raise RuntimeError("Neither `docker compose` nor `docker-compose` found")
        return ["docker-compose"]


def pick_runtime() -> str:
    rt = os.getenv("DOCKER_RUNTIME", "").strip().lower()
    if rt in {"docker", "colima"}:
        return rt
    # default colima-first if present
    return "colima" if which("colima") else "docker"


def ensure_runtime_ready() -> None:
    rt = pick_runtime()
    if rt == "colima":
        if which("colima") is None:
            raise RuntimeError("DOCKER_RUNTIME=colima but colima is not installed")
        # Start if not running
        try:
            run(["colima", "status"], check=True)
        except Exception:
            run(["colima", "start", "--cpu", "6", "--memory", "12", "--disk", "80"], check=True)
    else:
        run(["docker", "info"], check=True)