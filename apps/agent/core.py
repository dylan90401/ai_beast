#!/usr/bin/env python3
"""AI Beast Builder Agent core.

A deterministic tool-using agent that runs locally on your machine:
- Brain: Ollama /api/chat
- Hands: bounded filesystem ops + bounded shell + patch application

Design goals:
- Reproducible, minimal diffs
- DRYRUN by default; writes/patches only with --apply
- Optional --allow-destructive for risky shell commands
- Persistent, non-sensitive run state in config/agent_state.json
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.tools.registry import run_tool

import requests

DEFAULT_OLLAMA = os.environ.get("AI_BEAST_OLLAMA", "http://127.0.0.1:11434")
DEFAULT_MODEL = (
    os.environ.get("AI_BEAST_AGENT_MODEL")
    or os.environ.get("FEATURE_AGENT_MODEL_DEFAULT")
    or "llama3.2:latest"
)

SAFE_SUBDIRS = {
    "config",
    "bin",
    "scripts",
    "apps",
    "docker",
    "data",
    "models",
    "outputs",
    "logs",
    "backups",
    "extensions",
    ".vscode",
}

# Commands we consider "risky" even in apply mode unless allow_destructive is set.
RISKY_BINS = {
    "rm",
    "mv",
    "dd",
    "diskutil",
    "mkfs",
    "fdisk",
    "shutdown",
    "reboot",
    "launchctl",
    "chown",
    "chmod",
    "sudo",
}


@dataclass
class RunResult:
    code: int
    out: str
    err: str


@dataclass
class ToolContext:
    base: Path
    apply: bool
    allow_destructive: bool
    touched: list[str]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def base_dir_from_cwd() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "bin" / "beast").exists():
        return cwd
    for p in [cwd] + list(cwd.parents)[:8]:
        if (p / "bin" / "beast").exists():
            return p
    raise SystemExit(
        "Cannot locate BASE_DIR (expected bin/beast). cd into your AI Beast workspace root."
    )


def is_path_allowed(base: Path, target: Path) -> bool:
    try:
        base = base.resolve()
        target = target.resolve()
        if not str(target).startswith(str(base) + os.sep):
            return False
        rel = target.relative_to(base)
        return bool(rel.parts) and rel.parts[0] in SAFE_SUBDIRS
    except Exception:
        return False


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str, apply: bool) -> str:
    if not apply:
        return f"[dry-run] would write {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def run_cmd(
    cmd: Sequence[str],
    cwd: Path,
    apply: bool,
    allow_destructive: bool,
    timeout: int = 300,
) -> RunResult:
    cmd = list(cmd)
    if not cmd:
        return RunResult(2, "", "empty command")

    exe = Path(cmd[0]).name

    # DRYRUN blocks anything that could mutate state.
    if not apply:
        if exe in RISKY_BINS or exe in {
            "git",
            "pip3",
            "brew",
            "docker",
            "colima",
            "python3",
        }:
            # We still allow *read-only* docker and git via allowlist below.
            pass

        # allow a conservative set of read-only commands
        allowed_prefixes = {
            "ls",
            "pwd",
            "whoami",
            "uname",
            "sw_vers",
            "which",
            "command",
            "echo",
            "cat",
            "head",
            "tail",
            "grep",
            "rg",
            "find",
            "stat",
            "wc",
            "python3",
            "curl",
            "lsof",
            "netstat",
            "ss",
            "ps",
            "pgrep",
            "ollama",
            "docker",
            "colima",
            "git",
            "./bin/beast",
        }

        first = cmd[0]
        if Path(first).name not in allowed_prefixes and first not in allowed_prefixes:
            return RunResult(2, "", f"[dry-run] blocked command: {' '.join(cmd)}")

        # additionally block obvious "write" subcommands
        joined = " ".join(cmd)
        blocked_patterns = [
            r"\bgit\s+apply\b",
            r"\bgit\s+commit\b",
            r"\bgit\s+checkout\b",
            r"\bdocker\s+compose\s+up\b",
            r"\bdocker\s+compose\s+down\b",
            r"\bdocker\s+rm\b",
            r"\bbrew\s+install\b",
            r"\bpip3\s+install\b",
            r"\bpython3\s+-m\s+pip\s+install\b",
        ]
        for pat in blocked_patterns:
            if re.search(pat, joined):
                return RunResult(
                    2, "", f"[dry-run] blocked command pattern: {pat} ({joined})"
                )

    # APPLY mode still blocks risky binaries unless allow_destructive.
    if apply and not allow_destructive and exe in RISKY_BINS:
        return RunResult(
            2, "", f"blocked risky command without --allow-destructive: {' '.join(cmd)}"
        )

    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return RunResult(p.returncode, p.stdout, p.stderr)


def apply_unified_diff(base: Path, diff_text: str, apply: bool) -> str:
    if not apply:
        return "[dry-run] would apply patch"

    tmp = base / ".tmp_agent_patch.diff"
    tmp.write_text(diff_text, encoding="utf-8")

    # Prefer git apply if git repo
    if (base / ".git").exists():
        rr = run_cmd(
            ["git", "apply", str(tmp)],
            cwd=base,
            apply=True,
            allow_destructive=True,
            timeout=120,
        )
        tmp.unlink(missing_ok=True)
        if rr.code == 0:
            return "patch applied with git apply"
        return f"git apply failed:\n{rr.err}\n{rr.out}"

    rr = run_cmd(
        ["patch", "-p0", "-i", str(tmp)],
        cwd=base,
        apply=True,
        allow_destructive=True,
        timeout=120,
    )
    tmp.unlink(missing_ok=True)
    if rr.code == 0:
        return "patch applied with patch"
    return f"patch failed:\n{rr.err}\n{rr.out}"


def ollama_chat(
    base_url: str, model: str, messages: list[dict[str, str]], temperature: float = 0.2
) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    r = requests.post(url, json=payload, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"Ollama chat failed: HTTP {r.status_code}: {r.text[:2000]}")
    data = r.json()
    return data.get("message", {}).get("content", "")


def parse_tool_lines(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                calls.append(obj)
        except Exception:
            continue
    return calls


def tool_help() -> str:
    """A machine-readable tool schema for the LLM."""
    return json.dumps(
        {
            "tools": {
                "fs_read": {"args": {"path": "relative/path"}},
                "fs_write": {
                    "args": {"path": "relative/path", "content": "..."},
                    "apply_required": True,
                },
                "fs_list": {"args": {"path": "relative/path"}},
                "grep": {"args": {"pattern": "regex", "path": "relative/path"}},
                "shell": {"args": {"cmd": "string or list", "timeout": 300}},
                "patch": {
                    "args": {"diff": "unified diff text"},
                    "apply_required": True,
                },
                "http_get": {
                    "args": {"url": "http://127.0.0.1:3000/health", "timeout": 10}
                },
                "ai_tool_run": {
                    "args": {
                        "name": "nmap",
                        "mode": "run or test",
                        "entrypoint": "bin/nmap",
                        "args": "--version",
                    }
                },
            }
        },
        indent=2,
    )


# ---------------- Tools -----------------


def tool_fs_read(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rel = args.get("path")
    if not rel:
        return {"ok": False, "error": "missing path"}
    path = ctx.base / rel
    if not is_path_allowed(ctx.base, path):
        return {"ok": False, "error": f"read denied: {rel}"}
    if not path.exists():
        return {"ok": False, "error": f"not found: {rel}"}
    ctx.touched.append(str(path.relative_to(ctx.base)))
    return {"ok": True, "content": read_text(path)}


def tool_fs_write(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rel = args.get("path")
    if not rel:
        return {"ok": False, "error": "missing path"}
    path = ctx.base / rel
    if not is_path_allowed(ctx.base, path):
        return {"ok": False, "error": f"write denied: {rel}"}
    ctx.touched.append(str(path.relative_to(ctx.base)))
    msg = write_text(path, args.get("content", ""), apply=ctx.apply)
    return {"ok": True, "result": msg}


def tool_fs_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    rel = args.get("path", ".")
    root = ctx.base if rel in (".", "") else (ctx.base / rel)
    if root != ctx.base and not is_path_allowed(ctx.base, root):
        return {"ok": False, "error": "list denied"}
    if not root.exists():
        return {"ok": False, "error": f"not found: {rel}"}
    ctx.touched.append(str(root.relative_to(ctx.base)) if root != ctx.base else ".")
    items = []
    for p in sorted(root.iterdir()):
        items.append({"name": p.name, "type": "dir" if p.is_dir() else "file"})
    return {"ok": True, "items": items}


def tool_grep(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    pattern = args.get("pattern", "")
    rel = args.get("path", ".")
    root = ctx.base if rel in (".", "") else (ctx.base / rel)
    if root != ctx.base and not is_path_allowed(ctx.base, root):
        return {"ok": False, "error": "grep denied"}
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return {"ok": False, "error": f"bad regex: {e}"}

    ctx.touched.append(str(root.relative_to(ctx.base)) if root != ctx.base else ".")
    hits: list[dict[str, Any]] = []
    for p in root.rglob("*"):
        if p.is_dir() or p.name.startswith("."):
            continue
        try:
            txt = read_text(p)
        except Exception:
            continue
        for i, line in enumerate(txt.splitlines(), start=1):
            if rx.search(line):
                hits.append(
                    {
                        "file": str(p.relative_to(ctx.base)),
                        "line": i,
                        "text": line[:240],
                    }
                )
                if len(hits) >= 200:
                    return {"ok": True, "hits": hits, "truncated": True}
    return {"ok": True, "hits": hits}


def tool_shell(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    cmd = args.get("cmd")
    if not cmd:
        return {"ok": False, "error": "missing cmd"}
    cmd_list = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    ctx.touched.append(f"$ {' '.join(cmd_list)}")
    rr = run_cmd(
        cmd_list,
        cwd=ctx.base,
        apply=ctx.apply,
        allow_destructive=ctx.allow_destructive,
        timeout=int(args.get("timeout", 300)),
    )
    return {
        "ok": rr.code == 0,
        "code": rr.code,
        "stdout": rr.out[-8000:],
        "stderr": rr.err[-8000:],
    }


def tool_patch(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    diff = args.get("diff", "")
    if not diff.strip():
        return {"ok": False, "error": "empty diff"}
    ctx.touched.append("(patch)")
    res = apply_unified_diff(ctx.base, diff, apply=ctx.apply)
    ok = "failed" not in res.lower()
    return {"ok": ok, "result": res}


def tool_http_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    url = args.get("url")
    if not url:
        return {"ok": False, "error": "missing url"}
    ctx.touched.append(f"GET {url}")
    try:
        r = requests.get(url, timeout=int(args.get("timeout", 10)))
        return {
            "ok": 200 <= r.status_code < 400,
            "status": r.status_code,
            "headers": dict(r.headers),
            "text": r.text[:2000],
        }
    except Exception as e:
        return {"ok": False, "error": f"http_error: {e}"}


def tool_ai_tool_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing name"}
    mode = args.get("mode") or "run"
    entrypoint = args.get("entrypoint")
    tool_args = args.get("args")
    ctx.touched.append(f"tool:{name}:{mode}")
    code, obj = run_tool(
        name=str(name),
        mode=str(mode),
        entrypoint=str(entrypoint) if entrypoint else None,
        args=str(tool_args) if tool_args else None,
        base=ctx.base,
    )
    if code != 200:
        return {"ok": False, "error": obj.get("error", "tool error")}
    return obj


TOOLS = {
    "fs_read": tool_fs_read,
    "fs_write": tool_fs_write,
    "fs_list": tool_fs_list,
    "grep": tool_grep,
    "shell": tool_shell,
    "patch": tool_patch,
    "http_get": tool_http_get,
    "ai_tool_run": tool_ai_tool_run,
}


# ---------------- State -----------------


def load_agent_state(base: Path) -> dict[str, Any]:
    state_path = base / "config" / "agent_state.json"
    if not state_path.exists():
        return {"version": 1, "history": []}
    try:
        return json.loads(read_text(state_path))
    except Exception:
        return {"version": 1, "history": []}


def save_agent_state(base: Path, state: dict[str, Any], apply: bool) -> None:
    state_path = base / "config" / "agent_state.json"
    if not apply:
        return
    write_text(state_path, json.dumps(state, indent=2), apply=True)


def record_run(
    base: Path,
    state: dict[str, Any],
    model: str,
    ollama: str,
    apply: bool,
    allow_destructive: bool,
    task: str,
    final: str,
    verification: list[str],
    touched: list[str],
) -> None:
    entry = {
        "timestamp": utc_now(),
        "model": model,
        "ollama_url": ollama,
        "apply": apply,
        "allow_destructive": allow_destructive,
        "task": task[:2000],
        "final_excerpt": final[:4000],
        "verification": verification[:10],
        "touched": sorted(set(touched))[:200],
    }
    hist = state.setdefault("history", [])
    hist.append(entry)
    # keep last 30
    state["history"] = hist[-30:]
    state["last_run"] = entry


def state_context_snippet(state: dict[str, Any], max_items: int = 5) -> str:
    hist = state.get("history", [])
    if not hist:
        return "(no prior agent runs recorded)"
    recent = hist[-max_items:]
    lines = []
    for r in reversed(recent):
        ts = r.get("timestamp", "?")
        task = (r.get("task", "") or "").strip().replace("\n", " ")
        task = task[:120] + ("…" if len(task) > 120 else "")
        lines.append(f"- {ts} apply={r.get('apply')} task={task}")
    return "\n".join(lines)


# ---------------- Tool loop -----------------


def run_tool_loop(
    *,
    base: Path,
    ollama: str,
    model: str,
    system_prompt: str,
    user_content: str,
    apply: bool,
    allow_destructive: bool,
    max_steps: int = 30,
    temperature: float = 0.2,
    extra_messages: list[dict[str, str]] | None = None,
) -> tuple[int, str, list[str]]:
    """Run an agent tool loop.

    Returns: (exit_code, final_text_or_error, touched_items)
    """

    ctx = ToolContext(
        base=base, apply=apply, allow_destructive=allow_destructive, touched=[]
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": user_content})

    for step in range(1, max_steps + 1):
        try:
            content = ollama_chat(ollama, model, messages, temperature=temperature)
        except Exception as e:
            return 3, f"ollama_error: {e}", ctx.touched

        calls = parse_tool_lines(content)

        for obj in calls:
            if "final" in obj:
                return 0, str(obj["final"]), ctx.touched

        if not calls:
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": "You MUST respond with one JSON tool call per line or a single final JSON. Try again.",
                }
            )
            continue

        tool_outputs: list[str] = []
        for obj in calls:
            tool = obj.get("tool")
            args = obj.get("args", {})
            if tool not in TOOLS:
                tool_outputs.append(
                    json.dumps({"ok": False, "error": f"unknown tool: {tool}"})
                )
                continue
            try:
                out = TOOLS[tool](ctx, args)
            except Exception as e:
                out = {"ok": False, "error": f"tool_exception: {e}"}
            tool_outputs.append(json.dumps(out))

        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"STEP {step} TOOL_RESULTS:\n"
                    + "\n".join(tool_outputs)
                    + '\n\nContinue. End with {"final":"..."} including verification commands and rollback notes.'
                ),
            }
        )

    return 4, f"Max steps reached ({max_steps}) without a final response.", ctx.touched


def extract_verification_lines(final_text: str) -> list[str]:
    """Heuristic: lines beginning with '$ ' are commands."""
    out: list[str] = []
    for ln in final_text.splitlines():
        s = ln.strip()
        if s.startswith("$ "):
            out.append(s[2:])
    return out
