#!/usr/bin/env python3
"""
Performance testing script for AI Beast project.
This script tests the performance of various components.
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
        logging.FileHandler('/tmp/performance_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PerformanceTest:
    def __init__(self):
        self.results = []
    
    def test_cpu_performance(self, duration=10):
        """Test CPU performance."""
        logger.info("Testing CPU performance...")
        
        start_time = time.time()
        start_cpu = psutil.cpu_percent(interval=1)
        
        # Simple CPU intensive task
        total = 0
        while time.time() - start_time < duration:
            total += sum(range(1000))
        
        end_cpu = psutil.cpu_percent(interval=1)
        end_time = time.time()
        
        result = {
            'test': 'cpu_performance',
            'duration': end_time - start_time,
            'cpu_before': start_cpu,
            'cpu_after': end_cpu,
            'cpu_change': end_cpu - start_cpu,
            'total_calculations': total,
            'timestamp': datetime.now().isoformat()
        }
        
        self.results.append(result)
        logger.info(f"CPU test completed: {result}")
        return result
    
    def test_memory_performance(self, iterations=1000):
        """Test memory performance."""
        logger.info("Testing memory performance...")
        
        start_memory = psutil.virtual_memory().percent
        
        # Allocate memory
        data = []
        for i in range(iterations):
            data.append([0] * 1000)
        
        end_memory = psutil.virtual_memory().percent
        
        result = {
            'test': 'memory_performance',
            'iterations': iterations,
            'memory_before': start_memory,
            'memory_after': end_memory,
            'memory_change': end_memory - start_memory,
            'timestamp': datetime.now().isoformat()
        }
        
        self.results.append(result)
        logger.info(f"Memory test completed: {result}")
        return result
    
    def test_disk_performance(self, file_size_mb=10):
        """Test disk performance."""
        logger.info("Testing disk performance...")
        
        # Create test file
        test_file = f"test_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tmp"
        file_size = file_size_mb * 1024 * 1024
        
        # Write test
        start_time = time.time()
        with open(test_file, 'wb') as f:
            f.write(os.urandom(file_size))
        write_time = time.time() - start_time
        
        # Read test
        start_time = time.time()
        with open(test_file, 'rb') as f:
            data = f.read()
        read_time = time.time() - start_time
        
        # Clean up
        os.remove(test_file)
        
        result = {
            'test': 'disk_performance',
            'file_size_mb': file_size_mb,
            'write_time': write_time,
            'read_time': read_time,
            'timestamp': datetime.now().isoformat()
        }
        
        self.results.append(result)
        logger.info(f"Disk test completed: {result}")
        return result
    
    def run_all_tests(self):
        """Run all performance tests."""
        logger.info("Running all performance tests...")
        
        try:
            self.test_cpu_performance()
            self.test_memory_performance()
            self.test_disk_performance()
            
            logger.info("All performance tests completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Performance test failed: {str(e)}")
            return False
    
    def save_results(self, filename=None):
        """Save test results to a file."""
        if not filename:
            filename = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Performance results saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
            return False
    
    def print_summary(self):
        """Print a summary of test results."""
        logger.info("Performance Test Summary:")
        logger.info("=" * 50)
        
        for result in self.results:
            logger.info(f"Test: {result['test']}")
            for key, value in result.items():
                if key != 'test' and key != 'timestamp':
                    logger.info(f"  {key}: {value}")
            logger.info("-" * 30)

def main():
    """Main function for performance testing."""
    logger.info("Starting performance testing...")
    
    try:
        # Create performance test instance
        perf_test = PerformanceTest()
        
        # Run all tests
        success = perf_test.run_all_tests()
        
        if success:
            # Print summary
            perf_test.print_summary()
            
            # Save results
            perf_test.save_results()
            
            logger.info("Performance testing completed successfully!")
            return 0
        else:
            logger.error("Performance testing failed")
            return 1
            
    except Exception as e:
        logger.error(f"Performance testing failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
