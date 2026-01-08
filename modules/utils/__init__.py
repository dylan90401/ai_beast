"""
Utility functions for AI Beast.

Provides common helper functions used across modules.
"""

import os
import subprocess
from pathlib import Path


def run_command(
    cmd: list, cwd: Path | None = None, timeout: int = 300
) -> tuple[int, str, str]:
    """
    Run a shell command and return results.

    Args:
        cmd: Command as list of strings
        cwd: Working directory
        timeout: Timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def get_base_dir() -> Path:
    """
    Get the base directory of the AI Beast installation.

    Returns:
        Path to base directory
    """
    # Try environment variable first
    if "BASE_DIR" in os.environ:
        return Path(os.environ["BASE_DIR"])

    # Try to find bin/beast
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "bin" / "beast").exists():
            return parent

    # Fallback to current directory
    return current


def read_config_file(config_path: Path) -> dict:
    """
    Read a configuration file (JSON or YAML).

    Args:
        config_path: Path to config file

    Returns:
        Dict with configuration
    """
    if not config_path.exists():
        return {}

    content = config_path.read_text()

    if config_path.suffix == ".json":
        import json

        return json.loads(content)
    elif config_path.suffix in (".yml", ".yaml"):
        try:
            import yaml

            return yaml.safe_load(content) or {}
        except ImportError:
            # Fallback to simple parsing if PyYAML not available
            result = {}
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if value in ("true", "True"):
                        result[key] = True
                    elif value in ("false", "False"):
                        result[key] = False
                    else:
                        result[key] = value
            return result

    return {}


def ensure_dir(path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path
    """
    path.mkdir(parents=True, exist_ok=True)


def safe_remove(path: Path) -> bool:
    """
    Safely remove a file or directory.

    Args:
        path: Path to remove

    Returns:
        True if removed, False if not found or error
    """
    try:
        if path.is_file():
            path.unlink()
            return True
        elif path.is_dir():
            import shutil

            shutil.rmtree(path)
            return True
        return False
    except Exception:
        return False


def format_bytes(bytes_val: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"
