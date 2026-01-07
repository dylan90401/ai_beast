#!/usr/bin/env python3
"""
Deterministic verifier for AI Beast workspace.
- No writes, no patches.
- Exits non-zero on failure.
"""
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple, List

def run(cmd: List[str], cwd: Path, timeout: int = 300) -> Tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    return p.returncode, p.stdout, p.stderr

def load_env_file(p: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # allow "export X=Y" or "X=Y"
        line = re.sub(r"^export\s+", "", line)
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def curl_ok(url: str, timeout: int = 8) -> bool:
    code, _, _ = run(["curl", "-fsS", "--max-time", str(timeout), url], cwd=Path.cwd(), timeout=timeout + 2)
    return code == 0

def main() -> int:
    base = Path.cwd().resolve()
    if not (base / "bin" / "beast").exists():
        print("[fail] run from workspace root (expected bin/beast).", file=sys.stderr)
        return 2

    ports = load_env_file(base / "config" / "ports.env")
    bind_env = load_env_file(base / "config" / "ai-beast.env")
    bind_addr = bind_env.get("AI_BEAST_BIND_ADDR", "127.0.0.1")

    checks = []

    def add(name: str, ok: bool, detail: str = ""):
        checks.append((name, ok, detail))

    def port(name: str, default: str) -> str:
        return ports.get(name, default)

    # 1) Preflight
    code, out, err = run([str(base / "bin" / "beast"), "preflight", "--verbose"], cwd=base, timeout=300)
    add("beast preflight", code == 0, (err or out)[-800:])

    # 2) Status
    code2, out2, err2 = run([str(base / "bin" / "beast"), "status", "--verbose"], cwd=base, timeout=180)
    add("beast status", code2 == 0, (err2 or out2)[-800:])

    # 3) Endpoints (best-effort)
    add("ollama /api/version", curl_ok(f"http://{bind_addr}:{port('PORT_OLLAMA','11434')}/api/version"), f"{bind_addr}:{port('PORT_OLLAMA','11434')}")
    add("qdrant /healthz", curl_ok(f"http://{bind_addr}:{port('PORT_QDRANT','6333')}/healthz"), f"{bind_addr}:{port('PORT_QDRANT','6333')}")
    add("comfyui /", curl_ok(f"http://{bind_addr}:{port('PORT_COMFYUI','8188')}/"), f"{bind_addr}:{port('PORT_COMFYUI','8188')}")
    add("webui /", curl_ok(f"http://{bind_addr}:{port('PORT_WEBUI','3000')}/"), f"{bind_addr}:{port('PORT_WEBUI','3000')}")

    # 4) Compose generation (dry-run)
    code3, out3, err3 = run([str(base / "bin" / "beast"), "compose", "gen", "--dry-run", "--verbose"], cwd=base, timeout=180)
    add("compose gen (dry-run)", code3 == 0, (err3 or out3)[-800:])

    any_fail = any(not ok for _, ok, _ in checks)
    print("\nKRYPTOS STRICT VERIFIER\n" + "-" * 28)
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if (not ok) and detail:
            print("  " + detail.replace("\n", "\n  "))
    print("-" * 28)
    print("Result:", "FAIL" if any_fail else "PASS")
    return 1 if any_fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
