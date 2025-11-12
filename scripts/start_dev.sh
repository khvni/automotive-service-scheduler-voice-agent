#!/bin/bash

# Start all services for local development

echo "Starting AI Automotive Service Scheduler..."
echo ""

# Start Docker services
echo "Starting Docker services (postgres, redis)..."
docker-compose up -d postgres redis

echo "Waiting for services to be ready..."
sleep 3

# Start ngrok (optional, for Twilio webhooks)
echo ""
echo "To expose server for Twilio webhooks, run:"
echo "  docker-compose --profile dev up ngrok"
echo ""

echo "=========================================="
echo "Services Started"
echo "=========================================="
echo ""
echo "To start the server:"
echo "  cd server && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "To start the worker:"
echo "  cd worker && source venv/bin/activate && python -m worker.main"
echo ""
echo "To start the web UI:"
echo "  cd web && npm run dev"
echo ""
