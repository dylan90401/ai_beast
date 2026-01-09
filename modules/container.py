"""Dependency injection container for AI Beast.

Provides centralized configuration and dependency management.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass
class AppContext:
    """Application context with all configuration."""

    # Directories
    base_dir: Path
    guts_dir: Path
    heavy_dir: Path
    models_dir: Path
    data_dir: Path
    outputs_dir: Path
    cache_dir: Path
    backup_dir: Path
    log_dir: Path

    # Runtime settings
    apply_mode: bool = False
    verbose: bool = False
    dry_run: bool = True

    # Service URLs
    ollama_url: str = "http://127.0.0.1:11434"
    qdrant_url: str = "http://127.0.0.1:6333"

    # Ports
    ports: dict[str, int] = field(default_factory=dict)

    # Feature flags
    features: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> AppContext:
        """Load configuration from environment variables.

        Args:
            base_dir: Base directory (detected if not provided)

        Returns:
            AppContext instance
        """
        if base_dir is None:
            base_dir = cls._detect_base_dir()

        # Load paths
        paths = cls._load_paths_env(base_dir)

        # Load ports
        ports = cls._load_ports_env(base_dir)

        # Load features
        features = cls._load_features_env(base_dir)

        return cls(
            base_dir=base_dir,
            guts_dir=Path(paths.get("GUTS_DIR", str(base_dir))),
            heavy_dir=Path(paths.get("HEAVY_DIR", str(base_dir))),
            models_dir=Path(paths.get("MODELS_DIR", str(base_dir / "models"))),
            data_dir=Path(paths.get("DATA_DIR", str(base_dir / "data"))),
            outputs_dir=Path(paths.get("OUTPUTS_DIR", str(base_dir / "outputs"))),
            cache_dir=Path(paths.get("CACHE_DIR", str(base_dir / "cache"))),
            backup_dir=Path(paths.get("BACKUP_DIR", str(base_dir / "backups"))),
            log_dir=Path(paths.get("LOG_DIR", str(base_dir / "logs"))),
            ollama_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
            qdrant_url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333"),
            ports=ports,
            features=features,
        )

    @staticmethod
    def _detect_base_dir() -> Path:
        """Detect BASE_DIR from environment or filesystem."""
        if base := os.environ.get("BASE_DIR"):
            return Path(base)

        # Walk up from cwd to find project root
        cwd = Path.cwd()
        for path in [cwd, *list(cwd.parents)]:
            if (path / "bin" / "beast").exists():
                return path

        return cwd

    @staticmethod
    def _load_paths_env(base_dir: Path) -> dict[str, str]:
        """Load paths.env file."""
        paths_file = base_dir / "config" / "paths.env"
        if not paths_file.exists():
            return {}

        paths: dict[str, str] = {}
        for line in paths_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                paths[key.strip()] = value.strip().strip('"').strip("'")

        return paths

    @staticmethod
    def _load_ports_env(base_dir: Path) -> dict[str, int]:
        """Load ports.env file."""
        ports_file = base_dir / "config" / "ports.env"
        if not ports_file.exists():
            return {}

        ports: dict[str, int] = {}
        for line in ports_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                try:
                    ports[key.strip()] = int(value.strip().strip('"').strip("'"))
                except ValueError:
                    pass

        return ports

    @staticmethod
    def _load_features_env(base_dir: Path) -> dict[str, bool]:
        """Load features.env file."""
        features_file = base_dir / "config" / "features.env"
        if not features_file.exists():
            return {}

        features: dict[str, bool] = {}
        for line in features_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                value_str = value.strip().strip('"').strip("'")
                features[key.strip()] = value_str.lower() in ("1", "true", "yes")

        return features


class Container:
    """Dependency injection container.

    Usage:
        container = Container(context)
        llm_manager = container.get(LLMManager)
        rag_ingestor = container.get(RAGIngestor)
    """

    def __init__(self, context: AppContext):
        """Initialize container with application context.

        Args:
            context: Application context with configuration
        """
        self.context = context
        self._singletons: dict[type, Any] = {}
        self._factories: dict[type, Callable[[], Any]] = {}

    def register(self, interface: type[T], factory: Callable[[], T]) -> None:
        """Register a factory for a type.

        Args:
            interface: Type to register factory for
            factory: Factory callable that creates instances
        """
        self._factories[interface] = factory

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """Register a singleton instance.

        Args:
            interface: Type to register instance for
            instance: Pre-created instance
        """
        self._singletons[interface] = instance

    def get(self, interface: type[T]) -> T:
        """Get instance of a type.

        Args:
            interface: Type to get instance of

        Returns:
            Instance of requested type

        Raises:
            ValueError: If no factory registered for type
        """
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]

        # Check factories
        if interface in self._factories:
            instance = self._factories[interface]()
            self._singletons[interface] = instance
            return instance

        raise ValueError(f"No factory registered for {interface}")

    def has(self, interface: type) -> bool:
        """Check if a type is registered.

        Args:
            interface: Type to check

        Returns:
            True if type has a factory or singleton registered
        """
        return interface in self._singletons or interface in self._factories

    def setup_defaults(self) -> None:
        """Setup default factories for common types."""
        # Import here to avoid circular imports
        from modules.llm import LLMManager
        from modules.agent import AgentOrchestrator
        from modules.evaluation import Evaluator

        self.register(
            LLMManager,
            lambda: LLMManager(base_dir=self.context.base_dir),
        )

        self.register(
            AgentOrchestrator,
            lambda: AgentOrchestrator(
                base_dir=self.context.base_dir,
                apply=self.context.apply_mode,
            ),
        )

        self.register(
            Evaluator,
            lambda: Evaluator(root_dir=self.context.base_dir),
        )

    def reset(self) -> None:
        """Clear all singletons (useful for testing)."""
        self._singletons.clear()


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get global container instance.

    Returns:
        Global Container instance (created on first call)
    """
    global _container
    if _container is None:
        context = AppContext.from_env()
        _container = Container(context)
        _container.setup_defaults()
    return _container


def get_context() -> AppContext:
    """Get global application context.

    Returns:
        AppContext from global container
    """
    return get_container().context


def reset_container() -> None:
    """Reset global container (for testing)."""
    global _container
    _container = None
