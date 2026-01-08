"""
Security module for AI Beast.

Provides scanning, validation, and security enforcement.
"""

import hashlib
from pathlib import Path


def compute_sha256(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


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

    actual_hash = compute_sha256(file_path)
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
