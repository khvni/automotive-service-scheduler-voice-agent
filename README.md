# Automotive Voice Agent

AI-powered voice assistant for automotive dealership appointment booking and customer service.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://github.com/psf/black)

## Overview

Production-ready voice AI system that handles inbound appointment booking calls and automated outbound reminder calls. Built with real-time speech processing, natural language understanding, and full CRM integration delivering sub-2-second latency.

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
   - Validate Python version (3.11+)
   - Create virtual environment and install dependencies
   - Verify database and Redis connections
   - Run migrations and tests
   - Generate systemd service files (Linux only)

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and credentials
   ```

3. Initialize database:
   ```bash
   python scripts/init_db.py
   python scripts/seed_test_data.py  # Optional: Load sample data
   ```

4. Start services:
   ```bash
   # Development
   cd server && uvicorn app.main:app --reload

   # Or use convenience script
   ./scripts/start_dev.sh

   # Production (systemd)
   sudo systemctl start automotive-voice
   sudo systemctl start automotive-worker
   ```

5. Verify health:
   ```bash
   curl http://localhost:8000/api/v1/health
   # {"status":"healthy","service":"ai-automotive-scheduler"}

   curl http://localhost:8000/api/v1/health/db
   # {"status":"healthy","database":"connected"}

   curl http://localhost:8000/api/v1/health/redis
   # {"status":"healthy","redis":"connected"}
   ```

## Configuration

Required environment variables in `.env`:

```bash
# Application
ENV=production
BASE_URL=https://yourdomain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/automotive_voice  # pragma: allowlist secret

# Redis
REDIS_URL=redis://default:password@host:6379  # pragma: allowlist secret

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # pragma: allowlist secret
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
GET /api/v1/health
Response: {"status":"healthy","service":"ai-automotive-scheduler"}

GET /api/v1/health/db
Response: {"status":"healthy","database":"connected"}

GET /api/v1/health/redis
Response: {"status":"healthy","redis":"connected"}
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

### Unit & Integration Tests

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

Quick test (format + lint + tests):
```bash
./scripts/quick_test.sh
```

**Test Summary:**
- 100+ tests covering all features
- Integration tests for voice flows and CRM tools
- Load tests for concurrency and scalability
- Security tests for input validation and data isolation

### Functional Demos

Run interactive demonstrations to verify end-to-end functionality:

```bash
# Demo 1: Inbound call - Customer books appointment
python demos/demo_1_inbound_call.py

# Demo 2: Outbound reminder call with rescheduling
python demos/demo_2_outbound_reminder.py
```

See [demos/README.md](demos/README.md) for detailed demo documentation.

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
├── server/                     # FastAPI application
│   ├── app/
│   │   ├── models/             # SQLAlchemy models (Customer, Vehicle, Appointment)
│   │   ├── routes/             # API routes (health, voice, webhooks)
│   │   ├── services/           # Core services (STT, TTS, OpenAI, Redis, DB)
│   │   ├── tools/              # CRM tools (crm_tools.py, calendar_tools.py, vin_tools.py)
│   │   ├── utils/              # Utilities (call_logger.py)
│   │   ├── config.py           # Configuration management
│   │   └── main.py             # FastAPI application entry point
│   ├── tests/                  # Test suite (integration, load, security)
│   ├── requirements.txt
│   └── Dockerfile
├── worker/                     # Background worker for scheduled tasks
│   ├── jobs/
│   │   └── reminder_job.py     # Appointment reminder job
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── demos/                      # Functional demonstrations
│   ├── demo_1_inbound_call.py  # Inbound booking demo
│   ├── demo_2_outbound_reminder.py
│   ├── README.md               # Demo documentation
│   └── QUICKSTART.md
├── scripts/                    # Utility scripts
│   ├── production_setup.sh     # Automated production setup
│   ├── setup.sh
│   ├── start_dev.sh
│   ├── init_db.py              # Database initialization
│   ├── seed_test_data.py
│   ├── generate_mock_crm_data.py
│   ├── load_customer_data.py
│   ├── update_twilio_webhook.py
│   ├── test_voice_calls.py
│   ├── format_code.sh          # Code formatting (black, isort)
│   ├── check_code_quality.sh   # Linting (flake8, mypy, bandit)
│   └── run_demo*.sh            # Demo runners
├── tests/                      # Root-level tests
├── docs/                       # Documentation
│   ├── API.md                  # API reference
│   ├── ARCHITECTURE.md         # System architecture
│   ├── CONTRIBUTING.md         # Contribution guidelines
│   ├── deployment.md           # Deployment guides
│   ├── local-testing-guide.md  # Local testing instructions
│   ├── production-checklist.md # Pre-launch checklist
│   └── render-deployment.md    # Render-specific deployment
├── deployment/                 # Deployment configurations
├── web/                        # Web dashboard (React/Next.js)
├── venv-new/                   # Python virtual environment
├── .github/                    # GitHub Actions workflows
├── .env.example                # Environment template
├── docker-compose.yml
├── Makefile
├── pyproject.toml              # Python project config
├── pytest.ini                  # Pytest configuration
├── mypy.ini                    # Type checking config
└── README.md
```

> **Note:** The `YOUR PATH/` directory is used by coding agents for temporary documentation and should remain gitignored to prevent accidental commits.

## Development

### Code Quality
```bash
# Format code
./scripts/format_code.sh
# Or manually:
black server/app/ worker/
isort server/app/ worker/

# Check code quality (linting + type checking + security)
./scripts/check_code_quality.sh
# Or manually:
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
- [Contributing Guide](docs/CONTRIBUTING.md)

## Contributing

This is a private project. If contributing:

1. Follow existing code style (Black, isort)
2. Write tests for new features
3. Update documentation
4. Run pre-commit hooks before committing
5. Ensure all tests pass

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for details.

### Important: Development Documentation

**For Coding Agents:**
- Temporary progress tracking files may be created in `YOUR PATH/` directory
- This directory is gitignored and should NEVER be committed
- Use this space for analysis, logs, and temporary documentation
- Clean documentation belongs in `docs/` directory only

## License

Proprietary

## Support

**Third-Party Documentation:**
- [Twilio Support](https://support.twilio.com)
- [Deepgram Docs](https://deepgram.com/docs)
- [OpenAI API](https://platform.openai.com/docs)
- [Neon Docs](https://neon.tech/docs)

---

Built with [FastAPI](https://fastapi.tiangolo.com/), [Twilio](https://www.twilio.com/), [Deepgram](https://deepgram.com/), [OpenAI](https://openai.com/), and [Google Calendar API](https://developers.google.com/calendar).
