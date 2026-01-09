"""
Smoke tests for AI Beast / Kryptos buildability.
"""

import os
from pathlib import Path


def test_repo_structure():
    """Verify essential directories exist."""
    base = Path(__file__).parent.parent
    assert (base / "bin").exists()
    assert (base / "scripts").exists()
    assert (base / "config").exists()
    assert (base / "beast").exists()


def test_config_files_exist():
    """Verify config file examples exist."""
    base = Path(__file__).parent.parent / "config"
    assert (base / "ports.env.example").exists()
    assert (base / "paths.env.example").exists()
    assert (base / "features.yml").exists()


def test_cli_executable():
    """Verify beast CLI is executable."""
    beast_cli = Path(__file__).parent.parent / "bin" / "beast"
    assert beast_cli.exists()
    assert os.access(beast_cli, os.X_OK)


def test_scripts_lib_exists():
    """Verify scripts/lib helpers exist."""
    lib_dir = Path(__file__).parent.parent / "scripts" / "lib"
    assert lib_dir.exists()
    assert (lib_dir / "common.sh").exists()
