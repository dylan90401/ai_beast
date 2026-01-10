"""
Security module for AI Beast.

Provides scanning, validation, and security enforcement.
"""

import hashlib
from pathlib import Path


def _is_placeholder_secret(value: str) -> bool:
    value = value.strip().lower()
    placeholders = {
        "your_api_key_here",
        "your_password_here",
        "your_secret_here",
        "your_token_here",
        "changeme",
        "password",
        "example",
        "example_password",
    }
    if value in placeholders:
        return True
    if value.startswith("your_") and value.endswith("_here"):
        return True
    return False


def compute_sha256(file_path: Path) -> dict:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Dict with success flag and SHA256 hex digest
    """
    if not file_path.exists():
        return {"success": False, "error": "File does not exist", "sha256": ""}

    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
    except OSError as exc:
        return {"success": False, "error": str(exc), "sha256": ""}

    return {"success": True, "sha256": sha256_hash.hexdigest()}


def verify_file_hash(file_path: Path, expected_hash: str) -> bool:
    """
    Verify file hash matches expected value.

    Args:
        file_path: Path to file
        expected_hash: Expected SHA256 hash

    Returns:
        True if hash matches, False otherwise
    """
    if not file_path.exists():
        return False

    result = compute_sha256(file_path)
    if not result.get("success"):
        return False
    actual_hash = result.get("sha256", "")
    return actual_hash.lower() == expected_hash.lower()


def scan_for_secrets(text: str) -> list:
    """
    Scan text for potential secrets/credentials.

    Args:
        text: Text to scan

    Returns:
        List of potential secret patterns found
    """
    import re

    patterns = [
        (r'api[_-]?key[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
        (r'password[\s=:]+["\']?([^\s"\']+)["\']?', "Password"),
        (r'secret[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "Secret"),
        (r'token[\s=:]+["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', "Token"),
        (r"(sk-[a-zA-Z0-9]{20,})", "OpenAI API Key"),
    ]

    findings = []
    for pattern, name in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            candidate = match.group(1) if match.groups() else match.group(0)
            if _is_placeholder_secret(candidate):
                continue
            findings.append(
                {"type": name, "pattern": pattern, "position": match.start()}
            )

    return findings


def validate_file_permissions(file_path: Path) -> dict:
    """
    Validate file has appropriate permissions.

    Args:
        file_path: Path to file

    Returns:
        Dict with validation results
    """
    import stat

    if not file_path.exists():
        return {"valid": False, "message": "File does not exist"}

    mode = file_path.stat().st_mode

    # Check if world-readable
    if mode & stat.S_IROTH:
        return {
            "valid": False,
            "message": "File is world-readable",
            "recommendation": f"Run: chmod o-r {file_path}",
        }

    # Check if world-writable
    if mode & stat.S_IWOTH:
        return {
            "valid": False,
            "message": "File is world-writable",
            "recommendation": f"Run: chmod o-w {file_path}",
        }

    return {"valid": True, "message": "Permissions OK"}
