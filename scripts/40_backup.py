#!/usr/bin/env python3
"""
Backup script for AI Beast project.
This script handles creating backups of important project data
and configurations for disaster recovery.
"""

import os
import sys
import shutil
import logging
import zipfile
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_backup_directory(base_dir):
    """Create backup directory with timestamp."""
    logger.info("Creating backup directory...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(base_dir, 'backups', f'backup_{timestamp}')
    
    os.makedirs(backup_dir, exist_ok=True)
    logger.info(f"Backup directory created: {backup_dir}")
    
    return backup_dir

def backup_project_files(base_dir, backup_dir):
    """Backup important project files and directories."""
    logger.info("Backing up project files...")
    
    # Define what to backup
    backup_sources = [
        'config',
        'data',
        'models',
        'outputs',
        'scripts',
        'requirements.txt',
        'README.md'
    ]
    
    backup_count = 0
    
    for source in backup_sources:
        source_path = os.path.join(base_dir, source)
        if os.path.exists(source_path):
            try:
                if os.path.isdir(source_path):
                    dest_path = os.path.join(backup_dir, source)
                    shutil.copytree(source_path, dest_path)
                else:
                    dest_path = os.path.join(backup_dir, source)
                    shutil.copy2(source_path, dest_path)
                
                backup_count += 1
                logger.info(f"Backed up: {source}")
            except Exception as e:
                logger.error(f"Failed to backup {source}: {str(e)}")
        else:
            logger.warning(f"Source not found: {source}")
    
    logger.info(f"Backed up {backup_count} items")
    return True

def backup_database(base_dir, backup_dir):
    """Backup database files (if any)."""
    logger.info("Checking for database backups...")
    
    # Look for common database directories
    db_dirs = ['db', 'database', 'data/db']
    
    for db_dir in db_dirs:
        db_path = os.path.join(base_dir, db_dir)
        if os.path.exists(db_path):
            try:
                dest_path = os.path.join(backup_dir, 'database')
                shutil.copytree(db_path, dest_path)
                logger.info(f"Backed up database from {db_dir}")
            except Exception as e:
                logger.error(f"Failed to backup database {db_dir}: {str(e)}")
    
    return True

def create_zip_backup(base_dir, backup_dir):
    """Create a zip archive of the backup."""
    logger.info("Creating zip archive of backup...")
    
    try:
        zip_filename = f"{backup_dir}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_path = os.path.relpath(file_path, backup_dir)
                    zipf.write(file_path, arc_path)
        
        logger.info(f"Created zip backup: {zip_filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to create zip backup: {str(e)}")
        return False

def cleanup_old_backups(base_dir, max_backups=5):
    """Remove old backups to save space."""
    logger.info("Cleaning up old backups...")
    
    backups_dir = os.path.join(base_dir, 'backups')
    
    if os.path.exists(backups_dir):
        try:
            # Get all backup directories
            backup_dirs = []
            for item in os.listdir(backups_dir):
                item_path = os.path.join(backups_dir, item)
                if os.path.isdir(item_path) and item.startswith('backup_'):
                    backup_dirs.append((item_path, os.path.getctime(item_path)))
            
            # Sort by creation time (newest first)
            backup_dirs.sort(key=lambda x: x[1], reverse=True)
            
            # Remove oldest backups if we have too many
            for backup_dir, _ in backup_dirs[max_backups:]:
                shutil.rmtree(backup_dir)
                logger.info(f"Removed old backup: {os.path.basename(backup_dir)}")
            
            logger.info(f"Cleaned up old backups, keeping {min(len(backup_dirs), max_backups)} backups")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {str(e)}")
            return False
    else:
        logger.info("No backups directory found")
        return True

def main():
    """Main backup function."""
    logger.info("Starting AI Beast backup process...")
    
    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")
        
        # Create backup directory
        backup_dir = create_backup_directory(base_dir)
        
        # Backup project files
        if not backup_project_files(base_dir, backup_dir):
            logger.error("Project file backup failed")
            return 1
        
        # Backup database
        if not backup_database(base_dir, backup_dir):
            logger.error("Database backup failed")
            return 1
        
        # Create zip archive
        if not create_zip_backup(base_dir, backup_dir):
            logger.error("Zip backup creation failed")
            return 1
        
        # Cleanup old backups
        if not cleanup_old_backups(base_dir):
            logger.error("Cleanup of old backups failed")
            return 1
        
        logger.info("Backup process completed successfully!")
        logger.info(f"Backup created at: {backup_dir}")
        return 0
            
    except Exception as e:
        logger.error(f"Backup process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
