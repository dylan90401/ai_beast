#!/usr/bin/env python3
"""
Monitoring script for AI Beast project.
This script monitors the project's performance and resource usage.
"""

import os
import sys
import logging
import time
import psutil
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Monitor:
    def __init__(self, duration=60, interval=5):
        self.duration = duration  # Total monitoring duration in seconds
        self.interval = interval  # Monitoring interval in seconds
        self.start_time = None
        self.monitoring = False
        
    def get_system_stats(self):
        """Get current system statistics."""
        stats = {}
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        stats['cpu_percent'] = cpu_percent
        
        # Memory usage
        memory = psutil.virtual_memory()
        stats['memory_total'] = memory.total
        stats['memory_available'] = memory.available
        stats['memory_percent'] = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        stats['disk_total'] = disk.total
        stats['disk_used'] = disk.used
        stats['disk_percent'] = disk.percent
        
        # Network usage
        net_io = psutil.net_io_counters()
        stats['bytes_sent'] = net_io.bytes_sent
        stats['bytes_recv'] = net_io.bytes_recv
        
        return stats
    
    def get_process_stats(self):
        """Get stats for the main process."""
        stats = {}
        
        # Get current process
        process = psutil.Process()
        
        # CPU usage
        cpu_percent = process.cpu_percent()
        stats['process_cpu_percent'] = cpu_percent
        
        # Memory usage
        memory_info = process.memory_info()
        stats['process_memory_rss'] = memory_info.rss
        stats['process_memory_vms'] = memory_info.vms
        
        # Process start time
        stats['process_start_time'] = process.create_time()
        
        return stats
    
    def log_stats(self, stats):
        """Log system statistics."""
        logger.info("System Statistics:")
        logger.info(f"  CPU Usage: {stats['cpu_percent']:.2f}%")
        logger.info(f"  Memory Usage: {stats['memory_percent']:.2f}%")
        logger.info(f"  Disk Usage: {stats['disk_percent']:.2f}%")
        logger.info(f"  Bytes Sent: {stats['bytes_sent']}")
        logger.info(f"  Bytes Received: {stats['bytes_recv']}")
    
    def log_process_stats(self, stats):
        """Log process statistics."""
        logger.info("Process Statistics:")
        logger.info(f"  CPU Usage: {stats['process_cpu_percent']:.2f}%")
        logger.info(f"  Memory RSS: {stats['process_memory_rss'] / (1024*1024):.2f} MB")
        logger.info(f"  Memory VMS: {stats['process_memory_vms'] / (1024*1024):.2f} MB")
    
    def start_monitoring(self):
        """Start monitoring for the specified duration."""
        self.start_time = datetime.now()
        self.monitoring = True
        
        logger.info(f"Starting monitoring for {self.duration} seconds with {self.interval} second intervals")
        
        try:
            start_time = time.time()
            iteration = 0
            
            while time.time() - start_time < self.duration:
                iteration += 1
                logger.info(f"--- Monitoring Iteration {iteration} ---")
                
                # Get system stats
                system_stats = self.get_system_stats()
                self.log_stats(system_stats)
                
                # Get process stats
                process_stats = self.get_process_stats()
                self.log_process_stats(process_stats)
                
                # Save to file
                self.save_stats_to_file({
                    'timestamp': datetime.now().isoformat(),
                    'system': system_stats,
                    'process': process_stats
                })
                
                # Wait for next interval
                time.sleep(self.interval)
            
            self.monitoring = False
            end_time = datetime.now()
            logger.info(f"Monitoring completed at: {end_time}")
            logger.info(f"Total monitoring time: {end_time - self.start_time}")
            
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
            self.monitoring = False
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
            self.monitoring = False
    
    def save_stats_to_file(self, stats):
        """Save statistics to a JSON file."""
        try:
            filename = f"monitor_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Statistics saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save statistics: {str(e)}")

def main():
    """Main monitoring function."""
    logger.info("Starting AI Beast monitoring...")
    
    try:
        # Parse command line arguments
        duration = 60  # Default 60 seconds
        interval = 5   # Default 5 seconds
        
        if len(sys.argv) > 1:
            duration = int(sys.argv[1])
        if len(sys.argv) > 2:
            interval = int(sys.argv[2])
        
        # Create monitor instance
        monitor = Monitor(duration=duration, interval=interval)
        
        # Start monitoring
        monitor.start_monitoring()
        
        logger.info("Monitoring completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Monitoring process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
