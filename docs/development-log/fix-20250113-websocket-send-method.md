# Fix: WebSocket Send Method Change (2025-01-13)

## Issue
Application error ("we are sorry - application error has occurred - goodbye") occurring during calls, even after initial error handling improvements.

## Root Cause Investigation
Compared our implementation with working example (mohammed97ashraf/Custom-Telephony-Voice-Agent):
- Working example uses `websocket.send_text(json.dumps({...}))`
- Our implementation used `websocket.send_json({...})`
- FastAPI's `send_json()` may serialize differently than Twilio expects

## Fix Applied
Changed all Twilio WebSocket communication from `send_json()` to `send_text(json.dumps())`:

### Changes Made

**File:** `server/app/routes/voice.py`

**Line 383-385** (Barge-in clear):
```python
# Before:
await websocket.send_json({"event": "clear", "streamSid": stream_sid})

# After:
await websocket.send_text(
    json.dumps({"event": "clear", "streamSid": stream_sid})
)
```

**Line 426-434** (Audio streaming):
```python
# Before:
await websocket.send_json({
    "event": "media",
    "streamSid": stream_sid,
    "media": {
        "payload": base64.b64encode(audio_chunk).decode("utf-8")
    },
})

# After:
await websocket.send_text(
    json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": base64.b64encode(audio_chunk).decode("utf-8")
        },
    })
)
```

**Line 551-553** (Error clear):
```python
# Before:
await websocket.send_json({"event": "clear", "streamSid": stream_sid})

# After:
await websocket.send_text(
    json.dumps({"event": "clear", "streamSid": stream_sid})
)
```

## Why This Matters
1. **Protocol Compatibility**: Twilio Media Streams may expect specific JSON serialization
2. **Working Examples**: All successful implementations use send_text()
3. **WebSocket Standards**: send_text() with manual JSON is more explicit and standard
4. **Debugging**: Makes message format more predictable and traceable

## Testing
After this fix:
1. Restart server: `killall uvicorn && venv-new/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir server`
2. Make test call
3. Say "hello" to trigger response
4. Check if audio plays correctly

## Rollback
If this causes issues:
```bash
git revert HEAD
```

## Commit
Commit: 31c37bd
Message: "fix: change WebSocket send method from send_json() to send_text(json.dumps())"

## Next Steps If This Doesn't Fix
1. Consider migrating TTS to Deepgram SDK WebSocket (SpeakWSOptions)
2. Add more detailed logging around audio streaming
3. Test with simpler response to isolate TTS vs WebSocket issues
