#!/usr/bin/env python3
"""00_verify_stack.py — Verify AI Beast stack completeness"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv


def log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "✓", "WARN": "⚠", "ERROR": "✗", "CHECK": "→"}
    print(f"[verify] {prefix.get(level, '•')} {msg}")


def check_file(path: Path, required: bool = True) -> bool:
    exists = path.exists()
    if not exists and required:
        log(f"MISSING: {path.relative_to(BASE_DIR)}", "ERROR")
    elif VERBOSE:
        log(f"Found: {path.relative_to(BASE_DIR)}", "INFO")
    return exists


def check_dir(path: Path, required: bool = True) -> bool:
    exists = path.is_dir()
    if not exists and required:
        log(f"MISSING DIR: {path.relative_to(BASE_DIR)}", "ERROR")
    elif VERBOSE:
        log(f"Found dir: {path.relative_to(BASE_DIR)}", "INFO")
    return exists


def main():
    errors = []
    warnings = []

    log("Verifying AI Beast stack...", "CHECK")
    print()

    # Core files
    log("Core files:", "CHECK")
    core_files = [
        "bin/beast",
        "beast/cli.py",
        "beast/runtime.py",
        "VERSION",
        "Makefile",
        "pyproject.toml",
        "requirements.txt",
    ]
    for f in core_files:
        if not check_file(BASE_DIR / f):
            errors.append(f"Missing core file: {f}")

    # Config files
    print()
    log("Config files:", "CHECK")
    config_files = [
        "config/paths.env",
        "config/ports.env",
        "config/features.yml",
        "config/packs.json",
    ]
    for f in config_files:
        if not check_file(BASE_DIR / f):
            errors.append(f"Missing config: {f}")

    # Config examples
    config_examples = [
        "config/paths.env.example",
        "config/ports.env.example",
        "config/profiles.env.example",
    ]
    for f in config_examples:
        if not check_file(BASE_DIR / f, required=False):
            warnings.append(f"Missing example: {f}")

    # Lib scripts
    print()
    log("Library scripts:", "CHECK")
    lib_scripts = [
        "scripts/lib/common.sh",
        "scripts/lib/deps.sh",
        "scripts/lib/docker_runtime.sh",
        "scripts/lib/runtime.sh",
        "scripts/lib/extensions.sh",
        "scripts/lib/packs.sh",
        "scripts/lib/health.sh",
        "scripts/lib/config.sh",
        "scripts/lib/backup.sh",
        "scripts/lib/ux.sh",
    ]
    for f in lib_scripts:
        if not check_file(BASE_DIR / f):
            errors.append(f"Missing lib script: {f}")

    # Extensions
    print()
    log("Extensions:", "CHECK")
    expected_extensions = [
        "qdrant",
        "redis",
        "postgres",
        "open_webui",
        "n8n",
        "minio",
        "traefik",
        "uptime_kuma",
        "otel_collector",
        "searxng",
        "flowise",
        "langflow",
        "dify",
        "apache_tika",
        "unstructured_api",
    ]
    for ext in expected_extensions:
        ext_dir = BASE_DIR / "extensions" / ext
        if not check_dir(ext_dir, required=False):
            warnings.append(f"Missing extension: {ext}")
        else:
            # Check extension files
            if not (ext_dir / "compose.fragment.yaml").exists():
                warnings.append(f"Extension {ext} missing compose.fragment.yaml")

    # Packs
    print()
    log("Pack scripts:", "CHECK")
    expected_packs = [
        "agent_builders",
        "artifact_store_minio",
        "core_services",
        "dataviz_ml",
        "defsec",
        "mapping",
        "media_synth",
        "mlx_runtime",
        "monitoring",
        "networking",
        "observability_otel",
        "osint",
        "rag_ingest_pro",
        "research_hegel_esoteric",
        "speech_stack",
    ]
    for pack in expected_packs:
        if not check_file(BASE_DIR / "scripts" / "packs" / f"{pack}.sh", required=False):
            warnings.append(f"Missing pack script: {pack}.sh")

    # Modules
    print()
    log("Python modules:", "CHECK")
    modules = ["agent", "evaluation", "monitoring", "rag", "security", "utils"]
    for mod in modules:
        mod_dir = BASE_DIR / "modules" / mod
        if not check_dir(mod_dir, required=False):
            warnings.append(f"Missing module: {mod}")
        elif not (mod_dir / "__init__.py").exists():
            warnings.append(f"Module {mod} missing __init__.py")

    # Compose files
    print()
    log("Compose files:", "CHECK")
    check_file(BASE_DIR / "compose" / "base.yml")
    if not check_dir(BASE_DIR / "compose" / "packs", required=False):
        warnings.append("Missing compose/packs/ directory")

    # Summary
    print()
    print("=" * 50)
    if errors:
        log(f"ERRORS: {len(errors)}", "ERROR")
        for e in errors:
            print(f"  • {e}")
    if warnings:
        log(f"WARNINGS: {len(warnings)}", "WARN")
        for w in warnings[:10]:  # Limit output
            print(f"  • {w}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")

    if not errors and not warnings:
        log("Stack verification PASSED!", "INFO")
        return 0
    elif not errors:
        log("Stack OK with warnings", "WARN")
        return 0
    else:
        log("Stack verification FAILED", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
