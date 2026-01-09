#!/usr/bin/env python3
"""
Health check script for AI Beast project.
This script performs health checks on system components.
"""

import os
import sys
import logging
import time
import psutil
import subprocess
import json
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

class HealthCheck:
    def __init__(self):
        self.results = []
    
    def check_cpu_health(self):
        """Check CPU health."""
        logger.info("Checking CPU health...")
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Check if CPU usage is too high
            is_healthy = cpu_percent < 80  # Threshold
            
            result = {
                'check': 'cpu_health',
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'is_healthy': is_healthy,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(result)
            logger.info(f"CPU health check: {'OK' if is_healthy else 'WARNING'} - {cpu_percent}%")
            return result
            
        except Exception as e:
            logger.error(f"CPU health check failed: {str(e)}")
            return None
    
    def check_memory_health(self):
        """Check memory health."""
        logger.info("Checking memory health...")
        
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Check if memory usage is too high
            is_healthy = memory_percent < 80  # Threshold
            
            result = {
                'check': 'memory_health',
                'memory_total_mb': round(memory.total / 1024 / 1024, 2),
                'memory_available_mb': round(memory.available / 1024 / 1024, 2),
                'memory_percent': memory_percent,
                'is_healthy': is_healthy,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(result)
            logger.info(f"Memory health check: {'OK' if is_healthy else 'WARNING'} - {memory_percent}%")
            return result
            
        except Exception as e:
            logger.error(f"Memory health check failed: {str(e)}")
            return None
    
    def check_disk_health(self):
        """Check disk health."""
        logger.info("Checking disk health...")
        
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Check if disk usage is too high
            is_healthy = disk_percent < 90  # Threshold
            
            result = {
                'check': 'disk_health',
                'disk_total_gb': round(disk.total / (1024**3), 2),
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'disk_free_gb': round(disk.free / (1024**3), 2),
                'disk_percent': disk_percent,
                'is_healthy': is_healthy,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(result)
            logger.info(f"Disk health check: {'OK' if is_healthy else 'WARNING'} - {disk_percent}%")
            return result
            
        except Exception as e:
            logger.error(f"Disk health check failed: {str(e)}")
            return None
    
    def check_network_health(self):
        """Check network health."""
        logger.info("Checking network health...")
        
        try:
            # Check if we can reach a known host
            result = subprocess.run(['ping', '-c', '1', '8.8.8.8'], 
                                   capture_output=True, text=True, timeout=5)
            
            is_healthy = result.returncode == 0
            
            result = {
                'check': 'network_health',
                'ping_success': is_healthy,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(result)
            logger.info(f"Network health check: {'OK' if is_healthy else 'WARNING'}")
            return result
            
        except Exception as e:
            logger.error(f"Network health check failed: {str(e)}")
            return None
    
    def check_process_health(self, process_name):
        """Check if a specific process is running."""
        logger.info(f"Checking {process_name} health...")
        
        try:
            # Find processes by name
            processes = []
            for proc in psutil.process_iter(['pid', 'name']):
                if process_name.lower() in proc.info['name'].lower():
                    processes.append(proc.info)
            
            is_healthy = len(processes) > 0
            
            result = {
                'check': f'process_health_{process_name}',
                'process_name': process_name,
                'process_count': len(processes),
                'is_healthy': is_healthy,
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(result)
            logger.info(f"{process_name} health check: {'OK' if is_healthy else 'WARNING'}")
            return result
            
        except Exception as e:
            logger.error(f"{process_name} health check failed: {str(e)}")
            return None
    
    def run_all_checks(self):
        """Run all health checks."""
        logger.info("Running all health checks...")
        
        checks = [
            self.check_cpu_health,
            self.check_memory_health,
            self.check_disk_health,
            self.check_network_health
        ]
        
        # Run basic checks
        for check in checks:
            check()
        
        # Check specific processes
        required_processes = ['python', 'ssh', 'bash']  # Add your required processes
        for process in required_processes:
            self.check_process_health(process)
        
        logger.info("All health checks completed")
    
    def get_health_status(self):
        """Get overall health status."""
        if not self.results:
            return "No checks performed"
        
        unhealthy_checks = [r for r in self.results if not r.get('is_healthy', True)]
        
        if not unhealthy_checks:
            return "All systems healthy"
        else:
            return f"WARNING: {len(unhealthy_checks)} unhealthy checks"

def main():
    """Main function for health check."""
    logger.info("Starting health check...")
    
    try:
        # Create health check instance
        health = HealthCheck()
        
        # Run all checks
        health.run_all_checks()
        
        # Print results
        logger.info("=" * 50)
        logger.info("HEALTH CHECK RESULTS")
        logger.info("=" * 50)
        
        for result in health.results:
            check_type = result['check']
            is_healthy = result.get('is_healthy', True)
            status = "OK" if is_healthy else "WARNING"
            
            logger.info(f"{check_type}: {status}")
            
            # Print detailed info for warnings
            if not is_healthy:
                for key, value in result.items():
                    if key not in ['check', 'is_healthy', 'timestamp']:
                        logger.info(f"  {key}: {value}")
        
        logger.info("=" * 50)
        logger.info(f"OVERALL STATUS: {health.get_health_status()}")
        logger.info("=" * 50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
