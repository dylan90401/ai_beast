#!/usr/bin/env python3
"""
Test dashboard UI functionality and backend service connectivity.

This test validates that:
1. Dashboard UI can be started
2. All API endpoints respond correctly
3. Backend services (Ollama, tools, capabilities) are accessible
4. UI features work as expected
"""

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


@pytest.fixture
def token():
    """Load dashboard token from config file."""
    token_file = BASE_DIR / "config/secrets/dashboard_token.txt"
    if not token_file.exists():
        pytest.skip("Dashboard token not found - create config/secrets/dashboard_token.txt")
    return token_file.read_text(encoding='utf-8').strip()


@pytest.fixture
def dashboard_running():
    """Check if dashboard is running and skip if not."""
    try:
        req = Request("http://127.0.0.1:8787/api/health")
        with urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if not data.get('ok'):
                pytest.skip("Dashboard not responding correctly")
            return True
    except (URLError, HTTPError):
        pytest.skip("Dashboard not running - start with: ./bin/beast dashboard")


def test_dashboard_health(dashboard_running):
    """Test that dashboard health endpoint works."""
    req = Request("http://127.0.0.1:8787/api/health")
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Health check failed"


def test_config_endpoint(token, dashboard_running):
    """Test that config endpoint returns environment config."""
    req = Request("http://127.0.0.1:8787/api/config")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Config endpoint failed"
        config = data.get('config', {})
        assert 'BASE_DIR' in config, "BASE_DIR missing from config"


def test_capabilities_endpoint(token, dashboard_running):
    """Test that capabilities endpoint returns security capabilities."""
    req = Request("http://127.0.0.1:8787/api/capabilities")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Capabilities endpoint failed"
        items = data.get('items', [])
        assert len(items) > 0, "No capabilities returned"

        # Check for security capabilities
        security_caps = [
            cap for cap in items
            if any(keyword in cap.get('id', '').lower()
                  for keyword in ['osint', 'sigint', 'offsec', 'defcon', 'security'])
        ]
        assert len(security_caps) >= 1, f"Expected at least 1 security capability, found {len(security_caps)}"


def test_tools_catalog_endpoint(token, dashboard_running):
    """Test that tools catalog endpoint returns security tools."""
    req = Request("http://127.0.0.1:8787/api/tools/catalog")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Tools catalog endpoint failed"
        items = data.get('items', [])
        # Just verify we can fetch the catalog
        assert isinstance(items, list), "Tools catalog should be a list"


def test_packs_endpoint(token, dashboard_running):
    """Test that packs endpoint returns available packs."""
    req = Request("http://127.0.0.1:8787/api/packs")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Packs endpoint failed"
        packs = data.get('packs', [])
        assert isinstance(packs, list), "Packs should be a list"


def test_extensions_endpoint(token, dashboard_running):
    """Test that extensions endpoint returns available extensions."""
    req = Request("http://127.0.0.1:8787/api/extensions")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Extensions endpoint failed"
        extensions = data.get('extensions', [])
        assert isinstance(extensions, list), "Extensions should be a list"


def test_metrics_endpoint(token, dashboard_running):
    """Test that metrics endpoint returns system metrics."""
    req = Request("http://127.0.0.1:8787/api/metrics")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Metrics endpoint failed"
        metrics = data.get('metrics', {})
        assert 'memory' in metrics or 'disk' in metrics, "Metrics should include memory or disk info"


def test_services_endpoint(token, dashboard_running):
    """Test that services endpoint returns service status."""
    req = Request("http://127.0.0.1:8787/api/services")
    req.add_header('X-Beast-Token', token)
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data.get('ok') is True, "Services endpoint failed"
        services = data.get('services', [])
        assert isinstance(services, list), "Services should be a list"


def test_llm_endpoint(token, dashboard_running):
    """Test LLM integration (optional)."""
    # First check if Ollama is available
    try:
        ollama_req = Request("http://127.0.0.1:11434/api/version")
        with urlopen(ollama_req, timeout=3):
            pass  # Ollama is running
    except (URLError, HTTPError):
        pytest.skip("Ollama not running - LLM features unavailable")

    # Test LLM analyze endpoint
    req = Request(
        "http://127.0.0.1:8787/api/llm/analyze",
        data=json.dumps({"prompt": "test"}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-Beast-Token': token}
    )
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        # Just verify the endpoint responds, don't require success
        assert 'ok' in data, "LLM endpoint should return ok field"
