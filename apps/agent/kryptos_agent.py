#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

DEFAULT_OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODEL = os.environ.get("AI_BEAST_AGENT_MODEL", "llama3.2:latest")

SAFE_SUBDIRS = {
    "config","bin","scripts","apps","docker","data","models","outputs","logs","backups","extensions",".vscode"
}

@dataclass
class RunResult:
    code: int
    out: str
    err: str

def die(msg: str, code: int = 1) -> None:
    console.print(Panel(msg, title="Error", style="red"))
    sys.exit(code)

def base_dir_from_cwd() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "bin" / "beast").exists():
        return cwd
    for p in [cwd] + list(cwd.parents)[:6]:
        if (p / "bin" / "beast").exists():
            return p
    die("Cannot locate BASE_DIR (expected bin/beast). cd into your AI Beast workspace root.", 2)
    raise RuntimeError

def is_path_allowed(base: Path, target: Path) -> bool:
    try:
        target = target.resolve()
        base = base.resolve()
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

def run_cmd(cmd: List[str], cwd: Path, apply: bool, timeout: int = 300) -> RunResult:
    # For DRYRUN: allow safe commands, block obvious destructive ones.
    destructive = {"rm","mv","cp","chmod","chown"}
    if not apply and cmd and Path(cmd[0]).name in destructive:
        return RunResult(2, "", f"[dry-run] blocked potentially destructive command: {' '.join(cmd)}")

    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    return RunResult(p.returncode, p.stdout, p.stderr)

def apply_unified_diff(base: Path, diff_text: str, apply: bool) -> str:
    if not apply:
        return "[dry-run] would apply patch via git apply/patch"
    tmp = base / ".tmp_agent_patch.diff"
    tmp.write_text(diff_text, encoding="utf-8")
    # Prefer git apply if git exists
    if (base / ".git").exists():
        rr = run_cmd(["git", "apply", str(tmp)], cwd=base, apply=True, timeout=120)
        tmp.unlink(missing_ok=True)
        if rr.code == 0:
            return "patch applied with git apply"
        return f"git apply failed:\n{rr.err}\n{rr.out}"
    rr = run_cmd(["patch", "-p0", "-i", str(tmp)], cwd=base, apply=True, timeout=120)
    tmp.unlink(missing_ok=True)
    if rr.code == 0:
        return "patch applied with patch"
    return f"patch failed:\n{rr.err}\n{rr.out}"

def ollama_chat(base_url: str, model: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
    r = requests.post(url, json=payload, timeout=300)
    if r.status_code != 200:
        die(f"Ollama chat failed: HTTP {r.status_code}\n{r.text}", 3)
    data = r.json()
    return data.get("message", {}).get("content", "")

def parse_tool_lines(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                calls.append(obj)
        except Exception:
            continue
    return calls

def tool_help() -> str:
    return json.dumps(
        {
            "tools": {
                "fs_read": {"args": {"path": "relative/path"}},
                "fs_write": {"args": {"path": "relative/path", "content": "..."}, "apply_required": True},
                "fs_list": {"args": {"path": "relative/path"}},
                "grep": {"args": {"pattern": "regex", "path": "relative/path"}},
                "shell": {"args": {"cmd": "string or list", "timeout": 300}},
                "patch": {"args": {"diff": "unified diff text"}, "apply_required": True},
            }
        },
        indent=2,
    )

def tool_fs_read(base: Path, args: Dict[str, Any], touched: List[str]) -> Dict[str, Any]:
    path = base / args["path"]
    if not is_path_allowed(base, path):
        return {"ok": False, "error": f"read denied: {args['path']}"}
    if not path.exists():
        return {"ok": False, "error": f"not found: {args['path']}"}
    touched.append(str(path.relative_to(base)))
    return {"ok": True, "content": read_text(path)}

def tool_fs_write(base: Path, args: Dict[str, Any], apply: bool, touched: List[str]) -> Dict[str, Any]:
    path = base / args["path"]
    if not is_path_allowed(base, path):
        return {"ok": False, "error": f"write denied: {args['path']}"}
    touched.append(str(path.relative_to(base)))
    msg = write_text(path, args.get("content", ""), apply=apply)
    return {"ok": True, "result": msg}

def tool_fs_list(base: Path, args: Dict[str, Any], touched: List[str]) -> Dict[str, Any]:
    path = base / args.get("path", ".")
    if path == base:
        root_ok = True
    else:
        root_ok = is_path_allowed(base, path)
    if not root_ok:
        return {"ok": False, "error": "list denied"}
    if not path.exists():
        return {"ok": False, "error": "not found"}
    touched.append(str(path.relative_to(base)) if path != base else ".")
    items = [{"name": p.name, "type": "dir" if p.is_dir() else "file"} for p in sorted(path.iterdir())]
    return {"ok": True, "items": items}

def tool_grep(base: Path, args: Dict[str, Any], touched: List[str]) -> Dict[str, Any]:
    pattern = args.get("pattern", "")
    root = base / args.get("path", ".")
    if root != base and not is_path_allowed(base, root):
        return {"ok": False, "error": "grep denied"}
    touched.append(str(root.relative_to(base)) if root != base else ".")
    rx = re.compile(pattern)
    hits = []
    for p in root.rglob("*"):
        if p.is_dir() or p.name.startswith("."):
            continue
        try:
            text = read_text(p)
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append({"file": str(p.relative_to(base)), "line": i, "text": line[:240]})
                if len(hits) >= 200:
                    return {"ok": True, "hits": hits, "truncated": True}
    return {"ok": True, "hits": hits}

def tool_shell(base: Path, args: Dict[str, Any], apply: bool, touched: List[str]) -> Dict[str, Any]:
    cmd = args.get("cmd")
    if not cmd:
        return {"ok": False, "error": "missing cmd"}
    cmd_list = shlex.split(cmd) if isinstance(cmd, str) else cmd
    touched.append(f"$ {' '.join(cmd_list)}")
    rr = run_cmd(cmd_list, cwd=base, apply=apply, timeout=int(args.get("timeout", 300)))
    return {"ok": rr.code == 0, "code": rr.code, "stdout": rr.out[-8000:], "stderr": rr.err[-8000:]}

def tool_patch(base: Path, args: Dict[str, Any], apply: bool, touched: List[str]) -> Dict[str, Any]:
    diff_text = args.get("diff", "")
    if not diff_text.strip():
        return {"ok": False, "error": "empty diff"}
    touched.append("(patch)")
    result = apply_unified_diff(base, diff_text, apply=apply)
    ok = "failed" not in result.lower()
    return {"ok": ok, "result": result}

def update_state(base: Path, model: str, ollama: str, apply: bool, task: str, summary: str, verification: List[str], files_touched: List[str]) -> None:
    state_path = base / "config" / "agent_state.json"
    if not state_path.exists():
        return
    try:
        state = json.loads(read_text(state_path))
    except Exception:
        state = {"version": 1}
    state["last_run"] = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model": model,
        "ollama_url": ollama,
        "apply": apply,
        "task": task,
        "summary": summary,
        "verification": verification,
        "files_touched": sorted(set(files_touched)),
    }
    if apply:
        write_text(state_path, json.dumps(state, indent=2), apply=True)

def run_tool_loop(
    base: Path,
    ollama: str,
    model: str,
    system_prompt: str,
    user_content: str,
    apply: bool = False,
    max_steps: int = 30,
    temperature: float = 0.2,
    extra_messages: Optional[List[Dict[str, str]]] = None,
) -> Tuple[int, str]:
    """
    Tool-using loop. Returns (exit_code, final_text_or_error).
    In DRYRUN (apply=False) the agent may run read-only shell commands and will not write/patch files.
    """

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    if extra_messages:
        # Insert extra context right after the system message
        messages = [messages[0], *extra_messages, *messages[1:]]

    for step in range(1, max_steps + 1):
        content = ollama_chat(ollama, model, messages, temperature=temperature)
        calls = parse_tool_lines(content)

        # Check for final result
        for obj in calls:
            if isinstance(obj, dict) and "final" in obj:
                return 0, str(obj["final"])

        if not calls:
            # Nudge protocol compliance
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "You MUST respond with one JSON tool call per line or a final JSON. Try again using the tool protocol.",
            })
            continue

        tool_outputs: List[str] = []
        for obj in calls:
            tool = obj.get("tool")
            args_dict = obj.get("args", {})
            if tool not in TOOLS:
                tool_outputs.append(json.dumps({"ok": False, "error": f"unknown tool: {tool}"}))
                continue
            fn = TOOLS[tool]
            try:
                if tool in ("fs_write", "patch"):
                    out = fn(base, args_dict, apply=apply)  # type: ignore
                elif tool == "shell":
                    out = fn(base, args_dict, apply=apply)  # type: ignore
                else:
                    out = fn(base, args_dict)  # type: ignore
            except Exception as e:
                out = {"ok": False, "error": f"tool_exception: {e}"}
            tool_outputs.append(json.dumps(out))

        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": (
                f"STEP {step} TOOL_RESULTS:\n"
                + "\n".join(tool_outputs)
                + "\n\nContinue. End with {\"final\":...} including verification commands and rollback notes."
            ),
        })

    return 4, f"Max steps reached ({max_steps}) without a final response."


def main() -> None:
    ap = argparse.ArgumentParser(description="KRYPTOS Builder Agent (Ollama + deterministic tools)")
    ap.add_argument("task", nargs="*", help="Task prompt (quoted string recommended)")
    ap.add_argument("--ollama", default=DEFAULT_OLLAMA)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--system", default="apps/agent/prompts/kryptos_builder.system.md")
    ap.add_argument("--apply", action="store_true", help="Actually write/patch/run (otherwise dry-run)")
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()

    base = base_dir_from_cwd()
    system_path = base / args.system
    if not system_path.exists():
        die(f"Missing system prompt: {system_path}", 2)

    task = " ".join(args.task).strip()
    if not task:
        die("Provide a task prompt.", 2)

    system_prompt = read_text(system_path)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"BASE_DIR={str(base)}\nAPPLY={args.apply}\nTOOLS={tool_help()}\n\nTASK:\n{task}"},
    ]

    console.print(Panel(f"Model: {args.model}\nOllama: {args.ollama}\nAPPLY: {args.apply}", title="KRYPTOS Agent"))

    touched: List[str] = []

    for step in range(1, args.max_steps + 1):
        content = ollama_chat(args.ollama, args.model, messages, temperature=args.temperature)
        calls = parse_tool_lines(content)

        for obj in calls:
            if "final" in obj:
                final_text = obj["final"]
                # heuristic: extract verification commands lines starting with "$ "
                verification = [ln.strip()[2:] for ln in final_text.splitlines() if ln.strip().startswith("$ ")]
                update_state(base, args.model, args.ollama, args.apply, task, final_text[:4000], verification, touched)
                console.print(Panel(final_text, title="Result", style="green"))
                return

        if not calls:
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Use the tool protocol: one JSON tool call per line, or a single final JSON."})
            continue

        tool_outputs: List[str] = []
        for obj in calls:
            tool = obj.get("tool")
            a = obj.get("args", {})
            out = {"ok": False, "error": "unknown tool"}
            if tool == "fs_read":
                out = tool_fs_read(base, a, touched)
            elif tool == "fs_write":
                out = tool_fs_write(base, a, args.apply, touched)
            elif tool == "fs_list":
                out = tool_fs_list(base, a, touched)
            elif tool == "grep":
                out = tool_grep(base, a, touched)
            elif tool == "shell":
                out = tool_shell(base, a, args.apply, touched)
            elif tool == "patch":
                out = tool_patch(base, a, args.apply, touched)
            tool_outputs.append(json.dumps(out))

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": f"STEP {step} TOOL_RESULTS:\n" + "\n".join(tool_outputs) + "\n\nContinue. End with {\"final\":...} including verification and rollback notes."})

    die(f"Max steps reached ({args.max_steps}) without a final response.", 4)

if __name__ == "__main__":
    main()
