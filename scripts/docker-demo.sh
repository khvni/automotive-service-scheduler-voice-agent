#!/bin/bash
# Docker Demo Runner - Run demos with all dependencies in containers

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  AUTOMOTIVE VOICE - DOCKER DEMOS${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Show menu
echo -e "${BLUE}Select a demo to run:${NC}"
echo "  1) Start all services (PostgreSQL, Redis, Server)"
echo "  2) Run Demo 1 (Inbound Call Simulation)"
echo "  3) Run Demo 2 (Outbound Call Simulation)"
echo "  4) Run Demo 2 with REAL outbound call"
echo "  5) Stop all services"
echo "  6) View server logs"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo -e "${YELLOW}Starting all services with Docker Compose...${NC}"
        docker compose up -d postgres redis server
        echo ""
        echo -e "${GREEN}✓ Services started!${NC}"
        echo -e "  - PostgreSQL: localhost:5432"
        echo -e "  - Redis: localhost:6379"
        echo -e "  - Server: http://localhost:8000"
        echo ""
        echo -e "Waiting for services to be healthy..."
        sleep 5
        docker compose ps
        echo ""
        echo -e "${GREEN}Ready to run demos!${NC}"
        ;;

    2)
        echo -e "${YELLOW}Running Demo 1: Inbound Call${NC}"
        echo ""
        # Ensure services are running
        docker compose up -d postgres redis
        sleep 3

        # Run demo directly with Python (connects to Docker containers)
        if [ -d ".venv" ]; then
            .venv/bin/python demos/demo_1_inbound_call.py
        else
            python3 demos/demo_1_inbound_call.py
        fi
        ;;

    3)
        echo -e "${YELLOW}Running Demo 2: Outbound Call (Simulation)${NC}"
        echo ""
        # Ensure services are running
        docker compose up -d postgres redis
        sleep 3

        # Run demo
        if [ -d ".venv" ]; then
            .venv/bin/python demos/demo_2_outbound_reminder.py
        else
            python3 demos/demo_2_outbound_reminder.py
        fi
        ;;

    4)
        echo -e "${YELLOW}Running Demo 2: REAL Outbound Call${NC}"
        echo ""

        # Check prerequisites
        TEST_NUMBER=$(grep "YOUR_TEST_NUMBER" .env | cut -d'=' -f2)
        if [ -z "$TEST_NUMBER" ] || [ "$TEST_NUMBER" == "+1234567890" ]; then
            echo -e "${RED}Error: YOUR_TEST_NUMBER not configured in .env${NC}"
            exit 1
        fi

        echo -e "${GREEN}✓ Test number: ${TEST_NUMBER}${NC}"

        # Start all services
        echo -e "${YELLOW}Starting services...${NC}"
        docker compose up -d postgres redis server

        # Wait for server to be ready
        echo -e "${YELLOW}Waiting for server to be ready...${NC}"
        for i in {1..30}; do
            if curl -s http://localhost:8000/health > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Server is ready!${NC}"
                break
            fi
            sleep 1
            if [ $i -eq 30 ]; then
                echo -e "${RED}Error: Server failed to start${NC}"
                docker compose logs server
                exit 1
            fi
        done

        # Show info
        echo ""
        echo -e "${BLUE}=== Important ===${NC}"
        echo -e "${YELLOW}⚠️  This will make a REAL phone call to: ${TEST_NUMBER}${NC}"
        echo -e "Cost: ~$0.01-0.02 per minute"
        echo ""
        read -p "Press ENTER to make the call, or Ctrl+C to cancel..."

        # Run demo with --make-call flag
        if [ -d ".venv" ]; then
            .venv/bin/python demos/demo_2_outbound_reminder.py --make-call
        else
            python3 demos/demo_2_outbound_reminder.py --make-call
        fi
        ;;

    5)
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker compose down
        echo -e "${GREEN}✓ All services stopped${NC}"
        ;;

    6)
        echo -e "${YELLOW}Server logs:${NC}"
        docker compose logs -f server
        ;;

    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
