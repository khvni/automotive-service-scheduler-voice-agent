# Implementation Guide - Automotive Voice Agent

## Quick Reference: What We're Building

**Voice Flow:**
```
Caller → Twilio → FastAPI WebSocket → Deepgram STT → GPT-4o → Deepgram TTS → Twilio → Caller
                                            ↓
                                    Tool Functions:
                                    - lookup_customer()
                                    - get_vehicle_info()
                                    - check_availability()
                                    - book_appointment()
                                         ↓
                                    Redis (session)
                                    Neon PG (CRM)
                                    Google Calendar (appointments)
```

## Project Structure (Already Created)

```
automotive-voice/
├── server/
│   └── app/
│       ├── main.py                    # FastAPI entry point
│       ├── config.py                  # Environment variables
│       ├── models/                    # SQLAlchemy models
│       │   ├── customer.py
│       │   ├── vehicle.py
│       │   ├── appointment.py
│       │   └── call_log.py
│       ├── services/
│       │   ├── database.py            # Postgres connection
│       │   └── redis_client.py        # Redis connection
│       ├── routes/
│       │   ├── health.py              # Health check endpoint
│       │   ├── voice.py               # Voice call WebSocket handler
│       │   └── webhooks.py            # Twilio webhooks
│       └── tools/
│           ├── crm_tools.py           # Customer/vehicle lookup
│           ├── calendar_tools.py      # Google Calendar functions
│           └── vin_tools.py           # VIN decoder (optional)
├── worker/
│   ├── main.py                        # Cron worker entry
│   └── jobs/
│       └── reminder_job.py            # Daily appointment reminders
├── scripts/
│   ├── init_db.py                     # Create tables
│   ├── generate_mock_crm_data.py      # Faker data generation
│   └── test_tools.py                  # Test tool functions
├── requirements.txt
├── .env.example
└── README.md
```

## Step-by-Step Implementation Plan

### Phase 1: Foundation (Hours 1-4)

#### 1.1 Database Setup
```bash
# Install dependencies
pip install faker faker-vehicle sqlalchemy asyncpg

# Run database init
python scripts/init_db.py

# Generate mock data
python scripts/generate_mock_crm_data.py
```

**Expected Output:**
- 10,000 customers loaded
- 16,000 vehicles loaded
- 8,000 appointments loaded

#### 1.2 Redis Setup
```bash
# Local development
docker run -d -p 6379:6379 redis:alpine

# Or use Upstash (serverless, free tier)
# https://upstash.com/
```

#### 1.3 Environment Variables
```bash
# .env
NEON_DATABASE_URL=postgresql://user:pass@host/dbname
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
YOUR_TEST_NUMBER=+1...  # POC safety: only call this number
```

### Phase 2: Core Voice Pipeline (Hours 5-12)

#### 2.1 Deepgram STT Integration
```python
# server/app/services/deepgram_stt.py
from deepgram import DeepgramClient, LiveTranscriptionEvents
import asyncio

class DeepgramSTTService:
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.connection = None
        self.transcript_queue = asyncio.Queue()
    
    async def connect(self):
        self.connection = self.client.listen.live({
            "model": "nova-2-phonecall",
            "language": "en",
            "smart_format": True,
            "encoding": "mulaw",
            "sample_rate": 8000,
            "channels": 1,
            "interim_results": True,  # For barge-in detection
            "endpointing": 300,
            "utterance_end_ms": 1000
        })
        
        self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        await self.connection.start()
    
    async def _on_transcript(self, result):
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            if result.is_final:
                await self.transcript_queue.put({
                    "type": "final",
                    "text": transcript
                })
            else:
                await self.transcript_queue.put({
                    "type": "interim",
                    "text": transcript
                })
    
    async def send_audio(self, audio_chunk: bytes):
        if self.connection:
            self.connection.send(audio_chunk)
    
    async def get_transcript(self):
        return await self.transcript_queue.get()
```

#### 2.2 Deepgram TTS Integration
```python
# server/app/services/deepgram_tts.py
import websockets
import json

class DeepgramTTSService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws_url = "wss://api.deepgram.com/v1/speak?encoding=mulaw&sample_rate=8000&container=none"
    
    async def synthesize_stream(self, text: str):
        """Stream TTS audio back"""
        headers = {
            "Authorization": f"Token {self.api_key}"
        }
        
        async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
            # Send text chunks
            await ws.send(json.dumps({"type": "Speak", "text": text}))
            await ws.send(json.dumps({"type": "Flush"}))
            
            # Receive audio chunks
            async for message in ws:
                try:
                    # JSON control messages
                    json.loads(message)
                except:
                    # Binary audio data
                    yield message
```

#### 2.3 Main Voice Handler
```python
# server/app/routes/voice.py
from fastapi import WebSocket, APIRouter
import asyncio

router = APIRouter()

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    
    # Initialize services
    stt = DeepgramSTTService(DEEPGRAM_API_KEY)
    tts = DeepgramTTSService(DEEPGRAM_API_KEY)
    
    await stt.connect()
    
    # Session state
    call_sid = None
    stream_sid = None
    conversation_history = []
    speaking = False
    
    async def receive_from_twilio():
        """Handle incoming audio from Twilio"""
        async for message in websocket.iter_text():
            data = json.loads(message)
            
            if data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                print(f"Call started: {call_sid}")
            
            elif data['event'] == 'media':
                # Send audio to Deepgram STT
                audio = base64.b64decode(data['media']['payload'])
                await stt.send_audio(audio)
    
    async def process_transcripts():
        """Handle transcripts and generate responses"""
        while True:
            transcript_data = await stt.get_transcript()
            
            if transcript_data['type'] == 'interim':
                # Barge-in detection
                if speaking:
                    print("User interrupted, clearing audio")
                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid
                    })
                    speaking = False
            
            elif transcript_data['type'] == 'final':
                user_message = transcript_data['text']
                conversation_history.append({
                    "role": "user",
                    "content": user_message
                })
                
                # GPT-4o reasoning
                response = await openai.chat.completions.create(
                    model="gpt-4o",
                    messages=conversation_history,
                    tools=get_tool_definitions(),
                    temperature=0.8
                )
                
                # Handle tool calls
                if response.choices[0].message.tool_calls:
                    for tool_call in response.choices[0].message.tool_calls:
                        result = await execute_tool(tool_call)
                        # Add result to conversation
                        conversation_history.append({
                            "role": "function",
                            "name": tool_call.function.name,
                            "content": json.dumps(result)
                        })
                    
                    # Get final response after tool execution
                    response = await openai.chat.completions.create(
                        model="gpt-4o",
                        messages=conversation_history
                    )
                
                assistant_message = response.choices[0].message.content
                conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                # Synthesize speech
                speaking = True
                async for audio_chunk in tts.synthesize_stream(assistant_message):
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": base64.b64encode(audio_chunk).decode()
                        }
                    })
                speaking = False
    
    # Run both tasks concurrently
    await asyncio.gather(
        receive_from_twilio(),
        process_transcripts()
    )
```

### Phase 3: Tool Functions (Hours 13-20)

#### 3.1 CRM Tools
```python
# server/app/tools/crm_tools.py
async def lookup_customer(phone: str):
    """
    Lookup customer by phone number (with Redis caching)
    """
    # Check cache
    cached = await redis.get(f"customer:{phone}")
    if cached:
        return json.loads(cached)
    
    # Query database
    customer = await db.fetch_one(
        """
        SELECT c.*, 
               json_agg(v.*) as vehicles
        FROM customers c
        LEFT JOIN vehicles v ON v.customer_id = c.id
        WHERE c.phone = :phone
        GROUP BY c.id
        """,
        {"phone": phone}
    )
    
    if customer:
        # Cache for 5 minutes
        await redis.setex(
            f"customer:{phone}",
            300,
            json.dumps(customer)
        )
    
    return customer
```

#### 3.2 Calendar Tools
```python
# server/app/tools/calendar_tools.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

async def get_available_slots(date: str):
    """
    Get available time slots for a given date
    Returns slots between 9 AM - 5 PM, excluding lunch (12-1 PM)
    """
    service = get_calendar_service()
    
    # Parse date
    start_time = datetime.fromisoformat(f"{date}T09:00:00")
    end_time = datetime.fromisoformat(f"{date}T17:00:00")
    
    # Query freebusy
    body = {
        "timeMin": start_time.isoformat() + "Z",
        "timeMax": end_time.isoformat() + "Z",
        "items": [{"id": "primary"}]
    }
    
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.freebusy().query(body=body).execute()
    )
    
    busy_periods = result['calendars']['primary']['busy']
    
    # Calculate free slots
    free_slots = calculate_free_slots(busy_periods, start_time, end_time)
    
    return free_slots


async def book_appointment(
    customer_name: str,
    phone: str,
    vehicle_info: str,
    service_type: str,
    start_time: str
):
    """
    Book appointment in both Google Calendar and CRM database
    """
    # Create calendar event
    service = get_calendar_service()
    
    event = {
        "summary": f"{service_type} - {customer_name}",
        "description": f"Vehicle: {vehicle_info}\nPhone: {phone}",
        "start": {
            "dateTime": start_time,
            "timeZone": "America/New_York"
        },
        "end": {
            "dateTime": (datetime.fromisoformat(start_time) + timedelta(minutes=30)).isoformat(),
            "timeZone": "America/New_York"
        }
    }
    
    calendar_event = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.events().insert(calendarId='primary', body=event).execute()
    )
    
    # Save to database
    appointment = await db.execute(
        """
        INSERT INTO appointments 
        (id, customer_id, vehicle_id, service_type, scheduled_at, calendar_event_id, status)
        VALUES (:id, :customer_id, :vehicle_id, :service_type, :scheduled_at, :calendar_event_id, 'scheduled')
        """,
        {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "service_type": service_type,
            "scheduled_at": start_time,
            "calendar_event_id": calendar_event["id"]
        }
    )
    
    return {
        "success": True,
        "appointment_id": appointment["id"],
        "calendar_link": calendar_event["htmlLink"]
    }
```

### Phase 4: Outbound Reminders (Hours 21-24)

```python
# worker/jobs/reminder_job.py
from twilio.rest import Client
import asyncio

async def send_appointment_reminders():
    """
    Run daily at 9 AM to remind customers about tomorrow's appointments
    """
    # Find appointments for tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    
    appointments = await db.fetch_all(
        """
        SELECT a.*, c.phone, c.name, v.make, v.model
        FROM appointments a
        JOIN customers c ON c.id = a.customer_id
        JOIN vehicles v ON v.id = a.vehicle_id
        WHERE DATE(a.scheduled_at) = :tomorrow
        AND a.status = 'scheduled'
        """,
        {"tomorrow": tomorrow}
    )
    
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    for appt in appointments:
        # POC SAFETY: Only call YOUR_TEST_NUMBER
        if appt['phone'] != YOUR_TEST_NUMBER:
            print(f"Skipping call to {appt['phone']} (POC safety)")
            continue
        
        # Make outbound call
        call = twilio_client.calls.create(
            to=appt['phone'],
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}/outbound-reminder?appointment_id={appt['id']}"
        )
        
        print(f"Reminder call initiated: {call.sid}")
        await asyncio.sleep(2)  # Rate limiting
```

## Testing Checklist

- [ ] Health endpoint returns 200
- [ ] Database has mock data loaded
- [ ] Redis connection works
- [ ] Twilio Media Stream connects
- [ ] Deepgram STT receives audio and transcribes
- [ ] GPT-4o generates responses
- [ ] Deepgram TTS synthesizes audio
- [ ] Customer lookup tool works (cached + DB)
- [ ] Calendar availability check works
- [ ] Appointment booking works (Calendar + DB)
- [ ] Barge-in detection triggers audio clear
- [ ] Outbound reminder calls only YOUR_NUMBER

## Performance Targets

| Operation | Target Latency |
|-----------|---------------|
| Customer lookup (cached) | <2ms |
| Customer lookup (DB) | <30ms |
| Calendar freebusy | <1s |
| Appointment booking | <2s |
| STT transcript (final) | <500ms |
| TTS first byte | <300ms |
| Barge-in response | <200ms |

## Common Issues & Solutions

### Issue: High STT latency
**Solution:** Ensure `interim_results: True` and `endpointing: 300` in Deepgram config

### Issue: Barge-in not working
**Solution:** Check interim transcript handler triggers `clear` event to Twilio

### Issue: Google Calendar 401
**Solution:** Refresh OAuth token using `refresh_token` flow

### Issue: Redis connection timeout
**Solution:** Use connection pooling with `aioredis` or `redis-py` with `decode_responses=True`

---

**Next Steps:**
1. Run Phase 1 (database + mock data)
2. Test individual services (STT, TTS, tools)
3. Build Phase 2 (voice pipeline)
4. Integrate Phase 3 (tools)
5. Deploy Phase 4 (reminders)
6. Demo with YOUR_NUMBER