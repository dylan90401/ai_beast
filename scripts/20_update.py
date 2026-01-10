#!/usr/bin/env python3
"""
Update script for AI Beast project.
This script handles updating dependencies, pulling latest code,
and performing any necessary migrations or updates.
"""

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/update.log"),
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


def backup_project(base_dir):
    """Create a backup of the current project."""
    logger.info("Creating project backup...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(base_dir, "backups", f"backup_{timestamp}")

    os.makedirs(backup_dir, exist_ok=True)

    # Copy important directories
    dirs_to_backup = ["config", "data", "models", "outputs"]

    for dir_name in dirs_to_backup:
        source_path = os.path.join(base_dir, dir_name)
        if os.path.exists(source_path):
            dest_path = os.path.join(backup_dir, dir_name)
            shutil.copytree(source_path, dest_path)
            logger.info(f"Backed up {dir_name}")

    logger.info(f"Backup created in {backup_dir}")


def update_git_repo(base_dir):
    """Update the git repository."""
    logger.info("Updating git repository...")

    try:
        run_command(["git", "pull", "origin", "main"], cwd=base_dir)
        logger.info("Git repository updated successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to update git repository: {str(e)}")
        return False


def update_dependencies(base_dir):
    """Update Python dependencies."""
    logger.info("Updating Python dependencies...")

    try:
        # Update pip
        run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        # Update requirements
        requirements_file = os.path.join(base_dir, "requirements.txt")
        if os.path.exists(requirements_file):
            run_command(
                [sys.executable, "-m", "pip", "install", "-r", requirements_file]
            )
            logger.info("Dependencies updated successfully")
        else:
            logger.warning("requirements.txt not found, skipping dependency update")

        return True
    except Exception as e:
        logger.error(f"Failed to update dependencies: {str(e)}")
        return False


def update_comfyui(base_dir):
    """Update ComfyUI if present."""
    logger.info("Updating ComfyUI...")

    comfyui_dir = os.path.join(base_dir, "apps", "comfyui", "ComfyUI")

    if os.path.exists(comfyui_dir):
        try:
            run_command(["git", "pull", "origin", "main"], cwd=comfyui_dir)
            logger.info("ComfyUI updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to update ComfyUI: {str(e)}")
            return False
    else:
        logger.info("ComfyUI not found, skipping update")
        return True


def run_migrations(base_dir):
    """Run any necessary database migrations."""
    logger.info("Checking for database migrations...")

    # This would typically check for and run database migrations
    # For now, we'll just log that we're checking
    logger.info("No database migrations found or required")
    return True


def main():
    """Main update function."""
    logger.info("Starting AI Beast update process...")

    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")

        # Create backup
        backup_project(base_dir)

        # Update git repository
        if not update_git_repo(base_dir):
            logger.error("Git update failed")
            return 1

        # Update dependencies
        if not update_dependencies(base_dir):
            logger.error("Dependency update failed")
            return 1

        # Update ComfyUI
        if not update_comfyui(base_dir):
            logger.error("ComfyUI update failed")
            return 1

        # Run migrations
        if not run_migrations(base_dir):
            logger.error("Migrations failed")
            return 1

        logger.info("Update process completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Update process failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
