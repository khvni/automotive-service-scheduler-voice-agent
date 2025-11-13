# Feature 9: Twilio Webhooks & Call Routing - Implementation Summary

## Overview
Feature 9 implements the **webhook infrastructure** that connects Twilio's phone network to the voice agent's WebSocket handler. This is the entry point for all inbound calls.

**Status:** ✅ COMPLETE  
**Completion Date:** 2025-01-12  
**Commit:** cf3f4d8

## Architecture

### Call Flow Diagram
```
Caller → Twilio Phone Number → Twilio Infrastructure
                                        ↓
                          POST /api/v1/webhooks/incoming-call
                                        ↓
                            Generate TwiML with <Stream>
                                        ↓
                    WebSocket connection to /api/v1/voice/media-stream
                                        ↓
                          Voice Agent (Feature 8 handler)
```

### Webhook Endpoints

1. **`POST /api/v1/webhooks/incoming-call`**
   - Called by Twilio when a call comes in
   - Returns TwiML to establish WebSocket connection
   - Passes caller parameters to WebSocket

2. **`POST /api/v1/webhooks/call-status`**
   - Receives call lifecycle events (ringing, in-progress, completed, etc.)
   - Used for logging and analytics
   - Non-blocking acknowledgment

## Implementation Details

### File: server/app/config.py (Enhanced)

**Added Configuration:**
```python
BASE_URL: str = "https://your-domain.ngrok.io"  # Public URL for webhooks
```

**Purpose:**
- Dynamic WebSocket URL generation
- Support for ngrok during development
- Production-ready for custom domains

### File: server/app/routes/webhooks.py (193 lines)

**Key Components:**

1. **Incoming Call Webhook** (Lines 15-68)
   ```python
   @router.post("/incoming-call")
   async def handle_incoming_call(
       From: str = Form(...),
       To: str = Form(...),
       CallSid: str = Form(...)
   ):
       """Generate TwiML to connect to WebSocket"""
       response = VoiceResponse()
       
       # WebSocket URL construction
       ws_url = f"wss://{settings.BASE_URL}/api/v1/voice/media-stream"
       
       # Connect with parameters
       connect = Connect()
       stream = connect.stream(url=ws_url)
       stream.parameter(name="From", value=From)
       stream.parameter(name="To", value=To)
       stream.parameter(name="CallSid", value=CallSid)
       
       response.append(connect)
       return Response(content=str(response), media_type="application/xml")
   ```

2. **Call Status Webhook** (Lines 71-110)
   ```python
   @router.post("/call-status")
   async def handle_call_status(
       CallSid: str = Form(...),
       CallStatus: str = Form(...),
       CallDuration: str = Form(None)
   ):
       """Log call status updates"""
       logger.info(f"Call {CallSid} status: {CallStatus}")
       # TODO: Store in database for analytics
       return {"status": "received"}
   ```

**TwiML Example:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://abc123.ngrok.io/api/v1/voice/media-stream">
            <Parameter name="From" value="+15551234567"/>
            <Parameter name="To" value="+15559876543"/>
            <Parameter name="CallSid" value="CA1234567890abcdef"/>
        </Stream>
    </Connect>
</Response>
```

### File: .env.example (Updated)

**Added Variables:**
```bash
# Base URL for webhooks (use ngrok URL during development)
# Example: https://abcd-1234.ngrok.io (no trailing slash)
BASE_URL=https://your-domain.ngrok.io

# POC SAFETY: Only call this number for testing outbound calls
YOUR_TEST_NUMBER=+1234567890
```

### File: scripts/test_twilio_webhooks.py (570 lines)

Comprehensive test suite with 4 test categories:

1. **Incoming Call Webhook Test** (Lines 84-179)
   - Simulates Twilio POST request
   - Parses TwiML XML response
   - Validates `<Connect>` and `<Stream>` structure
   - Verifies WebSocket URL format (wss://)
   - Checks parameter passing

2. **Call Status Webhook Test** (Lines 182-227)
   - Tests different call statuses (ringing, in-progress, completed, etc.)
   - Verifies HTTP 200 responses
   - Validates acknowledgment format

3. **WebSocket URL Construction Test** (Lines 230-249)
   - Tests URL transformation logic
   - Handles different BASE_URL formats (http://, https://, no protocol)
   - Ensures wss:// prefix for WebSocket

4. **Parameter Passing Test** (Lines 252-314)
   - Verifies From, To, CallSid parameters in TwiML
   - Validates parameter values match input
   - Ensures parameters are accessible in WebSocket

**Test Execution:**
```bash
# Start server
cd server
uvicorn app.main:app --reload --port 8000

# Run tests
python scripts/test_twilio_webhooks.py
```

**Expected Output:**
```
================================================================================
TWILIO WEBHOOK TEST SUITE
================================================================================

✅ Server is running at http://localhost:8000

TEST: Incoming Call Webhook
  ✅ Webhook returned 200 OK
  ✅ TwiML validation passed

TEST: Call Status Webhook
  ✅ All call status tests passed

TEST: WebSocket URL Construction
  ✅ URL construction logic validated

TEST: TwiML Parameter Passing
  ✅ All parameters passed correctly

🎉 ALL TESTS PASSED
```

## Key Design Decisions

### 1. WebSocket URL Construction
**Challenge:** BASE_URL can have different formats (http://, https://, no protocol)

**Solution:**
```python
ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"
```

**Why:** 
- Strip any existing protocol
- Always use wss:// for secure WebSocket
- Works with ngrok, custom domains, or bare hostnames

### 2. Parameter Passing via TwiML
**Pattern:** Use `<Parameter>` tags in `<Stream>`

**Alternative Considered:** Query string parameters
- Rejected: Twilio doesn't support query params in Stream URL
- TwiML parameters are accessible via WebSocket `start` event

**Access in WebSocket:**
```python
# In voice.py handle_media_stream()
custom_params = data['start'].get('customParameters', {})
caller_phone = custom_params.get('From')
```

### 3. Optional Initial Greeting
**Design:** Commented out by default

**Reasoning:**
- Faster connection (no TTS delay)
- WebSocket handler provides greeting via AI
- Can be enabled for specific use cases

**To Enable:**
```python
response.say(
    "Thank you for calling Bart's Automotive. "
    "Please wait while we connect you to our AI assistant.",
    voice="Polly.Joanna"
)
response.pause(length=1)
```

### 4. Call Status Logging
**Current:** Logs to console only

**Future (Feature 10):**
- Store in database (call_logs table)
- Send to monitoring/alerting system
- Analytics dashboard

### 5. Separation of Concerns
**Why two incoming call endpoints?**

1. `/api/v1/webhooks/incoming-call` (this feature)
   - Twilio-specific webhook
   - Form data parsing
   - TwiML generation

2. `/api/v1/voice/incoming` (voice.py, Feature 8)
   - Legacy/alternative endpoint
   - Direct TwiML without form parsing
   - Kept for backward compatibility

**Recommended:** Use `/webhooks/incoming-call` for production

## Integration Points

### Services Used:
1. **Twilio TwiML Library**
   - VoiceResponse, Connect, Stream classes
   - XML generation
   - Parameter handling

2. **FastAPI Form Handling**
   - `Form(...)` for Twilio POST data
   - Automatic validation
   - Type conversion

3. **Settings (config.py)**
   - BASE_URL for dynamic URL construction
   - Environment-based configuration

### Endpoints Registered:
```python
# In main.py
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
```

**Full Endpoint URLs:**
- POST `/api/v1/webhooks/incoming-call`
- POST `/api/v1/webhooks/call-status`
- POST `/api/v1/webhooks/twilio/status` (existing)
- POST `/api/v1/webhooks/calendar/notification` (existing)

## Testing Strategy

### Unit Testing:
✅ **Test Script:** scripts/test_twilio_webhooks.py

**Test Coverage:**
- TwiML XML structure validation
- WebSocket URL format
- Parameter extraction
- Call status handling
- HTTP response codes
- Error handling

### Integration Testing (Manual):

1. **Local Testing with ngrok:**
   ```bash
   # Terminal 1: Start server
   cd server
   uvicorn app.main:app --reload --port 8000
   
   # Terminal 2: Start ngrok
   ngrok http 8000
   
   # Copy ngrok URL (e.g., https://abc123.ngrok.io)
   ```

2. **Update .env:**
   ```bash
   BASE_URL=https://abc123.ngrok.io
   ```

3. **Configure Twilio Console:**
   - Go to: https://console.twilio.com/
   - Navigate to: Phone Numbers → Manage → Active Numbers
   - Select your Twilio number
   - Under "Voice Configuration":
     - A CALL COMES IN: Webhook
     - URL: `https://abc123.ngrok.io/api/v1/webhooks/incoming-call`
     - HTTP Method: POST
   - Under "Status Callback URL":
     - URL: `https://abc123.ngrok.io/api/v1/webhooks/call-status`
     - HTTP Method: POST
   - Save

4. **Test Call:**
   ```bash
   # Call your Twilio number from your phone
   # Watch server logs for:
   # - Incoming call webhook hit
   # - WebSocket connection
   # - STT transcripts
   # - LLM responses
   # - TTS audio streaming
   # - Call status updates
   ```

### End-to-End Testing:

**Test Scenarios:**

1. **New Customer Call:**
   - Call from unknown number
   - AI greets generically
   - Book appointment
   - Verify calendar entry

2. **Existing Customer Call:**
   - Call from known number
   - AI greets by name
   - Mentions previous service
   - Reschedule appointment

3. **Barge-in Test:**
   - Interrupt AI mid-sentence
   - Verify audio clears immediately
   - AI responds to new input

4. **Call Status Tracking:**
   - Check logs for status events
   - Verify ringing → in-progress → completed

## Ngrok Setup Guide

### Installation:
```bash
# macOS
brew install ngrok

# Linux
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```

### Configuration:
```bash
# Get auth token from: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### Usage:
```bash
# Basic tunnel
ngrok http 8000

# With custom subdomain (paid plan)
ngrok http 8000 --subdomain=myautoshop

# With custom domain (paid plan)
ngrok http 8000 --domain=voice.myautoshop.com
```

### Output:
```
Session Status                online
Account                       user@example.com
Version                       3.x.x
Region                        United States (us)
Latency                       30ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok.io -> http://localhost:8000

# Copy the https:// URL and use as BASE_URL
```

### Monitoring:
- Open http://127.0.0.1:4040 for ngrok inspector
- View all HTTP requests in real-time
- Replay requests for debugging

## Production Deployment

### Using Custom Domain:

1. **Set up DNS:**
   ```
   voice.myautoshop.com → CNAME → your-server.com
   ```

2. **Configure SSL (Let's Encrypt):**
   ```bash
   sudo certbot --nginx -d voice.myautoshop.com
   ```

3. **Update .env:**
   ```bash
   BASE_URL=https://voice.myautoshop.com
   ```

4. **Configure Twilio:**
   - Webhook URL: `https://voice.myautoshop.com/api/v1/webhooks/incoming-call`

### Using Twilio Elastic SIP Trunk (Advanced):
- Route calls via SIP instead of webhooks
- Lower latency (<50ms)
- Requires more setup

## Known Issues & Limitations

### 1. BASE_URL Must Be Set
**Issue:** No default fallback if BASE_URL not configured

**Impact:** WebSocket URL will be invalid
**Fix:** Add validation in startup:
```python
if not settings.BASE_URL or "your-domain" in settings.BASE_URL:
    raise ValueError("BASE_URL must be configured in .env")
```

### 2. No Database Logging Yet
**Issue:** Call status events only logged to console

**Impact:** Can't track call history or analytics
**Fix:** Feature 10 will implement database storage

### 3. No Authentication on Webhooks
**Issue:** Webhook endpoints are publicly accessible

**Impact:** Could be abused (DDoS, fake calls)
**Fix:** Add Twilio signature validation:
```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
if not validator.validate(url, form_data, signature):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

### 4. Ngrok Free Tier Limits
**Issue:** Ngrok free URLs change on restart

**Impact:** Must update Twilio webhook URL every restart
**Solution:** 
- Paid plan: Fixed subdomain
- Production: Custom domain

## Next Steps (Future Features)

### Feature 10: Comprehensive Logging & Analytics
- Database storage for call logs
- Performance metrics (latency, success rate)
- Analytics dashboard
- Call recordings (optional)

### Feature 11: Outbound Calls (Reminders)
- Use same webhook infrastructure
- Cron job triggers calls
- Safety: Only call YOUR_TEST_NUMBER during POC
- `/incoming-reminder` endpoint for outbound context

### Feature 12: Multi-Tenant Support
- Support multiple Twilio numbers
- Route to different businesses
- Separate configurations per tenant

### Feature 13: Advanced Features
- Call transfer (to human agent)
- Conference calls
- Call recording with transcription
- Voicemail support
- SMS fallback

## Success Criteria

✅ **Functional Requirements:**
- [x] Webhook accepts Twilio POST requests
- [x] TwiML generation with WebSocket connection
- [x] WebSocket URL uses BASE_URL from settings
- [x] Parameters passed from webhook to WebSocket
- [x] Call status callbacks logged
- [x] Integration with existing voice handler

✅ **Testing Requirements:**
- [x] Unit tests for TwiML generation
- [x] Unit tests for URL construction
- [x] Unit tests for parameter passing
- [x] Manual testing with ngrok
- [x] End-to-end call testing (manual)

✅ **Documentation Requirements:**
- [x] Ngrok setup guide
- [x] Twilio configuration steps
- [x] Testing instructions
- [x] Production deployment guide

## Lessons Learned

1. **TwiML is XML-based:**
   - Use twilio library for generation (don't build XML manually)
   - Proper escaping handled automatically
   - Type-safe parameter handling

2. **WebSocket URL format matters:**
   - Must use wss:// (not ws://)
   - No trailing slashes in BASE_URL
   - Protocol stripping logic prevents double https://

3. **ngrok is essential for local development:**
   - Twilio needs public URL
   - ngrok inspector is great for debugging
   - Free tier is sufficient for POC

4. **Parameter passing via TwiML works well:**
   - Cleaner than query strings
   - Accessible in WebSocket via customParameters
   - Type-safe with Form(...) validation

5. **Call status callbacks are optional but valuable:**
   - Great for analytics
   - Non-blocking (async)
   - Can be used for alerting (e.g., failed calls)

## References

### Code Inspiration:
1. **twilio-samples/speech-assistant-openai-realtime-api-python**
   - Lines 38-63: Incoming call webhook
   - TwiML with <Connect><Stream>
   - Simple implementation (no parameters)

2. **Twilio Media Streams Documentation:**
   - https://www.twilio.com/docs/voice/media-streams
   - Parameter passing
   - WebSocket message formats

3. **Twilio TwiML Documentation:**
   - https://www.twilio.com/docs/voice/twiml
   - <Connect>, <Stream>, <Parameter> tags
   - Voice attributes

### Testing References:
- XML parsing with ElementTree
- httpx for async HTTP requests
- Twilio form data format

---

**Implementation Time:** ~2 hours  
**Lines of Code:** 763 (webhooks.py: 193, test: 570)  
**Critical Path:** YES (blocks real call testing)  
**Status:** COMPLETE ✅

**Next Feature:** Feature 10 - Comprehensive Logging & Analytics
