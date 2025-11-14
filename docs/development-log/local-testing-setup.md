# Local Testing Setup Summary

## Quick Start Commands

### 1. Start Server
```bash
source .venv/bin/activate
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start ngrok (new terminal)
```bash
ngrok http 8000
# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

### 3. Update .env
```bash
BASE_URL=https://abc123.ngrok.io  # Your ngrok URL
YOUR_TEST_NUMBER=+15555555555     # Your phone for testing
```

### 4. Configure Twilio
- Go to Twilio Console → Phone Numbers
- Set webhook: `https://abc123.ngrok.io/api/v1/webhooks/incoming-call`

### 5. Test Inbound
- Call your Twilio number from any phone
- AI should answer and guide conversation

### 6. Test Outbound
```bash
# Create test appointment for tomorrow
python test_outbound.py

# Trigger reminder manually
cd worker
python -c "import asyncio; from jobs.reminder_job import send_appointment_reminders; asyncio.run(send_appointment_reminders())"
```

## Key Safety Feature
`YOUR_TEST_NUMBER` in .env restricts ALL outbound calls to only that number during testing. Remove for production.

## Architecture for Local Testing
```
Phone Call → Twilio → ngrok → localhost:8000 → FastAPI → WebSocket → Deepgram/OpenAI
                                                    ↓
                                            PostgreSQL + Redis
```

## Important Notes
1. ngrok URLs expire after 2 hours (free tier) - restart and update Twilio webhook
2. Keep server, ngrok, and worker terminals running
3. Monitor server terminal for real-time logs
4. Check health: `curl http://localhost:8000/health`
5. Database should have mock data: `python scripts/generate_mock_crm_data.py`

## Created Documentation
- docs/local-testing-guide.md - Complete walkthrough with troubleshooting
