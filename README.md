# AI Automotive Service Scheduler

A real-time voice agent that autonomously handles inbound and outbound calls for car service centers and dealerships. Built with FastAPI, OpenAI Realtime API, Deepgram, and Twilio.

## 🎯 Features

- **Inbound Call Handling**: Real-time voice streaming with natural conversation
- **Outbound Reminders**: Automated appointment reminder calls
- **CRM Integration**: Customer and vehicle management
- **Calendar Integration**: Google Calendar for appointment scheduling
- **VIN Decoding**: Automatic vehicle identification and service suggestions
- **Multi-tool Orchestration**: Seamless integration of voice, AI, and business logic

## 🏗️ Architecture

```
┌─────────────┐     WebSocket      ┌──────────┐
│   Twilio    │ ←─────────────────→ │  Server  │
│   (Voice)   │                     │ FastAPI  │
└─────────────┘                     └────┬─────┘
                                         │
                                         ├─→ Deepgram (STT/VAD)
                                         ├─→ OpenAI Realtime API
                                         ├─→ PostgreSQL (CRM)
                                         ├─→ Redis (Session)
                                         ├─→ Google Calendar
                                         └─→ NHTSA VIN API
```

## 📁 Project Structure

```
automotive-voice/
├── server/              # FastAPI backend
│   ├── app/
│   │   ├── models/      # Database models
│   │   ├── routes/      # API routes
│   │   ├── services/    # Core services
│   │   └── tools/       # AI agent tools
│   └── requirements.txt
├── worker/              # Background job worker
│   ├── jobs/
│   └── requirements.txt
├── web/                 # Admin UI (React + Vite)
│   ├── src/
│   └── package.json
├── infra/               # Docker configuration
│   └── docker/
├── scripts/             # Utility scripts
└── docker-compose.yml
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Twilio account
- Deepgram API key
- OpenAI API key
- Google Cloud project (for Calendar API)

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/khvni/automotive-service-scheduler-voice-agent.git
cd automotive-service-scheduler-voice-agent
```

2. **Copy environment variables**

```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Run setup script**

```bash
./scripts/setup.sh
```

This will:
- Create Python virtual environments
- Install dependencies
- Start Docker services (PostgreSQL, Redis)
- Initialize database with sample data

### Running the Application

#### Option 1: Using Docker Compose (Recommended)

```bash
docker-compose up
```

#### Option 2: Manual Start

```bash
# Terminal 1: Start database and Redis
docker-compose up postgres redis

# Terminal 2: Start server
cd server
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 3: Start worker
cd worker
source venv/bin/activate
python -m worker.main

# Terminal 4: Start web UI
cd web
npm run dev
```

#### Option 3: Development script

```bash
./scripts/start_dev.sh
```

### Exposing Server for Twilio Webhooks

For local development, use ngrok to expose your server:

```bash
docker-compose --profile dev up ngrok
```

Or manually:

```bash
ngrok http 8000
```

Update your Twilio webhook URL with the ngrok URL.

## 📋 API Endpoints

### Health Checks

- `GET /api/v1/health` - Basic health check
- `GET /api/v1/health/db` - Database health check
- `GET /api/v1/health/redis` - Redis health check

### Voice

- `POST /api/v1/voice/incoming` - Twilio incoming call webhook
- `WS /api/v1/voice/ws` - WebSocket for voice streaming

### Webhooks

- `POST /api/v1/webhooks/twilio/status` - Twilio status callbacks
- `POST /api/v1/webhooks/calendar/notification` - Google Calendar notifications

## 🛠️ Development

### Database Migrations

```bash
cd server
source venv/bin/activate
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Testing Tools

```bash
python scripts/test_tools.py
```

### Reinitialize Database

```bash
python scripts/init_db.py
```

## 📊 Database Schema

### Tables

- **customers**: Customer information (name, phone, email)
- **vehicles**: Vehicle details (VIN, make, model, year)
- **appointments**: Service appointments (scheduled_at, service_type, status)
- **call_logs**: Call history and metadata (transcript, intent, tools_used)

## 🔧 Configuration

Key configuration options in `.env`:

- **Twilio**: Account SID, Auth Token, Phone Number
- **Deepgram**: API Key, Model (nova-2)
- **OpenAI**: API Key, Model (gpt-4o-realtime-preview)
- **Google Calendar**: Service Account JSON, Calendar ID
- **Worker**: Cron schedule for reminders

## 📈 Success Metrics

- Latency < 2s end-to-end response
- 90%+ task completion rate
- < 1% double-booking rate
- Cost < $0.50 per successful call

## 🧪 Testing Scenarios

The system is designed to handle:

1. **New Booking**: Customer calls to schedule service
2. **Reschedule**: Customer wants to change appointment time
3. **Cancellation**: Customer cancels appointment
4. **Confirmation**: Customer confirms existing appointment
5. **Conflict Resolution**: Handling double-booking attempts

## 📝 License

MIT

## 👤 Author

Ali Khani - [@khvni](https://github.com/khvni)

Built for Hiya's AI Engineer assignment.
