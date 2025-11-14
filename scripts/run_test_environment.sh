#!/bin/bash
# Voice Agent Test Environment Setup Script
#
# This script boots up all required services for testing the voice agent locally:
# 1. PostgreSQL (via Docker or local)
# 2. Redis (via Docker or local)
# 3. ngrok tunnel (for Twilio webhooks)
# 4. FastAPI server (uvicorn)
# 5. Interactive testing menu

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Voice Agent Test Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a service is running
check_service() {
    local service=$1
    local port=$2
    nc -z localhost "$port" 2>/dev/null
}

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

if ! command_exists ngrok; then
    echo -e "${RED}✗ ngrok not found${NC}"
    echo -e "${YELLOW}Install ngrok: https://ngrok.com/download${NC}"
    exit 1
fi
echo -e "${GREEN}✓ ngrok found${NC}"

if [ ! -d "venv-new" ]; then
    echo -e "${RED}✗ Virtual environment 'venv-new' not found${NC}"
    echo -e "${YELLOW}Run: python3 -m venv venv-new && source venv-new/bin/activate && pip install -r server/requirements.txt${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Virtual environment found${NC}"

echo ""

# Step 2: Start/Check PostgreSQL
echo -e "${YELLOW}[2/5] Checking PostgreSQL...${NC}"

if check_service postgres 5432; then
    echo -e "${GREEN}✓ PostgreSQL is running on port 5432${NC}"
else
    echo -e "${YELLOW}! PostgreSQL not detected on port 5432${NC}"
    echo -e "${YELLOW}  Using remote database from .env${NC}"
    # Could start Docker PostgreSQL here if needed
fi

echo ""

# Step 3: Start/Check Redis
echo -e "${YELLOW}[3/5] Checking Redis...${NC}"

if check_service redis 6379; then
    echo -e "${GREEN}✓ Redis is running on port 6379${NC}"
else
    echo -e "${YELLOW}! Redis not running, attempting to start...${NC}"

    if command_exists redis-server; then
        redis-server --daemonize yes --port 6379
        sleep 2
        if check_service redis 6379; then
            echo -e "${GREEN}✓ Redis started successfully${NC}"
        else
            echo -e "${RED}✗ Failed to start Redis${NC}"
            exit 1
        fi
    elif command_exists docker; then
        docker run -d --name voice-agent-redis -p 6379:6379 redis:7-alpine
        sleep 3
        if check_service redis 6379; then
            echo -e "${GREEN}✓ Redis started via Docker${NC}"
        else
            echo -e "${RED}✗ Failed to start Redis via Docker${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ Redis not available and cannot start it${NC}"
        echo -e "${YELLOW}Install Redis: brew install redis (macOS) or apt install redis (Linux)${NC}"
        exit 1
    fi
fi

echo ""

# Step 4: Start ngrok tunnel
echo -e "${YELLOW}[4/5] Starting ngrok tunnel...${NC}"

# Kill any existing ngrok process
pkill ngrok 2>/dev/null || true
sleep 1

# Start ngrok in background
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
echo -e "${GREEN}✓ ngrok started (PID: $NGROK_PID)${NC}"

# Wait for ngrok to start and get the URL
echo -e "${YELLOW}  Waiting for ngrok tunnel...${NC}"
sleep 3

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}✗ Failed to get ngrok URL${NC}"
    echo -e "${YELLOW}  Check ngrok logs: tail -f /tmp/ngrok.log${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ngrok tunnel established${NC}"
echo -e "${BLUE}  Public URL: $NGROK_URL${NC}"

# Update .env file with ngrok URL
if [ -f ".env" ]; then
    # Create backup
    cp .env .env.backup

    # Update BASE_URL
    if grep -q "^BASE_URL=" .env; then
        sed -i.tmp "s|^BASE_URL=.*|BASE_URL=$NGROK_URL|" .env
        rm -f .env.tmp
        echo -e "${GREEN}✓ Updated BASE_URL in .env${NC}"
    else
        echo "BASE_URL=$NGROK_URL" >> .env
        echo -e "${GREEN}✓ Added BASE_URL to .env${NC}"
    fi
fi

# Auto-update Twilio webhook for inbound calls
echo -e "${YELLOW}  Updating Twilio webhook for inbound calls...${NC}"
venv-new/bin/python scripts/update_twilio_webhook.py "$NGROK_URL"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Twilio webhook configured${NC}"
else
    echo -e "${RED}✗ Failed to update Twilio webhook${NC}"
    echo -e "${YELLOW}  Inbound calls may not work. Check Twilio credentials in .env${NC}"
fi

echo ""

# Step 5: Start FastAPI server
echo -e "${YELLOW}[5/5] Starting FastAPI server...${NC}"

# Kill any existing uvicorn process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

# Start server in background
venv-new/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir server > /tmp/uvicorn.log 2>&1 &
SERVER_PID=$!
echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"

# Wait for server to be ready
echo -e "${YELLOW}  Waiting for server to be ready...${NC}"
for i in {1..30}; do
    if check_service localhost 8000; then
        echo -e "${GREEN}✓ Server is ready${NC}"
        break
    fi
    sleep 1
done

if ! check_service localhost 8000; then
    echo -e "${RED}✗ Server failed to start${NC}"
    echo -e "${YELLOW}  Check logs: tail -f /tmp/uvicorn.log${NC}"
    exit 1
fi

echo ""

# Generate fresh Google Calendar refresh token
echo -e "${YELLOW}Checking Google Calendar authentication...${NC}"
if venv-new/bin/python scripts/generate_google_refresh_token.py --update-env 2>&1 | grep -q "SUCCESS"; then
    echo -e "${GREEN}✓ Google Calendar refresh token updated${NC}"
else
    echo -e "${YELLOW}⚠ OAuth authorization failed or skipped${NC}"
    echo -e "${YELLOW}  Testing if existing refresh token is still valid...${NC}"

    # Test if current token works
    if venv-new/bin/python -c "
import sys
sys.path.insert(0, 'server')
from app.config import settings
from app.services.calendar_service import CalendarService
try:
    cal = CalendarService(
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_CLIENT_SECRET,
        settings.GOOGLE_REFRESH_TOKEN,
        settings.CALENDAR_TIMEZONE
    )
    cal.get_calendar_service()
    print('VALID')
except:
    print('INVALID')
" 2>/dev/null | grep -q "VALID"; then
        echo -e "${GREEN}✓ Existing Google Calendar token is valid${NC}"
    else
        echo -e "${RED}✗ Existing token is invalid - using MOCK calendar${NC}"
        echo -e "${YELLOW}  📅 Calendar operations will use mock data for testing${NC}"
        echo -e "${YELLOW}  To fix: Update redirect URI in Google Cloud Console to include:${NC}"
        echo -e "${YELLOW}     - http://localhost:8080${NC}"
        echo -e "${YELLOW}     - http://localhost:8080/${NC}"
        echo -e "${YELLOW}  Then run: python scripts/generate_google_refresh_token.py --update-env${NC}"
    fi
fi
echo ""

# Seed test data (if needed)
echo -e "${YELLOW}Checking for test data...${NC}"
venv-new/bin/python scripts/seed_test_data.py 2>&1 | grep -v "sqlalchemy\|psycopg" || true
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All services running successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Display service status
echo -e "${BLUE}Service Status:${NC}"
echo -e "  PostgreSQL: ${GREEN}Running${NC}"
echo -e "  Redis:      ${GREEN}Running (port 6379)${NC}"
echo -e "  ngrok:      ${GREEN}Running (PID: $NGROK_PID)${NC}"
echo -e "  Server:     ${GREEN}Running (port 8000, PID: $SERVER_PID)${NC}"
echo ""
echo -e "${BLUE}URLs:${NC}"
echo -e "  Local:      http://localhost:8000"
echo -e "  Public:     $NGROK_URL"
echo -e "  API Docs:   http://localhost:8000/docs"
echo -e "  ngrok UI:   http://localhost:4040"
echo ""

# Interactive menu
while true; do
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Voice Agent Test Menu${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "What would you like to test?"
    echo ""
    echo "  1) Test INBOUND call (call the agent)"
    echo "  2) Test OUTBOUND call (agent calls you)"
    echo "  3) Test OUTBOUND REMINDER call"
    echo "  4) Check call status"
    echo "  5) List recent calls"
    echo "  6) View server logs"
    echo "  7) View ngrok logs"
    echo "  8) Stop all services and exit"
    echo ""
    read -p "Enter choice [1-8]: " choice

    case $choice in
        1)
            echo ""
            venv-new/bin/python scripts/test_voice_calls.py inbound
            echo ""
            echo -e "${BLUE}Sample Customers You Can Pose As:${NC}"
            echo "  • Ali Khani - Phone: (408) 613-7788"
            echo "    2019 Honda CR-V (upcoming oil change)"
            echo ""
            echo "  • Maria Garcia - Phone: (512) 555-1001"
            echo "    2018 Toyota Camry (upcoming brake service)"
            echo ""
            echo "  • Robert Johnson - Phone: (512) 555-1002"
            echo "    2016 Honda CR-V & 2011 Ford F-150"
            echo ""
            echo "  • Lisa Chen - Phone: (512) 555-1003"
            echo "    2020 VW Jetta (upcoming inspection)"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        2)
            echo ""
            venv-new/bin/python scripts/test_voice_calls.py outbound
            echo ""
            echo -e "${BLUE}What to Test:${NC}"
            echo "  • Answer the call - Sophie will mention specific appointment details"
            echo "  • Try interrupting with 'wait' or 'hold on' (barge-in test)"
            echo "  • Ask off-topic questions like 'tell me about cybersecurity'"
            echo "  • Say 'goodbye' to test auto hang-up"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            venv-new/bin/python scripts/test_voice_calls.py outbound-reminder
            echo ""
            echo -e "${BLUE}What to Test:${NC}"
            echo "  • Answer the call - Sophie will provide appointment reminder"
            echo "  • Try interrupting Sophie while she's speaking"
            echo "  • Test natural conversation flow"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        4)
            echo ""
            read -p "Enter Call SID: " call_sid
            venv-new/bin/python scripts/test_voice_calls.py status "$call_sid"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        5)
            echo ""
            read -p "How many calls to show? [10]: " count
            count=${count:-10}
            venv-new/bin/python scripts/test_voice_calls.py list "$count"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        6)
            echo ""
            echo -e "${YELLOW}Server logs (Ctrl+C to exit):${NC}"
            tail -f /tmp/uvicorn.log
            ;;
        7)
            echo ""
            echo -e "${YELLOW}ngrok logs (Ctrl+C to exit):${NC}"
            tail -f /tmp/ngrok.log
            ;;
        8)
            echo ""
            echo -e "${YELLOW}Stopping all services...${NC}"

            # Stop server
            if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
                kill "$SERVER_PID"
                echo -e "${GREEN}✓ Server stopped${NC}"
            fi

            # Stop ngrok
            if [ -n "$NGROK_PID" ] && kill -0 "$NGROK_PID" 2>/dev/null; then
                kill "$NGROK_PID"
                echo -e "${GREEN}✓ ngrok stopped${NC}"
            fi

            # Restore .env backup
            if [ -f ".env.backup" ]; then
                mv .env.backup .env
                echo -e "${GREEN}✓ .env restored${NC}"
            fi

            echo ""
            echo -e "${GREEN}All services stopped. Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo ""
            echo -e "${RED}Invalid choice. Please enter 1-8.${NC}"
            echo ""
            ;;
    esac
done
