# AI-Powered Automotive Voice Agent
**POC Presentation**

---

## Slide 1: Customer Scenario

**Problem:**
- Dealerships lose 60% of after-hours calls → missed revenue
- Manual scheduling creates booking friction
- Customers want 24/7 service without phone tag

**Solution:**
- AI voice agent handles inbound appointment bookings
- Automated outbound reminder calls (reduce no-shows)
- Real-time calendar integration & CRM lookups
- <2s response latency for natural conversations

**Target Impact:**
- 24/7 availability → capture after-hours leads
- 40% reduction in no-shows via automated reminders
- Free up staff for high-value interactions

---

## Slide 2: Technical Architecture

```
         Twilio Phone Network
                 │
       WebSocket ↕ (mulaw @ 8kHz)
                 │
    ┌────────────┴────────────┐
    │   FastAPI Server        │
    │  ┌─────────────────┐    │
    │  │ Media Handler   │    │
    │  │  Audio → STT    │    │
    │  │     ↓           │    │
    │  │  GPT-4o         │    │
    │  │     ↓           │    │
    │  │  TTS → Audio    │    │
    │  └────────┬────────┘    │
    │           │             │
    │     ┌─────▼──────┐      │
    │     │ CRM Tools  │      │
    │     │ (7 funcs)  │      │
    │     └─────┬──────┘      │
    └───────────┼─────────────┘
                │
    ┌───────────┼───────────┐
    ↓           ↓           ↓
 Redis      Postgres    Google
 Cache        DB       Calendar
             │    │
          Customers │
          Vehicles  │
          Appointments
```

**Key Components:**
- **WebSocket**: Real-time bidirectional audio streaming
- **Deepgram**: STT (nova-2-phonecall) + TTS (aura-asteria)
- **GPT-4o**: Function calling for CRM operations
- **PostgreSQL**: Customer/vehicle/appointment data
- **Redis**: Session state & caching (2ms lookups)

---

## Slide 3: Technology Choices

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Orchestration** | FastAPI (async) | Native WebSocket support, async I/O for concurrent calls |
| **Telephony** | Twilio Media Streams | Production-grade reliability, mulaw @ 8kHz |
| **STT** | Deepgram nova-2 | <500ms latency, phone-optimized acoustic model |
| **TTS** | Deepgram Aura | <300ms synthesis, natural conversational voice |
| **LLM** | GPT-4o | Function calling for CRM tools, streaming responses |
| **Database** | PostgreSQL (Neon) | ACID compliance for appointments, serverless scaling |
| **Cache** | Redis | Sub-2ms customer lookups, session state management |

**Why No LangChain/LlamaIndex?**
- Direct APIs → lower latency (no abstraction overhead)
- Full control over streaming & function execution
- Simplified debugging in production

---

## Slide 4: POC Demos

### **What Works:**
✅ Inbound call handling with customer verification
✅ Real-time appointment scheduling with calendar integration
✅ Outbound reminder calls with rescheduling support
✅ Barge-in support (interrupt agent mid-sentence)
✅ Vehicle service history lookup
✅ Mock calendar fallback for testing
✅ **Security**: Input validation, prompt injection protection, session timeouts

### **Demo Environment:**
**One-Command Local Testing** (`run_test_environment.sh`):
1. Auto-start PostgreSQL, Redis, ngrok tunnel
2. Generate fresh ngrok URL → auto-configure Twilio webhooks via CLI
3. Launch FastAPI server with seeded mock CRM data
4. Interactive menu: test inbound/outbound calls instantly

**Example Test Flow:**
- Call agent as "Ali Khani" (seeded customer with 2019 Honda CR-V)
- Book oil change appointment
- Agent checks real-time calendar availability
- Confirms booking → creates Google Calendar event

**Security Features:**
- Phone/email/VIN validation prevents injection
- Session TTL enforcement (1-hour max)
- Atomic Redis ops (Lua scripts) prevent race conditions

---

## Slide 5: Limitations & Next Steps

### **Incomplete Areas:**
🔸 **Google Calendar OAuth**: Refresh token flow works locally, but OAuth 2.0 redirect URI challenges in prod → mock calendar fallback implemented for reliability

### **Future Enhancements:**

**Integration Depth:**
- Plug into real CRMs (Salesforce, Attio, Twenty) for live customer data
- Email confirmations (AWS SES) for scheduled appointments

**Audio Quality:**
- Swap Deepgram TTS → ElevenLabs for more natural conversations

**Developer Experience:**
- Migrate Python → TypeScript for better SDK support (Twilio/Deepgram)
- Robust webhook validation & retry logic

**Production:**
- Deploy to Railway/Render with managed Postgres + Redis
- Prometheus + Grafana for latency monitoring
- Rate limiting & circuit breakers for API resilience

**Advanced Features:**
- Multi-language support (Spanish for automotive market)
- Voicemail transcription & callback scheduling
