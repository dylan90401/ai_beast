#!/usr/bin/env python3
"""
AI Beast Preflight Checks
This script performs comprehensive preflight checks for the AI Beast environment.
It verifies system requirements, dependencies, and configuration files.
"""

import os
import platform
import subprocess
import sys


def log_info(message):
    """Log info message with timestamp"""
    print(f"[INFO] {message}")


def log_success(message):
    """Log success message"""
    print(f"[SUCCESS] {message}")


def log_error(message):
    """Log error message"""
    print(f"[ERROR] {message}")


def log_warn(message):
    """Log warning message"""
    print(f"[WARNING] {message}")


def check_command_exists(cmd):
    """Check if command exists in PATH"""
    try:
        subprocess.run(["which", cmd], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_command_version(cmd, version_args=None):
    """Get version of command"""
    try:
        if isinstance(cmd, (list, tuple)):
            base_cmd = list(cmd)
        else:
            base_cmd = [cmd]
        args = version_args or ["--version"]
        result = subprocess.run(
            base_cmd + args, capture_output=True, text=True, check=True
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output.split("\n")[0] if output else None
    except subprocess.CalledProcessError:
        return None


def check_python_version():
    """Check Python version requirement"""
    version = platform.python_version()
    version_tuple = tuple(map(int, version.split(".")))

    if version_tuple >= (3, 11):
        log_success(f"Python {version} (>= 3.11)")
        return True
    else:
        log_error(f"Python {version} (< 3.11 required)")
        return False


def check_docker():
    """Check Docker daemon status"""
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        version = get_command_version("docker")
        log_success(f"Docker daemon running ({version})")
        return True
    except subprocess.CalledProcessError:
        log_error("Docker daemon not running")
        return False


def check_compose():
    """Check Docker Compose availability"""
    try:
        version = get_command_version("docker-compose")
        if version:
            log_success(f"Docker Compose {version}")
            return True
    except Exception:
        pass

    try:
        version = get_command_version(["docker", "compose"], ["version"])
        if version:
            log_success(f"Docker Compose {version}")
            return True
    except Exception:
        pass

    log_error("Docker Compose not available")
    return False


def check_required_commands():
    """Check all required commands exist"""
    required_commands = ["git", "python3", "docker"]
    missing_commands = []

    for cmd in required_commands:
        if check_command_exists(cmd):
            version = get_command_version(cmd)
            log_success(f"{cmd}: {version}")
        else:
            missing_commands.append(cmd)
            log_error(f"{cmd}: not found")

    return missing_commands


def check_config_files(base_dir):
    """Check configuration files exist"""
    config_files = ["config/paths.env", "config/ports.env", "config/features.yml"]

    missing_configs = []

    for file in config_files:
        file_path = os.path.join(base_dir, file)
        if os.path.exists(file_path):
            log_success(file)
        else:
            missing_configs.append(file)
            log_warn(f"{file}: not found (will use example)")

    return missing_configs


def check_directories(base_dir):
    """Check required directories exist"""
    required_dirs = ["scripts", "config", "compose"]

    for dir in required_dirs:
        dir_path = os.path.join(base_dir, dir)
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            log_success(dir_path)
        else:
            log_error(f"{dir_path}: not found")
            return False

    return True


def check_compose_file(base_dir):
    """Validate compose file"""
    compose_file = os.path.join(base_dir, "compose", "base.yml")

    if not os.path.exists(compose_file):
        log_error("compose/base.yml not found")
        return False

    try:
        compose_cmd = None
        if check_command_exists("docker"):
            if get_command_version(["docker", "compose"], ["version"]):
                compose_cmd = ["docker", "compose"]
        if not compose_cmd and check_command_exists("docker-compose"):
            compose_cmd = ["docker-compose"]
        if not compose_cmd:
            log_error("Docker Compose not available for config check")
            return False
        subprocess.run(
            compose_cmd + ["-f", compose_file, "config"],
            check=True,
            capture_output=True,
        )
        log_success("compose/base.yml valid")
        return True
    except subprocess.CalledProcessError:
        log_error("compose/base.yml invalid")
        return False


def check_python_packages():
    """Check required Python packages"""
    required_packages = {
        "pytest": "pytest",
        "ruff": "ruff",
        "pyyaml": "yaml",
    }
    missing_packages = []

    for pkg, module in required_packages.items():
        try:
            __import__(module)
            log_success(pkg)
        except ImportError:
            missing_packages.append(pkg)
            log_warn(f"{pkg}: not installed")

    return missing_packages


def main():
    """Main preflight check function"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)

    print("==> AI Beast Preflight Checks")
    print(f"    BASE_DIR: {base_dir}")
    print()

    # Check 1: Operating System
    log_info("[1/8] Checking operating system...")
    system = platform.system()
    if system == "Darwin":
        os_version = platform.mac_ver()[0]
        log_success(f"macOS {os_version}")
    elif system == "Linux":
        os_version = platform.release()
        log_success(f"Linux {os_version}")
    else:
        log_error(f"Unsupported operating system: {system}")
        return 1

    # Check 2: Required commands
    log_info("[2/8] Checking required commands...")
    missing_commands = check_required_commands()
    if missing_commands:
        log_error(f"Missing commands: {', '.join(missing_commands)}")
        log_info("Install with:")
        if system == "Darwin":
            log_info("  brew install " + " ".join(missing_commands))
        else:
            log_info("  apt install " + " ".join(missing_commands))
        return 1

    # Check 3: Python version
    log_info("[3/8] Checking Python version...")
    if not check_python_version():
        return 1

    # Check 4: Docker status
    log_info("[4/8] Checking Docker...")
    if not check_docker():
        return 1

    # Check 5: Configuration files
    log_info("[5/8] Checking configuration files...")
    missing_configs = check_config_files(base_dir)
    if missing_configs:
        log_info("Copy example files:")
        for file in missing_configs:
            example_file = f"{file}.example"
            if os.path.exists(os.path.join(base_dir, example_file)):
                log_info(f"  cp {example_file} {file}")

    # Check 6: Required directories
    log_info("[6/8] Checking directories...")
    if not check_directories(base_dir):
        return 1

    # Check 7: Docker Compose
    log_info("[7/8] Checking Docker Compose...")
    if not check_compose():
        return 1

    # Validate compose file
    log_info("[7/8] Validating compose file...")
    if not check_compose_file(base_dir):
        return 1

    # Check 8: Python packages
    log_info("[8/8] Checking Python packages...")
    missing_packages = check_python_packages()
    if missing_packages:
        log_info("Install with: pip install " + " ".join(missing_packages))

    print()
    log_success("Preflight checks complete")
    print("Next steps:")
    print("  ./bin/beast init --apply       # Initialize environment")
    print("  ./bin/beast bootstrap --apply  # Bootstrap macOS")
    print("  make check                     # Run quality gates")

    return 0


if __name__ == "__main__":
    sys.exit(main())
