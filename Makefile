.PHONY: help install dev clean test lint format docker-up docker-down docker-build init-db

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(BLUE)AI Automotive Service Scheduler - Make Commands$(NC)'
	@echo ''
	@echo 'Usage:'
	@echo '  $(GREEN)make$(NC) $(YELLOW)<target>$(NC)'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install all dependencies (server, worker, web)
	@echo "$(BLUE)Installing dependencies...$(NC)"
	cd server && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	cd worker && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	cd web && npm install
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

install-hooks: ## Install pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

dev: ## Start all services for development
	@echo "$(BLUE)Starting development environment...$(NC)"
	./scripts/start_dev.sh

server: ## Start FastAPI server
	@echo "$(BLUE)Starting server...$(NC)"
	cd server && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Start background worker
	@echo "$(BLUE)Starting worker...$(NC)"
	cd worker && source venv/bin/activate && python -m worker.main

web: ## Start web UI
	@echo "$(BLUE)Starting web UI...$(NC)"
	cd web && npm run dev

docker-up: ## Start all Docker services
	@echo "$(BLUE)Starting Docker services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"

docker-down: ## Stop all Docker services
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build
	@echo "$(GREEN)✓ Docker images built$(NC)"

docker-logs: ## Show Docker logs
	docker-compose logs -f

init-db: ## Initialize database with sample data
	@echo "$(BLUE)Initializing database...$(NC)"
	cd server && source venv/bin/activate && python ../scripts/init_db.py
	@echo "$(GREEN)✓ Database initialized$(NC)"

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	cd server && source venv/bin/activate && pytest tests/ -v
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-tools: ## Test CRM, Calendar, and VIN tools
	@echo "$(BLUE)Testing tools...$(NC)"
	cd server && source venv/bin/activate && python ../scripts/test_tools.py

lint: ## Run linters (flake8, mypy)
	@echo "$(BLUE)Running linters...$(NC)"
	cd server && source venv/bin/activate && flake8 app/ --max-line-length=100 --exclude=venv
	cd server && source venv/bin/activate && mypy app/ --ignore-missing-imports
	@echo "$(GREEN)✓ Linting completed$(NC)"

format: ## Format code (black, isort)
	@echo "$(BLUE)Formatting code...$(NC)"
	cd server && source venv/bin/activate && black app/ --line-length=100
	cd server && source venv/bin/activate && isort app/
	cd worker && source venv/bin/activate && black . --line-length=100
	cd worker && source venv/bin/activate && isort .
	cd web && npm run format || true
	@echo "$(GREEN)✓ Code formatted$(NC)"

security: ## Run security checks (bandit)
	@echo "$(BLUE)Running security checks...$(NC)"
	cd server && source venv/bin/activate && bandit -r app/ -ll
	@echo "$(GREEN)✓ Security checks completed$(NC)"

clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf web/node_modules 2>/dev/null || true
	rm -rf web/dist 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

ngrok: ## Start ngrok tunnel
	@echo "$(BLUE)Starting ngrok tunnel...$(NC)"
	docker-compose --profile dev up ngrok
	@echo "$(GREEN)✓ Ngrok started - Visit http://localhost:4040 for tunnel URL$(NC)"

setup: ## Full setup (install + docker + init-db)
	@echo "$(BLUE)Running full setup...$(NC)"
	make install
	make docker-up
	sleep 5
	make init-db
	make install-hooks
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Update .env with your API keys"
	@echo "  2. Run 'make dev' to start all services"
	@echo "  3. Run 'make ngrok' to expose server for Twilio webhooks"

all: setup ## Alias for setup

.DEFAULT_GOAL := help
