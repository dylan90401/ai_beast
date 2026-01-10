#!/usr/bin/env python3
"""
Bootstrap script for AI Beast project initialization.
This script handles the complete setup of the project environment,
including virtual environment creation, package installation, and
initial configuration.
"""

import logging
import os
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/bootstrap.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_command(command, cwd=None, check=True):
    """Execute a shell command and handle errors."""
    try:
        logger.info(
            f"Running: {' '.join(command) if isinstance(command, list) else command}"
        )
        result = subprocess.run(
            command, cwd=cwd, check=check, capture_output=True, text=True
        )
        logger.info(
            f"Command succeeded: {' '.join(command) if isinstance(command, list) else command}"
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Command failed: {' '.join(command) if isinstance(command, list) else command}"
        )
        logger.error(f"Error output: {e.stderr}")
        raise


def setup_virtual_environment(venv_dir):
    """Create and setup Python virtual environment."""
    logger.info(f"Setting up virtual environment in {venv_dir}")

    if not os.path.exists(venv_dir):
        logger.info("Creating virtual environment...")
        run_command([sys.executable, "-m", "venv", venv_dir])
    else:
        logger.info("Virtual environment already exists")

    # Activate virtual environment and upgrade pip
    if sys.platform == "win32":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
        python_path = os.path.join(venv_dir, "Scripts", "python")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")

    run_command([pip_path, "install", "--upgrade", "pip"])
    return python_path


def install_requirements(requirements_file, python_path):
    """Install Python requirements from file."""
    logger.info(f"Installing requirements from {requirements_file}")
    if os.path.exists(requirements_file):
        run_command([python_path, "-m", "pip", "install", "-r", requirements_file])
    else:
        logger.warning(f"Requirements file not found: {requirements_file}")


def setup_project_structure(base_dir):
    """Create project directory structure."""
    logger.info("Setting up project structure...")

    dirs_to_create = [
        "apps",
        "config",
        "data",
        "models",
        "outputs",
        "scripts",
        "logs",
        "cache",
        "backups",
        "venv",
    ]

    for dir_name in dirs_to_create:
        dir_path = os.path.join(base_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")


def setup_comfyui(base_dir, comfyui_dir):
    """Setup ComfyUI if not already present."""
    logger.info("Setting up ComfyUI...")

    if not os.path.exists(comfyui_dir):
        logger.info("Cloning ComfyUI...")
        run_command(
            [
                "git",
                "clone",
                "https://github.com/comfyanonymous/ComfyUI.git",
                comfyui_dir,
            ]
        )
    else:
        logger.info("ComfyUI already exists")


def setup_git_hooks(base_dir):
    """Setup Git hooks for project."""
    logger.info("Setting up Git hooks...")

    hooks_dir = os.path.join(base_dir, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    # Create pre-commit hook
    pre_commit_hook = os.path.join(hooks_dir, "pre-commit")
    with open(pre_commit_hook, "w") as f:
        f.write("""#!/bin/bash
echo "Running pre-commit checks..."
# Add your pre-commit checks here
echo "Pre-commit checks passed!"
""")

    os.chmod(pre_commit_hook, 0o755)


def main():
    """Main bootstrap function."""
    logger.info("Starting AI Beast bootstrap process...")

    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")

        # Setup project structure
        setup_project_structure(base_dir)

        # Setup virtual environment
        venv_dir = os.path.join(base_dir, "venv")
        python_path = setup_virtual_environment(venv_dir)

        # Install requirements
        requirements_file = os.path.join(base_dir, "requirements.txt")
        install_requirements(requirements_file, python_path)

        # Setup ComfyUI
        comfyui_dir = os.path.join(base_dir, "apps", "comfyui", "ComfyUI")
        setup_comfyui(base_dir, comfyui_dir)

        # Setup Git hooks
        setup_git_hooks(base_dir)

        logger.info("Bootstrap process completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Bootstrap process failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
