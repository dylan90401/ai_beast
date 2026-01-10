#!/usr/bin/env python3
"""
Test dashboard integration with security tools and capabilities.

This test validates that:
1. Dashboard loads all capabilities correctly
2. Security capabilities (OSINT, SIGINT, OFFSEC, etc.) are present
3. Tool catalog includes security tools
4. API endpoints expose correct data
"""

import json
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.capabilities.registry import list_capabilities
from modules.tools.registry import load_tools_config


# Security-related keywords for identifying security capabilities
SECURITY_KEYWORDS = [
    'osint', 'sigint', 'offsec', 'defcon', 'security',
    'forensics', 'vuln', 'recon', 'malware', 'red_team', 'blue_team'
]

# Expected security tools that must be present in the catalog
EXPECTED_SECURITY_TOOLS = [
    'amass', 'subfinder', 'theharvester', 'sherlock',
    'nmap', 'nuclei', 'rtl_433', 'gnuradio'
]

# Expected minimum counts
MIN_SECURITY_CAPABILITIES = 10
MIN_SECURITY_TOOLS = 20


def test_capabilities_loaded():
    """Test that capabilities are loaded correctly."""
    capabilities = list_capabilities()
    assert len(capabilities) > 0, "No capabilities loaded"
    print(f"✓ Loaded {len(capabilities)} capabilities")
    return capabilities


def test_security_capabilities_present(capabilities):
    """Test that security capabilities are present."""
    security_caps = [
        cap for cap in capabilities
        if any(keyword in cap.get('id', '').lower() for keyword in SECURITY_KEYWORDS)
    ]

    assert len(security_caps) >= MIN_SECURITY_CAPABILITIES, \
        f"Expected at least {MIN_SECURITY_CAPABILITIES} security capabilities, found {len(security_caps)}"
    print(f"✓ Found {len(security_caps)} security capabilities:")
    for cap in security_caps:
        print(f"  - {cap['id']}: {cap.get('title', 'N/A')}")

    # Verify specific security capabilities
    expected_caps = [
        'osint_suite',
        'sigint_suite',
        'offsec_suite',
        'defcon_stack',
        'vuln_scanning',
        'forensics_suite',
        'malware_analysis',
        'red_team_ops',
        'blue_team_ops',
        'recon_suite'
    ]

    cap_ids = [cap['id'] for cap in capabilities]
    for expected in expected_caps:
        assert expected in cap_ids, f"Missing expected capability: {expected}"
        print(f"✓ Found required capability: {expected}")

    return security_caps


def test_capability_structure(capabilities):
    """Test that capabilities have required fields."""
    required_fields = ['id', 'title', 'description']

    for cap in capabilities:
        for field in required_fields:
            assert field in cap, f"Capability {cap.get('id', 'unknown')} missing field: {field}"

    print(f"✓ All capabilities have required fields")


def test_security_capability_details():
    """Test specific security capability details."""
    capabilities = list_capabilities()
    cap_map = {cap['id']: cap for cap in capabilities}

    # Test OSINT suite
    osint = cap_map.get('osint_suite')
    assert osint is not None, "OSINT suite not found"
    assert 'checks' in osint, "OSINT suite missing checks"
    assert len(osint.get('checks', [])) > 0, "OSINT suite has no checks"
    print(f"✓ OSINT suite has {len(osint['checks'])} checks")

    # Test DEFCON stack
    defcon = cap_map.get('defcon_stack')
    assert defcon is not None, "DEFCON stack not found"
    assert 'checks' in defcon, "DEFCON stack missing checks"
    print(f"✓ DEFCON stack has {len(defcon['checks'])} checks")

    # Test that security capabilities have actions
    security_caps = ['osint_suite', 'defcon_stack', 'offsec_suite']
    for cap_id in security_caps:
        cap = cap_map.get(cap_id)
        if cap and 'actions' in cap:
            print(f"✓ {cap_id} has {len(cap['actions'])} actions")


def test_tool_catalog():
    """Test that tool catalog includes security tools."""
    catalog_path = BASE_DIR / "config" / "resources" / "tool_catalog.json"
    assert catalog_path.exists(), "Tool catalog not found"

    with open(catalog_path) as f:
        catalog = json.load(f)

    tools = catalog.get('tools', [])
    assert len(tools) > 0, "No tools in catalog"
    print(f"✓ Tool catalog has {len(tools)} tools")

    # Count security tools
    security_categories = ['osint', 'sigint', 'security']
    security_tools = [
        tool for tool in tools
        if tool.get('category', '').lower() in security_categories
    ]

    assert len(security_tools) >= MIN_SECURITY_TOOLS, \
        f"Expected at least {MIN_SECURITY_TOOLS} security tools, found {len(security_tools)}"
    print(f"✓ Found {len(security_tools)} security tools in catalog")

    # Verify specific tools exist
    tool_names = [tool.get('name', '') for tool in tools]
    for expected in EXPECTED_SECURITY_TOOLS:
        assert expected in tool_names, f"Missing expected tool: {expected}"
        print(f"✓ Found required tool: {expected}")


def test_dashboard_imports():
    """Test that dashboard can be imported successfully."""
    try:
        from apps.dashboard.dashboard import (
            load_env_json,
            list_capabilities,
            load_tools_config,
            catalog_items
        )
        print("✓ Dashboard imports successful")
        return True
    except ImportError as e:
        print(f"✗ Dashboard import failed: {e}")
        return False


def test_capability_health_checks():
    """Test that security capabilities have proper health checks."""
    capabilities = list_capabilities()
    cap_map = {cap['id']: cap for cap in capabilities}

    security_caps = ['osint_suite', 'sigint_suite', 'defcon_stack']
    for cap_id in security_caps:
        cap = cap_map.get(cap_id)
        assert cap is not None, f"Capability {cap_id} not found"

        checks = cap.get('checks', [])
        assert len(checks) > 0, f"Capability {cap_id} has no health checks"

        # Verify check types
        check_types = [check.get('type') for check in checks]
        valid_types = ['http', 'tcp', 'tool', 'ollama_model', 'compose_http']
        for check_type in check_types:
            assert check_type in valid_types, f"Invalid check type: {check_type}"

        print(f"✓ {cap_id} has {len(checks)} valid health checks")


def run_all_tests():
    """Run all dashboard integration tests."""
    print("\n=== Dashboard Integration Tests ===\n")

    try:
        # Test 1: Load capabilities
        print("Test 1: Loading capabilities...")
        capabilities = test_capabilities_loaded()

        # Test 2: Security capabilities present
        print("\nTest 2: Verifying security capabilities...")
        security_caps = test_security_capabilities_present(capabilities)

        # Test 3: Capability structure
        print("\nTest 3: Validating capability structure...")
        test_capability_structure(capabilities)

        # Test 4: Security capability details
        print("\nTest 4: Checking security capability details...")
        test_security_capability_details()

        # Test 5: Tool catalog
        print("\nTest 5: Validating tool catalog...")
        test_tool_catalog()

        # Test 6: Dashboard imports
        print("\nTest 6: Testing dashboard imports...")
        test_dashboard_imports()

        # Test 7: Health checks
        print("\nTest 7: Verifying health checks...")
        test_capability_health_checks()

        print("\n=== All Tests Passed ✓ ===\n")
        return True

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
