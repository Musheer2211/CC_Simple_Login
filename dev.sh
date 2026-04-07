#!/bin/bash

##############################################################################
# OAuth 2.0 Server - Quick Development Server Script
# 
# Simplified script for quick local development
# Usage: ./dev.sh [port]
##############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get port from argument or use default
PORT="${1:-8000}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║   OAuth 2.0 Dev Server (Linux)            ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

echo "Setting up environment..."

# Create/activate virtual environment
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies quietly
pip install -q Flask Werkzeug 2>/dev/null || pip install Flask Werkzeug

echo -e "${GREEN}✓${NC} Ready"
echo ""
echo "Starting server on http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
python3 -c "
import os
os.environ['FLASK_PORT'] = '$PORT'
exec(open('app.py').read())
" 2>/dev/null || python3 app.py
