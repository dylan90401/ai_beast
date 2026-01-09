#!/usr/bin/env python3
"""
Cleanup script for AI Beast project.
This script handles cleaning up temporary files, logs, and other
unnecessary data to maintain a clean project environment.
"""

import os
import sys
import shutil
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/cleanup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def cleanup_temp_files(base_dir):
    """Clean up temporary files."""
    logger.info("Cleaning up temporary files...")
    
    temp_dirs = [
        os.path.join(base_dir, 'temp'),
        os.path.join(base_dir, 'tmp'),
        os.path.join(base_dir, 'logs', 'temp')
    ]
    
    cleaned_files = 0
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        os.remove(file_path)
                        cleaned_files += 1
                logger.info(f"Cleaned temporary files from {temp_dir}")
            except Exception as e:
                logger.error(f"Failed to clean {temp_dir}: {str(e)}")
    
    logger.info(f"Cleaned {cleaned_files} temporary files")
    return True

def cleanup_logs(base_dir):
    """Clean up old log files."""
    logger.info("Cleaning up log files...")
    
    log_dir = os.path.join(base_dir, 'logs')
    
    if os.path.exists(log_dir):
        try:
            # Keep only recent log files (last 7 days)
            cutoff_date = datetime.now().timestamp() - (7 * 24 * 60 * 60)
            
            for file in os.listdir(log_dir):
                file_path = os.path.join(log_dir, file)
                if os.path.isfile(file_path):
                    file_time = os.path.getctime(file_path)
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        logger.info(f"Removed old log file: {file}")
            
            logger.info("Log cleanup completed")
            return True
        except Exception as e:
            logger.error(f"Failed to clean logs: {str(e)}")
            return False
    else:
        logger.info("No logs directory found")
        return True

def cleanup_cache(base_dir):
    """Clean up cache files."""
    logger.info("Cleaning up cache files...")
    
    cache_dirs = [
        os.path.join(base_dir, '.cache'),
        os.path.join(base_dir, 'cache')
    ]
    
    cleaned_files = 0
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        os.remove(file_path)
                        cleaned_files += 1
                logger.info(f"Cleaned cache files from {cache_dir}")
            except Exception as e:
                logger.error(f"Failed to clean {cache_dir}: {str(e)}")
    
    logger.info(f"Cleaned {cleaned_files} cache files")
    return True

def cleanup_outputs(base_dir):
    """Clean up output files (optional - can be configured)."""
    logger.info("Cleaning up output files...")
    
    # This is a safety check - we don't want to accidentally delete important outputs
    # In a real implementation, you might want to be more selective
    outputs_dir = os.path.join(base_dir, 'outputs')
    
    if os.path.exists(outputs_dir):
        # For now, just log that we found outputs
        logger.info(f"Found outputs directory: {outputs_dir}")
        logger.info("Note: Output files are not automatically cleaned to prevent data loss")
        return True
    else:
        logger.info("No outputs directory found")
        return True

def main():
    """Main cleanup function."""
    logger.info("Starting AI Beast cleanup process...")
    
    try:
        # Get project base directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")
        
        # Run all cleanup operations
        cleanup_operations = [
            cleanup_temp_files,
            cleanup_logs,
            cleanup_cache,
            cleanup_outputs
        ]
        
        all_passed = True
        
        for operation in cleanup_operations:
            try:
                if not operation(base_dir):
                    all_passed = False
            except Exception as e:
                logger.error(f"Cleanup operation {operation.__name__} failed: {str(e)}")
                all_passed = False
        
        if all_passed:
            logger.info("Cleanup process completed successfully!")
            return 0
        else:
            logger.error("Some cleanup operations failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Cleanup process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
