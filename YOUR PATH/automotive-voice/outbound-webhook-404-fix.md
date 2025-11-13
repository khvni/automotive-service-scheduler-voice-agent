# Outbound Call Webhook 404 Fix

## Problem
When making outbound reminder calls, users heard "application error has occurred - goodbye" immediately after the call connected. The call would fail without the AI agent responding.

## Root Cause
The demo was trying to call `/api/v1/webhooks/outbound-reminder`, but this endpoint doesn't exist. The server returned a 404 error, causing Twilio to fail and hang up with the error message.

Looking at the route registration in `main.py`:
- `voice.router` is mounted at `/api/v1/voice`
- `webhooks.router` is mounted at `/api/v1/webhooks`

The actual endpoint for outbound reminders is `/incoming-reminder` in `voice.py` (line 116), which becomes:
`/api/v1/voice/incoming-reminder`

## Fix Applied
Updated all references in `demo_2_outbound_reminder.py`:
- Changed from: `/api/v1/webhooks/outbound-reminder`
- Changed to: `/api/v1/voice/incoming-reminder`

## Files Modified
- `demos/demo_2_outbound_reminder.py` (3 occurrences)

## Impact
Outbound reminder calls now properly connect to the AI agent via the correct webhook endpoint. The 404 error is resolved and calls work as expected.

## Related Issue
This was discovered through server logs showing:
```
INFO: 54.146.44.158:0 - "POST /api/v1/webhooks/outbound-reminder?appointment_id=7 HTTP/1.1" 404 Not Found
```
