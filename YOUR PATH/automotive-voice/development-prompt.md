# Development Prompt for Claude Code - Automotive Voice Agent

## Project Context

You are building a **48-hour POC** for an AI-powered voice agent for Bart's Automotive, a car dealership/service center. The system handles inbound calls for appointment scheduling and outbound reminder calls.

## Architecture Overview

**Technology Stack:**
- **Runtime:** Python, FastAPI, asyncio
- **Audio Pipeline:** Twilio Media Streams → Deepgram STT (nova-2-phonecall) → GPT-4o → Deepgram TTS → Twilio
- **State Management:** Redis (session state, customer cache)
- **Database:** Neon Postgres + SQLAlchemy
- **Calendar:** Google Calendar API (real integration)
- **Data:** Faker library (10k customers, 16k vehicles, 8k appointments)

**Key Design Principles:**
1. Single streaming pipeline (modular TTS/STT providers)
2. Custom LLM orchestration (NOT OpenAI Realtime API)
3. Inline function execution (no queue workers)
4. Cron-based outbound calls (daily at 9 AM)

## Memory Bank Files - READ THESE FIRST ⭐

Before starting, read these files from the allpepper-memory-bank project `automotive-voice`:

1. **architecture-decisions.md** - Complete tech stack, tradeoffs, and rationale
2. **customer-data-schema.md** - Database schema with verification fields
3. **call-flows-and-scripts.md** - Conversation flows for all call types
4. **implementation-guide.md** - Step-by-step implementation plan
5. **reference-repositories.md** - GitHub repos with code to copy ⭐⭐⭐

## Reference Repositories - USE GITHUB MCP ⭐⭐⭐

**IMPORTANT:** Use the GitHub MCP to read production-ready code from these repositories. See **reference-repositories.md** for detailed guidance on what to copy from each repo.

### Priority Repositories (Must Read Before Implementation)

**1. deepgram/deepgram-twilio-streaming-voice-agent** ⭐⭐⭐
- **Use for:** Features 3, 4, 5, 8
- **Read:** `server.js` (entire file)
- **Copy directly:**
  - Deepgram STT configuration (lines 230-290)
  - Deepgram TTS WebSocket setup (lines 165-210)
  - Barge-in detection logic (lines 298-330)
  - Streaming LLM integration (lines 137-160)

**2. duohub-ai/google-calendar-voice-agent** ⭐⭐⭐
- **Use for:** Feature 7
- **Read:** `calendar_service.py` (entire file), `bot.py`
- **Copy directly:**
  - OAuth2 refresh token pattern
  - Freebusy availability logic
  - Event creation/update/cancel operations
  - Timezone handling

**3. twilio-samples/speech-assistant-openai-realtime-api-python** ⭐⭐⭐
- **Use for:** Features 8, 9
- **Read:** `main.py` (entire file)
- **Copy directly:**
  - FastAPI WebSocket handler structure
  - Twilio Media Stream event handling
  - Interruption handling (lines 141-168)
  - TwiML response generation

**4. Barty-Bart/openai-realtime-api-voice-assistant-V2** ⭐⭐
- **Use for:** Features 5, 8
- **Read:** `index.js` (lines 237-430)
- **Copy patterns:**
  - Function calling schema definitions
  - Inline function execution
  - Session management (translate to Redis)

### How to Use GitHub MCP

Before implementing each feature, read the relevant repositories:

```python
# Example: Before Feature 3 (Deepgram STT)
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)

# Example: Before Feature 7 (Google Calendar)
mcp__github__get_file_contents(
    owner="duohub-ai",
    repo="google-calendar-voice-agent",
    path="calendar_service.py"
)

# Example: Before Feature 8 (WebSocket Handler)
mcp__github__get_file_contents(
    owner="twilio-samples",
    repo="speech-assistant-openai-realtime-api-python",
    path="main.py"
)
```

**Refer to reference-repositories.md for:**
- Specific line numbers to focus on
- Node.js → Python translation patterns
- What to copy vs. what to adapt

## Project Structure

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
│       │   ├── redis_client.py        # Redis connection
│       │   ├── deepgram_stt.py        # Deepgram STT service
│       │   ├── deepgram_tts.py        # Deepgram TTS service
│       │   └── openai_service.py      # GPT-4o integration
│       ├── routes/
│       │   ├── health.py              # Health check
│       │   ├── voice.py               # WebSocket handler (MAIN)
│       │   └── webhooks.py            # Twilio webhooks
│       └── tools/
│           ├── crm_tools.py           # Customer/vehicle lookup
│           ├── calendar_tools.py      # Google Calendar
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

## Feature List (Delegate to Sub-Agents)

Implement features in this order, delegating each to a separate planning session or agent:

### **Feature 1: Database Setup & Mock Data Generation**
**Goal:** Set up Neon Postgres database with complete schema and load realistic mock data

**Reference Repos:** None (straightforward SQLAlchemy + Faker)

**Tasks:**
- Create SQLAlchemy models for customers, vehicles, appointments, call_logs, service_history (see customer-data-schema.md)
- Add indexes for phone, VIN, scheduled_at
- Write `scripts/init_db.py` to create tables
- Write `scripts/generate_mock_crm_data.py` using Faker + faker-vehicle
  - 10,000 customers with DOB, addresses, preferences
  - 16,000 vehicles with VINs, service history
  - 8,000 appointments (past and future)
- Add `scripts/test_db.py` to verify data loaded correctly

**Acceptance Criteria:**
- Database has all tables with proper relationships
- Mock data loads in <2 minutes
- Customer lookup by phone returns results in <30ms
- Sample queries work (get customer vehicles, upcoming appointments)

---

### **Feature 2: Redis Session Management**
**Goal:** Implement Redis for session state and customer caching

**Reference Repos:** Barty-Bart/openai-realtime-api-voice-assistant-V2 (session management patterns)

**Tasks:**
- Create `server/app/services/redis_client.py` with connection pooling
- Implement session state management:
  - `session:{call_sid}` → conversation history, collected slots, current state
- Implement customer cache:
  - `customer:{phone}` → customer + vehicles data (5min TTL)
- Add Redis health check to `/health` endpoint
- Write `scripts/test_redis.py` to verify caching works

**Acceptance Criteria:**
- Redis connects successfully (local or Upstash)
- Session state persists across requests
- Customer cache reduces DB queries (hit rate >80% in tests)
- TTL expires correctly after 5 minutes

---

### **Feature 3: Deepgram STT Integration**
**Goal:** Receive audio from Twilio and transcribe to text using Deepgram

**Reference Repos:** ⭐⭐⭐ deepgram/deepgram-twilio-streaming-voice-agent

**Before Starting:**
```python
# Read this file via GitHub MCP
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)
```

**Focus on lines 230-330 in server.js:**
- STT configuration (lines 230-260)
- Transcript event handling (lines 298-330)
- Interim results for barge-in (lines 310-320)

**Tasks:**
- Create `server/app/services/deepgram_stt.py`
- Implement WebSocket connection to Deepgram Live API
- Configure for phone audio (copy from server.js):
  - model: "nova-2-phonecall"
  - encoding: "mulaw", sample_rate: 8000
  - interim_results: True (for barge-in detection)
  - endpointing: 300, utterance_end_ms: 1000
- Implement async queue for transcripts (interim + final)
- Handle barge-in: interim transcripts trigger audio clear
- Add logging for transcript events

**Acceptance Criteria:**
- Deepgram STT connects via WebSocket
- Receives mulaw audio chunks from Twilio
- Returns interim transcripts (for barge-in)
- Returns final transcripts (for LLM processing)
- Logs transcript events for debugging

---

### **Feature 4: Deepgram TTS Integration**
**Goal:** Synthesize GPT-4o responses to audio and send to Twilio

**Reference Repos:** ⭐⭐⭐ deepgram/deepgram-twilio-streaming-voice-agent

**Before Starting:**
```python
# Read server.js again, focus on TTS section
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)
```

**Focus on lines 165-210 in server.js:**
- TTS WebSocket setup (lines 165-175)
- Streaming patterns (Speak/Flush commands)
- Time-to-first-byte tracking (lines 183-190)

**Tasks:**
- Create `server/app/services/deepgram_tts.py`
- Implement WebSocket streaming to Deepgram TTS API
- Configure for phone audio:
  - encoding: "mulaw", sample_rate: 8000, container: "none"
- Implement async streaming: send text chunks, receive audio chunks
- Handle Speak/Flush commands for streaming
- Measure time-to-first-byte (log for optimization)
- Abstract behind TTS interface for future ElevenLabs swap

**Acceptance Criteria:**
- Deepgram TTS connects via WebSocket
- Accepts text input (streaming or full sentence)
- Returns mulaw audio chunks
- Time-to-first-byte <300ms
- Interface allows easy provider swap (TTS protocol/ABC)

---

### **Feature 5: OpenAI GPT-4o Integration**
**Goal:** Implement conversational AI with function calling for appointment scheduling

**Reference Repos:**
- ⭐⭐⭐ deepgram/deepgram-twilio-streaming-voice-agent (lines 137-160)
- ⭐⭐ Barty-Bart/openai-realtime-api-voice-assistant-V2 (lines 237-430)

**Before Starting:**
```python
# Read LLM integration from Deepgram repo
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)

# Read function calling from Barty-Bart repo
mcp__github__get_file_contents(
    owner="Barty-Bart",
    repo="openai-realtime-api-voice-assistant-V2",
    path="index.js"
)
```

**Tasks:**
- Create `server/app/services/openai_service.py`
- Implement standard OpenAI SDK (NOT Realtime API)
- Build conversation history management (system + user + assistant + function messages)
- Define function/tool schemas (copy from Barty-Bart lines 237-280):
  - `lookup_customer(phone: str)`
  - `get_vehicle_info(customer_id: str)`
  - `get_available_slots(date: str)`
  - `book_appointment(...)`
  - `reschedule_appointment(...)`
  - `cancel_appointment(...)`
- Implement tool execution router (copy inline pattern from lines 360-430)
- Build system prompts for each call type (see call-flows-and-scripts.md)
- Add token usage logging

**Acceptance Criteria:**
- GPT-4o generates contextual responses
- Function calls execute correctly
- Conversation history maintains context
- System prompts personalize responses (customer name, history)
- Token usage logged for cost tracking

---

### **Feature 6: CRM Tool Functions**
**Goal:** Implement customer/vehicle lookup with Redis caching

**Reference Repos:** None (straightforward database queries)

**Tasks:**
- Create `server/app/tools/crm_tools.py`
- Implement `lookup_customer(phone: str)`:
  - Check Redis cache first
  - Query Postgres if cache miss
  - Return customer + vehicles + upcoming appointments
  - Cache result for 5 minutes
- Implement `get_service_history(vehicle_id: str)`:
  - Query past appointments for vehicle
  - Return last service date, type, mileage
- Implement `create_customer(...)` for new customers
- Implement `create_vehicle(...)` for new vehicles
- Add customer verification helpers (DOB, VIN, address checks)

**Acceptance Criteria:**
- `lookup_customer()` returns complete customer data
- Cache hit: <2ms, cache miss: <30ms
- New customer creation works
- Verification helpers validate correctly
- All functions have proper error handling

---

### **Feature 7: Google Calendar Integration**
**Goal:** Real calendar integration for appointment scheduling

**Reference Repos:** ⭐⭐⭐ duohub-ai/google-calendar-voice-agent

**Before Starting:**
```python
# Read the ENTIRE calendar service - this is a goldmine
mcp__github__get_file_contents(
    owner="duohub-ai",
    repo="google-calendar-voice-agent",
    path="calendar_service.py"
)

# Also read tool definitions
mcp__github__get_file_contents(
    owner="duohub-ai",
    repo="google-calendar-voice-agent",
    path="bot.py"
)
```

**COPY DIRECTLY from calendar_service.py:**
- OAuth2 setup (lines 82-95)
- `get_free_availability()` (lines 145-180)
- `create_calendar_event()` (lines 112-144)
- `update_calendar_event()` (lines 182-220)
- `cancel_calendar_event()` (lines 222-245)
- `_parse_start_time()` (lines 255-265)
- `_process_freebusy_response()` (lines 267-285)

**Tasks:**
- Create `server/app/tools/calendar_tools.py`
- Copy and adapt the entire CalendarService class
- Implement OAuth2 refresh token flow
- Implement `get_available_slots(date: str)`:
  - Query Google Calendar freebusy API
  - Return slots between 9 AM - 5 PM (exclude 12-1 PM lunch)
  - Calculate free periods from busy blocks
- Implement `book_appointment(...)`:
  - Create Google Calendar event
  - Store calendar_event_id in database
  - Handle timezone (configurable in .env)
- Implement `update_appointment(...)`:
  - Update Google Calendar event
  - Update database record
- Use async wrapper for blocking Google API calls
- Add retry logic for API failures

**Acceptance Criteria:**
- OAuth2 refresh token works
- Freebusy query returns available slots
- Event creation works (visible in Google Calendar)
- Event updates work (reschedule)
- Timezone handling correct
- All operations <1 second latency

---

### **Feature 8: Main Voice WebSocket Handler**
**Goal:** Orchestrate Twilio ↔ Deepgram ↔ GPT-4o ↔ Deepgram flow

**Reference Repos:**
- ⭐⭐⭐ twilio-samples/speech-assistant-openai-realtime-api-python
- ⭐⭐⭐ deepgram/deepgram-twilio-streaming-voice-agent

**Before Starting:**
```python
# Read the complete Twilio WebSocket handler
mcp__github__get_file_contents(
    owner="twilio-samples",
    repo="speech-assistant-openai-realtime-api-python",
    path="main.py"
)

# Read barge-in logic from Deepgram repo
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)
```

**COPY DIRECTLY from main.py:**
- WebSocket event handling structure (lines 60-130)
- Interruption handling (lines 141-168)
- Mark queue pattern

**COPY barge-in detection from server.js (lines 310-320)**

**Tasks:**
- Create `server/app/routes/voice.py`
- Implement `/media-stream` WebSocket endpoint
- Handle Twilio events:
  - `start`: Initialize session, get call_sid, stream_sid
  - `media`: Forward audio to Deepgram STT
  - `mark`: Track audio playback completion
  - `stop`: End call, save transcript
- Implement two async tasks:
  - `receive_from_twilio()`: Handle incoming audio
  - `process_transcripts()`: Handle STT → LLM → TTS pipeline
- Implement barge-in detection:
  - Interim transcript while speaking → send "clear" to Twilio
- Manage conversation state in Redis
- Log call to call_logs table with transcript
- Handle errors gracefully (reconnection, timeout)

**Acceptance Criteria:**
- WebSocket accepts Twilio Media Stream connections
- Audio flows: Twilio → Deepgram STT → text
- Transcripts trigger GPT-4o responses
- Responses synthesized via Deepgram TTS → Twilio
- Barge-in works (user can interrupt AI)
- Call transcripts saved to database
- Session state persists in Redis

---

### **Feature 9: Twilio Webhooks & Call Routing**
**Goal:** Handle incoming calls and route to WebSocket

**Reference Repos:** ⭐⭐⭐ twilio-samples/speech-assistant-openai-realtime-api-python

**Before Starting:**
```python
# Read TwiML generation
mcp__github__get_file_contents(
    owner="twilio-samples",
    repo="speech-assistant-openai-realtime-api-python",
    path="main.py"
)
```

**COPY DIRECTLY from main.py (lines 38-63):**
- TwiML response structure
- Custom parameter passing

**Tasks:**
- Create `server/app/routes/webhooks.py`
- Implement `/incoming-call` endpoint (GET/POST)
- Return TwiML with:
  - Welcome message
  - `<Connect><Stream>` pointing to `/media-stream` WebSocket
  - Pass custom parameters (caller number, first message)
- Implement `/outbound-reminder` endpoint for outbound calls
- Add call logging (call_sid, direction, caller_phone)
- Handle Twilio call status callbacks (optional)

**Acceptance Criteria:**
- Incoming call triggers TwiML response
- TwiML connects to WebSocket
- Caller number passed to session
- Outbound calls routed correctly
- All calls logged in call_logs table

---

### **Feature 10: Conversation Flow Implementation**
**Goal:** Implement all 6 call flows from call-flows-and-scripts.md

**Reference Repos:** Read call-flows-and-scripts.md from memory bank

**Tasks:**
- Implement Flow 1: New Customer - First Appointment
- Implement Flow 2: Existing Customer - Service Appointment
- Implement Flow 3: Appointment Modification (Reschedule/Cancel)
- Implement Flow 4: General Inquiry
- Implement Flow 5: Appointment Reminder (Outbound)
- Implement Flow 6: Post-Service Follow-Up (Outbound)
- Create system prompt templates for each flow type
- Implement intent detection (which flow to use)
- Add conversation state machine (track progress through flow)
- Implement verification protocol (DOB, VIN, address)
- Add escalation triggers (transfer to human)

**Acceptance Criteria:**
- Each flow completes successfully
- Intent detection >90% accurate in tests
- State machine tracks conversation progress
- Verification works (correct/incorrect responses)
- Escalation triggers appropriately
- Conversations feel natural (not robotic)

---

### **Feature 11: Outbound Call Worker (Cron)**
**Goal:** Daily cron job for appointment reminders

**Reference Repos:** None (straightforward Twilio REST API)

**Tasks:**
- Create `worker/main.py` with APScheduler or simple cron
- Create `worker/jobs/reminder_job.py`
- Implement daily job (9 AM):
  - Query appointments for tomorrow
  - Filter by status = 'scheduled'
  - For each appointment:
    - **POC SAFETY:** Only call YOUR_TEST_NUMBER from .env
    - Use Twilio REST API to make outbound call
    - Point to `/outbound-reminder?appointment_id={id}`
    - Rate limit: 2 second delay between calls
- Log all outbound call attempts
- Mark appointments as `reminder_sent = TRUE`
- Handle call failures (busy, no answer)

**Acceptance Criteria:**
- Cron job runs daily at 9 AM
- Queries tomorrow's appointments correctly
- **Only calls YOUR_TEST_NUMBER** (POC safety check)
- Twilio outbound calls initiated successfully
- Call connects to WebSocket with appointment context
- Reminder script followed (Flow 5)
- Database updated (reminder_sent flag)

---

### **Feature 12: Testing & Validation**
**Goal:** End-to-end testing of all features

**Tasks:**
- Create `scripts/test_tools.py`:
  - Test all CRM tool functions
  - Test calendar functions (mock or real API)
  - Test customer verification
- Create `tests/test_call_flows.py`:
  - Simulate each call flow
  - Verify correct tool calls
  - Check conversation state transitions
- Create `tests/test_integration.py`:
  - Full pipeline test (audio → transcript → response → audio)
- Add performance tests:
  - Customer lookup latency
  - Calendar query latency
  - End-to-end call latency
- Create test data fixtures
- Document test coverage

**Acceptance Criteria:**
- All unit tests pass
- Integration tests pass
- Performance targets met:
  - Customer lookup (cached): <2ms
  - Customer lookup (DB): <30ms
  - Calendar query: <1s
  - End-to-end call: <500ms response time
- Test coverage >80%

---

### **Feature 13: Deployment & Environment Setup**
**Goal:** Production-ready deployment configuration

**Tasks:**
- Create comprehensive `.env.example` with all variables
- Write `requirements.txt` with pinned versions
- Create `README.md` with:
  - Setup instructions
  - Environment variables documentation
  - Architecture diagram
  - API documentation
- Add Docker support (optional):
  - Dockerfile for server
  - docker-compose.yml (server + Redis + worker)
- Add health monitoring:
  - `/health` endpoint checks all services
  - Prometheus metrics (optional)
- Add logging configuration (structured JSON logs)
- Document deployment to Railway/Render/Fly.io

**Acceptance Criteria:**
- `.env.example` complete
- `requirements.txt` accurate
- README comprehensive
- Health endpoint works
- Logs structured and useful
- Deployment documented

---

### **Feature 14: Admin UI (Optional - Time Permitting)**
**Goal:** Simple web UI to browse customers and appointments

**Tasks:**
- Create `server/app/routes/admin.py`
- Implement GET `/admin/customers`:
  - Paginated customer list (50 per page)
  - Search by phone/name
- Implement GET `/admin/customers/{id}`:
  - Customer detail page
  - Show vehicles
  - Show appointment history
- Implement GET `/admin/appointments`:
  - Upcoming appointments view
  - Filter by date range
- Create simple HTML templates (Jinja2 + Tailwind CSS)
- No auth required for POC (add note in README)

**Acceptance Criteria:**
- Customer list paginated and searchable
- Customer detail shows complete info
- Appointments view shows upcoming schedule
- UI is mobile-responsive
- Fast loading (<500ms per page)

---

## Development Instructions

### Setup Phase
1. **Read all memory bank files** to understand architecture
2. **Read reference repositories** using GitHub MCP before each feature
3. Set up Python virtual environment
4. Install dependencies (create requirements.txt)
5. Set up environment variables (.env)
6. Initialize Neon database (run init_db.py)
7. Generate mock data (run generate_mock_crm_data.py)
8. Start Redis (local or Upstash)

### Implementation Phase
Implement features **in order** (1-14). For each feature:
1. **Read relevant GitHub repos via MCP** (see reference-repositories.md)
2. **Copy production-ready code** (don't reinvent the wheel)
3. **Adapt to our architecture** (translate Node.js → Python if needed)
4. Include error handling
5. Include logging
6. Write tests
7. Verify acceptance criteria

### Testing Phase
After each feature:
1. Write unit tests
2. Test manually via scripts
3. Verify performance targets
4. Document any issues

### Integration Phase
After all features complete:
1. Run full integration tests
2. Test each call flow end-to-end
3. Verify outbound calls (YOUR_TEST_NUMBER only)
4. Load test (simulate 10 concurrent calls)

## Key Constraints

### POC Safety Rules
- **CRITICAL:** Outbound calls only to `YOUR_TEST_NUMBER` from .env
- No real customer data (all Faker-generated)
- No payment processing
- No real VIN decoding (just store VINs)

### Performance Targets
- Customer lookup (cached): <2ms
- Customer lookup (DB): <30ms
- Calendar freebusy: <1s
- Appointment booking: <2s
- STT final transcript: <500ms
- TTS first byte: <300ms
- Barge-in response: <200ms

### Code Quality
- Type hints for all functions
- Docstrings for all classes/functions
- Error handling with try/except
- Logging at INFO level minimum
- No secrets in code (use .env)

## Environment Variables Required

```bash
# Database
NEON_DATABASE_URL=postgresql://user:pass@host/dbname

# Redis
REDIS_URL=redis://localhost:6379

# OpenAI
OPENAI_API_KEY=sk-...

# Deepgram
DEEPGRAM_API_KEY=...

# Google Calendar
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_CALENDAR_ID=primary

# Twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# POC Safety
YOUR_TEST_NUMBER=+1...  # Only number to call for outbound

# Server
BASE_URL=https://your-domain.com
PORT=5050
ENVIRONMENT=development  # development, staging, production
```

## Success Metrics

### For POC Demo:
✅ Inbound call connects and greets caller by name (if existing customer)
✅ New customer can schedule appointment in <2 minutes
✅ Existing customer can reschedule appointment
✅ Calendar shows booked appointments
✅ Outbound reminder call works (to YOUR_TEST_NUMBER)
✅ Barge-in/interruption works smoothly
✅ Call transcripts saved and viewable
✅ No crashes during 10-call test

### Performance:
- 95th percentile response time: <1s
- Customer lookup cache hit rate: >80%
- Zero dropped calls
- Zero data loss (all calls logged)

## Getting Help

If stuck on any feature:
1. Re-read relevant memory bank file
2. **Re-read reference repository code via GitHub MCP**
3. Check reference-repositories.md for specific line numbers
4. Test components independently (don't debug full pipeline)
5. Add logging/print statements liberally
6. Ask specific questions with error logs

## Timeline Estimate

- **Hours 1-4:** Database + Mock Data + Redis (Features 1-2)
- **Hours 5-8:** Deepgram STT + TTS (Features 3-4)
- **Hours 9-12:** GPT-4o + CRM Tools (Features 5-6)
- **Hours 13-16:** Calendar + WebSocket Handler (Features 7-8)
- **Hours 17-20:** Webhooks + Call Flows (Features 9-10)
- **Hours 21-24:** Outbound Worker + Testing (Features 11-12)
- **Hours 25-28:** Polish + Admin UI (Features 13-14)

Total: **28 hours** (leaves buffer for 48h POC)

---

## Start Here

1. **Read all 5 memory bank files** (architecture-decisions.md, customer-data-schema.md, call-flows-and-scripts.md, implementation-guide.md, reference-repositories.md)
2. **Use GitHub MCP to read reference repositories before each feature**
3. Begin with Feature 1 (Database Setup)
4. Use plan mode to outline implementation strategy
5. Execute and verify before moving to next feature

**Remember:** Don't reinvent the wheel. The reference repositories contain production-ready code that solves 80% of our problems. Copy, adapt, and improve.

Good luck! 🚀