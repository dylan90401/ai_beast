from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from beast.runtime import docker_compose_cmd, ensure_runtime_ready, run


ROOT = Path(os.environ.get("BEAST_ROOT", Path(__file__).resolve().parents[1]))
REGISTRY = ROOT / "packs" / "registry.json"
COMPOSE_BASE = ROOT / "compose" / "base.yml"
COMPOSE_PACKS_DIR = ROOT / "compose" / "packs"


def _load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if "packs" not in data or not isinstance(data["packs"], dict):
        raise RuntimeError("Invalid packs/registry.json: expected {packs:{...}}")
    return data


def _enabled_packs(reg: dict[str, Any]) -> list[str]:
    packs = []
    for name, meta in reg["packs"].items():
        if bool(meta.get("enabled", False)):
            packs.append(name)
    return packs


def _compose_files(extra_packs: list[str] | None = None) -> list[Path]:
    reg = _load_registry()
    enabled = set(_enabled_packs(reg))
    if extra_packs:
        enabled |= set([p.strip() for p in extra_packs if p.strip()])

    files = [COMPOSE_BASE]
    for pack in sorted(enabled):
        frag = COMPOSE_PACKS_DIR / f"{pack}.yml"
        if not frag.exists():
            raise RuntimeError(f"Pack fragment missing: {frag}")
        files.append(frag)
    return files


def _compose(args: list[str], *, packs: list[str] | None = None) -> None:
    ensure_runtime_ready()
    cmd = docker_compose_cmd()
    files = _compose_files(packs)
    full = cmd[:]
    for f in files:
        full += ["-f", str(f)]
    full += args
    run(full, cwd=str(ROOT), check=True)


def cmd_preflight() -> None:
    # lightweight checks; keep it fast
    problems: list[str] = []
    if not COMPOSE_BASE.exists():
        problems.append("compose/base.yml missing")
    if not REGISTRY.exists():
        problems.append("packs/registry.json missing")
    if problems:
        raise RuntimeError("Preflight failed:\n- " + "\n- ".join(problems))

    # runtime readiness (colima/docker)
    ensure_runtime_ready()
    print("OK: preflight passed")


def cmd_bootstrap() -> None:
    # Delegate OS-specific bootstrap scripts (keeps system changes in bash)
    if os.uname().sysname.lower().startswith("darwin"):
        run([str(ROOT / "scripts" / "20_bootstrap_macos.sh")], cwd=str(ROOT), check=True)
    else:
        run([str(ROOT / "scripts" / "21_bootstrap_linux.sh")], cwd=str(ROOT), check=True)
    print("OK: bootstrap complete")


def cmd_up(with_packs: list[str]) -> None:
    _compose(["up", "-d"], packs=with_packs)
    print("OK: stack up")


def cmd_down() -> None:
    _compose(["down", "--remove-orphans"])
    print("OK: stack down")


def cmd_status() -> None:
    ensure_runtime_ready()
    cmd = docker_compose_cmd()
    run(cmd + ["ps"], cwd=str(ROOT), check=True)
    # show enabled packs
    reg = _load_registry()
    print("\nEnabled packs:", ", ".join(_enabled_packs(reg)) or "(none)")


def cmd_logs(service: str | None, follow: bool) -> None:
    args = ["logs"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    _compose(args)
    print("OK: logs done")


def cmd_pack_list() -> None:
    reg = _load_registry()
    for name, meta in reg["packs"].items():
        status = "ENABLED" if meta.get("enabled") else "disabled"
        desc = meta.get("description", "")
        print(f"- {name:20} {status:8} {desc}")


def cmd_pack_enable(name: str) -> None:
    reg = _load_registry()
    if name not in reg["packs"]:
        raise RuntimeError(f"Unknown pack: {name}")
    reg["packs"][name]["enabled"] = True
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    print(f"OK: enabled {name}")


def cmd_pack_disable(name: str) -> None:
    reg = _load_registry()
    if name not in reg["packs"]:
        raise RuntimeError(f"Unknown pack: {name}")
    reg["packs"][name]["enabled"] = False
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    print(f"OK: disabled {name}")


def main() -> None:
    p = argparse.ArgumentParser(prog="beast")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight")
    sub.add_parser("bootstrap")

    up = sub.add_parser("up")
    up.add_argument("--with", dest="with_packs", default="", help="Comma-separated packs to include temporarily")

    sub.add_parser("down")
    sub.add_parser("status")

    logs = sub.add_parser("logs")
    logs.add_argument("service", nargs="?", default=None)
    logs.add_argument("-f", "--follow", action="store_true")

    pack = sub.add_parser("pack")
    pack_sub = pack.add_subparsers(dest="pack_cmd", required=True)
    pack_sub.add_parser("list")

    en = pack_sub.add_parser("enable")
    en.add_argument("name")

    dis = pack_sub.add_parser("disable")
    dis.add_argument("name")

    args = p.parse_args()

    try:
        if args.cmd == "preflight":
            cmd_preflight()
        elif args.cmd == "bootstrap":
            cmd_bootstrap()
        elif args.cmd == "up":
            packs = [x.strip() for x in args.with_packs.split(",") if x.strip()]
            cmd_up(packs)
        elif args.cmd == "down":
            cmd_down()
        elif args.cmd == "status":
            cmd_status()
        elif args.cmd == "logs":
            cmd_logs(args.service, args.follow)
        elif args.cmd == "pack":
            if args.pack_cmd == "list":
                cmd_pack_list()
            elif args.pack_cmd == "enable":
                cmd_pack_enable(args.name)
            elif args.pack_cmd == "disable":
                cmd_pack_disable(args.name)
    except Exception as e:
        # clean, agent-friendly failure
        raise SystemExit(f"ERROR: {e}") from e


if __name__ == "__main__":
    main()