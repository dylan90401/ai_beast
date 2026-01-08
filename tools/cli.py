"""
CLI tools for AI Beast.

Provides command-line utilities for maintenance and operations.
"""

import argparse
import sys
from pathlib import Path


def check_health(base_dir: Path) -> int:
    """Check health of all services."""
    from modules.monitoring import check_service_health

    services = [
        ("Ollama", 11434),
        ("ComfyUI", 8188),
        ("Qdrant", 6333),
        ("Open WebUI", 3000),
    ]

    all_healthy = True
    for name, port in services:
        result = check_service_health(name, port)
        status = "✓" if result["healthy"] else "✗"
        print(f"{status} {result['message']}")
        if not result["healthy"]:
            all_healthy = False

    return 0 if all_healthy else 1


def verify_security(base_dir: Path) -> int:
    """Run security checks."""
    from modules.security import scan_for_secrets, validate_file_permissions

    print("==> Checking for exposed secrets...")

    config_files = [
        base_dir / "config" / "ai-beast.env",
        base_dir / "config" / "features.yml",
        base_dir / ".env",
    ]

    issues = []
    for config_file in config_files:
        if not config_file.exists():
            continue

        text = config_file.read_text()
        findings = scan_for_secrets(text)

        if findings:
            print(f"  {config_file}: {len(findings)} potential secret(s) found")
            issues.extend(findings)

        # Check permissions
        perm_check = validate_file_permissions(config_file)
        if not perm_check["valid"]:
            print(f"  {config_file}: {perm_check['message']}")
            if "recommendation" in perm_check:
                print(f"    {perm_check['recommendation']}")
            issues.append(perm_check)

    if not issues:
        print("  No issues found")
        return 0
    else:
        print(f"\n  Total issues: {len(issues)}")
        return 1


def collect_diagnostics(base_dir: Path) -> int:
    """Collect diagnostic information."""
    import json

    from modules.monitoring import collect_metrics

    print("==> Collecting diagnostics...")

    metrics = collect_metrics(base_dir)

    print(f"\nTimestamp: {metrics.get('timestamp', 'N/A')}")

    if "disk_usage" in metrics:
        du = metrics["disk_usage"]
        print("\nDisk Usage:")
        print(f"  Total: {du.get('total_gb', 0)} GB")
        print(f"  Used:  {du.get('used_gb', 0)} GB ({du.get('percent_used', 0)}%)")
        print(f"  Free:  {du.get('free_gb', 0)} GB")

    # Save full metrics
    output = base_dir / ".cache" / "diagnostics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2))
    print(f"\nFull diagnostics saved to: {output}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="AI Beast CLI tools")
    parser.add_argument(
        "command", choices=["health", "security", "diagnostics"], help="Command to run"
    )
    parser.add_argument(
        "--base-dir", type=Path, help="Base directory (auto-detected if not specified)"
    )

    args = parser.parse_args()

    # Detect base directory
    if args.base_dir:
        base_dir = args.base_dir
    else:
        from modules.utils import get_base_dir

        base_dir = get_base_dir()

    if not base_dir.exists():
        print(f"Error: Base directory not found: {base_dir}", file=sys.stderr)
        return 1

    # Run command
    if args.command == "health":
        return check_health(base_dir)
    elif args.command == "security":
        return verify_security(base_dir)
    elif args.command == "diagnostics":
        return collect_diagnostics(base_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
