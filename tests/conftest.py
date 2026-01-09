"""Pytest configuration and shared fixtures.

Task 2.5 - Enhanced test configuration for coverage.
"""
import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "benchmark: mark test as benchmark")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless AI_BEAST_INTEGRATION=1."""
    if os.environ.get("AI_BEAST_INTEGRATION") in ("1", "true", "True"):
        return
    skip = pytest.mark.skip(reason="Set AI_BEAST_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
