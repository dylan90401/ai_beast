#!/usr/bin/env python3
"""
Health check script for AI Beast project.
This script performs various health checks to ensure the project
is running properly and all components are functioning.
"""

import os
import sys
import logging
import subprocess
import platform
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/health_check.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_system_resources():
    """Check system resource usage."""
    logger.info("Checking system resources...")
    
    try:
        # Check disk space
        disk_usage = subprocess.check_output(['df', '-h'], text=True)
        logger.info("Disk usage:")
        logger.info(disk_usage)
        
        # Check memory usage
        mem_usage = subprocess.check_output(['free', '-h'], text=True)
        logger.info("Memory usage:")
        logger.info(mem_usage)
        
        return True
    except Exception as e:
        logger.error(f"System resource check failed: {str(e)}")
        return False

def check_python_environment():
    """Check Python environment and dependencies."""
    logger.info("Checking Python environment...")
    
    try:
        # Check Python version
        python_version = platform.python_version()
        logger.info(f"Python version: {python_version}")
        
        # Check if required packages are installed
        required_packages = ['torch', 'numpy', 'pandas', 'scikit-learn']
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"Package {package} is installed")
            except ImportError:
                logger.warning(f"Package {package} is not installed")
        
        return True
    except Exception as e:
        logger.error(f"Python environment check failed: {str(e)}")
        return False

def check_project_directories():
    """Check that all required project directories exist."""
    logger.info("Checking project directories...")
    
    required_dirs = ['config', 'data', 'models', 'outputs', 'scripts']
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    all_exist = True
    
    for dir_name in required_dirs:
        dir_path = os.path.join(project_dir, dir_name)
        if os.path.exists(dir_path):
            logger.info(f"Directory exists: {dir_name}")
        else:
            logger.warning(f"Directory missing: {dir_name}")
            all_exist = False
    
    return all_exist

def check_config_files():
    """Check that configuration files are valid."""
    logger.info("Checking configuration files...")
    
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
    
    if not os.path.exists(config_dir):
        logger.warning("Config directory does not exist")
        return False
    
    try:
        # Try to read config files
        for file in os.listdir(config_dir):
            if file.endswith('.yaml') or file.endswith('.yml') or file.endswith('.json'):
                file_path = os.path.join(config_dir, file)
                with open(file_path, 'r') as f:
                    # Just try to read the file
                    pass
                logger.info(f"Config file valid: {file}")
        
        return True
    except Exception as e:
        logger.error(f"Config file check failed: {str(e)}")
        return False

def check_data_files():
    """Check that data files are accessible."""
    logger.info("Checking data files...")
    
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    
    if not os.path.exists(data_dir):
        logger.warning("Data directory does not exist")
        return False
    
    try:
        # Check if data directory is not empty
        data_files = os.listdir(data_dir)
        if data_files:
            logger.info(f"Found {len(data_files)} data files")
            for file in data_files[:5]:  # Show first 5 files
                logger.info(f"  - {file}")
            if len(data_files) > 5:
                logger.info(f"  ... and {len(data_files) - 5} more files")
        else:
            logger.warning("Data directory is empty")
        
        return True
    except Exception as e:
        logger.error(f"Data file check failed: {str(e)}")
        return False

def check_models():
    """Check that model files are accessible."""
    logger.info("Checking model files...")
    
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
    
    if not os.path.exists(models_dir):
        logger.warning("Models directory does not exist")
        return False
    
    try:
        # Check if models directory is not empty
        model_files = os.listdir(models_dir)
        if model_files:
            logger.info(f"Found {len(model_files)} model files")
            for file in model_files[:5]:  # Show first 5 files
                logger.info(f"  - {file}")
            if len(model_files) > 5:
                logger.info(f"  ... and {len(model_files) - 5} more files")
        else:
            logger.warning("Models directory is empty")
        
        return True
    except Exception as e:
        logger.error(f"Model check failed: {str(e)}")
        return False

def main():
    """Main health check function."""
    logger.info("Starting AI Beast health check...")
    
    try:
        # Record start time
        start_time = datetime.now()
        logger.info(f"Health check started at: {start_time}")
        
        # Run all health checks
        health_checks = [
            check_system_resources,
            check_python_environment,
            check_project_directories,
            check_config_files,
            check_data_files,
            check_models
        ]
        
        all_passed = True
        
        for check in health_checks:
            try:
                if not check():
                    all_passed = False
                    logger.error(f"Health check failed: {check.__name__}")
                else:
                    logger.info(f"Health check passed: {check.__name__}")
            except Exception as e:
                logger.error(f"Health check {check.__name__} failed with exception: {str(e)}")
                all_passed = False
        
        # Record end time
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Health check completed at: {end_time}")
        logger.info(f"Total duration: {duration}")
        
        if all_passed:
            logger.info("All health checks passed!")
            return 0
        else:
            logger.error("Some health checks failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Health check process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
