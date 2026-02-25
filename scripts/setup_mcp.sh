#!/bin/bash
# ============================================================
# WC Optimizer — One-Click MCP Auto-Configuration (Mac/Linux)
# Run: chmod +x scripts/setup_mcp.sh && ./scripts/setup_mcp.sh
# ============================================================

echo ""
echo "========================================"
echo " WC Optimizer - MCP Auto-Setup"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/setup_mcp.py" "$@"
elif command -v python &>/dev/null; then
    python "$SCRIPT_DIR/setup_mcp.py" "$@"
else
    echo "ERROR: Python is not installed."
    echo "Install Python 3.8+:"
    echo "  macOS:  brew install python3"
    echo "  Ubuntu: sudo apt install python3"
    exit 1
fi
