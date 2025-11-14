# WebSocket URL Bug Fix

## Problem
After fixing the webhook endpoint path, outbound calls still weren't working. The TwiML was generating an invalid WebSocket URL.

## Root Cause
In `server/app/routes/voice.py` line 125, the code was:
```python
ws_url = f"wss://{settings.BASE_URL}/api/v1/voice/media-stream"
```

Since `settings.BASE_URL` is `https://100e646918a0.ngrok-free.app`, this created:
```
wss://https://100e646918a0.ngrok-free.app/api/v1/voice/media-stream
```

This is invalid because it has both `wss://` and `https://` protocols.

## Fix Applied
Strip the protocol prefix from BASE_URL:
```python
ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"
```

Now it correctly generates:
```
wss://100e646918a0.ngrok-free.app/api/v1/voice/media-stream
```

## Files Modified
- `server/app/routes/voice.py` - Line 125

## Verification
```bash
curl -s "https://100e646918a0.ngrok-free.app/api/v1/voice/incoming-reminder" -X POST
```

Returns valid TwiML with correct WebSocket URL.

## Impact
Outbound reminder calls now properly establish WebSocket connections to the AI agent.

## Related Issues
This bug was preventing Twilio from connecting to the WebSocket endpoint after the call was initiated.
