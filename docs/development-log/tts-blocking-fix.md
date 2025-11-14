# TTS Blocking Fix - Voice Agent 30-Second Timeout

## Problem
Voice agent had 30-second delay after user says "hello", followed by "application error has occurred" message.

## Root Cause Analysis
Investigation revealed:
1. Server logs showed NO recent errors - code was running but timing out
2. `deepgram_tts.py` `send_text()` was spawning background task with `asyncio.create_task(_stream_audio(text))`
3. Method returned immediately before audio was fully generated and queued
4. Voice.py polling loop would start before audio was available, leading to timeouts

## Reference Repo Analysis
Used GitHub MCP to analyze:
- `twilio-samples/speech-assistant-openai-realtime-api-python` - Only relevant Python+Twilio example
- Architecture difference: They use OpenAI Realtime API (handles STT+TTS internally) vs our pipeline (Deepgram STT → OpenAI text → Deepgram TTS)
- Their pattern: Simple two-task architecture with direct passthrough
- Our pattern: Complex three-stage pipeline with queuing

## Fix Applied

### 1. Made TTS Blocking (deepgram_tts.py:104-124)
**Before:**
```python
async def send_text(self, text: str) -> None:
    asyncio.create_task(self._stream_audio(text))  # Non-blocking
```

**After:**
```python
async def send_text(self, text: str) -> None:
    await self._stream_audio(text)  # Blocking - waits for completion
```

### 2. Fixed Voice Agent to Send Complete Response Once (voice.py:394-428)
**Before:**
```python
async for event in openai.generate_response(stream=True):
    if event["type"] == "content_delta":
        response_text += chunk
        await tts.send_text(response_text)  # Sends "Hello", "Hello how", "Hello how are"
```

**After:**
```python
async for event in openai.generate_response(stream=True):
    if event["type"] == "content_delta":
        response_text += chunk  # Just accumulate
    elif event["type"] == "done":
        await tts.send_text(response_text)  # Send complete response once
```

### 3. Added Comprehensive Logging
- `[TTS]` prefix: API calls, chunk queuing, TTFB, timing metrics
- `[VOICE]` prefix: User speech, OpenAI streaming, audio delivery
- Enables tracking exact failure point in pipeline

## Impact
- TTS now ensures audio is fully queued before returning
- No duplicate text sent to TTS (was causing massive repetition)
- Detailed logging shows exact flow: User → STT → OpenAI → TTS → Twilio

## Testing Required
Test voice agent and observe logs with prefixes `[TTS]` and `[VOICE]` to verify:
1. User says "hello"
2. OpenAI generates response
3. TTS creates audio chunks
4. Audio streams to Twilio successfully
5. No 30-second timeout

## Files Changed
- `server/app/services/deepgram_tts.py` - Made send_text() blocking, added logging to _stream_audio()
- `server/app/routes/voice.py` - Fixed to send complete response once, added comprehensive logging

## Commit
eb27833 - "fix: simplify TTS flow and add comprehensive logging for voice agent"
