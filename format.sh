#!/bin/bash
# Code Formatting Script
# Auto-formats code using black and ruff

set -e  # Exit on error

echo "🎨 Formatting code..."
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run this script from the project root."
    exit 1
fi

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "▶ Running Black formatter..."
uv run black backend/
echo -e "${GREEN}✓${NC} Black formatting complete"
echo ""

echo "▶ Running Ruff auto-fixes..."
uv run ruff check backend/ --fix
echo -e "${GREEN}✓${NC} Ruff fixes applied"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ Code formatting complete!${NC}"
echo ""
echo "Run './quality.sh' to verify all quality checks pass."
