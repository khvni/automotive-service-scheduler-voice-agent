#!/bin/bash
# Production Setup Script for Bart's Automotive Voice Agent
# Usage: ./scripts/production_setup.sh

set -e  # Exit on error

echo "========================================="
echo "Bart's Automotive Voice Agent"
echo "Production Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Error: Do not run this script as root${NC}"
    exit 1
fi

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.11+ required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check if .env exists
echo -e "${YELLOW}Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file from .env.example"
    exit 1
fi
echo -e "${GREEN}✓ .env file found${NC}"

# Secure .env file
chmod 600 .env
echo -e "${GREEN}✓ .env permissions set to 600${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install server dependencies
echo -e "${YELLOW}Installing server dependencies...${NC}"
cd server
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Server dependencies installed${NC}"

# Install worker dependencies
echo -e "${YELLOW}Installing worker dependencies...${NC}"
cd ../worker
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Worker dependencies installed${NC}"
cd ..

# Install test dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -r server/tests/requirements-test.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Test dependencies installed${NC}"

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
source .env
python3 -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_db():
    try:
        engine = create_async_engine('$DATABASE_URL', echo=False)
        async with engine.begin() as conn:
            await conn.execute('SELECT 1')
        print('${GREEN}✓ Database connection successful${NC}')
        return True
    except Exception as e:
        print('${RED}✗ Database connection failed: {e}${NC}')
        return False

asyncio.run(test_db())
" || echo -e "${RED}✗ Database connection failed${NC}"

# Check Redis connection
echo -e "${YELLOW}Checking Redis connection...${NC}"
python3 -c "
import asyncio
import redis.asyncio as redis

async def test_redis():
    try:
        client = redis.from_url('$REDIS_URL')
        await client.ping()
        print('${GREEN}✓ Redis connection successful${NC}')
        await client.close()
        return True
    except Exception as e:
        print('${RED}✗ Redis connection failed: {e}${NC}')
        return False

asyncio.run(test_redis())
" || echo -e "${RED}✗ Redis connection failed${NC}"

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
cd server
alembic upgrade head
echo -e "${GREEN}✓ Database migrations completed${NC}"
cd ..

# Run code quality checks
echo -e "${YELLOW}Running code quality checks...${NC}"
cd server

echo "  - Running Black..."
black --check app/ > /dev/null 2>&1 && echo -e "${GREEN}  ✓ Black${NC}" || echo -e "${YELLOW}  ⚠ Black formatting needed${NC}"

echo "  - Running isort..."
isort --check-only app/ > /dev/null 2>&1 && echo -e "${GREEN}  ✓ isort${NC}" || echo -e "${YELLOW}  ⚠ isort formatting needed${NC}"

echo "  - Running flake8..."
flake8 app/ > /dev/null 2>&1 && echo -e "${GREEN}  ✓ flake8${NC}" || echo -e "${YELLOW}  ⚠ flake8 issues found${NC}"

cd ..

# Run tests
echo -e "${YELLOW}Running test suite...${NC}"
cd server
pytest tests/ -v --tb=short -q > /tmp/test_output.txt 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed (check /tmp/test_output.txt)${NC}"
fi
cd ..

# Check for YOUR_TEST_NUMBER in production
echo -e "${YELLOW}Checking POC safety configuration...${NC}"
if grep -q "^YOUR_TEST_NUMBER=" .env; then
    echo -e "${RED}⚠ WARNING: YOUR_TEST_NUMBER is set in .env${NC}"
    echo -e "${RED}  This restricts outbound calls to test number only${NC}"
    echo -e "${RED}  Remove this line before production launch${NC}"
else
    echo -e "${GREEN}✓ YOUR_TEST_NUMBER not set (production mode)${NC}"
fi

# Create systemd service files (if on Linux)
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
        echo -e "${YELLOW}Creating systemd service files...${NC}"

        # Server service
        sudo tee /etc/systemd/system/automotive-voice.service > /dev/null <<EOF
[Unit]
Description=Bart's Automotive Voice Agent
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/server
Environment="PATH=$(pwd)/venv/bin"
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        # Worker service
        sudo tee /etc/systemd/system/automotive-worker.service > /dev/null <<EOF
[Unit]
Description=Automotive Voice Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)/worker
Environment="PATH=$(pwd)/venv/bin"
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

        sudo systemctl daemon-reload
        echo -e "${GREEN}✓ Systemd service files created${NC}"
        echo -e "  To enable: sudo systemctl enable automotive-voice automotive-worker"
        echo -e "  To start: sudo systemctl start automotive-voice automotive-worker"
    fi
fi

echo ""
echo "========================================="
echo -e "${GREEN}Production setup completed!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Review PRODUCTION_CHECKLIST.md"
echo "2. Configure Nginx reverse proxy (see DEPLOYMENT.md)"
echo "3. Set up SSL certificate (certbot)"
echo "4. Update Twilio webhook URLs"
echo "5. Enable and start services"
echo "6. Monitor logs and health check endpoint"
echo ""
echo "Health check: http://localhost:8000/health"
echo ""
