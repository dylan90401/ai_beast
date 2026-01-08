#!/usr/bin/env bash
# Patch script to fix 82_assets.sh duplication
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

TARGET="$BASE_DIR/ai_beast/scripts/82_assets.sh"

echo "==> Fixing scripts/82_assets.sh duplication"

# Create backup
cp "$TARGET" "$TARGET.bak.$(date +%Y%m%d_%H%M%S)"

# Remove duplicate lines 1047-1243
sed -i.tmp '1047,$d' "$TARGET"
rm -f "$TARGET.tmp"

echo "✓ Removed duplicate lines 1047-1243"
echo "✓ Backup saved to: ${TARGET}.bak.*"
echo ""
echo "Verifying..."
lines=$(wc -l < "$TARGET" | tr -d ' ')
echo "  New line count: $lines (expected: 1046)"

if [[ "$lines" -eq 1046 ]]; then
  echo "✓ File successfully patched"
  exit 0
else
  echo "✗ Warning: Unexpected line count"
  exit 1
fi
