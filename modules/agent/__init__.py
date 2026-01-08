"""
Agent module for AI Beast.

Provides agent orchestration, state management, and tool execution.
"""

import importlib.util
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AgentState:
    """Agent state snapshot."""

    task: str = ""
    step: int = 0
    max_steps: int = 0
    apply_mode: bool = False
    files_touched: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    status: str = "idle"  # "running", "completed", "failed"
    task_count: int = 0
    result: str | None = None
    error: str | None = None


class AgentOrchestrator:
    """
    Orchestrate agent execution with state tracking.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        apply: bool = False,
        state_file: Path | None = None,
    ):
        if base_dir is None:
            from modules.utils import get_base_dir

            base_dir = get_base_dir()

        self.base_dir = base_dir
        self.apply = apply
        self.state_file = state_file or (base_dir / "config" / "agent_state.json")
        self.state = AgentState(apply_mode=apply)
        self.current_state: AgentState | None = self.state

    def load_state(self) -> AgentState:
        """Load agent state from disk."""
        if not self.state_file.exists():
            return self.state

        try:
            import json

            data = json.loads(self.state_file.read_text())
            state_data = data.get("current", data)
            self.state = AgentState(**state_data)
            self.current_state = self.state
            return self.state
        except Exception:
            return self.state

    def save_state(self, state: AgentState | None = None) -> None:
        """Save agent state to disk."""
        import json
        from datetime import UTC, datetime

        state = state or self.state
        data = {
            "current": asdict(state),
            "last_updated": datetime.now(UTC).isoformat(),
        }

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, indent=2))

    def _load_agent_core(self):
        core_path = self.base_dir / "apps" / "agent" / "core.py"
        if not core_path.exists():
            raise FileNotFoundError(f"Missing agent core: {core_path}")
        spec = importlib.util.spec_from_file_location("ai_beast_agent_core", core_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load agent core module spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _tools_from_touched(self, touched: list[str]) -> list[str]:
        tools = set()
        for item in touched:
            if item.startswith("$ "):
                tools.add("shell")
            elif item == "(patch)":
                tools.add("patch")
            elif item.startswith("GET "):
                tools.add("http_get")
        return sorted(tools)

    def run_task(self, task: str, max_steps: int = 30) -> AgentState:
        """
        Run an agent task with state tracking.

        Args:
            task: Task description
            max_steps: Maximum number of steps

        Returns:
            Final agent state
        """
        state = AgentState(
            task=task,
            step=0,
            max_steps=max_steps,
            apply_mode=self.apply,
            files_touched=[],
            tools_used=[],
            status="running",
            task_count=self.state.task_count + 1,
        )

        self.state = state
        self.current_state = state
        self.save_state()

        try:
            core = self._load_agent_core()
            system_path = (
                self.base_dir
                / "apps"
                / "agent"
                / "prompts"
                / "kryptos_builder.system.md"
            )
            if not system_path.exists():
                raise FileNotFoundError(f"Missing system prompt: {system_path}")
            system_prompt = system_path.read_text(encoding="utf-8", errors="replace")

            user_content = (
                f"BASE_DIR={self.base_dir}\nAPPLY={self.apply}\n"
                f"TOOLS={core.tool_help()}\n\nTASK:\n{task}"
            )

            temperature = float(os.environ.get("AI_BEAST_AGENT_TEMPERATURE", "0.2"))
            code, final_text, touched = core.run_tool_loop(
                base=self.base_dir,
                ollama=core.DEFAULT_OLLAMA,
                model=core.DEFAULT_MODEL,
                system_prompt=system_prompt,
                user_content=user_content,
                apply=self.apply,
                allow_destructive=False,
                max_steps=max_steps,
                temperature=temperature,
            )

            state.files_touched = touched
            state.tools_used = self._tools_from_touched(touched)
            state.step = max_steps if code == 4 else 1
            if code == 0:
                state.status = "completed"
                state.result = final_text
            else:
                state.status = "failed"
                state.error = final_text
        except Exception as exc:
            state.status = "failed"
            state.error = str(exc)

        self.save_state()
        return state


def create_agent(base_dir: Path, apply: bool = False) -> AgentOrchestrator:
    """
    Factory function to create an agent orchestrator.

    Args:
        base_dir: Base directory of installation
        apply: Whether to run in APPLY mode

    Returns:
        AgentOrchestrator instance
    """
    return AgentOrchestrator(base_dir=base_dir, apply=apply)
