#!/usr/bin/env python3
"""
Version management script for AI Beast project.
Handles versioning, changelog generation, and release preparation.
"""

import subprocess
import sys
from pathlib import Path


def get_version():
    """Get current version from VERSION file or git tag."""
    version_file = Path("VERSION")
    if version_file.exists():
        return version_file.read_text().strip()

    try:
        # Try to get version from git tag
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "0.0.0"

def update_version(new_version):
    """Update version in VERSION file."""
    version_file = Path("VERSION")
    version_file.write_text(new_version)
    print(f"Updated version to {new_version}")

def generate_changelog():
    """Generate changelog from git history."""
    try:
        # Get commits since last tag
        result = subprocess.run(
            [
                "git",
                "log",
                "--oneline",
                "--decorate=short",
                "--no-merges",
                "--since=$(git describe --tags --abbrev=0 --always)^",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        commits = result.stdout.strip().split("\n")
        changelog = []

        for commit in commits:
            if commit.strip():
                # Extract commit hash and message
                parts = commit.split(" ", 1)
                if len(parts) == 2:
                    hash_part, msg = parts
                    changelog.append(f"- {msg} ({hash_part[:7]})")

        return "\n".join(changelog)
    except subprocess.CalledProcessError:
        return "No changelog available"

def main():
    """Main version management function."""
    if len(sys.argv) < 2:
        print("Usage: python version.py [version|changelog|bump]")
        return

    action = sys.argv[1]

    if action == "version":
        print(get_version())
    elif action == "changelog":
        print(generate_changelog())
    elif action == "bump":
        if len(sys.argv) < 3:
            print("Usage: python version.py bump [major|minor|patch]")
            return

        current = get_version()
        version_parts = current.split(".")

        if len(version_parts) < 3:
            version_parts.extend(["0"] * (3 - len(version_parts)))

        bump_type = sys.argv[2]
        if bump_type == "patch":
            version_parts[2] = str(int(version_parts[2]) + 1)
        elif bump_type == "minor":
            version_parts[1] = str(int(version_parts[1]) + 1)
            version_parts[2] = "0"
        elif bump_type == "major":
            version_parts[0] = str(int(version_parts[0]) + 1)
            version_parts[1] = "0"
            version_parts[2] = "0"

        new_version = ".".join(version_parts)
        update_version(new_version)
        print(f"Bumped version to {new_version}")
    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
