"""
AI Beast Agent Runner

Implements agent execution framework following AI Toolkit best practices.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runs AI agents with test datasets and collects responses."""

    def __init__(
        self, agent_config: dict[str, Any] | None = None, trace_enabled: bool = True
    ):
        """Initialize agent runner."""
        self.config = agent_config or self._default_config()
        self.trace_enabled = trace_enabled

        if self.trace_enabled:
            self._setup_tracing()

    def _default_config(self) -> dict[str, Any]:
        """Return default agent config."""
        return {
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model": "llama3.2:latest",
            "temperature": 0.7,
            "max_tokens": 2048,
            "retry_attempts": 3,
            "timeout_seconds": 30,
            "system_prompt": None,
            "fail_on_error": False,
        }

    def _setup_tracing(self):
        """Setup tracing/observability."""
        trace_dir = Path("outputs/traces")
        trace_dir.mkdir(parents=True, exist_ok=True)

        self.trace_file = trace_dir / "agent_traces.jsonl"
        logger.info(f"Tracing enabled: {self.trace_file}")

    def run_single(self, prompt: str, test_id: str | None = None) -> dict[str, Any]:
        """Run agent on single prompt."""
        trace_id = test_id or f"trace_{id(prompt)}"

        try:
            response = self._call_agent(prompt)

            result = {
                "test_id": test_id,
                "prompt": prompt,
                "response": response,
                "status": "success",
                "trace_id": trace_id,
            }

            if self.trace_enabled:
                self._log_trace(result)

            return result

        except Exception as e:
            logger.error(f"Agent run failed: {e}")

            result = {
                "test_id": test_id,
                "prompt": prompt,
                "response": None,
                "status": "error",
                "error": str(e),
                "trace_id": trace_id,
            }

            if self.trace_enabled:
                self._log_trace(result)

            return result

    def run_batch(
        self, test_dataset_path: Path, output_path: Path | None = None
    ) -> list[dict[str, Any]]:
        """Run agent on batch of test cases."""
        if not test_dataset_path.exists():
            raise FileNotFoundError(f"Test dataset not found: {test_dataset_path}")

        test_cases = []
        with open(test_dataset_path) as f:
            for line in f:
                test_cases.append(json.loads(line))

        logger.info(f"Running agent on {len(test_cases)} test cases")

        results = []
        for test_case in test_cases:
            result = self.run_single(
                prompt=test_case["input"], test_id=test_case.get("id")
            )
            results.append(result)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                for result in results:
                    f.write(json.dumps(result) + "\n")
            logger.info(f"Results saved to: {output_path}")

        return results

    def _call_agent(self, prompt: str) -> str:
        """Call agent/model with prompt."""
        provider = str(self.config.get("provider", "ollama")).lower()
        if provider == "ollama":
            return self._call_ollama(prompt)
        if provider == "echo":
            return f"Agent response to: {prompt[:200]}"
        raise ValueError(f"Unsupported provider: {provider}")

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama /api/chat with a single user prompt."""
        try:
            import requests
        except Exception as exc:
            if self.config.get("fail_on_error", False):
                raise RuntimeError(f"requests not available: {exc}") from exc
            logger.warning("requests not available, returning fallback response")
            return f"Agent response to: {prompt[:200]}"

        base_url = str(self.config.get("base_url", "http://127.0.0.1:11434")).rstrip(
            "/"
        )
        url = f"{base_url}/api/chat"
        model = str(self.config.get("model", "llama3.2:latest"))
        temperature = float(self.config.get("temperature", 0.7))
        timeout = int(self.config.get("timeout_seconds", 30))
        retries = int(self.config.get("retry_attempts", 3))
        system_prompt = self.config.get("system_prompt")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": str(system_prompt)})
        messages.append({"role": "user", "content": prompt})

        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    url,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                    timeout=timeout,
                )
                if r.status_code != 200:
                    raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:2000]}")
                data = r.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    raise RuntimeError("Empty response from Ollama")
                return content
            except Exception as exc:
                last_err = exc
                if attempt < retries:
                    time.sleep(min(0.5 * attempt, 2.0))
                continue

        if self.config.get("fail_on_error", False) and last_err is not None:
            raise last_err
        logger.warning("Ollama call failed, returning fallback response: %s", last_err)
        return f"Agent response to: {prompt[:200]}"

    def _log_trace(self, result: dict[str, Any]):
        """Log trace to file."""
        if not hasattr(self, "trace_file"):
            return

        with open(self.trace_file, "a") as f:
            f.write(json.dumps(result) + "\n")
