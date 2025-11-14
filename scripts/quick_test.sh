#!/bin/bash
# Quick Test Script - Assumes services are already running
# Use this if you already have server/redis/ngrok running

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Voice Agent Quick Test${NC}"
echo ""

# Check if server is running
if ! nc -z localhost 8000 2>/dev/null; then
    echo -e "${YELLOW}Server not running on port 8000${NC}"
    echo "Start server with: venv-new/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir server"
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"
echo ""

# Show menu
echo "Quick Test Options:"
echo ""
echo "  1) INBOUND - Show number to call"
echo "  2) OUTBOUND - Make test call to you"
echo ""
read -p "Choose [1-2]: " choice

case $choice in
    1)
        venv-new/bin/python scripts/test_voice_calls.py inbound
        ;;
    2)
        venv-new/bin/python scripts/test_voice_calls.py outbound
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
