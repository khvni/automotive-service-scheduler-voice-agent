# TTS Silence Issue Fix

## Problem
Phone calls made via `run_demo2_with_call.sh` were experiencing pure silence when buttons were pressed during the call. The TTS (Text-to-Speech) was not generating audio.

## Root Cause
Missing import in `server/app/services/deepgram_tts.py`. The code was trying to use `AsyncDeepgramClient` class which doesn't exist in Deepgram SDK v3.8.0.

## Investigation
1. Checked server logs and found: `NameError: name 'AsyncDeepgramClient' is not defined`
2. Used Context7 MCP to research Deepgram Python SDK documentation
3. Discovered that SDK v3.8.0 uses `DeepgramClient` for both sync and async operations, not a separate `AsyncDeepgramClient` class

## Solution
Updated `server/app/services/deepgram_tts.py`:
- Changed from: `from deepgram import DeepgramClient, DeepgramClientOptions, AsyncDeepgramClient`
- Changed to: `from deepgram import DeepgramClient, DeepgramClientOptions`
- Updated type hint: `self.client: Optional[DeepgramClient] = None`
- Updated instantiation: `self.client = DeepgramClient(self.api_key, config)`

## Files Modified
- `server/app/services/deepgram_tts.py`

## Commit
- SHA: 2fc20ca
- Message: "fix: add missing DeepgramClient import for TTS service"

## Status
✅ Fixed - Server now starts successfully without import errors. TTS service should now work correctly during phone calls.
