#!/usr/bin/env python3
"""
KRYPTOS Agent Hub — run a pipeline of agent phases (Supervisor → Implementer → Verifier, etc.)

Design goals:
- deterministic tool loop via kryptos_agent.run_tool_loop
- DRYRUN by default; writes/patches only in --apply and only for phases that allow it
- pipelines defined in apps/agent/pipelines/*.yaml
"""

import argparse
from pathlib import Path
from typing import Any

import yaml
from kryptos_agent import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA,
    base_dir_from_cwd,
    die,
    ollama_chat,
    read_text,
    run_tool_loop,
    tool_help,
)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        die(f"Missing pipeline: {path}", 2)
    return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}


def load_prompt(base: Path, rel: str) -> str:
    p = base / rel
    if not p.exists():
        die(f"Missing prompt: {p}", 2)
    return read_text(p)


def run_supervisor(
    base: Path, ollama: str, model: str, prompt_rel: str, task: str, temperature: float
) -> str:
    sys_prompt = load_prompt(base, prompt_rel)
    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": f"BASE_DIR={base}\nTASK:\n{task}\n\nReturn: plan steps + acceptance criteria + verification commands.",
        },
    ]
    return ollama_chat(ollama, model, messages, temperature=temperature)


def phase_user_content(base: Path, apply: bool, task: str, plan: str | None) -> str:
    uc = f"BASE_DIR={base}\nAPPLY={apply}\nTOOLS={tool_help()}\n\nTASK:\n{task}\n"
    if plan:
        uc += f"\nSUPERVISOR_PLAN:\n{plan}\n"
    return uc


def main() -> int:
    ap = argparse.ArgumentParser(description="KRYPTOS Agent Hub (pipeline runner)")
    ap.add_argument("task", nargs="*", help="Task prompt (quoted string recommended)")
    ap.add_argument(
        "--pipeline", default="build", help="Pipeline name (build|harden|docs|...)"
    )
    ap.add_argument("--ollama", default=DEFAULT_OLLAMA)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--apply", action="store_true", help="Allow write/patch phases that permit it"
    )
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()

    base = base_dir_from_cwd()
    task = " ".join(args.task).strip()
    if not task:
        die("Provide a task prompt.", 2)

    pipe_path = base / "apps/agent/pipelines" / f"{args.pipeline}.yaml"
    pipe = load_yaml(pipe_path)
    phases = pipe.get("phases", [])
    if not phases:
        die(f"Pipeline has no phases: {pipe_path}", 2)

    plan: str | None = None
    transcript: list[str] = []

    for idx, ph in enumerate(phases, start=1):
        role = str(ph.get("role", f"phase{idx}"))
        prompt_rel = str(
            ph.get("prompt", "apps/agent/prompts/kryptos_builder.system.md")
        )
        tool_loop = bool(ph.get("tool_loop", False))
        apply_forced = ph.get("apply_forced", None)

        # decide apply for this phase
        phase_apply = args.apply
        if isinstance(apply_forced, bool):
            phase_apply = apply_forced

        # common safety: only implementer/docs phases are allowed to apply unless pipeline forces otherwise
        if phase_apply and role not in ("implementer", "docs"):
            phase_apply = False

        if role == "supervisor":
            plan = run_supervisor(
                base, args.ollama, args.model, prompt_rel, task, args.temperature
            )
            transcript.append(f"\n=== SUPERVISOR PLAN ===\n{plan}\n")
            continue

        sys_prompt = load_prompt(base, prompt_rel)
        user_content = phase_user_content(base, phase_apply, task, plan)

        if tool_loop:
            code, final_text = run_tool_loop(
                base=base,
                ollama=args.ollama,
                model=args.model,
                system_prompt=sys_prompt,
                user_content=user_content,
                apply=phase_apply,
                max_steps=args.max_steps,
                temperature=args.temperature,
            )
            transcript.append(
                f"\n=== {role.upper()} (tool_loop, apply={phase_apply}) ===\n{final_text}\n"
            )
            if code != 0 and role != "auditor":
                # fail-fast on implementer/verifier/docs failures
                print("".join(transcript))
                return code
        else:
            # one-shot non-tool call
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_content},
            ]
            out = ollama_chat(
                args.ollama, args.model, messages, temperature=args.temperature
            )
            transcript.append(f"\n=== {role.upper()} (one-shot) ===\n{out}\n")

    print("".join(transcript))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
