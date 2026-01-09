#!/usr/bin/env python3
"""
System monitoring script for AI Beast project.
This script monitors system resources in real-time.
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
        logging.FileHandler('/tmp/system_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self, interval=1):
        self.interval = interval
        self.monitoring = False
        self.data = []
    
    def get_system_info(self):
        """Get current system information."""
        try:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory info
            memory = psutil.virtual_memory()
            
            # Disk info
            disk = psutil.disk_usage('/')
            
            # Network info
            net_io = psutil.net_io_counters()
            
            # Process info
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_mb': round(proc.info['memory_info'].rss / 1024 / 1024, 2)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort processes by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            top_processes = processes[:10]  # Top 10 processes
            
            info = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_total_mb': round(memory.total / 1024 / 1024, 2),
                'memory_available_mb': round(memory.available / 1024 / 1024, 2),
                'memory_percent': memory.percent,
                'disk_total_gb': round(disk.total / (1024**3), 2),
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'disk_percent': disk.percent,
                'network_bytes_sent': net_io.bytes_sent,
                'network_bytes_recv': net_io.bytes_recv,
                'top_processes': top_processes
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting system info: {str(e)}")
            return None
    
    def start_monitoring(self, duration=None):
        """Start monitoring system resources."""
        logger.info(f"Starting system monitoring (interval: {self.interval}s)")
        
        self.monitoring = True
        start_time = time.time()
        
        try:
            while self.monitoring:
                if duration and (time.time() - start_time) > duration:
                    break
                
                info = self.get_system_info()
                if info:
                    self.data.append(info)
                    logger.info(f"CPU: {info['cpu_percent']}% | "
                               f"Memory: {info['memory_percent']}% | "
                               f"Disk: {info['disk_percent']}%")
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
        finally:
            self.monitoring = False
            logger.info("System monitoring stopped")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
    
    def save_data(self, filename=None):
        """Save monitoring data to a file."""
        if not filename:
            filename = f"system_monitor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.info(f"Monitoring data saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save data: {str(e)}")
            return False
    
    def print_summary(self):
        """Print a summary of monitoring data."""
        if not self.data:
            logger.info("No data to summarize")
            return
        
        logger.info("System Monitoring Summary:")
        logger.info("=" * 60)
        
        # Calculate averages
        cpu_avg = sum([d['cpu_percent'] for d in self.data]) / len(self.data)
        memory_avg = sum([d['memory_percent'] for d in self.data]) / len(self.data)
        disk_avg = sum([d['disk_percent'] for d in self.data]) / len(self.data)
        
        logger.info(f"Duration: {len(self.data) * self.interval} seconds")
        logger.info(f"Average CPU: {cpu_avg:.2f}%")
        logger.info(f"Average Memory: {memory_avg:.2f}%")
        logger.info(f"Average Disk: {disk_avg:.2f}%")
        
        # Top processes
        all_processes = []
        for data in self.data:
            all_processes.extend(data['top_processes'])
        
        # Count process usage
        process_count = {}
        for proc in all_processes:
            name = proc['name']
            if name not in process_count:
                process_count[name] = 0
            process_count[name] += 1
        
        logger.info("Top processes by usage:")
        for name, count in sorted(process_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"  {name}: {count} times")

def main():
    """Main function for system monitoring."""
    logger.info("Starting system monitoring...")
    
    try:
        # Create monitor instance
        monitor = SystemMonitor(interval=2)
        
        # Parse command line arguments
        duration = None
        if len(sys.argv) > 1:
            try:
                duration = int(sys.argv[1])
            except ValueError:
                logger.error("Invalid duration specified")
                return 1
        
        # Start monitoring
        monitor.start_monitoring(duration)
        
        # Save data
        monitor.save_data()
        
        # Print summary
        monitor.print_summary()
        
        logger.info("System monitoring completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"System monitoring failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
