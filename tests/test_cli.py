"""
Tests for Python CLI.
"""

import pytest

from beast.cli import CLI


@pytest.fixture
def cli(tmp_path):
    """Create CLI instance with temp base dir."""
    base_dir = tmp_path / "ai_beast"
    base_dir.mkdir()
    (base_dir / "config").mkdir()

    return CLI(base_dir=base_dir)


def test_cli_initialization(cli):
    """Test CLI initializes correctly."""
    assert cli is not None
    assert cli.base_dir.exists()
    assert cli.config_dir.exists()


def test_show_status(cli, capsys):
    """Test status command."""
    exit_code = cli.show_status()

    assert exit_code == 0

    captured = capsys.readouterr()
    assert "AI Beast Status" in captured.out
    assert "Base directory:" in captured.out
