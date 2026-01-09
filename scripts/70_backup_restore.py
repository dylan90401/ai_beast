#!/usr/bin/env python3
"""
Backup and restore script for AI Beast project.
This script provides functionality to backup and restore project data.
"""

import os
import sys
import logging
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/backup_restore.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BackupRestore:
    def __init__(self, project_dir=None):
        self.project_dir = project_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.backup_dir = os.path.join(self.project_dir, 'backups')
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, backup_name=None, compress=True):
        """Create a backup of the project."""
        try:
            logger.info("Creating backup...")
            
            # Generate backup name
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"backup_{timestamp}"
            
            # Define backup file path
            backup_file = os.path.join(self.backup_dir, f"{backup_name}")
            
            # Get all directories to backup
            dirs_to_backup = ['config', 'data', 'models', 'outputs']
            files_to_backup = ['requirements.txt', 'README.md']
            
            # Create backup
            if compress:
                # Create compressed backup (tar.gz)
                backup_file += '.tar.gz'
                with tarfile.open(backup_file, 'w:gz') as tar:
                    for dir_name in dirs_to_backup:
                        dir_path = os.path.join(self.project_dir, dir_name)
                        if os.path.exists(dir_path):
                            tar.add(dir_path, arcname=dir_name)
                    
                    for file_name in files_to_backup:
                        file_path = os.path.join(self.project_dir, file_name)
                        if os.path.exists(file_path):
                            tar.add(file_path, arcname=file_name)
            else:
                # Create uncompressed backup (directory)
                backup_file = os.path.join(self.backup_dir, backup_name)
                os.makedirs(backup_file, exist_ok=True)
                
                for dir_name in dirs_to_backup:
                    dir_path = os.path.join(self.project_dir, dir_name)
                    if os.path.exists(dir_path):
                        shutil.copytree(dir_path, os.path.join(backup_file, dir_name))
                
                for file_name in files_to_backup:
                    file_path = os.path.join(self.project_dir, file_name)
                    if os.path.exists(file_path):
                        shutil.copy2(file_path, os.path.join(backup_file, file_name))
            
            logger.info(f"Backup created successfully: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            return None
    
    def restore_backup(self, backup_file, restore_to=None):
        """Restore from a backup file."""
        try:
            logger.info(f"Restoring from backup: {backup_file}")
            
            if not os.path.exists(backup_file):
                logger.error(f"Backup file does not exist: {backup_file}")
                return False
            
            # Determine restore location
            if not restore_to:
                restore_to = self.project_dir
            
            # Extract backup
            if backup_file.endswith('.tar.gz'):
                with tarfile.open(backup_file, 'r:gz') as tar:
                    tar.extractall(path=restore_to)
            elif backup_file.endswith('.zip'):
                with zipfile.ZipFile(backup_file, 'r') as zip_ref:
                    zip_ref.extractall(restore_to)
            else:
                logger.error(f"Unsupported backup format: {backup_file}")
                return False
            
            logger.info(f"Backup restored successfully to: {restore_to}")
            return True
            
        except Exception as e:
            logger.error(f"Backup restoration failed: {str(e)}")
            return False
    
    def list_backups(self):
        """List available backups."""
        try:
            backups = []
            for filename in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    backups.append({
                        'name': filename,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_ctime)
                    })
            
            logger.info("Available backups:")
            for backup in backups:
                logger.info(f"  {backup['name']} ({backup['size']} bytes) - {backup['created']}")
            
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
            return []
    
    def cleanup_old_backups(self, max_age_days=30):
        """Remove backups older than max_age_days."""
        try:
            logger.info(f"Cleaning up backups older than {max_age_days} days...")
            
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
            cleaned = 0
            
            for filename in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, filename)
                if os.path.isfile(file_path):
                    file_time = os.path.getctime(file_path)
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        logger.info(f"Removed old backup: {filename}")
                        cleaned += 1
            
            logger.info(f"Cleaned up {cleaned} old backups")
            return cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {str(e)}")
            return 0

def main():
    """Main function for backup/restore operations."""
    logger.info("Starting backup/restore operations...")
    
    try:
        # Create backup/restore instance
        backup_restore = BackupRestore()
        
        # Parse command line arguments
        if len(sys.argv) < 2:
            logger.info("Usage: python backup_restore.py [create|restore|list|cleanup] [options]")
            return 1
        
        command = sys.argv[1].lower()
        
        if command == 'create':
            backup_name = sys.argv[2] if len(sys.argv) > 2 else None
            compress = '--no-compress' not in sys.argv
            backup_file = backup_restore.create_backup(backup_name, compress)
            if backup_file:
                logger.info(f"Backup created: {backup_file}")
            else:
                logger.error("Backup creation failed")
                return 1
                
        elif command == 'restore':
            if len(sys.argv) < 3:
                logger.error("Restore requires backup file path")
                return 1
            backup_file = sys.argv[2]
            restore_to = sys.argv[3] if len(sys.argv) > 3 else None
            success = backup_restore.restore_backup(backup_file, restore_to)
            if success:
                logger.info("Restore completed successfully")
            else:
                logger.error("Restore failed")
                return 1
                
        elif command == 'list':
            backup_restore.list_backups()
            
        elif command == 'cleanup':
            max_age = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            cleaned = backup_restore.cleanup_old_backups(max_age)
            logger.info(f"Cleaned up {cleaned} old backups")
            
        else:
            logger.error(f"Unknown command: {command}")
            return 1
            
        return 0
        
    except Exception as e:
        logger.error(f"Backup/restore operation failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
