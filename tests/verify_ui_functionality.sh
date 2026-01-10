#!/bin/bash
# Test dashboard UI functionality by starting dashboard and running tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Dashboard UI Functionality Verification ==="
echo ""
echo "Base directory: $BASE_DIR"

# Check if token exists
TOKEN_FILE="$BASE_DIR/config/secrets/dashboard_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "Creating dashboard token..."
    mkdir -p "$(dirname "$TOKEN_FILE")"
    openssl rand -hex 32 > "$TOKEN_FILE"
    echo "✓ Token created: $TOKEN_FILE"
fi

# Check if dashboard is already running
if curl -s http://127.0.0.1:8787/api/health > /dev/null 2>&1; then
    echo "✓ Dashboard already running"
    echo ""
    echo "Running UI functionality tests..."
    cd "$BASE_DIR"
    python3 tests/test_dashboard_ui_functionality.py
else
    echo "Dashboard not running. Starting dashboard..."
    echo ""
    
    # Set up environment for dashboard - override BASE_DIR to current location
    export BASE_DIR="$BASE_DIR"
    export PYTHONPATH="$BASE_DIR:${PYTHONPATH:-}"
    
    # Source port config if available (but not paths.env which has wrong BASE_DIR)
    [ -f "$BASE_DIR/config/ports.env" ] && source "$BASE_DIR/config/ports.env" || true
    
    # Start dashboard in background
    cd "$BASE_DIR"
    python3 apps/dashboard/dashboard.py > /tmp/dashboard_test.log 2>&1 &
    DASHBOARD_PID=$!
    
    echo "Waiting for dashboard to start (PID: $DASHBOARD_PID)..."
    
    # Wait for dashboard to be ready (max 10 seconds)
    for i in {1..20}; do
        if curl -s http://127.0.0.1:8787/api/health > /dev/null 2>&1; then
            echo "✓ Dashboard started"
            break
        fi
        sleep 0.5
    done
    
    # Check if dashboard started successfully
    if ! curl -s http://127.0.0.1:8787/api/health > /dev/null 2>&1; then
        echo "✗ Dashboard failed to start"
        echo "Check logs: /tmp/dashboard_test.log"
        tail -50 /tmp/dashboard_test.log
        kill $DASHBOARD_PID 2>/dev/null || true
        exit 1
    fi
    
    echo ""
    echo "Running UI functionality tests..."
    python3 tests/test_dashboard_ui_functionality.py
    TEST_EXIT=$?
    
    # Stop dashboard
    echo ""
    echo "Stopping dashboard..."
    kill $DASHBOARD_PID 2>/dev/null || true
    wait $DASHBOARD_PID 2>/dev/null || true
    
    exit $TEST_EXIT
fi
