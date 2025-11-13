#!/bin/bash
# Demo 1 Runner Script: Inbound Call Demo
# This script runs the inbound call demonstration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DEMO 1: INBOUND CALL${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "demos/demo_1_inbound_call.py" ]; then
    echo -e "${RED}Error: Must run from project root${NC}"
    echo "Usage: ./scripts/run_demo1.sh"
    exit 1
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    PYTHON_CMD="venv/bin/python"
elif [ -d ".venv" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -d "venv-py311" ]; then
    PYTHON_CMD="venv-py311/bin/python"
elif [ -d "venv-new" ]; then
    PYTHON_CMD="venv-new/bin/python"
else
    echo -e "${YELLOW}Warning: No virtual environment found, using system python${NC}"
    PYTHON_CMD="python3"
fi

echo -e "Using Python: ${GREEN}${PYTHON_CMD}${NC}"
echo ""

# Check if PostgreSQL is running
echo -e "${YELLOW}Checking PostgreSQL...${NC}"
if ! pg_isready -q 2>/dev/null; then
    echo -e "${RED}Error: PostgreSQL is not running${NC}"
    echo "Please start PostgreSQL and try again"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL is running${NC}"

# Check if Redis is running
echo -e "${YELLOW}Checking Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}Error: Redis is not running${NC}"
    echo "Please start Redis and try again"
    exit 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi
echo -e "${GREEN}✓ .env file exists${NC}"
echo ""

# Run the demo
echo -e "${GREEN}Starting Demo 1...${NC}"
echo ""
$PYTHON_CMD demos/demo_1_inbound_call.py

echo ""
echo -e "${GREEN}Demo 1 completed!${NC}"
