# Local Testing Guide

Complete guide for testing the voice agent locally with both inbound and outbound calls.

## Prerequisites

1. **Twilio Account** with phone number
2. **Deepgram API Key**
3. **OpenAI API Key**
4. **Google Calendar OAuth2** credentials
5. **ngrok** for local tunnel (free account)
6. **PostgreSQL** running locally or Neon account
7. **Redis** running locally or Upstash account

## Quick Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install server dependencies
cd server
pip install -r requirements.txt

# Install worker dependencies
cd ../worker
pip install -r requirements.txt
cd ..
```

### 2. Setup Local Database

**Option A: Use existing Neon database** (easiest)
- Skip this step, use your existing DATABASE_URL from .env

**Option B: Local PostgreSQL**
```bash
# Start PostgreSQL (if not running)
brew services start postgresql  # macOS
# OR
sudo systemctl start postgresql  # Linux

# Create database
createdb automotive_voice

# Run migrations
cd server
alembic upgrade head

# Generate mock data
cd ..
python scripts/generate_mock_crm_data.py
```

### 3. Setup Local Redis

**Option A: Use existing Upstash** (easiest)
- Skip this step, use your existing REDIS_URL from .env

**Option B: Local Redis**
```bash
# Start Redis
brew services start redis  # macOS
# OR
sudo systemctl start redis  # Linux

# Test connection
redis-cli ping  # Should return PONG
```

### 4. Install ngrok

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com/download

# Authenticate (one-time setup)
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Critical .env settings for local testing:**
```bash
# Your actual credentials
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/automotive_voice  # pragma: allowlist secret
REDIS_URL=redis://localhost:6379/0

TWILIO_ACCOUNT_SID=ACxxxxx...
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+15551234567

DEEPGRAM_API_KEY=your_key
OPENAI_API_KEY=sk-proj-...

GOOGLE_CLIENT_ID=your_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token

# FOR TESTING: Restrict outbound calls to your test number only
YOUR_TEST_NUMBER=+15555555555  # Your actual phone number

# Will be set by ngrok (see below)
BASE_URL=https://your-ngrok-url.ngrok.io
```

## Testing Inbound Calls

### Step 1: Start the Server

```bash
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start ngrok Tunnel

In a **new terminal**:
```bash
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Step 3: Update .env and Restart Server

```bash
# Update BASE_URL in .env
BASE_URL=https://abc123.ngrok.io  # Your actual ngrok URL

# Restart the server
# Press Ctrl+C in server terminal, then restart:
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to: **Phone Numbers** → **Manage** → **Active numbers**
3. Click your phone number
4. Scroll to **Voice Configuration**
5. Set **A CALL COMES IN** webhook to:
   ```
   https://abc123.ngrok.io/api/v1/webhooks/incoming-call
   ```
6. Method: **HTTP POST**
7. Click **Save**

### Step 5: Make a Test Call

Call your Twilio phone number from your mobile phone.

**Expected flow:**
1. Call connects
2. AI greets you: "Hello! Thank you for calling Otto's Auto. How can I help you today?"
3. Say something like: "I need to book an oil change"
4. AI will look up your phone number and guide you through booking

**Monitor logs in server terminal:**
```
INFO: Incoming call - From: +15555555555, CallSid: CAxxxxx
INFO: WebSocket connected - CallSid: CAxxxxx
INFO: Transcription: "I need to book an oil change"
INFO: Tool called: lookup_customer
INFO: AI Response: "I found your account..."
```

### Troubleshooting Inbound Calls

**Call connects but AI doesn't respond:**
- Check server logs for errors
- Verify BASE_URL in .env matches ngrok URL exactly (no trailing slash)
- Check Deepgram and OpenAI API keys are valid

**WebSocket won't connect:**
- Ensure ngrok is running and forwarding to port 8000
- Check Twilio webhook URL is correct (must be HTTPS ngrok URL)
- Verify no firewall blocking connections

**"Customer not found" even though you exist:**
- Check if your phone number is in the database
- Run: `python scripts/generate_mock_crm_data.py` to add test customers
- Or call with a phone number that exists in the mock data

## Testing Outbound Calls

### Step 1: Ensure Server is Running

```bash
# Server should already be running from inbound test
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 2: Configure Test Number

In `.env`, set YOUR_TEST_NUMBER to your actual phone:
```bash
YOUR_TEST_NUMBER=+15551234567  # Your mobile number
```

This safety feature ensures outbound calls only go to your test number during development.

### Step 3: Create Test Appointment

**Option A: Use API to create appointment**

```bash
# Create an appointment for tomorrow
curl -X POST http://localhost:8000/api/v1/appointments \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "vehicle_id": 1,
    "appointment_datetime": "2025-11-14T14:00:00",
    "service_type": "Oil Change",
    "notes": "Test appointment"
  }'
```

**Option B: Use Python script**

Create `test_outbound.py`:
```python
import asyncio
from datetime import datetime, timedelta
import sys
sys.path.append("server")

from app.services.database import get_db, init_db
from app.models.appointment import Appointment

async def create_test_appointment():
    await init_db()
    async for db in get_db():
        # Create appointment for tomorrow at 2 PM
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=14, minute=0, second=0)

        appointment = Appointment(
            customer_id=1,  # Assumes customer with ID 1 exists
            vehicle_id=1,   # Assumes vehicle with ID 1 exists
            appointment_datetime=tomorrow,
            service_type="Oil Change",
            status="scheduled",
            notes="Test reminder call"
        )
        db.add(appointment)
        await db.commit()
        print(f"Created appointment ID: {appointment.id}")
        print(f"Scheduled for: {appointment.appointment_datetime}")
        return appointment.id

if __name__ == "__main__":
    asyncio.run(create_test_appointment())
```

Run it:
```bash
python test_outbound.py
```

### Step 4: Test Outbound Call Manually

**Option A: Trigger reminder job directly**

```bash
cd worker
python -c "
import asyncio
from jobs.reminder_job import send_appointment_reminders
asyncio.run(send_appointment_reminders())
"
```

**Option B: Use test script**

```bash
python scripts/test_reminder_job.py
```

### Step 5: Verify Call

You should receive a call on YOUR_TEST_NUMBER with:

1. **Greeting:** "Hello [Customer Name], this is Otto's Auto calling with a reminder."
2. **Appointment details:** "You have an appointment tomorrow at 2 PM for an oil change."
3. **Confirmation prompt:** "Please press 1 to confirm, or 2 to reschedule."

### Step 6: Test Worker (Scheduled Reminders)

To test the actual cron worker:

```bash
cd worker
python main.py
```

**Monitor logs:**
```
INFO: Starting outbound call worker...
INFO: Scheduler started. Jobs: ['appointment_reminders']
```

The worker runs on a cron schedule (default: 9 AM daily). To test immediately, modify `worker/config.py`:

```python
# Change from:
REMINDER_CRON_SCHEDULE = "0 9 * * *"  # 9 AM daily

# To:
REMINDER_CRON_SCHEDULE = "*/2 * * * *"  # Every 2 minutes (for testing)
```

### Troubleshooting Outbound Calls

**No call received:**
- Verify YOUR_TEST_NUMBER is set correctly in .env (include country code)
- Check Twilio console for call logs and errors
- Ensure appointment exists and is scheduled for tomorrow
- Check Twilio account has credits

**Call received but no audio:**
- Verify ngrok is still running
- Check outbound webhook URL is configured in Twilio
- Review server logs for TwiML generation errors

**"All circuits are busy" error:**
- Check Twilio account status
- Verify phone number is valid E.164 format (+1XXXXXXXXXX)
- Ensure Twilio number has outbound calling enabled

## Demo Walkthrough

### Complete Inbound Test Scenario

1. **Call Twilio number**
2. **AI:** "Hello! Thank you for calling Otto's Auto. How can I help you today?"
3. **You:** "I need to schedule an oil change"
4. **AI:** "I'd be happy to help you schedule an oil change. Can I get your phone number?"
5. **You:** "555-0123"
6. **AI:** "Thanks! I found your account, John. I see you have a 2021 Honda Accord. When would you like to bring it in?"
7. **You:** "How about next Tuesday afternoon?"
8. **AI:** "I have availability next Tuesday at 2 PM, 3 PM, and 4 PM. Which time works for you?"
9. **You:** "2 PM is perfect"
10. **AI:** "Great! I've booked your oil change for Tuesday at 2 PM. You'll receive a reminder call the day before. Is there anything else I can help you with?"
11. **You:** "No, that's all"
12. **AI:** "Perfect! Have a great day and we'll see you on Tuesday!"

### Complete Outbound Test Scenario

1. **You receive call** on YOUR_TEST_NUMBER
2. **AI:** "Hello John, this is Otto's Auto calling with a reminder about your appointment."
3. **AI:** "You have an appointment tomorrow, Tuesday, November 14th at 2 PM for an oil change on your 2021 Honda Accord."
4. **AI:** "Please press 1 to confirm your appointment, press 2 if you need to reschedule, or press 3 to cancel."
5. **You:** Press 1
6. **AI:** "Thank you for confirming! We'll see you tomorrow at 2 PM. If anything changes, please call us. Have a great day!"

## Monitoring & Debugging

### Check Health Endpoint

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}
```

### View Real-time Logs

**Server logs:**
```bash
# Server terminal shows all activity
# Watch for: WebSocket connections, transcriptions, tool calls, AI responses
```

**Database queries:**
```bash
# Connect to database
psql automotive_voice

# View recent appointments
SELECT * FROM appointments ORDER BY created_at DESC LIMIT 5;

# View customers
SELECT * FROM customers LIMIT 5;
```

**Redis cache:**
```bash
redis-cli

# View all keys
KEYS *

# View session data
GET session:{call_sid}

# Clear cache (if needed)
FLUSHDB
```

### Common Issues

**ngrok session expired:**
```bash
# Free ngrok URLs expire after 2 hours
# Restart ngrok to get new URL, then update .env and Twilio webhook
```

**Database connection refused:**
```bash
# Check if PostgreSQL is running
pg_isready

# Start if needed
brew services start postgresql
```

**Redis connection refused:**
```bash
# Check if Redis is running
redis-cli ping

# Start if needed
brew services start redis
```

## Production Testing Checklist

Before deploying to production, test:

- [ ] Inbound call connects successfully
- [ ] AI can hear and transcribe speech accurately
- [ ] Customer lookup works (cached and uncached)
- [ ] Appointment booking creates database entry
- [ ] Calendar integration shows correct availability
- [ ] Call ends gracefully
- [ ] Outbound call reaches correct number
- [ ] Reminder contains accurate appointment details
- [ ] DTMF input (press 1, 2, 3) works
- [ ] Confirmation updates database
- [ ] Error handling works (invalid input, API failures)
- [ ] Latency is acceptable (<2 seconds)

## Next Steps

Once local testing is complete:
1. Review [docs/deployment.md](deployment.md) for production deployment
2. Check [docs/production-checklist.md](production-checklist.md) before launch
3. Remove YOUR_TEST_NUMBER from .env for production
4. Setup proper monitoring and logging
