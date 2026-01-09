#!/usr/bin/env python3
"""
Preflight check script for AI Beast project.
This script verifies that all required dependencies and configurations
are present before running the main application.
"""

import logging
import os
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/preflight.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_python_version():
    """Check Python version requirement."""
    logger.info("Checking Python version...")

    required_version = (3, 8)
    current_version = sys.version_info[:2]

    if current_version >= required_version:
        logger.info(f"Python version OK: {sys.version}")
        return True
    else:
        logger.error(f"Python version too low. Required: {required_version}, Got: {current_version}")
        return False

def check_required_tools():
    """Check for required system tools."""
    logger.info("Checking required system tools...")

    required_tools = ['git', 'pip3', 'python3']
    missing_tools = []

    for tool in required_tools:
        try:
            subprocess.run(['which', tool], check=True, capture_output=True)
            logger.info(f"Tool found: {tool}")
        except subprocess.CalledProcessError:
            logger.warning(f"Tool not found: {tool}")
            missing_tools.append(tool)

    if missing_tools:
        logger.error(f"Missing required tools: {', '.join(missing_tools)}")
        return False

    return True

def check_environment_variables():
    """Check for required environment variables."""
    logger.info("Checking environment variables...")

    required_vars = ['PYTHONPATH', 'HOME']
    missing_vars = []

    for var in required_vars:
        if var not in os.environ:
            logger.warning(f"Environment variable not set: {var}")
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        return False

    return True

def check_project_structure(base_dir):
    """Check that project structure is correct."""
    logger.info("Checking project structure...")

    required_dirs = [
        'apps',
        'config',
        'data',
        'models',
        'outputs',
        'scripts',
        'logs',
        'cache',
        'backups'
    ]

    missing_dirs = []

    for dir_name in required_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if not os.path.exists(dir_path):
            logger.warning(f"Directory missing: {dir_path}")
            missing_dirs.append(dir_name)

    if missing_dirs:
        logger.error(f"Missing directories: {', '.join(missing_dirs)}")
        return False

    return True

def check_virtual_environment():
    """Check if virtual environment is active."""
    logger.info("Checking virtual environment...")

    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        logger.info("Virtual environment is active")
        return True
    else:
        logger.warning("Virtual environment is not active")
        return False

def check_comfyui_setup(base_dir):
    """Check if ComfyUI is properly set up."""
    logger.info("Checking ComfyUI setup...")

    comfyui_path = os.path.join(base_dir, 'apps', 'comfyui', 'ComfyUI')

    if os.path.exists(comfyui_path):
        logger.info("ComfyUI directory found")
        return True
    else:
        logger.warning("ComfyUI directory not found")
        return False

def main():
    """Main preflight check function."""
    logger.info("Starting preflight checks...")

    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")

        # Run all checks
        checks = [
            check_python_version,
            check_required_tools,
            check_environment_variables,
            lambda: check_project_structure(base_dir),
            check_virtual_environment,
            lambda: check_comfyui_setup(base_dir),
        ]

        all_passed = True

        for check in checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                logger.error(f"Check {check.__name__} failed with error: {str(e)}")
                all_passed = False

        if all_passed:
            logger.info("All preflight checks passed!")
            return 0
        else:
            logger.error("Some preflight checks failed!")
            return 1

    except Exception as e:
        logger.error(f"Preflight check process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
