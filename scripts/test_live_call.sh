#!/bin/bash
# Live Phone Call Testing Script
# This script helps you test outbound calls quickly

set -e

echo "=============================================="
echo "🚀 LIVE PHONE CALL TESTING"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please copy .env.example to .env and fill in your credentials"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo -e "${YELLOW}📋 Current Configuration:${NC}"
echo "  YOUR_TEST_NUMBER: ${YOUR_TEST_NUMBER}"
echo "  TWILIO_PHONE_NUMBER: ${TWILIO_PHONE_NUMBER}"
echo "  BASE_URL: ${BASE_URL}"
echo ""

# Check if YOUR_TEST_NUMBER is set
if [ "$YOUR_TEST_NUMBER" = "+1234567890" ] || [ -z "$YOUR_TEST_NUMBER" ]; then
    echo -e "${RED}❌ YOUR_TEST_NUMBER not configured!${NC}"
    echo "Please set YOUR_TEST_NUMBER in .env to your actual phone number"
    echo "Example: YOUR_TEST_NUMBER=+14086137788"
    exit 1
fi

# Check if BASE_URL is ngrok
if [[ "$BASE_URL" != *"ngrok"* ]]; then
    echo -e "${YELLOW}⚠️  BASE_URL doesn't contain 'ngrok'${NC}"
    echo "For local testing, you need to:"
    echo "  1. Run: ngrok http 8000"
    echo "  2. Copy the https://xxxxx.ngrok.io URL"
    echo "  3. Update BASE_URL in .env"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}✅ Configuration looks good!${NC}"
echo ""

# Check if server is running
echo "🔍 Checking if server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Server is running at http://localhost:8000${NC}"
else
    echo -e "${RED}❌ Server is not running!${NC}"
    echo ""
    echo "Please start the server first:"
    echo "  cd server"
    echo "  source ../venv/bin/activate"
    echo "  uvicorn app.main:app --reload"
    echo ""
    exit 1
fi

# Check if database is accessible
echo "🔍 Checking database connection..."
python3 -c "
import sys
sys.path.insert(0, 'server')
import asyncio
from app.services.database import init_db

async def check():
    try:
        await init_db()
        print('${GREEN}✅ Database connected${NC}')
        return True
    except Exception as e:
        print('${RED}❌ Database connection failed: {e}${NC}')
        return False

result = asyncio.run(check())
sys.exit(0 if result else 1)
" || exit 1

echo ""
echo -e "${YELLOW}📞 Ready to test live phone calls!${NC}"
echo ""
echo "Choose a test:"
echo "  1) Test OUTBOUND call (system calls YOU)"
echo "  2) Test INBOUND call (YOU call system)"
echo "  3) Run Demo 2 with --make-call flag"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo -e "${YELLOW}🚀 Initiating outbound call to ${YOUR_TEST_NUMBER}...${NC}"
        echo ""
        cd demos
        python3 demo_2_outbound_reminder.py --make-call
        ;;
    2)
        echo ""
        echo -e "${YELLOW}📞 Inbound call testing:${NC}"
        echo ""
        echo "Call your Twilio number from your phone:"
        echo "  ${GREEN}${TWILIO_PHONE_NUMBER}${NC}"
        echo ""
        echo "Make sure your Twilio console is configured:"
        echo "  1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming"
        echo "  2. Click on your phone number: ${TWILIO_PHONE_NUMBER}"
        echo "  3. Under 'Voice Configuration', set:"
        echo "     - 'A call comes in': Webhook"
        echo "     - URL: ${BASE_URL}/api/v1/webhooks/inbound-call"
        echo "     - HTTP: POST"
        echo ""
        echo "Then call ${TWILIO_PHONE_NUMBER} from your phone!"
        echo ""
        read -p "Press ENTER when ready to view live logs..."
        echo ""
        echo "Watching server logs (Ctrl+C to stop):"
        tail -f server/logs/*.log 2>/dev/null || echo "No log files found. Check terminal where server is running."
        ;;
    3)
        echo ""
        echo -e "${YELLOW}🚀 Running Demo 2 with real call...${NC}"
        echo ""
        cd demos
        python3 demo_2_outbound_reminder.py --make-call
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
