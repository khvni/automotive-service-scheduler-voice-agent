# Outbound Call Worker

Automated worker service for scheduling outbound reminder calls to customers with appointments.

## Overview

The worker service runs scheduled jobs (cron-based) to:

1. **Appointment Reminders**: Call customers 1 day before their scheduled appointments
2. Future: Marketing calls, follow-ups, satisfaction surveys

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Worker Service                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  APScheduler (AsyncIOScheduler)                        │
│       │                                                 │
│       ├─► Daily at 9 AM                                │
│       │   ├─► Query database for tomorrow appointments │
│       │   ├─► Filter by YOUR_TEST_NUMBER (POC safety) │
│       │   ├─► Initiate Twilio outbound calls          │
│       │   └─► Log calls to database                    │
│       │                                                 │
│       └─► Future jobs...                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │
         ├──► Postgres (appointments, customers, call_logs)
         ├──► Twilio REST API (initiate calls)
         └──► Server API (/api/v1/voice/incoming-reminder)
```

## Features

### 1. Appointment Reminder Job

**Schedule**: Daily at 9:00 AM (configurable via `REMINDER_CRON_SCHEDULE`)

**Logic**:
- Queries appointments scheduled for tomorrow
- Only calls appointments with status `CONFIRMED`
- **POC Safety**: Only calls `YOUR_TEST_NUMBER` from .env
- Creates call log entry for tracking
- Initiates Twilio outbound call
- Rate limiting: 2 seconds between calls

**Call Flow**:
1. Worker → Twilio REST API: `calls.create()`
2. Twilio → Server: POST `/api/v1/voice/incoming-reminder`
3. Server returns TwiML with WebSocket connection
4. Call connects to same WebSocket handler as inbound calls
5. AI assistant handles the conversation

## Configuration

All configuration is in `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db  # pragma: allowlist secret

# Twilio
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_PHONE_NUMBER=+1234567890

# Server API
SERVER_API_URL=https://your-domain.com/api/v1

# Scheduler
REMINDER_CRON_SCHEDULE=0 9 * * *  # Daily at 9 AM
REMINDER_DAYS_BEFORE=1            # Remind 1 day before

# POC SAFETY: Only call this number
YOUR_TEST_NUMBER=+1234567890
```

### Cron Schedule Format

The `REMINDER_CRON_SCHEDULE` uses standard cron syntax:

```
┌─── minute (0 - 59)
│ ┌─── hour (0 - 23)
│ │ ┌─── day of month (1 - 31)
│ │ │ ┌─── month (1 - 12)
│ │ │ │ ┌─── day of week (0 - 6) (Sunday=0)
│ │ │ │ │
* * * * *
```

**Examples**:
- `0 9 * * *` - Every day at 9:00 AM
- `0 9,15 * * *` - Every day at 9:00 AM and 3:00 PM
- `0 9 * * 1-5` - Weekdays at 9:00 AM
- `*/30 * * * *` - Every 30 minutes

## Running Locally

### Prerequisites

1. Python 3.11+
2. Postgres database (running)
3. Redis (optional, but recommended for server)
4. Twilio account with phone number
5. Server API running

### Setup

1. **Install dependencies**:
   ```bash
   cd worker
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp ../.env.example ../.env
   # Edit .env with your credentials
   ```

3. **Set YOUR_TEST_NUMBER**:
   ```bash
   # In .env
   YOUR_TEST_NUMBER=+1234567890  # Your phone number
   ```

### Run Worker

```bash
python -m worker.main
```

**Output**:
```
2025-01-12 09:00:00 - worker.main - INFO - Starting outbound call worker...
2025-01-12 09:00:00 - worker.main - INFO - Scheduler started. Jobs: ['appointment_reminders']
2025-01-12 09:00:00 - apscheduler.scheduler - INFO - Added job "Send appointment reminders" to job store "default"
2025-01-12 09:00:00 - apscheduler.scheduler - INFO - Scheduler started
```

## Testing

### Manual Test

Test the reminder job without waiting for the cron schedule:

```bash
python scripts/test_reminder_job.py
```

This script will:
1. Create a test appointment for tomorrow
2. Run the reminder job immediately
3. Verify the call was initiated
4. Check the call log in database

**Expected Output**:
```
============================================================
Testing Appointment Reminder Job
============================================================

✓ Configuration:
  - Test Number: +1234567890
  - Twilio Phone: +15551234567
  - Server URL: http://localhost:8000/api/v1
  - Reminder Days Before: 1

Creating test appointment for tomorrow...
✓ Created test appointment:
  - ID: 123e4567-e89b-12d3-a456-426614174000
  - Customer: Test Customer
  - Phone: +1234567890
  - Vehicle: 2021 Honda Civic
  - Service: Oil Change
  - Scheduled: 2025-01-13 10:00:00
  - Status: CONFIRMED

============================================================
Running Reminder Job
============================================================
Found 1 appointments to remind
Initiating reminder call for appointment 123e4567-e89b-12d3-a456-426614174000 to +1234567890
Reminder call initiated: CA1234567890abcdef1234567890abcdef for appointment 123e4567-e89b-12d3-a456-426614174000

============================================================
Verification
============================================================
Verifying call log...

✓ Found 1 call log(s):
  - Call SID: CA1234567890abcdef1234567890abcdef
  - Direction: outbound
  - Status: initiated
  - From: +15551234567
  - To: +1234567890
  - Intent: appointment_reminder
  - Started: 2025-01-12 14:30:00

============================================================
✓ TEST PASSED
============================================================

Check your phone for the reminder call!
You should receive a call at +1234567890
```

### Unit Test

```bash
pytest worker/tests/test_reminder_job.py
```

## Docker Deployment

### Build Image

```bash
docker build -f worker/Dockerfile -t automotive-voice-worker .
```

### Run Container

```bash
docker run -d \
  --name automotive-worker \
  --env-file .env \
  automotive-voice-worker
```

### Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  worker:
    build:
      context: .
      dockerfile: worker/Dockerfile
    env_file: .env
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Run:
```bash
docker-compose up -d worker
```

## Production Deployment

### Recommendations

1. **Logging**: Use structured logging (JSON format) and ship to logging service (e.g., Datadog, CloudWatch)

2. **Monitoring**:
   - Set up alerts for job failures
   - Monitor call success rate
   - Track call duration and costs

3. **Error Handling**:
   - Implement retry logic with exponential backoff
   - Dead letter queue for failed calls
   - Alert on consecutive failures

4. **Rate Limiting**:
   - Current: 2 seconds between calls (30 calls/minute)
   - Adjust based on Twilio rate limits and call volume
   - Consider batch processing for high volume

5. **Database Connection**:
   - Use connection pooling
   - Set appropriate timeouts
   - Handle connection failures gracefully

6. **Scaling**:
   - Run multiple workers with distributed locking (Redis)
   - Partition by timezone for optimal call times
   - Queue-based architecture for high volume

### Example: AWS ECS Deployment

**Fargate Task Definition**:
```json
{
  "family": "automotive-worker",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "worker",
    "image": "your-ecr-repo/automotive-voice-worker:latest",
    "environment": [
      {"name": "DATABASE_URL", "value": "postgresql+asyncpg://..."},
      {"name": "TWILIO_ACCOUNT_SID", "value": "ACxxxx"},
      {"name": "REMINDER_CRON_SCHEDULE", "value": "0 9 * * *"}
    ],
    "secrets": [
      {"name": "TWILIO_AUTH_TOKEN", "valueFrom": "arn:aws:secretsmanager:..."}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/automotive-worker",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

## Safety Features

### POC Safety: YOUR_TEST_NUMBER

**Purpose**: Prevent accidentally calling real customers during development/testing.

**How it works**:
1. Set `YOUR_TEST_NUMBER` in `.env` to your test phone number
2. Worker only calls this number (skips all others)
3. Logs warning for skipped numbers

**Disabling for production**:
```bash
# Option 1: Leave empty to call all customers
YOUR_TEST_NUMBER=

# Option 2: Remove from .env (defaults to empty)
```

**Verification**:
```python
# In worker/jobs/reminder_job.py
if settings.YOUR_TEST_NUMBER and customer.phone_number != settings.YOUR_TEST_NUMBER:
    logger.warning(
        f"Skipping call to {customer.phone_number} (POC safety - only calling {settings.YOUR_TEST_NUMBER})"
    )
    continue
```

## Troubleshooting

### Worker not running jobs

**Check scheduler logs**:
```bash
docker logs automotive-worker | grep apscheduler
```

**Verify cron schedule**:
```python
from apscheduler.triggers.cron import CronTrigger
trigger = CronTrigger.from_crontab("0 9 * * *")
print(trigger.get_next_fire_time(None, None))
```

### Calls not initiated

**Check Twilio credentials**:
```bash
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}.json" \
  -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}"
```

**Check server API URL**:
```bash
curl -X GET "${SERVER_API_URL}/health"
```

**Check database connection**:
```python
python -c "from worker.config import settings; print(settings.DATABASE_URL)"
```

### Customers not receiving calls

1. **Check YOUR_TEST_NUMBER**: Make sure it matches customer phone number
2. **Check appointment status**: Only `CONFIRMED` appointments get reminders
3. **Check appointment date**: Only appointments for tomorrow get reminders
4. **Check Twilio logs**: https://console.twilio.com/

## Future Enhancements

- [ ] Add SMS reminders (fallback if call fails)
- [ ] Add email reminders
- [ ] Marketing/promotional calls
- [ ] Customer satisfaction surveys (post-service)
- [ ] No-show follow-up calls
- [ ] Queue-based architecture (Celery/Bull)
- [ ] Distributed locking for multi-worker setup
- [ ] Webhook for call completion status
- [ ] Call recording and transcription storage
- [ ] AI analysis of call outcomes

## Support

For issues or questions:
1. Check logs: `docker logs automotive-worker`
2. Review error messages
3. Test with `scripts/test_reminder_job.py`
4. Check Twilio console for call logs
5. Verify database records (call_logs table)
