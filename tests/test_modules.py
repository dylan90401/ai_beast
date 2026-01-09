"""
Integration tests for AI Beast modules.
"""

import tempfile
from pathlib import Path


def test_monitoring_imports():
    """Test that monitoring module can be imported."""
    from modules.monitoring import check_service_health, collect_metrics

    assert callable(check_service_health)
    assert callable(collect_metrics)


def test_security_imports():
    """Test that security module can be imported."""
    from modules.security import (
        compute_sha256,
        scan_for_secrets,
        validate_file_permissions,
        verify_file_hash,
    )

    assert callable(compute_sha256)
    assert callable(verify_file_hash)
    assert callable(scan_for_secrets)
    assert callable(validate_file_permissions)


def test_agent_imports():
    """Test that agent module can be imported."""
    from modules.agent import AgentOrchestrator, AgentState

    assert AgentState is not None
    assert AgentOrchestrator is not None


def test_utils_imports():
    """Test that utils module can be imported."""
    from modules.utils import (
        ensure_dir,
        format_bytes,
        get_base_dir,
        read_config_file,
        run_command,
        safe_remove,
    )

    assert callable(run_command)
    assert callable(get_base_dir)
    assert callable(read_config_file)
    assert callable(ensure_dir)
    assert callable(safe_remove)
    assert callable(format_bytes)


def test_compute_sha256():
    """Test SHA256 computation."""
    from modules.security import compute_sha256

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content\n")
        f.flush()
        temp_path = Path(f.name)

    try:
        sha_result = compute_sha256(temp_path)
        assert sha_result["success"]
        assert "sha256" in sha_result
        assert len(sha_result["sha256"]) == 64  # SHA256 hex is 64 chars
    finally:
        temp_path.unlink()


def test_scan_for_secrets():
    """Test secret scanning."""
    from modules.security import scan_for_secrets

    # Should NOT flag example secrets
    safe_text = """
    API_KEY=your_api_key_here
    PASSWORD=your_password_here
    """
    findings = scan_for_secrets(safe_text)
    assert len(findings) == 0

    # Should flag actual-looking secrets
    unsafe_text = """
    API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz
    PASSWORD=MySecretP@ssw0rd123
    """
    findings = scan_for_secrets(unsafe_text)
    assert len(findings) > 0


def test_format_bytes():
    """Test byte formatting."""
    from modules.utils import format_bytes

    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"


def test_run_command_success():
    """Test successful command execution."""
    from modules.utils import run_command

    result = run_command(["echo", "test"])
    assert result["returncode"] == 0
    assert "test" in result["stdout"]


def test_run_command_failure():
    """Test failed command execution."""
    from modules.utils import run_command

    result = run_command(["false"])
    assert result["returncode"] != 0


def test_agent_state_persistence():
    """Test agent state save/load."""
    import tempfile

    from modules.agent import AgentOrchestrator

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "agent_state.json"

        # Create orchestrator with custom state file
        orchestrator = AgentOrchestrator(state_file=state_file)
        orchestrator.state.task_count = 5
        orchestrator.state.status = "active"
        orchestrator.save_state()

        # Load in new orchestrator
        orchestrator2 = AgentOrchestrator(state_file=state_file)
        orchestrator2.load_state()

        assert orchestrator2.state.task_count == 5
        assert orchestrator2.state.status == "active"


def test_ensure_dir():
    """Test directory creation."""
    import tempfile

    from modules.utils import ensure_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        new_dir = Path(tmpdir) / "test" / "nested" / "dir"
        result = ensure_dir(new_dir)

        assert result["success"]
        assert new_dir.exists()
        assert new_dir.is_dir()


def test_tools_cli_imports():
    """Test that tools CLI can be imported."""
    from tools.cli import check_health, collect_diagnostics, verify_security

    assert callable(check_health)
    assert callable(verify_security)
    assert callable(collect_diagnostics)
