# Docker Setup for Automotive Voice Agent

## Summary
Created a Docker-based demo runner that eliminates dependency management issues. All services run in containers with consistent environments.

## What's Available

### Docker Compose Services
The project includes a complete `docker-compose.yml` with:
- **PostgreSQL** (port 5432): Database
- **Redis** (port 6379): Session cache
- **Server** (port 8000): FastAPI application
- **Worker**: Background job processor for reminders
- **Ngrok** (optional, profile: dev): Exposes server for Twilio webhooks
- **Twenty CRM** (optional, profile: crm): Open-source CRM integration

### New Docker Demo Script
`scripts/docker-demo.sh` - Interactive menu for running demos:

#### Options:
1. **Start all services** - Brings up PostgreSQL, Redis, and Server
2. **Run Demo 1** - Inbound call simulation
3. **Run Demo 2** - Outbound call simulation  
4. **Run Demo 2 with REAL call** - Makes actual phone call
5. **Stop all services** - Clean shutdown
6. **View server logs** - Monitor server output

## Usage

### Prerequisites
1. Install Docker Desktop for Mac
2. Start Docker Desktop
3. Ensure `.env` file exists with configuration

### Running Demos with Docker

```bash
# Start the interactive menu
./scripts/docker-demo.sh

# Then select option:
# 1 - Start services first
# 2 - Run Demo 1  
# 4 - Run Demo 2 with real call
```

### Manual Docker Commands

```bash
# Start all core services
docker compose up -d postgres redis server

# Start with ngrok for webhooks
docker compose --profile dev up -d

# View logs
docker compose logs -f server

# Stop all services  
docker compose down

# Rebuild after code changes
docker compose build server
docker compose up -d server
```

## Benefits of Docker Approach

### ✅ Solved Problems
1. **No dependency conflicts** - Each service has isolated environment
2. **Consistent setup** - Same environment every time
3. **Easy cleanup** - `docker compose down` removes everything
4. **No manual service management** - No need to start/stop PostgreSQL, Redis manually
5. **Version control** - Services use specific image versions

### ⚠️ Current Limitation
- Docker Desktop must be running
- Initial image build takes a few minutes
- Demo scripts still run on host (connect to Docker containers)

## Architecture

```
Host Machine (macOS)
├── Demo Scripts (.venv/bin/python)
│   ├── demo_1_inbound_call.py
│   └── demo_2_outbound_reminder.py
│
└── Docker Containers
    ├── PostgreSQL:5432
    ├── Redis:6379  
    └── Server:8000 (FastAPI)
```

The demo Python scripts run on your host machine but connect to services in Docker containers via localhost ports.

## Files Created
- `scripts/docker-demo.sh` - Interactive demo runner
- Existing: `docker-compose.yml` - Service definitions
- Existing: `infra/docker/Dockerfile.server` - Server image
- Existing: `infra/docker/Dockerfile.worker` - Worker image

## Next Steps to Complete Docker Setup

### For Fully Containerized Demos:
1. Create demo Dockerfiles
2. Mount demo scripts into containers
3. Run demos inside containers

### OR Keep Current Hybrid Approach:
- Services in Docker (PostgreSQL, Redis, Server)
- Demos run on host (simpler, faster iteration)

## Recommended: Start Docker Desktop and Test

```bash
# 1. Start Docker Desktop app
# 2. Run the demo script
./scripts/docker-demo.sh

# 3. Select option 1 to start services
# 4. Wait for services to be healthy (~30 seconds)
# 5. Select option 4 for real outbound call demo
```

## Troubleshooting

### "Cannot connect to Docker daemon"
- Start Docker Desktop application
- Wait for it to fully start (whale icon in menu bar)

### "Port already allocated"
- Stop local PostgreSQL: `brew services stop postgresql@14`
- Stop local Redis: `brew services stop redis`
- Or change ports in docker-compose.yml

### Server won't start
- Check logs: `docker compose logs server`
- Rebuild: `docker compose build server --no-cache`
- Verify .env file exists

### Demo can't connect to services
- Ensure containers are running: `docker compose ps`
- Check health: `docker compose ps` (should show "healthy")
- Test connections:
  - PostgreSQL: `psql -h localhost -U postgres -d automotive_scheduler`
  - Redis: `redis-cli -h localhost ping`
  - Server: `curl http://localhost:8000/health`
