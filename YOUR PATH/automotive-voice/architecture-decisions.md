# Automotive Voice Agent - Architecture Decisions

## Project Overview
48-hour POC for an automotive voice agent that handles inbound calls for appointment scheduling and customer service at Bart's Automotive.

## Core Technology Stack

### 1. Runtime Stack
- **Language:** Python
- **Framework:** FastAPI + asyncio
- **Rationale:**
  - Majority of reference implementations (Twilio, Deepgram, Google Calendar) are in Python
  - Clean async/await model for WebSocket handling
  - Rich ecosystem for audio/telephony integrations

### 2. Audio Pipeline Architecture
**Flow:** Twilio Media Streams → Deepgram STT → GPT-4o → Deepgram TTS → Twilio

**Components:**
- **STT:** Deepgram (nova-2-phonecall model)
  - Better phone audio handling than OpenAI
  - Superior barge-in detection via interim results
  - 8kHz mulaw optimization for telephony

- **LLM:** OpenAI GPT-4o
  - Standard function calling (not Realtime API)
  - Reasoning and tool orchestration
  - Proven reliability for conversational AI

- **TTS:** Deepgram (aura-*)
  - Low latency streaming
  - Phone-optimized voices
  - **Modularity:** Abstracted behind interface for easy swap to ElevenLabs

**Design Principle:** Single streaming pipeline with modular components (not OpenAI Realtime's closed system)

### 3. State Management
**Solution:** Redis

**Use Cases:**
- Session state: `session:{call_sid}` → conversation context
- Customer cache: `customer:{phone}` → CRM data (5min TTL)
- Slot collection: Name, VIN, appointment preferences
- Idempotency for calendar operations

**Why Redis:**
- Essential for worker restarts/crashes
- Required for horizontal scaling
- Supports outbound call state persistence
- Fast lookups (<2ms cached, <10ms cold)

### 4. Calendar Integration
**Solution:** Real Google Calendar API

**Implementation Pattern:** (from duohub-ai/google-calendar-voice-agent)
- OAuth2 refresh token flow
- Freebusy queries for availability
- Event creation with attendees
- Timezone-aware scheduling (handle AEDT, PST, etc.)

**Key Functions:**
- `get_free_availability(start_time, end_time)` → Available slots
- `create_calendar_event(title, start_time, attendees)` → Booking
- Async wrapper with `asyncio.run_in_executor()` for blocking Google API calls

### 5. CRM Architecture
**Solution:** Neon Postgres + SQLAlchemy

**Schema:**
```sql
customers (id, phone, name, email, address, city, state, zip_code, created_at)
vehicles (id, customer_id, vin, make, model, year, color, mileage, license_plate)
appointments (id, customer_id, vehicle_id, service_type, scheduled_at, status, notes, total_cost, calendar_event_id)
call_logs (id, call_sid, customer_id, transcript, duration, created_at)
```

**Indexes:**
- `customers.phone` (primary lookup)
- `vehicles.vin` (VIN decoder lookup)
- `appointments.scheduled_at` (reminder queries)

**Data Generation:** Faker library (not HuggingFace datasets)
- `faker` for customer data (names, phones, addresses)
- `faker-vehicle` for automotive data (VINs, makes, models)
- ~10k customers, ~16k vehicles, ~8k appointments

**Why Neon:**
- Serverless Postgres (zero ops)
- Free tier: 3GB storage (using ~1GB)
- Connection pooling built-in
- Python-native with SQLAlchemy

**Why NOT Twenty CRM:**
- 7-9 hour setup (Nx monorepo, GraphQL, React UI)
- Overkill for POC where voice is primary interface
- Can migrate later if UI becomes critical

### 6. LLM Orchestration Style
**Solution:** Custom Agent Layer (NOT OpenAI Realtime API)

**Rationale:**
- OpenAI Realtime locks you into their STT/TTS pipeline
- Function calling is awkward (must create `function_call_output` events)
- No control over interruption logic (black box `server_vad`)
- Complex state management

**Our Approach:**
```python
# Deepgram STT stream → transcript
transcript = await deepgram_ws.get_final_transcript()

# GPT-4o tool calling (standard SDK)
response = await openai.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    tools=[...],
    stream=False
)

# Handle tool calls inline
if response.tool_calls:
    result = await execute_tool(response.tool_calls[0])

# Deepgram TTS
audio = await deepgram_tts.synthesize(response.content)
await websocket.send(audio)
```

**Advantages:**
- Deepgram's superior barge-in detection
- Standard OpenAI function calling (easier debugging)
- Swap TTS provider in 1 function
- Full control over turn-taking

### 7. Function Execution Model
**Solution:** Inline execution (NOT queue workers)

**All functions execute inline:**
- `lookup_customer(phone)` → 2-30ms (Redis → Postgres)
- `get_freebusy(date)` → 50-200ms (Google Calendar API)
- `book_appointment(...)` → 100-300ms (Postgres + Calendar API)

**Latency Comparison:**
- Inline: 2-300ms
- Queue worker: 250-550ms (adds 200ms+ overhead)

**When to scale:** Only at 1000+ concurrent calls (not needed for POC)

**Evidence:** All reference repos use inline execution
- Barty-Bart: Inline webhook calls (lines 360-430)
- duohub-ai: Inline Google Calendar API calls
- deepgram: Inline LLM prompts (line 226)

### 8. Outbound Call Architecture
**Solution:** Cron worker (NOT event-driven)

**Implementation:**
```python
# Cron: Daily at 9 AM
# Find appointments tomorrow
appointments = await db.query(
    "SELECT * FROM appointments WHERE scheduled_at::date = CURRENT_DATE + 1"
)

for appt in appointments:
    # Twilio REST API outbound call
    call = twilio_client.calls.create(
        to=appt.customer.phone,
        from_=TWILIO_NUMBER,
        url=f"{BASE_URL}/outbound-reminder?appointment_id={appt.id}"
    )
```

**POC Safety:** Hard-coded to only call `YOUR_NUMBER` from `.env`

**Why Cron:**
- Simple, predictable, debuggable
- Perfect for batch reminders (daily sweep)
- No need for Kafka/Redis Streams complexity

## Data Strategy

### Mock CRM Data Generation
**Solution:** Faker library (NOT HuggingFace datasets)

**Why Faker:**
- Automotive-specific: `faker-vehicle` has VINs, makes, models
- Fast: 10k customers in ~30 seconds
- No external dependencies (works offline)
- Fully customizable to our schema
- Realistic data (addresses, phones, emails)

**Why NOT HuggingFace CustomerPersonas:**
- Overkill: 4k character backstories not useful for phone calls
- 608MB download for data we don't need
- Missing automotive-specific fields (VIN, vehicle make/model)
- Better to use LLM context for conversation history

**Generation Script:**
```python
# scripts/generate_mock_crm_data.py
- 10,000 customers (realistic names, phones, addresses)
- 16,000 vehicles (1.6 per customer avg, realistic VINs)
- 8,000 appointments (70% have history, 15% have future)
- Service types: Oil Change, Brake Inspection, etc.
```

## Key Design Principles

1. **Modularity over Integration:** Abstract TTS behind interface for easy provider swap
2. **Simplicity for POC:** Choose solutions with <4 hour setup time
3. **Production Viability:** All choices scale to 1M+ customers without rewrite
4. **Standard Patterns:** Use proven libraries (not custom implementations)
5. **Offline-first:** Minimize external API dependencies where possible

## Reference Repositories

1. **twilio-samples/speech-assistant-openai-realtime-api-python**
   - Clean FastAPI + asyncio implementation
   - Interruption handling pattern (lines 141-168)

2. **deepgram/deepgram-twilio-streaming-voice-agent**
   - Deepgram STT/TTS integration
   - Barge-in detection (line 310: interim results trigger clear)

3. **duohub-ai/google-calendar-voice-agent**
   - Google Calendar async wrapper pattern
   - Pipecat framework (optional reference)

4. **Barty-Bart/openai-realtime-api-voice-assistant-V2**
   - Session management patterns
   - Inline function execution examples

## Technology Tradeoffs Made

| Decision | Alternative Considered | Why We Chose Current |
|----------|----------------------|---------------------|
| Deepgram STT | OpenAI Whisper via Realtime API | Better phone audio, barge-in detection |
| Custom orchestrator | OpenAI Realtime API | Modularity, standard function calling |
| Neon Postgres | Twenty CRM | 3-4 hours vs 7-9 hours setup |
| Faker | HuggingFace datasets | Automotive-specific, faster, offline |
| Inline functions | Queue workers | <300ms vs 500ms latency for POC |
| Cron | Event-driven | Simple for batch reminders |
| SQLAlchemy | Drizzle/Prisma | Python-native (Drizzle is TypeScript) |

## Success Metrics

**For POC Demo:**
- Call handling latency: <500ms end-to-end
- Customer lookup: <50ms (cached)
- Appointment booking: <2 seconds total
- Barge-in response: <200ms
- Calendar availability query: <1 second

**Future Production:**
- Support 100+ concurrent calls
- 99.9% uptime
- <1% error rate on bookings
- Horizontal scaling ready (Redis + Neon)

---

**Last Updated:** 2025-01-12
**Status:** Architecture Approved, Ready for Implementation