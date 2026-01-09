"""Core evaluation framework for AI Beast workspace.

This module provides a flexible evaluation framework for assessing
workspace configurations, docker services, extensions, and overall health.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class MetricStatus(Enum):
    """Status of an evaluation metric."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    name: str
    status: MetricStatus
    score: float | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class EvaluationResult:
    """Complete evaluation result."""

    category: str
    metrics: list[MetricResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_metric(self, metric: MetricResult) -> None:
        """Add a metric result."""
        self.metrics.append(metric)

    def compute_summary(self) -> None:
        """Compute summary statistics from metrics."""
        if not self.metrics:
            self.summary = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "skipped": 0,
                "pass_rate": 0.0,
            }
            return

        total = len(self.metrics)
        passed = sum(1 for m in self.metrics if m.status == MetricStatus.PASS)
        failed = sum(1 for m in self.metrics if m.status == MetricStatus.FAIL)
        warnings = sum(1 for m in self.metrics if m.status == MetricStatus.WARN)
        skipped = sum(1 for m in self.metrics if m.status == MetricStatus.SKIP)
        evaluated_count = total - skipped

        self.summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "skipped": skipped,
            "pass_rate": passed / evaluated_count if evaluated_count > 0 else 0.0,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category,
            "metrics": [m.to_dict() for m in self.metrics],
            "summary": self.summary,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


class Evaluator:
    """Main evaluation framework class.

    Provides methods to evaluate various aspects of the AI Beast workspace:
    - System health and dependencies
    - Docker services and containers
    - Extension installations
    - Configuration validity
    - Resource availability
    """

    def __init__(
        self, root_dir: Path | str | None = None, config: dict[str, Any] | None = None
    ):
        """Initialize evaluator.

        Args:
            root_dir: Root directory of the AI Beast workspace
            config: Optional evaluation configuration
        """
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.config = config or {"metrics": ["accuracy", "exact_match"]}
        self.metrics = {
            "accuracy": self._accuracy,
            "exact_match": self._exact_match,
        }
        self.results: list[EvaluationResult] = []

    def evaluate(
        self, predictions: list[dict], ground_truth: list[dict]
    ) -> dict[str, float]:
        """Evaluate predictions against ground truth."""
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")

        metric_names = self.config.get("metrics", list(self.metrics.keys()))
        scores: dict[str, float] = {}
        for name in metric_names:
            metric_fn = self.metrics.get(name)
            if metric_fn is None:
                continue
            scores[name] = metric_fn(predictions, ground_truth)
        return scores

    def _accuracy(self, predictions: list[dict], ground_truth: list[dict]) -> float:
        """Compute accuracy by comparing 'value' fields."""
        if not predictions:
            return 0.0
        matches = 0
        for pred, truth in zip(predictions, ground_truth, strict=True):
            if pred.get("value") == truth.get("value"):
                matches += 1
        return matches / len(predictions)

    def _exact_match(self, predictions: list[dict], ground_truth: list[dict]) -> float:
        """Return 1.0 if all values match, otherwise 0.0."""
        if not predictions:
            return 0.0
        for pred, truth in zip(predictions, ground_truth, strict=True):
            if pred.get("value") != truth.get("value"):
                return 0.0
        return 1.0

    def save_results(self, results: dict[str, Any], output_path: Path) -> None:
        """Save evaluation results to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))

    def evaluate_system_health(self) -> EvaluationResult:
        """Evaluate system health and dependencies."""
        start_time = time.time()
        result = EvaluationResult(category="system_health")

        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 11):
            result.add_metric(
                MetricResult(
                    name="python_version",
                    status=MetricStatus.PASS,
                    message=f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
                )
            )
        else:
            result.add_metric(
                MetricResult(
                    name="python_version",
                    status=MetricStatus.FAIL,
                    message=f"Python {python_version.major}.{python_version.minor} < required 3.11",
                )
            )

        # Check key directories exist
        key_dirs = ["beast", "modules", "compose", "config"]
        for dir_name in key_dirs:
            dir_path = self.root_dir / dir_name
            if dir_path.exists():
                result.add_metric(
                    MetricResult(
                        name=f"directory_{dir_name}",
                        status=MetricStatus.PASS,
                        message=f"Directory exists: {dir_name}",
                    )
                )
            else:
                result.add_metric(
                    MetricResult(
                        name=f"directory_{dir_name}",
                        status=MetricStatus.FAIL,
                        message=f"Missing directory: {dir_name}",
                    )
                )

        # Check pyproject.toml
        pyproject = self.root_dir / "pyproject.toml"
        if pyproject.exists():
            result.add_metric(
                MetricResult(
                    name="pyproject_toml",
                    status=MetricStatus.PASS,
                    message="pyproject.toml found",
                )
            )
        else:
            result.add_metric(
                MetricResult(
                    name="pyproject_toml",
                    status=MetricStatus.FAIL,
                    message="pyproject.toml missing",
                )
            )

        result.duration_seconds = time.time() - start_time
        result.compute_summary()
        self.results.append(result)
        return result

    def evaluate_docker_services(self) -> EvaluationResult:
        """Evaluate Docker services and containers."""
        start_time = time.time()
        result = EvaluationResult(category="docker_services")

        # Check Docker availability
        try:
            subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            result.add_metric(
                MetricResult(
                    name="docker_available",
                    status=MetricStatus.PASS,
                    message="Docker daemon is accessible",
                )
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            result.add_metric(
                MetricResult(
                    name="docker_available",
                    status=MetricStatus.FAIL,
                    message=f"Docker not accessible: {str(e)}",
                )
            )
            result.duration_seconds = time.time() - start_time
            result.compute_summary()
            self.results.append(result)
            return result

        # Check Docker Compose availability
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            result.add_metric(
                MetricResult(
                    name="docker_compose_available",
                    status=MetricStatus.PASS,
                    message="Docker Compose is available",
                )
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            result.add_metric(
                MetricResult(
                    name="docker_compose_available",
                    status=MetricStatus.FAIL,
                    message=f"Docker Compose not available: {str(e)}",
                )
            )

        # Check compose files
        compose_base = self.root_dir / "compose" / "base.yml"
        if compose_base.exists():
            result.add_metric(
                MetricResult(
                    name="compose_base_file",
                    status=MetricStatus.PASS,
                    message="Base compose file exists",
                )
            )
        else:
            result.add_metric(
                MetricResult(
                    name="compose_base_file",
                    status=MetricStatus.WARN,
                    message="Base compose file missing",
                )
            )

        result.duration_seconds = time.time() - start_time
        result.compute_summary()
        self.results.append(result)
        return result

    def evaluate_configuration(self) -> EvaluationResult:
        """Evaluate workspace configuration."""
        start_time = time.time()
        result = EvaluationResult(category="configuration")

        # Check config directory
        config_dir = self.root_dir / "config"
        if config_dir.exists():
            result.add_metric(
                MetricResult(
                    name="config_directory",
                    status=MetricStatus.PASS,
                    message="Config directory exists",
                )
            )
        else:
            result.add_metric(
                MetricResult(
                    name="config_directory",
                    status=MetricStatus.FAIL,
                    message="Config directory missing",
                )
            )
            result.duration_seconds = time.time() - start_time
            result.compute_summary()
            self.results.append(result)
            return result

        # Check for important config files (non-critical, just informational)
        config_files = ["allowlists.json", "models.json"]
        for config_file in config_files:
            config_path = config_dir / "resources" / config_file
            if config_path.exists():
                result.add_metric(
                    MetricResult(
                        name=f"config_{config_file}",
                        status=MetricStatus.PASS,
                        message=f"Config file exists: {config_file}",
                    )
                )
            else:
                result.add_metric(
                    MetricResult(
                        name=f"config_{config_file}",
                        status=MetricStatus.WARN,
                        message=f"Optional config file missing: {config_file}",
                    )
                )

        result.duration_seconds = time.time() - start_time
        result.compute_summary()
        self.results.append(result)
        return result

    def evaluate_extensions(self) -> EvaluationResult:
        """Evaluate installed extensions."""
        start_time = time.time()
        result = EvaluationResult(category="extensions")

        extensions_dir = self.root_dir / "extensions"
        if not extensions_dir.exists():
            result.add_metric(
                MetricResult(
                    name="extensions_directory",
                    status=MetricStatus.FAIL,
                    message="Extensions directory missing",
                )
            )
            result.duration_seconds = time.time() - start_time
            result.compute_summary()
            self.results.append(result)
            return result

        result.add_metric(
            MetricResult(
                name="extensions_directory",
                status=MetricStatus.PASS,
                message="Extensions directory exists",
            )
        )

        # Count extensions
        try:
            extensions = [
                d
                for d in extensions_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            result.add_metric(
                MetricResult(
                    name="extensions_count",
                    status=MetricStatus.PASS,
                    score=float(len(extensions)),
                    message=f"Found {len(extensions)} extension(s)",
                    details={"extensions": [e.name for e in extensions]},
                )
            )
        except Exception as e:
            result.add_metric(
                MetricResult(
                    name="extensions_count",
                    status=MetricStatus.WARN,
                    message=f"Could not count extensions: {str(e)}",
                )
            )

        result.duration_seconds = time.time() - start_time
        result.compute_summary()
        self.results.append(result)
        return result

    def run_all_evaluations(self) -> list[EvaluationResult]:
        """Run all evaluation categories."""
        self.results = []

        self.evaluate_system_health()
        self.evaluate_docker_services()
        self.evaluate_configuration()
        self.evaluate_extensions()

        return self.results

    def generate_report(self, output_format: str = "json") -> str:
        """Generate evaluation report.

        Args:
            output_format: Format for the report ("json" or "text")

        Returns:
            Formatted report string
        """
        if output_format == "json":
            return json.dumps(
                {
                    "results": [r.to_dict() for r in self.results],
                    "timestamp": datetime.utcnow().isoformat(),
                },
                indent=2,
            )

        elif output_format == "text":
            lines = ["=" * 60]
            lines.append("AI BEAST WORKSPACE EVALUATION REPORT")
            lines.append("=" * 60)
            lines.append(f"Generated: {datetime.utcnow().isoformat()}")
            lines.append("")

            for eval_result in self.results:
                lines.append(f"\n{eval_result.category.upper().replace('_', ' ')}")
                lines.append("-" * 60)
                lines.append(f"Duration: {eval_result.duration_seconds:.2f}s")
                lines.append(
                    f"Summary: {eval_result.summary.get('passed', 0)}/{eval_result.summary.get('total', 0)} passed"
                )
                if eval_result.summary.get("failed", 0) > 0:
                    lines.append(f"  FAILURES: {eval_result.summary.get('failed', 0)}")
                if eval_result.summary.get("warnings", 0) > 0:
                    lines.append(
                        f"  WARNINGS: {eval_result.summary.get('warnings', 0)}"
                    )
                lines.append("")

                for metric in eval_result.metrics:
                    status_icon = {
                        MetricStatus.PASS: "✓",
                        MetricStatus.FAIL: "✗",
                        MetricStatus.WARN: "⚠",
                        MetricStatus.SKIP: "○",
                    }.get(metric.status, "?")

                    lines.append(f"  {status_icon} {metric.name}: {metric.message}")
                    if metric.details:
                        for key, value in metric.details.items():
                            lines.append(f"      {key}: {value}")

            lines.append("\n" + "=" * 60)
            return "\n".join(lines)

        else:
            raise ValueError(f"Unknown output format: {output_format}")

    def save_report(self, output_path: Path | str, output_format: str = "json") -> None:
        """Save evaluation report to file.

        Args:
            output_path: Path to save the report
            output_format: Format for the report ("json" or "text")
        """
        report = self.generate_report(output_format)
        Path(output_path).write_text(report, encoding="utf-8")
