#!/bin/bash
# Demo 2 with Real Call - Complete Setup Script
# This script ensures server is running and then makes a real outbound call

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DEMO 2: REAL OUTBOUND CALL SETUP${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "demos/demo_2_outbound_reminder.py" ]; then
    echo -e "${RED}Error: Must run from project root${NC}"
    echo "Usage: ./scripts/run_demo2_with_call.sh"
    exit 1
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    PYTHON_CMD="venv/bin/python"
    UVICORN_CMD="venv/bin/uvicorn"
elif [ -d ".venv" ]; then
    PYTHON_CMD=".venv/bin/python"
    UVICORN_CMD=".venv/bin/uvicorn"
elif [ -d "venv-py311" ]; then
    PYTHON_CMD="venv-py311/bin/python"
    UVICORN_CMD="venv-py311/bin/uvicorn"
elif [ -d "venv-new" ]; then
    PYTHON_CMD="venv-new/bin/python"
    UVICORN_CMD="venv-new/bin/uvicorn"
else
    echo -e "${YELLOW}Warning: No virtual environment found, using system python${NC}"
    PYTHON_CMD="python3"
    UVICORN_CMD="uvicorn"
fi

echo -e "Using Python: ${GREEN}${PYTHON_CMD}${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}=== Checking Prerequisites ===${NC}"

echo -e "${YELLOW}Checking PostgreSQL...${NC}"
if ! pg_isready -q 2>/dev/null; then
    echo -e "${RED}Error: PostgreSQL is not running${NC}"
    echo "Please start PostgreSQL and try again"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL is running${NC}"

echo -e "${YELLOW}Checking Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}Error: Redis is not running${NC}"
    echo "Please start Redis and try again"
    exit 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"

if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi
echo -e "${GREEN}✓ .env file exists${NC}"

# Check if YOUR_TEST_NUMBER is configured
TEST_NUMBER=$(grep "YOUR_TEST_NUMBER" .env | cut -d'=' -f2)
if [ -z "$TEST_NUMBER" ] || [ "$TEST_NUMBER" == "+1234567890" ]; then
    echo -e "${RED}Error: YOUR_TEST_NUMBER not configured in .env${NC}"
    echo "Please set YOUR_TEST_NUMBER to your actual phone number"
    exit 1
fi
echo -e "${GREEN}✓ Test number configured: ${TEST_NUMBER}${NC}"

# Check BASE_URL
BASE_URL=$(grep "^BASE_URL=" .env | cut -d'=' -f2)
if [ -z "$BASE_URL" ]; then
    echo -e "${RED}Error: BASE_URL not configured in .env${NC}"
    exit 1
fi
echo -e "${GREEN}✓ BASE_URL configured: ${BASE_URL}${NC}"

echo ""
echo -e "${BLUE}=== Starting Server ===${NC}"

# Check if server is already running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server already running at http://localhost:8000${NC}"
else
    echo -e "${YELLOW}Starting server in background...${NC}"
    cd server
    $UVICORN_CMD app.main:app --host 0.0.0.0 --port 8000 > ../server.log 2>&1 &
    SERVER_PID=$!
    cd ..

    # Save PID for cleanup
    echo $SERVER_PID > .server.pid

    # Wait for server to start
    echo -e "${YELLOW}Waiting for server to be ready...${NC}"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Server is ready!${NC}"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e "${RED}Error: Server failed to start after 30 seconds${NC}"
            echo "Check server.log for errors"
            exit 1
        fi
    done
fi

echo ""
echo -e "${BLUE}=== Verifying Server Health ===${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
echo "$HEALTH_RESPONSE"
echo ""

echo -e "${BLUE}=== Important Information ===${NC}"
echo -e "${YELLOW}⚠️  This will make a REAL phone call to: ${TEST_NUMBER}${NC}"
echo -e "Twilio will call this number and connect to your server"
echo -e "Make sure your phone is ready to answer!"
echo -e "Cost: ~$0.01-0.02 per minute"
echo ""
echo -e "Server running at: ${GREEN}http://localhost:8000${NC}"
echo -e "Webhook URL: ${GREEN}${BASE_URL}/api/v1/webhooks/outbound-reminder${NC}"
echo ""

# Ask for confirmation
read -p "$(echo -e ${YELLOW}Press ENTER to make the call, or Ctrl+C to cancel...${NC})"

echo ""
echo -e "${GREEN}Starting Demo 2 with real call...${NC}"
echo ""

# Run the demo with --make-call flag
$PYTHON_CMD demos/demo_2_outbound_reminder.py --make-call

echo ""
echo -e "${GREEN}Demo 2 with real call completed!${NC}"
echo ""
echo -e "${YELLOW}Note: Server is still running in background (PID: $(cat .server.pid 2>/dev/null || echo 'unknown'))${NC}"
echo -e "To stop it: kill \$(cat .server.pid)"
