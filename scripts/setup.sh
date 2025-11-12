#!/bin/bash

# Setup script for AI Automotive Service Scheduler
# This script sets up the development environment

set -e

echo "=========================================="
echo "AI Automotive Service Scheduler - Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ Created .env file. Please update it with your API keys."
    echo ""
fi

# Setup server
echo "Setting up server..."
cd server
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ..
echo "✓ Server setup complete"
echo ""

# Setup worker
echo "Setting up worker..."
cd worker
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd ..
echo "✓ Worker setup complete"
echo ""

# Setup web
echo "Setting up web admin UI..."
cd web
npm install
cd ..
echo "✓ Web UI setup complete"
echo ""

# Docker setup
echo "=========================================="
echo "Starting Docker services..."
echo "=========================================="
echo ""
docker-compose up -d postgres redis
echo "Waiting for services to be ready..."
sleep 5
echo "✓ Docker services started"
echo ""

# Initialize database
echo "Initializing database..."
cd server
source venv/bin/activate
python ../scripts/init_db.py
deactivate
cd ..
echo "✓ Database initialized with sample data"
echo ""

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update .env with your API keys"
echo "2. Run 'docker-compose up' to start all services"
echo "3. Run 'cd server && source venv/bin/activate && uvicorn app.main:app --reload'"
echo "4. Run 'cd web && npm run dev' to start the admin UI"
echo ""
