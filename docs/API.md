# API Documentation - Otto's Auto Voice Agent

## Table of Contents
1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [HTTP Endpoints](#http-endpoints)
5. [WebSocket Protocol](#websocket-protocol)
6. [Tool/Function Definitions](#tool-function-definitions)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)

---

## Overview

The Otto's Auto Voice Agent API consists of:
- **HTTP REST Endpoints**: For webhooks, health checks, and management
- **WebSocket Endpoint**: For real-time bidirectional audio streaming
- **Tool Functions**: AI-callable functions for CRM and calendar operations

All endpoints use JSON for request/response except where noted (TwiML, WebSocket binary).

---

## Base URL

### Development
```
http://localhost:8000
```

### Production
```
https://yourdomain.com
```

All API routes are prefixed with `/api/v1/`.

---

## Authentication

### External Services
- **Twilio Webhooks**: Validated via Twilio signature (recommended for production)
- **WebSocket**: No authentication (secured by unpredictable URL)
- **Health Endpoint**: Public, no authentication required

### Future
- JWT tokens for customer portal
- API keys for third-party integrations

---

## HTTP Endpoints

### Health Check

Check system health and service connectivity.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-01-15T12:00:00Z"
}
```

**Status Codes:**
- `200 OK`: All services healthy
- `503 Service Unavailable`: One or more services down

**Example:**
```bash
curl https://yourdomain.com/health
```

---

### Root Endpoint

Get API information.

**Endpoint:** `GET /`

**Response:**
```json
{
  "service": "AI Automotive Service Scheduler",
  "version": "1.0.0",
  "status": "running"
}
```

---

### Inbound Call Webhook

Twilio webhook called when a customer dials your phone number.

**Endpoint:** `POST /api/v1/webhooks/incoming-call`

**Content-Type:** `application/x-www-form-urlencoded`

**Request Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| CallSid | string | Yes | Unique call identifier |
| From | string | Yes | Caller's phone number (E.164 format) |
| To | string | Yes | Your Twilio number being called |
| CallStatus | string | Yes | Call status (usually "ringing") |
| Direction | string | Yes | "inbound" |

**Response:**
TwiML XML with `<Connect><Stream>` element

**Example Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://yourdomain.com/api/v1/voice/media-stream">
            <Parameter name="From" value="+15551234567"/>
            <Parameter name="To" value="+15559876543"/>
            <Parameter name="CallSid" value="CA1234567890abcdef"/>  <!-- pragma: allowlist secret -->
        </Stream>
    </Connect>
</Response>
```

**Twilio Configuration:**
```
Voice & Fax > Phone Numbers > [Your Number]
A CALL COMES IN: Webhook
URL: https://yourdomain.com/api/v1/webhooks/incoming-call
HTTP POST
```

---

### Call Status Webhook

Optional webhook for call status updates.

**Endpoint:** `POST /api/v1/webhooks/call-status`

**Content-Type:** `application/x-www-form-urlencoded`

**Request Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| CallSid | string | Yes | Unique call identifier |
| CallStatus | string | Yes | Current status |
| CallDuration | string | No | Duration in seconds (if completed) |
| From | string | No | Caller's phone number |
| To | string | No | Called phone number |

**Call Statuses:**
- `queued`: Call is queued
- `ringing`: Call is ringing
- `in-progress`: Call answered
- `completed`: Call finished normally
- `busy`: Callee was busy
- `no-answer`: No one answered
- `canceled`: Call canceled before connection
- `failed`: Call failed

**Response:**
```json
{
  "status": "received"
}
```

**Twilio Configuration:**
```
Voice & Fax > Phone Numbers > [Your Number]
STATUS CALLBACK URL: https://yourdomain.com/api/v1/webhooks/call-status
HTTP POST
```

---

### Outbound Reminder Webhook

Internal webhook used by the worker to make reminder calls.

**Endpoint:** `POST /api/v1/webhooks/outbound-reminder?appointment_id={id}`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| appointment_id | integer | Yes | Appointment ID for reminder |

**Response:**
TwiML XML with reminder message

**Example Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Hello! This is a reminder from Otto's Auto.
        You have an appointment tomorrow at 2 PM for an oil change.
        If you need to reschedule, please call us at 555-123-4567.
        Thank you!
    </Say>
</Response>
```

**Usage:**
Called by worker job, not exposed publicly.

---

### Google Calendar Notification

Webhook for Google Calendar push notifications.

**Endpoint:** `POST /api/v1/webhooks/calendar/notification`

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "kind": "api#channel",
  "id": "unique-channel-id",
  "resourceId": "resource-identifier",
  "resourceUri": "https://www.googleapis.com/calendar/v3/...",
  "expiration": "1234567890000"
}
```

**Response:**
```json
{
  "status": "received"
}
```

**Setup:**
Configured via Google Calendar API watch endpoint.

---

## WebSocket Protocol

### Media Stream Endpoint

Real-time bidirectional audio streaming for voice conversations.

**Endpoint:** `WS /api/v1/voice/media-stream`

**Protocol:** Twilio Media Streams

**Encoding:** mulaw @ 8kHz, 1 channel

**Connection Flow:**
1. Client (Twilio) connects to WebSocket
2. Server accepts connection
3. Client sends `connected` event
4. Client sends `start` event with call metadata
5. Bidirectional audio streaming begins
6. Client sends `stop` event when call ends
7. Connection closes

---

### Message Types

#### 1. Connected Event

Sent by Twilio immediately after WebSocket connection.

**From:** Twilio → Server

**Format:**
```json
{
  "event": "connected",
  "protocol": "Call",
  "version": "1.0.0"
}
```

---

#### 2. Start Event

Sent by Twilio when media streaming begins.

**From:** Twilio → Server

**Format:**
```json
{
  "event": "start",
  "sequenceNumber": "1",
  "start": {
    "streamSid": "MZ1234567890abcdef",
    "accountSid": "AC1234567890abcdef",  # pragma: allowlist secret
    "callSid": "CA1234567890abcdef",  # pragma: allowlist secret
    "tracks": ["inbound"],
    "customParameters": {
      "From": "+15551234567",
      "To": "+15559876543",
      "CallSid": "CA1234567890abcdef"  // pragma: allowlist secret
    },
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    }
  },
  "streamSid": "MZ1234567890abcdef"
}
```

---

#### 3. Media Event (Inbound Audio)

Audio chunks from customer.

**From:** Twilio → Server

**Format:**
```json
{
  "event": "media",
  "sequenceNumber": "2",
  "media": {
    "track": "inbound",
    "chunk": "1",
    "timestamp": "5",
    "payload": "base64-encoded-mulaw-audio"
  },
  "streamSid": "MZ1234567890abcdef"
}
```

**Payload:**
- Base64-encoded mulaw audio
- 20ms of audio per chunk (160 bytes decoded)
- Sent continuously while customer is speaking

---

#### 4. Media Event (Outbound Audio)

Audio chunks to customer (AI voice).

**From:** Server → Twilio

**Format:**
```json
{
  "event": "media",
  "streamSid": "MZ1234567890abcdef",
  "media": {
    "payload": "base64-encoded-mulaw-audio"
  }
}
```

**Usage:**
Server sends these messages to play AI-generated speech to customer.

---

#### 5. Mark Event

Synchronization marker.

**From:** Twilio → Server (acknowledgment)
**From:** Server → Twilio (request)

**Format:**
```json
{
  "event": "mark",
  "sequenceNumber": "100",
  "streamSid": "MZ1234567890abcdef",
  "mark": {
    "name": "my-marker-name"
  }
}
```

**Usage:**
- Server can send mark to request acknowledgment
- Twilio sends mark back when audio finishes playing
- Useful for synchronizing audio playback

---

#### 6. Clear Event

Clear outbound audio queue.

**From:** Server → Twilio

**Format:**
```json
{
  "event": "clear",
  "streamSid": "MZ1234567890abcdef"
}
```

**Usage:**
- Sent by server when barge-in detected
- Immediately stops playing current audio to customer
- Allows customer to interrupt AI mid-sentence

---

#### 7. Stop Event

Media streaming stopped.

**From:** Twilio → Server

**Format:**
```json
{
  "event": "stop",
  "sequenceNumber": "500",
  "stop": {
    "accountSid": "AC1234567890abcdef",  // pragma: allowlist secret
    "callSid": "CA1234567890abcdef"  // pragma: allowlist secret
  },
  "streamSid": "MZ1234567890abcdef"
}
```

**Usage:**
Indicates call ended, server should cleanup resources.

---

### Server-Side Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET SERVER FLOW                         │
└──────────────────────────────────────────────────────────────────┘

1. WebSocket Connection Accepted
   ↓
2. Initialize Services
   • Deepgram STT (WebSocket)
   • Deepgram TTS (WebSocket)
   • OpenAI Service (HTTP streaming)
   • Database session
   • Tool router with 7 tools
   ↓
3. Receive "start" event
   • Extract call metadata (CallSid, caller phone)
   • Create Redis session
   • Lookup customer by phone
   • Personalize system prompt if customer found
   ↓
4. Start Concurrent Tasks
   ┌─────────────────────┬──────────────────────┐
   │ receive_from_twilio │ process_transcripts  │
   │                     │                      │
   │ • Receive audio     │ • Get STT transcript │
   │ • Send to STT       │ • Detect barge-in    │
   │ • Handle events     │ • Call OpenAI        │
   │                     │ • Execute tools      │
   │                     │ • Generate TTS       │
   │                     │ • Send audio to      │
   │                     │   Twilio             │
   └─────────────────────┴──────────────────────┘
   ↓
5. Receive "stop" event
   ↓
6. Cleanup
   • Close STT connection
   • Close TTS connection
   • Close database session
   • Save final session state to Redis
   • Close WebSocket
```

---

### Audio Encoding

**Format:** mulaw (μ-law)
**Sample Rate:** 8000 Hz
**Channels:** 1 (mono)
**Chunk Size:** 20ms (160 bytes decoded)
**Transmission:** Base64-encoded

**Python Encoding Example:**
```python
import base64

# Raw mulaw bytes from Deepgram
mulaw_audio = b'\x7f\x7f...'

# Encode for Twilio
encoded = base64.b64encode(mulaw_audio).decode('utf-8')

# Send to Twilio
await websocket.send_json({
    "event": "media",
    "streamSid": stream_sid,
    "media": {
        "payload": encoded
    }
})
```

**Python Decoding Example:**
```python
import base64

# Receive from Twilio
message = await websocket.receive_json()
payload = message["media"]["payload"]

# Decode
mulaw_audio = base64.b64decode(payload)

# Send to Deepgram STT
await stt.send_audio(mulaw_audio)
```

---

## Tool/Function Definitions

The AI assistant can call these functions during conversations to perform CRM and calendar operations.

### 1. lookup_customer

Look up customer by phone number.

**Function Signature:**
```python
async def lookup_customer(phone: str) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| phone_number | string | Yes | Customer's phone number (10 digits) |

**Returns:**
```json
{
  "id": 123,
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone_number": "+15551234567",
  "customer_since": "2023-01-15",
  "last_service_date": "2024-12-01T10:00:00Z",
  "vehicles": [
    {
      "id": 456,
      "vin": "1HGBH41JXMN109186",
      "year": 2021,
      "make": "Honda",
      "model": "Accord",
      "trim": "EX",
      "color": "Silver",
      "current_mileage": 25000,
      "is_primary_vehicle": true
    }
  ],
  "notes": "Prefers morning appointments"
}
```

**Error Response:**
```json
null
```
(Returns `null` if customer not found)

**Cache Behavior:**
- Cache hit: <2ms response
- Cache miss: ~20-30ms response (database query)
- TTL: 5 minutes

---

### 2. get_available_slots

Get available appointment slots for a date.

**Function Signature:**
```python
async def get_available_slots(
    date: str,
    duration_minutes: int = 30
) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| date | string | Yes | Date in YYYY-MM-DD format |
| service_type | string | No | Service type (affects duration) |

**Returns:**
```json
{
  "success": true,
  "date": "2025-01-15",
  "day_of_week": "Wednesday",
  "available_slots": [
    "2025-01-15T09:00:00Z",
    "2025-01-15T09:30:00Z",
    "2025-01-15T10:00:00Z",
    "2025-01-15T10:30:00Z"
  ],
  "message": "Found 4 available time slots"
}
```

**Business Hours:**
- Monday-Friday: 9 AM - 5 PM (excluding 12-1 PM lunch)
- Saturday: 9 AM - 3 PM (excluding 12-1 PM lunch)
- Sunday: Closed

**Error Response:**
```json
{
  "success": false,
  "error": "Invalid date format. Please use YYYY-MM-DD",
  "message": "Invalid date format"
}
```

---

### 3. book_appointment

Book a service appointment.

**Function Signature:**
```python
async def book_appointment(
    db: AsyncSession,
    customer_id: int,
    vehicle_id: int,
    scheduled_at: str,
    service_type: str,
    duration_minutes: int = 60,
    service_description: Optional[str] = None,
    customer_concerns: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| customer_id | integer | Yes | Customer ID from lookup_customer |
| vehicle_id | integer | Yes | Vehicle ID from lookup_customer |
| service_type | string | Yes | Type of service (see enum below) |
| start_time | string | Yes | ISO datetime (e.g., "2025-01-15T09:00:00") |
| notes | string | No | Special notes or concerns |

**Service Types:**
- `oil_change`
- `brake_service`
- `tire_rotation`
- `inspection`
- `general_service`
- `engine_diagnostic`
- `transmission_service`
- `other`

**Returns:**
```json
{
  "success": true,
  "data": {
    "appointment_id": 789,
    "customer_id": 123,
    "customer_name": "John Doe",
    "vehicle_id": 456,
    "vehicle_description": "2021 Honda Accord",
    "scheduled_at": "2025-01-15T09:00:00Z",
    "service_type": "oil_change",
    "duration_minutes": 60,
    "status": "scheduled"
  },
  "message": "Appointment booked successfully for John Doe on January 15, 2025 at 09:00 AM"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Customer ID 123 not found",
  "message": "Customer not found"
}
```

**Side Effects:**
- Creates appointment in database
- Creates Google Calendar event
- Invalidates customer cache
- Sends confirmation (future)

---

### 4. get_upcoming_appointments

Get customer's upcoming appointments.

**Function Signature:**
```python
async def get_upcoming_appointments(
    db: AsyncSession,
    customer_id: int
) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| customer_id | integer | Yes | Customer ID from lookup_customer |

**Returns:**
```json
{
  "success": true,
  "data": {
    "customer_id": 123,
    "appointments": [
      {
        "appointment_id": 789,
        "scheduled_at": "2025-01-15T09:00:00Z",
        "service_type": "oil_change",
        "duration_minutes": 60,
        "status": "scheduled",
        "vehicle": {
          "id": 456,
          "year": 2021,
          "make": "Honda",
          "model": "Accord",
          "vin": "1HGBH41JXMN109186"
        },
        "service_description": "Synthetic oil change",
        "confirmation_sent": true
      }
    ]
  },
  "message": "Found 1 upcoming appointment"
}
```

---

### 5. cancel_appointment

Cancel an existing appointment.

**Function Signature:**
```python
async def cancel_appointment(
    db: AsyncSession,
    appointment_id: int,
    reason: str
) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| appointment_id | integer | Yes | Appointment ID to cancel |
| reason | string | No | Cancellation reason |

**Cancellation Reasons:**
- `schedule_conflict`
- `got_service_elsewhere`
- `vehicle_sold`
- `issue_resolved`
- `other`

**Returns:**
```json
{
  "success": true,
  "data": {
    "appointment_id": 789,
    "status": "cancelled",
    "cancellation_reason": "schedule_conflict",
    "cancelled_at": "2025-01-14T15:30:00Z"
  },
  "message": "Appointment cancelled successfully. Reason: schedule_conflict"
}
```

**Side Effects:**
- Updates appointment status
- Deletes Google Calendar event
- Invalidates customer cache

---

### 6. reschedule_appointment

Reschedule an appointment to a new time.

**Function Signature:**
```python
async def reschedule_appointment(
    db: AsyncSession,
    appointment_id: int,
    new_datetime: str
) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| appointment_id | integer | Yes | Appointment ID to reschedule |
| new_start_time | string | Yes | New ISO datetime |

**Returns:**
```json
{
  "success": true,
  "data": {
    "appointment_id": 789,
    "old_datetime": "2025-01-15T09:00:00Z",
    "new_datetime": "2025-01-16T14:00:00Z",
    "service_type": "oil_change",
    "status": "scheduled"
  },
  "message": "Appointment rescheduled successfully to January 16, 2025 at 02:00 PM"
}
```

**Side Effects:**
- Updates appointment datetime
- Updates Google Calendar event
- Invalidates customer cache

---

### 7. decode_vin

Decode a VIN to get vehicle information.

**Function Signature:**
```python
async def decode_vin(vin: str) -> Dict[str, Any]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| vin | string | Yes | 17-character VIN |

**Returns:**
```json
{
  "success": true,
  "data": {
    "vin": "1HGBH41JXMN109186",
    "make": "Honda",
    "model": "Accord",
    "year": 2021,
    "vehicle_type": "Passenger Car",
    "manufacturer": "Honda Motor Company"
  },
  "message": "VIN decoded successfully: 2021 Honda Accord"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "VIN must be exactly 17 characters, got 16",
  "message": "Invalid VIN length"
}
```

**Cache Behavior:**
- Cache hit: <5ms response
- Cache miss: ~800ms response (NHTSA API call)
- TTL: 7 days

**API:** NHTSA Vehicle API
**Timeout:** 5 seconds

---

## Error Handling

### HTTP Error Responses

**Format:**
```json
{
  "detail": "Error message",
  "status_code": 500
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid input
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service down (health check)

### WebSocket Errors

**Connection Errors:**
- WebSocket closes with error code
- Server logs error and performs cleanup
- Client (Twilio) receives disconnection

**Service Errors:**
- Logged but not exposed to client
- Graceful degradation where possible
- Call may continue with reduced functionality

### Tool Execution Errors

**Format:**
```json
{
  "success": false,
  "error": "Detailed error message",
  "message": "User-friendly error message"
}
```

**Handling:**
- Error returned to OpenAI
- LLM incorporates error into conversation
- User informed naturally via voice

**Example Conversation:**
```
AI: "I'm sorry, I wasn't able to book that appointment. The selected time slot appears to be unavailable. Would you like me to check other times?"
```

---

## Rate Limiting

### Current Status

Rate limiting not implemented in POC.

### Planned Implementation

**Strategy:** Redis-based sliding window

**Limits:**
- 100 requests per minute per IP (webhooks)
- 10 concurrent WebSocket connections per IP
- 1000 tool executions per hour per customer

**Response:**
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "status_code": 429
}
```

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890
```

---

## Testing

### Health Check Test
```bash
curl https://yourdomain.com/health
```

### Webhook Test (Twilio Simulator)
```bash
curl -X POST https://yourdomain.com/api/v1/webhooks/incoming-call \
  -d "CallSid=CA1234567890abcdef" \
  -d "From=+15551234567" \
  -d "To=+15559876543" \
  -d "CallStatus=ringing" \
  -d "Direction=inbound"
```

### WebSocket Test (wscat)
```bash
npm install -g wscat
wscat -c wss://yourdomain.com/api/v1/voice/media-stream
```

### Load Testing (k6)
```javascript
import ws from 'k6/ws';
import { check } from 'k6';

export default function () {
  const url = 'wss://yourdomain.com/api/v1/voice/media-stream';

  const res = ws.connect(url, function (socket) {
    socket.on('open', () => {
      console.log('Connected');
    });

    socket.on('message', (data) => {
      console.log('Message received');
    });

    socket.on('close', () => {
      console.log('Disconnected');
    });
  });

  check(res, { 'status is 101': (r) => r && r.status === 101 });
}
```

---

## Appendix

### Complete TwiML Examples

**Basic Inbound:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://yourdomain.com/api/v1/voice/media-stream"/>
    </Connect>
</Response>
```

**With Greeting:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Thank you for calling Otto's Auto.
        Please wait while we connect you to our AI assistant.
    </Say>
    <Pause length="1"/>
    <Connect>
        <Stream url="wss://yourdomain.com/api/v1/voice/media-stream"/>
    </Connect>
</Response>
```

**Outbound Reminder:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Hello! This is a reminder from Otto's Auto.
        You have an appointment tomorrow at 2 PM for an oil change.
        If you need to reschedule, please call us at 555-123-4567.
        Thank you!
    </Say>
</Response>
```

### Tool Schema (OpenAI Format)

Complete tool definitions for OpenAI function calling are in `server/app/services/tool_definitions.py`.

---

## Support

For API questions or issues:
- Check logs: `journalctl -u automotive-voice -f`
- Health endpoint: `GET /health`
- Documentation: This file and ARCHITECTURE.md
- Code: `server/app/routes/` and `server/app/tools/`
