# Automotive Voice AI - System Architecture Diagram

## High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CUSTOMER                                    │
│                    (Phone Call to Twilio)                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ Voice Call
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TWILIO VOICE                                 │
│                  - Phone Number: +1510350155                        │
│                  - WebSocket Media Stream (mulaw @ 8kHz)            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ WebSocket Connection
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI SERVER (Port 8000)                       │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │              /api/v1/voice/media-stream                    │    │
│  │                  (WebSocket Handler)                       │    │
│  └────────────────────────────────────────────────────────────┘    │
│                               │                                      │
│         ┌─────────────────────┼─────────────────────┐               │
│         ▼                     ▼                     ▼               │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐       │
│  │  Deepgram    │   │   OpenAI         │   │  Deepgram    │       │
│  │  STT Service │   │   Service        │   │  TTS Service │       │
│  │              │   │                  │   │              │       │
│  │  ~150ms      │   │   GPT-4o         │   │   ~300ms     │       │
│  │  latency     │   │   ~500ms first   │   │   latency    │       │
│  └──────┬───────┘   │   token          │   └──────┬───────┘       │
│         │           │                  │          │               │
│         │           │   Function       │          │               │
│         │           │   Calling        │          │               │
│         │           │   (7 tools)      │          │               │
│         │           └────────┬─────────┘          │               │
│         │                    │                    │               │
│         │                    ▼                    │               │
│         │           ┌─────────────────┐           │               │
│         │           │   Tool Router   │           │               │
│         │           │                 │           │               │
│         │           │  7 CRM Tools:   │           │               │
│         │           │  1. lookup      │           │               │
│         │           │  2. search      │           │               │
│         │           │  3. availability│           │               │
│         │           │  4. book        │           │               │
│         │           │  5. upcoming    │           │               │
│         │           │  6. cancel      │           │               │
│         │           │  7. reschedule  │           │               │
│         │           └────────┬─────────┘           │               │
│         │                    │                    │               │
│  Audio  │                    │ Tool Calls         │  Audio        │
│  (In)   │                    │                    │  (Out)        │
└─────────┼────────────────────┼────────────────────┼───────────────┘
          │                    │                    │
          │                    ▼                    │
          │      ┌─────────────────────────┐        │
          │      │   INTEGRATION LAYER     │        │
          │      └─────────────────────────┘        │
          │                    │                    │
          │         ┌──────────┼──────────┐         │
          │         ▼          ▼          ▼         │
          │   ┌─────────┐ ┌─────────┐ ┌─────────┐  │
          │   │ Redis   │ │PostgreSQL│ │ Google  │  │
          │   │ Cache   │ │   DB     │ │Calendar │  │
          │   │         │ │          │ │  API    │  │
          │   │ <2ms    │ │ 20-30ms  │ │ 400ms   │  │
          │   │ lookup  │ │ (uncached│ │ (freebusy│ │
          │   │         │ │  query)  │ │  query)  │ │
          │   └─────────┘ └─────────┘ └─────────┘  │
          │                                         │
          └─────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                    BACKGROUND WORKER                                 │
│                      (APScheduler)                                   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Daily Job (Cron: 0 9 * * *)                                 │  │
│  │  - Query appointments for tomorrow                           │  │
│  │  - Initiate outbound reminder calls via Twilio API          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow (Detailed)

### Inbound Call Flow

```
1. Customer Dials +15103501550
         ↓
2. Twilio → POST /api/v1/webhooks/inbound-call
         ↓
3. Server Returns TwiML: <Connect><Stream url="wss://..."/></Connect>
         ↓
4. Twilio Opens WebSocket → /api/v1/voice/media-stream
         ↓
5. Server Initializes:
   - Deepgram STT WebSocket
   - Deepgram TTS WebSocket
   - OpenAI Service (GPT-4o)
   - Database Session
   - 7 CRM Tools Registered
         ↓
6. Customer Lookup by Phone:
   ┌─> Check Redis Cache (target: <2ms) ──> HIT → Return
   │
   └─> MISS → Query PostgreSQL (20-30ms) → Cache Result → Return
         ↓
7. Personalize System Prompt with Customer Data
         ↓
8. Real-time Conversation Loop:
   ┌───────────────────────────────────────────────┐
   │                                                │
   │  Customer Speaks                               │
   │       ↓                                        │
   │  Audio (mulaw) → Deepgram STT (~150ms)        │
   │       ↓                                        │
   │  Transcript → OpenAI GPT-4o                   │
   │       ↓                                        │
   │  ┌─ Tool Call Needed?                         │
   │  │    ↓ Yes                                    │
   │  │  Execute Tool (lookup, book, etc.)         │
   │  │    ↓                                        │
   │  │  Return Result to GPT-4o                   │
   │  │    ↓                                        │
   │  └─ GPT-4o Generates Verbal Response          │
   │       ↓                                        │
   │  Response Text → Deepgram TTS (~300ms)        │
   │       ↓                                        │
   │  Audio (mulaw) → Twilio → Customer Hears      │
   │                                                │
   │  [Barge-in Detection]:                        │
   │    If customer speaks while AI talking:       │
   │    - Interim transcript detected              │
   │    - Send "clear" to Twilio                   │
   │    - Clear TTS queue                          │
   │    - Process new input                        │
   │                                                │
   └───────────────────────────────────────────────┘
         ↓
9. Call Ends:
   - Close STT/TTS connections
   - Save conversation to DB (call_logs)
   - Update customer last_contact
   - Clear session from Redis
```

### Tool Execution Example: Book Appointment

```
Customer: "I need an oil change for next Tuesday at 2pm"
         ↓
OpenAI GPT-4o: Calls `get_available_slots("2025-01-21")`
         ↓
Tool Execution:
   1. Parse date "2025-01-21"
   2. Determine business hours (9 AM - 5 PM for weekday)
   3. Call Google Calendar freebusy API
         ↓
   Google Calendar Returns: Busy periods
         ↓
   4. Calculate free slots (exclude lunch 12-1 PM)
   5. Return: [{"start": "2025-01-21T14:00:00", "end": "2025-01-21T15:00:00", ...}]
         ↓
GPT-4o: "I have 2 PM available. Which vehicle?"
         ↓
Customer: "My Honda CR-V"
         ↓
GPT-4o: Calls `book_appointment(customer_id=1, vehicle_id=2, scheduled_at="2025-01-21T14:00:00", ...)`
         ↓
Tool Execution:
   1. Validate customer exists (DB query)
   2. Validate vehicle belongs to customer (DB query)
   3. Create Google Calendar event:
      - Title: "Oil Change - Ali Khani"
      - Description: Vehicle info, customer phone, etc.
      - Attendees: [customer.email]
         ↓
   Google Calendar Returns: event_id, calendar_link
         ↓
   4. Create appointment record in PostgreSQL:
      - All booking details
      - calendar_event_id (link to Google Calendar)
         ↓
   5. Invalidate customer cache in Redis
   6. Commit database transaction
   7. Return: {"success": true, "appointment_id": 42, "calendar_link": "..."}
         ↓
GPT-4o: "Perfect! Your oil change is booked for Tuesday, January 21st at 2 PM. I've sent you a calendar invite."
```

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Voice Infrastructure** | Twilio Media Streams | Phone calls, WebSocket audio (mulaw @ 8kHz) |
| **Speech-to-Text** | Deepgram nova-2-phonecall | Real-time transcription, barge-in detection |
| **Text-to-Speech** | Deepgram aura-2-asteria | Natural voice synthesis |
| **AI Engine** | OpenAI GPT-4o (Chat API) | Conversation, function calling (7 tools) |
| **Web Framework** | FastAPI (Python 3.11+) | HTTP webhooks, WebSocket handler |
| **Database** | PostgreSQL (Neon Serverless) | Customer, vehicle, appointment data |
| **Cache** | Redis (Upstash) | Session state, customer lookup, VIN decode |
| **Calendar** | Google Calendar API | Real availability, event CRUD (OAuth2) |
| **Background Jobs** | APScheduler | Daily reminder calls (cron) |
| **VIN Decoder** | NHTSA API | Vehicle information lookup |

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Customer lookup (cached) | <2ms | Redis GET |
| Customer lookup (uncached) | 20-30ms | PostgreSQL with JOIN |
| Calendar availability query | ~400ms | Google Calendar freebusy API |
| VIN decode (cached) | <5ms | Redis GET |
| VIN decode (uncached) | ~800ms | NHTSA API + cache |
| STT latency | ~150ms | Deepgram streaming |
| LLM first token | ~500ms | GPT-4o streaming |
| TTS first audio | ~300ms | Deepgram streaming |
| Barge-in detection | ~100ms | Interim transcript → audio clear |
| **End-to-end latency** | **~1.2s** | User stops speaking → AI starts speaking |

## Scalability

- **Concurrent calls per server**: 100+ (tested with load tests)
- **Database connection pool**: 20 base + 40 overflow = 60 total
- **Redis connection pool**: 10 connections
- **Horizontal scaling**: Stateless design allows multiple server instances with load balancer
- **Sticky sessions**: Required for WebSocket connections (IP hash or session affinity)

## Security

- **Input validation**: Phone numbers, VINs, dates, state codes
- **SQL injection prevention**: Parameterized queries via SQLAlchemy
- **Session isolation**: Redis TTL enforcement (1 hour max)
- **Secrets management**: Environment variables, .gitignore for .env file
- **HTTPS/WSS**: All external communication encrypted
- **POC safety**: `YOUR_TEST_NUMBER` limits outbound calls during testing
