#!/bin/bash
# Code Quality Check Script
# Runs code formatting and linting tools

set -e  # Exit on error

echo "🔍 Running code quality checks..."
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run this script from the project root."
    exit 1
fi

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Flag to track if any checks fail
FAILED=0

# Function to run a check
run_check() {
    local name=$1
    local cmd=$2

    echo "▶ Running $name..."
    if eval "$cmd"; then
        echo -e "${GREEN}✓${NC} $name passed"
    else
        echo -e "${RED}✗${NC} $name failed"
        FAILED=1
    fi
    echo ""
}

# 1. Black formatting check
run_check "Black (format check)" "uv run black --check backend/"

# 2. Ruff linting
run_check "Ruff (linting)" "uv run ruff check backend/"

# 3. Run tests if requested
if [ "$1" == "--with-tests" ]; then
    run_check "Pytest (tests)" "cd backend && uv run pytest"
fi

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some quality checks failed.${NC}"
    echo ""
    echo "To auto-fix formatting issues, run:"
    echo "  uv run black backend/"
    echo ""
    echo "To auto-fix some linting issues, run:"
    echo "  uv run ruff check backend/ --fix"
    exit 1
fi
