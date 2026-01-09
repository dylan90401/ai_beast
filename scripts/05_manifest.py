#!/usr/bin/env python3
"""
Manifest generation script for AI Beast project.
This script creates a SHA256 manifest of all project files,
excluding sensitive directories like secrets.
"""

import hashlib
import logging
import os
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/manifest.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def generate_manifest(base_dir, output_file):
    """Generate SHA256 manifest of project files."""
    logger.info(f"Generating manifest for {base_dir}")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Define excluded directories and files
    excluded_patterns = [
        'config/secrets',
        '.git',
        'venv',
        '__pycache__',
        '.pytest_cache',
        '.DS_Store',
        '.gitignore',
        '.gitmodules',
        'logs',
        'cache',
        'backups'
    ]

    manifest_entries = []

    # Walk through project directory
    for root, dirs, files in os.walk(base_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in excluded_patterns)]

        for file in files:
            # Skip excluded files
            if any(pattern in file for pattern in excluded_patterns):
                continue

            file_path = os.path.join(root, file)

            # Calculate SHA256 hash
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                # Get relative path
                rel_path = os.path.relpath(file_path, base_dir)
                manifest_entries.append(f"{file_hash}  {rel_path}")

            except Exception as e:
                logger.warning(f"Could not hash file {file_path}: {str(e)}")

    # Sort entries for consistent output
    manifest_entries.sort()

    # Write manifest to file
    with open(output_file, 'w') as f:
        f.write(f"# AI Beast Manifest - Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Base directory: {base_dir}\n")
        f.write("#\n")
        f.write("# This manifest includes all project files except those in excluded directories\n")
        f.write("#\n")
        for entry in manifest_entries:
            f.write(f"{entry}\n")

    logger.info(f"Manifest written to {output_file}")
    logger.info(f"Total files included: {len(manifest_entries)}")

    return len(manifest_entries)

def main():
    """Main manifest generation function."""
    logger.info("Starting manifest generation...")

    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")

        # Generate manifest file name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(base_dir, 'config', 'manifests', f'manifest_{timestamp}.sha256')

        # Generate manifest
        count = generate_manifest(base_dir, output_file)

        logger.info("Manifest generation completed successfully!")
        logger.info(f"Manifest file: {output_file}")
        logger.info(f"Files included: {count}")

        return 0

    except Exception as e:
        logger.error(f"Manifest generation failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
