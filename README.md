# Automotive Voice Agent

AI-powered voice agent for automotive dealership appointment booking and customer service.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://github.com/psf/black)

## Overview

Production-ready voice AI system for Otto's Auto that handles inbound appointment booking calls and automated outbound reminder calls. Features real-time speech processing, natural language understanding, and full CRM integration with sub-2-second latency.

**Core Capabilities:**
- Real-time voice conversations with barge-in support
- Intelligent appointment scheduling with calendar integration
- Customer verification and vehicle tracking
- Automated 24-hour reminder calls
- Multi-flow conversation handling (booking, rescheduling, inquiries)

## Architecture

```
Twilio Phone Network
        │
        ├─ WebSocket Media Stream (mulaw @ 8kHz)
        ▼
┌────────────────────────────────────┐
│     FastAPI Server                 │
│  ┌──────────┬──────────┬────────┐ │
│  │ Deepgram │  OpenAI  │Deepgram│ │
│  │   STT    │  GPT-4o  │  TTS   │ │
│  └────┬─────┴────┬─────┴────┬───┘ │
│       │          │          │     │
│       └──────────┼──────────┘     │
│                  │                │
│         ┌────────▼────────┐       │
│         │   CRM Tools     │       │
│         │  (7 functions)  │       │
│         └────────┬────────┘       │
└──────────────────┼────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   ┌─────────┐        ┌──────────────┐
   │  Redis  │        │  PostgreSQL  │
   │ Session │        │   Customer   │
   │  Cache  │        │   Vehicle    │
   └─────────┘        │ Appointment  │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │    Google    │
                      │   Calendar   │
                      └──────────────┘
```

## Technology Stack

**Backend:**
- Python 3.11+ with asyncio
- FastAPI (ASGI web framework)
- SQLAlchemy 2.0 (async ORM)
- Uvicorn (ASGI server)

**Voice & AI:**
- Twilio Media Streams (telephony)
- Deepgram STT (nova-2-phonecall)
- Deepgram TTS (aura-2-asteria-en)
- OpenAI GPT-4o (function calling)

**Data:**
- PostgreSQL (Neon Serverless)
- Redis (session management)
- Google Calendar API

**DevOps:**
- Docker & Docker Compose
- GitHub Actions (CI/CD)
- Systemd (service management)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Neon account)
- Redis 6.0+ (or Upstash account)
- Twilio account with phone number
- Deepgram API key
- OpenAI API key
- Google Cloud OAuth2 credentials

### Installation

1. Clone and setup:
   ```bash
   git clone <repository-url>
   cd automotive-voice
   chmod +x scripts/production_setup.sh
   ./scripts/production_setup.sh
   ```

   The automated setup script will:
   - Validate Python version
   - Create virtual environment and install dependencies
   - Verify database and Redis connections
   - Run migrations and tests
   - Generate systemd service files (Linux only)

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and credentials
   ```

3. Start services:
   ```bash
   # Development
   cd server && uvicorn app.main:app --reload

   # Production (systemd)
   sudo systemctl start automotive-voice
   sudo systemctl start automotive-worker
   ```

4. Verify health:
   ```bash
   curl http://localhost:8000/health
   # {"status":"healthy","database":"connected","redis":"connected"}
   ```

## Configuration

Required environment variables in `.env`:

```bash
# Application
ENV=production
BASE_URL=https://yourdomain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/automotive_voice

# Redis
REDIS_URL=redis://default:password@host:6379

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15555551234

# Deepgram
DEEPGRAM_API_KEY=your_deepgram_api_key

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Google Calendar
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token

# Worker
WORKER_REMINDER_HOUR=18
WORKER_REMINDER_TIMEZONE=America/Chicago
```

See `.env.example` for all available options.

## API Documentation

### Health Check
```
GET /health
Response: {"status":"healthy","database":"connected","redis":"connected"}
```

### Webhooks

**Inbound Call:**
```
POST /api/v1/webhooks/inbound-call
Content-Type: application/x-www-form-urlencoded
Response: TwiML with <Connect><Stream>
```

**Outbound Reminder:**
```
POST /api/v1/webhooks/outbound-reminder?appointment_id={id}
Content-Type: application/x-www-form-urlencoded
Response: TwiML with appointment details
```

### WebSocket

**Media Stream:**
```
WS /api/v1/voice/media-stream
Protocol: Twilio Media Streams
Format: mulaw @ 8kHz
```

See [docs/API.md](docs/API.md) for complete API reference.

## Testing

Run all tests:
```bash
cd server
pytest tests/ -v
```

Run specific test suites:
```bash
pytest tests/test_integration_e2e.py -v        # Integration tests
pytest tests/test_load_performance.py -v       # Load tests
pytest tests/test_security.py -v               # Security tests
```

Test coverage:
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Test Summary:**
- 100+ tests covering all features
- Integration tests for voice flows and CRM tools
- Load tests for concurrency and scalability
- Security tests for input validation and data isolation

## Performance Benchmarks

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Customer Lookup (cached) | <2ms | <2ms | Pass |
| Customer Lookup (uncached) | <30ms | ~20-30ms | Pass |
| STT to LLM | <800ms | ~500ms | Pass |
| LLM to TTS | <500ms | ~300ms | Pass |
| Barge-in Response | <200ms | ~100ms | Pass |
| End-to-End Latency | <2s | ~1.2s | Pass |
| Concurrent Sessions | 10-20 | 100+ | Pass |

## Deployment

### Option 1: Automated Setup Script
```bash
./scripts/production_setup.sh
```

### Option 2: Docker Compose
```bash
docker-compose up -d
```

### Option 3: Railway (Cloud)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

See [docs/deployment.md](docs/deployment.md) for comprehensive deployment guides covering:
- Railway, Render, Fly.io deployment
- Docker and VPS setup
- Nginx reverse proxy configuration
- SSL/TLS with Let's Encrypt
- Database and Redis provisioning
- Monitoring and logging
- Scaling strategies

See [docs/production-checklist.md](docs/production-checklist.md) for 100+ pre-launch verification items.

## Project Structure

```
automotive-voice/
├── server/                 # FastAPI application
│   ├── app/
│   │   ├── core/           # Config, database, dependencies
│   │   ├── models/         # SQLAlchemy models
│   │   ├── routes/         # API routes and WebSocket handler
│   │   ├── services/       # STT, TTS, OpenAI, Redis, DB services
│   │   ├── tools/          # CRM tools (7 function calling tools)
│   │   └── integrations/   # External API integrations
│   ├── tests/              # Test suite (100+ tests)
│   ├── Dockerfile
│   └── requirements.txt
├── worker/                 # Background worker for cron jobs
│   ├── jobs/               # Scheduled tasks
│   ├── Dockerfile
│   └── requirements.txt
├── web/                    # Web dashboard (optional)
├── scripts/                # Utility scripts
│   ├── production_setup.sh
│   ├── init_db.py
│   └── generate_mock_data.py
├── docs/                   # Documentation
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── deployment.md
│   ├── production-checklist.md
│   └── prd.md
├── infra/                  # Infrastructure configs
├── .github/                # GitHub Actions workflows
├── docker-compose.yml
├── Makefile
└── README.md
```

## Development

### Code Quality
```bash
# Format and lint
black server/app/ worker/
isort server/app/ worker/
flake8 server/app/ worker/
mypy server/app/
bandit -r server/app/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Database Migrations
```bash
cd server
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

## Monitoring

### Logs
```bash
# Systemd
journalctl -u automotive-voice -f
journalctl -u automotive-worker -f

# Docker
docker logs -f automotive-voice-server
docker logs -f automotive-voice-worker
```

### Recommended Monitoring
- **Uptime:** UptimeRobot, Pingdom
- **Errors:** Sentry
- **Logs:** Better Stack (Logtail)
- **Metrics:** Prometheus + Grafana
- **APM:** New Relic

## Security

**Production Security Features:**
- Input validation (phone, email, VIN, state codes)
- SQL injection prevention (parameterized queries)
- Timezone-aware datetime handling
- Session TTL enforcement (1 hour max)
- Atomic operations (Lua scripts prevent race conditions)
- Sensitive data masking in logs
- HTTPS-only in production
- CORS configuration

**POC Safety:**
During testing, set `YOUR_TEST_NUMBER` in `.env` to restrict outbound calls to a single test number. Remove before production launch.

## Documentation

- [API Reference](docs/API.md)
- [Architecture Details](docs/ARCHITECTURE.md)
- [Deployment Guide](docs/deployment.md)
- [Production Checklist](docs/production-checklist.md)
- [Product Requirements](docs/prd.md)

## Contributing

This is a private project for Otto's Auto. If contributing:

1. Follow existing code style (Black, isort)
2. Write tests for new features
3. Update documentation
4. Run pre-commit hooks
5. Ensure all tests pass

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

Proprietary - Otto's Auto

## Support

**Third-Party Documentation:**
- [Twilio Support](https://support.twilio.com)
- [Deepgram Docs](https://deepgram.com/docs)
- [OpenAI API](https://platform.openai.com/docs)
- [Neon Docs](https://neon.tech/docs)

---

Built with [FastAPI](https://fastapi.tiangolo.com/), [Twilio](https://www.twilio.com/), [Deepgram](https://deepgram.com/), [OpenAI](https://openai.com/), and [Google Calendar API](https://developers.google.com/calendar).
