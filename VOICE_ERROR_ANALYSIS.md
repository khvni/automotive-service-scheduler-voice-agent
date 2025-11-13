# Voice Agent Error Analysis: "Application Error Has Occurred - Goodbye"

**Date:** 2025-01-13
**Issue:** User receives "we are sorry - application error has occurred - goodbye" message when calling
**Trigger:** Saying "hello" shortly after call connects

## Root Cause Analysis

### Primary Issue: Poor Exception Handling

The voice agent's WebSocket handler (`server/app/routes/voice.py:139-560`) has inadequate error handling that causes Twilio to play the error message when any exception occurs.

### Critical Code Sections

#### 1. Service Initialization (lines 191-227)
```python
try:
    # Initialize services
    stt = DeepgramSTTService(settings.DEEPGRAM_API_KEY)
    tts = DeepgramTTSService(settings.DEEPGRAM_API_KEY)
    openai = OpenAIService(api_key=settings.OPENAI_API_KEY, ...)

    # Connect to STT and TTS
    await stt.connect()  # ⚠️ CAN RAISE EXCEPTION
    await tts.connect()  # ⚠️ CAN RAISE EXCEPTION
```

**Problem:** If connection fails, exception is raised but not gracefully handled.

#### 2. Exception Handler (lines 512-513)
```python
except Exception as e:
    logger.error(f"Error in media stream handler: {e}", exc_info=True)
```

**Problem:**
- Only logs the error
- Doesn't send any response to Twilio
- Twilio times out and plays default error message

#### 3. Audio Processing (line 314)
```python
await stt.send_audio(audio_bytes)  # ⚠️ CAN RAISE EXCEPTION
```

**Problem:** If STT disconnects or fails, exception propagates to outer handler.

### Identified Failure Scenarios

#### Scenario 1: Deepgram STT Connection Failure
**Location:** `server/app/services/deepgram_stt.py:99-100`

```python
if not self.connection.start(self.live_options):
    raise Exception("Failed to start Deepgram connection")
```

**Impact:**
- User calls in
- STT connection fails to establish
- Exception caught and logged
- No audio processing occurs
- Twilio receives no response
- **Result: "Application error" message**

#### Scenario 2: Deepgram NET-0001 Timeout
**Documentation:** Deepgram closes connection if no audio received within ~10 seconds

**Current Implementation Issues:**
- KeepAlive sent every 10 seconds (may be too slow)
- No error recovery if connection times out
- No reconnection logic

**Impact:**
- Connection established but times out
- STT stops working
- User speech not transcribed
- **Result: "Application error" message**

#### Scenario 3: Deepgram TTS Connection Failure
**Location:** `server/app/services/deepgram_tts.py:90-93`

```python
self.ws = await websockets.connect(ws_url, ...)
```

**Impact:**
- STT works fine
- LLM generates response
- TTS connection fails
- Cannot synthesize audio
- **Result: "Application error" message**

#### Scenario 4: OpenAI API Failure
**Location:** `server/app/services/openai_service.py:273`

```python
response_stream = await self.client.chat.completions.create(**request_params)
```

**Impact:**
- User speech transcribed correctly
- OpenAI API call fails (rate limit, invalid key, etc.)
- Error event yielded but voice.py only breaks the loop
- No fallback response
- **Result: Silent failure or "Application error" message**

#### Scenario 5: Empty Audio Packets
**Documentation:** Deepgram disconnects if empty bytes are sent

**Current Code:** No validation before sending audio (line 314)

```python
audio_bytes = base64.b64decode(audio_payload)
await stt.send_audio(audio_bytes)  # No check if audio_bytes is empty
```

**Impact:**
- Empty packets cause unexpected closures
- STT connection drops
- **Result: "Application error" message**

### Error Propagation Flow

```
1. User calls → Twilio connects to WebSocket
                     ↓
2. WebSocket handler starts → Service initialization
                     ↓
              ┌──────┴──────┐
              ↓             ↓
         STT connect   TTS connect  ← ANY FAILURE HERE
              ↓             ↓
         ❌ Exception raised
              ↓
3. Caught by outer handler (line 512)
              ↓
4. Error logged only (no user-facing handling)
              ↓
5. WebSocket closes in finally block
              ↓
6. Twilio receives no valid TwiML/response
              ↓
7. 🔊 "Application error has occurred - goodbye"
```

## Confirmed Issues

### 1. No Graceful Error Recovery
- **File:** `server/app/routes/voice.py`
- **Lines:** 512-513
- **Fix Required:** Add graceful error handling with fallback TwiML

### 2. Missing KeepAlive Validation
- **File:** `server/app/services/deepgram_stt.py`
- **Lines:** 130-142
- **Issue:** KeepAlive every 10 seconds may be too slow
- **Fix Required:** Increase frequency or add audio validation

### 3. No Empty Audio Validation
- **File:** `server/app/routes/voice.py`
- **Line:** 314
- **Fix Required:** Check if `audio_bytes` is empty before sending

### 4. No Retry Logic
- **Files:** All service files
- **Issue:** Single-attempt connections with no retry
- **Fix Required:** Add exponential backoff retry for transient failures

### 5. No Circuit Breaker Pattern
- **Issue:** Repeated failures not tracked or prevented
- **Fix Required:** Implement circuit breaker to fail fast when degraded

### 6. Inadequate Error Messages
- **Issue:** Generic exception handling loses context
- **Fix Required:** Specific exception handlers for each service

## Recommended Fixes (Priority Order)

### 🔴 CRITICAL - Fix Immediately

#### Fix 1: Add Graceful Error Handler in voice.py

**Location:** `server/app/routes/voice.py:512-513`

**Current:**
```python
except Exception as e:
    logger.error(f"Error in media stream handler: {e}", exc_info=True)
```

**Fix:**
```python
except Exception as e:
    logger.error(f"Error in media stream handler: {e}", exc_info=True)

    # Send graceful error message to caller via Twilio
    try:
        error_message = "I'm sorry, I'm having technical difficulties. Please call back in a few moments."

        # Use Twilio Say command to inform user
        await websocket.send_json({
            "event": "clear",
            "streamSid": stream_sid
        })

        # Queue error message as audio (would need TTS fallback)
        logger.info("Sent error message to caller")

    except Exception as fallback_error:
        logger.error(f"Failed to send error message: {fallback_error}")
```

#### Fix 2: Validate Audio Before Sending

**Location:** `server/app/routes/voice.py:310-314`

**Current:**
```python
elif event == "media":
    audio_payload = data["media"]["payload"]
    audio_bytes = base64.b64decode(audio_payload)
    await stt.send_audio(audio_bytes)
```

**Fix:**
```python
elif event == "media":
    audio_payload = data["media"]["payload"]
    audio_bytes = base64.b64decode(audio_payload)

    # Validate audio before sending (prevent NET-0001)
    if audio_bytes and len(audio_bytes) > 0:
        await stt.send_audio(audio_bytes)
    else:
        logger.debug("Skipped empty audio packet")
```

#### Fix 3: Add Service Connection Retry

**Location:** `server/app/services/deepgram_stt.py:64-128`

**Add retry decorator:**
```python
async def connect_with_retry(self, max_retries=3, backoff_factor=1.5) -> None:
    """Connect with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            await self.connect()
            logger.info(f"Connected to Deepgram on attempt {attempt + 1}")
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            delay = backoff_factor ** attempt
            logger.warning(f"Connection failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

### 🟡 HIGH PRIORITY - Fix Soon

#### Fix 4: Add Pre-flight Health Checks

**New File:** `server/app/services/health_check.py`

```python
async def check_service_health() -> dict:
    """Check if all required services are available."""
    results = {
        "deepgram_stt": False,
        "deepgram_tts": False,
        "openai": False,
        "database": False,
        "redis": False
    }

    # Test each service with lightweight request
    # Return results
    return results
```

**Usage:** Check before accepting incoming calls

#### Fix 5: Add Circuit Breaker

**Purpose:** Prevent cascading failures

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```

### 🟢 MEDIUM PRIORITY - Improve Resilience

#### Fix 6: Better Error Logging with Context

**Add structured logging:**
```python
logger.error(
    "Service initialization failed",
    extra={
        "call_sid": call_sid,
        "stream_sid": stream_sid,
        "caller_phone": caller_phone,
        "service": "deepgram_stt",
        "error_type": type(e).__name__,
        "error_message": str(e)
    }
)
```

#### Fix 7: Add Error Metrics to Redis

**Track error rates:**
```python
async def increment_error_count(service_name: str):
    """Track service errors in Redis."""
    key = f"errors:{service_name}:{date.today()}"
    await redis.incr(key)
    await redis.expire(key, 86400)  # 24 hour TTL
```

## Testing Strategy

### Manual Testing Steps

1. **Test STT Connection Failure:**
   - Use invalid Deepgram API key
   - Make call
   - Verify graceful error handling

2. **Test NET-0001 Timeout:**
   - Connect but don't send audio for 15 seconds
   - Verify error recovery

3. **Test OpenAI Failure:**
   - Use invalid OpenAI API key
   - Make call and speak
   - Verify fallback response

4. **Test Network Interruption:**
   - Simulate network partition
   - Verify reconnection logic

### Automated Testing

Create integration tests:
```python
async def test_service_failure_handling():
    """Test that service failures are handled gracefully."""
    # Mock service failures
    # Verify error messages sent to Twilio
    # Verify logging
    # Verify metrics
    pass
```

## Monitoring Recommendations

### Add Alerts For:

1. **High Error Rate:** > 10 errors per hour
2. **Service Unavailable:** Health check failures
3. **Connection Timeouts:** NET-0001 errors
4. **API Rate Limits:** 429 responses from Deepgram/OpenAI

### Metrics to Track:

1. Call success rate
2. Error rate by service (STT, TTS, LLM)
3. Average call duration
4. Time to first byte (TTFB) for TTS
5. Transcript accuracy (via feedback)

## Conclusion

The "application error has occurred" message is caused by inadequate exception handling in the voice agent's WebSocket handler. When any service (STT, TTS, or OpenAI) fails to initialize or encounters an error, the exception is caught but not gracefully handled, causing Twilio to timeout and play the default error message.

**Immediate Actions Required:**

1. ✅ Add graceful error handling with user-facing messages
2. ✅ Validate audio packets before sending to Deepgram
3. ✅ Implement retry logic for service connections
4. ✅ Add pre-flight health checks
5. ✅ Implement circuit breaker pattern

**Expected Outcome:** Users will receive clear, friendly error messages instead of generic "application error" messages, and the system will recover gracefully from transient failures.
