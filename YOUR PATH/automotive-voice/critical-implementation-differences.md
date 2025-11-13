# Critical Implementation Differences with Working Example

## Repository Analyzed
mohammed97ashraf/Custom-Telephony-Voice-Agent - Working FastAPI + Twilio + Deepgram implementation

## Key Architectural Differences

### 1. **Deepgram TTS WebSocket vs REST API** ⚠️ CRITICAL

**Our Implementation:**
- Uses `websockets` library directly
- Connects to `wss://api.deepgram.com/v1/speak`
- Manual WebSocket management

**Working Example:**
- Uses `deepgram_client.speak.asyncwebsocket.v("1")` from SDK
- Uses `SpeakWSOptions` for configuration
- Leverages built-in event handlers (on_speak_open, on_speak_close, on_speak_error, on_speak_audio)
- SDK handles connection lifecycle automatically

**Impact:** Our manual WebSocket implementation may not handle Deepgram's protocol correctly, causing audio streaming failures.

### 2. **Audio Packet Handling**

**Our Implementation:**
```python
# voice.py:315-319
if audio_bytes and len(audio_bytes) > 0:
    await stt.send_audio(audio_bytes)
else:
    logger.debug("Skipped empty audio packet")
```

**Working Example:**
```python
# Decodes base64 audio immediately
audio_data = base64.b64decode(media_payload)
# Sends raw bytes directly to Deepgram
```

**Impact:** Potentially identical, but their immediate decode approach is cleaner.

### 3. **TTS Streaming to Twilio**

**Our Implementation:**
- Uses background task: `asyncio.create_task(stream_agent_response(...))`
- Sends audio via: `await websocket.send_json({...})`

**Working Example:**
```python
async def on_speak_audio(self, data, **kwargs):
    # Encodes Deepgram audio to base64
    audio_base64 = base64.b64encode(data).decode('utf-8')
    
    # Sends to Twilio with streamSid
    await websocket.send_text(json.dumps({
        "event": "media",
        "streamSid": twilio_stream_sid,
        "media": {"payload": audio_base64}
    }))
```

**Impact:** They use `send_text()` with `json.dumps()` instead of `send_json()`. May be more reliable.

### 4. **Interrupt Handling**

**Working Example:**
- Uses global `interrupt_event = asyncio.Event()`
- Checks `interrupt_event.is_set()` before sending each audio chunk
- Cancels TTS task immediately on interruption

**Our Implementation:**
- Uses `tts.clear()` for barge-in
- No explicit interrupt event checking in audio streaming loop

**Impact:** Their approach provides more granular control over interruptions.

### 5. **Connection Initialization**

**Working Example:**
```python
# Starts connection with explicit await
await dg_speak_connection.start(speak_options)

# Has clear lifecycle:
# 1. Create connection
# 2. Register event handlers  
# 3. Start connection
# 4. Send text
# 5. Flush
# 6. Finish
```

**Our Implementation:**
- Uses manual `websockets.connect()`
- Less structured lifecycle management

### 6. **Error Recovery**

**Working Example:**
```python
async def on_speak_error(self, error, **kwargs):
    print(f"[Speak WS] Error: {error}")
    interrupt_event.set()
    if dg_speak_connection:
        asyncio.create_task(dg_speak_connection.finish())
```

**Our Implementation:**
- Generic exception handling
- No specific Deepgram error event handlers

## Potential Root Causes Based on Differences

### Issue #1: WebSocket Send Method
**Symptom:** Audio not reaching caller or Twilio timeout
**Cause:** Using `send_json()` instead of `send_text(json.dumps())`
**Fix Priority:** HIGH

### Issue #2: SDK vs Manual WebSocket
**Symptom:** TTS connection drops or audio not generated
**Cause:** Not using Deepgram SDK's built-in WebSocket methods
**Fix Priority:** CRITICAL

### Issue #3: Missing Flush Operation
**Symptom:** Last part of audio cut off or delayed
**Cause:** No explicit flush after sending text to TTS
**Fix Priority:** MEDIUM

### Issue #4: Interrupt Detection
**Symptom:** Agent continues speaking even when user interrupts
**Cause:** Not checking interrupt event in audio streaming loop
**Fix Priority:** MEDIUM

## Recommended Fixes

### Fix 1: Switch to Deepgram SDK TTS WebSocket
Replace manual websocket implementation with SDK:

```python
from deepgram import SpeakWSOptions, SpeakWebSocketEvents

# In deepgram_tts.py
async def connect(self):
    speak_options = SpeakWSOptions(
        model="aura-2-asteria-en",
        encoding="mulaw",
        sample_rate=8000,
    )
    
    self.connection = self.client.speak.asyncwebsocket.v("1")
    
    # Register event handlers
    self.connection.on(SpeakWebSocketEvents.Open, self._on_open)
    self.connection.on(SpeakWebSocketEvents.Close, self._on_close)
    self.connection.on(SpeakWebSocketEvents.Error, self._on_error)
    self.connection.on(SpeakWebSocketEvents.AudioData, self._on_audio)
    
    await self.connection.start(speak_options)
```

### Fix 2: Change Twilio Send Method
```python
# In voice.py - change from:
await websocket.send_json({...})

# To:
await websocket.send_text(json.dumps({
    "event": "media",
    "streamSid": stream_sid,
    "media": {"payload": audio_base64}
}))
```

### Fix 3: Add Flush Operation
```python
# After sending text to TTS
await tts.send_text(text)
await tts.flush()  # Ensure all audio is generated
```

## Testing Priority

1. **Test TTS Audio Delivery** - Make call, check if audio reaches Twilio
2. **Test Error Logging** - Check what errors occur during call
3. **Test Interrupt Handling** - Speak while agent is talking
4. **Test Connection Lifecycle** - Multiple calls in succession

## Next Steps

1. Check if our app uses correct Deepgram SDK version
2. Review our deepgram_tts.py implementation vs SDK approach
3. Make a test call and capture real-time logs
4. Consider switching to SDK-based TTS implementation
