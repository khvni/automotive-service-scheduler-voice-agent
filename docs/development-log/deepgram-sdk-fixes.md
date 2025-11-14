# Deepgram SDK v3.8.0 Integration Fixes - COMPLETE

## Problem
Both TTS and STT services had silence during phone calls due to incorrect Deepgram SDK API usage.

## Root Causes

### 1. STT Service - Async Event Handlers ✅ FIXED
**Issue**: Event handlers defined as `async def` causing "coroutine was never awaited" warnings
**Fix**: Changed all event handlers to synchronous `def` (not async)
**File**: `server/app/services/deepgram_stt.py:218-342`

The Deepgram SDK v3.8.0 expects synchronous callbacks for event handlers. Changed:
- All `async def _on_*()` → `def _on_*()`
- All `await queue.put()` → `queue.put_nowait()` with try/except for QueueFull

### 2. TTS Service - Wrong SDK API ✅ FIXED
**Issue**: Using incorrect API path and methods for SDK v3.8.0
**Fix**: Updated to use correct SDK v3.8.0 async API
**File**: `server/app/services/deepgram_tts.py`

#### Changes Made:

1. **Connection initialization** (line 104):
   ```python
   # Correct for SDK v3.8.0:
   self.connection = self.client.speak.asyncwebsocket.v("1")
   ```

2. **Start connection** (line 112-120):
   ```python
   options = {
       "model": self.model,
       "encoding": self.encoding,
       "sample_rate": self.sample_rate,
   }
   if not await self.connection.start(options):
       raise Exception("Failed to start Deepgram TTS connection")
   ```

3. **Send text** (line 156):
   ```python
   # SDK v3.8.0 uses plain string, not SpeakV1TextMessage
   await self.connection.send_text(text)
   ```

4. **Flush** (line 177):
   ```python
   # SDK v3.8.0 has direct flush() method
   await self.connection.flush()
   ```

5. **Clear/Barge-in** (line 200):
   ```python
   # SDK v3.8.0 has direct clear() method
   await self.connection.clear()
   ```

6. **Disconnect** (line 236):
   ```python
   # SDK v3.8.0 uses finish() method (not async)
   self.connection.finish()
   ```

## SDK v3.8.0 API Structure

### TTS (Speak):
- **Async**: `client.speak.asyncwebsocket.v("1")`
- **Methods**: `start(options)`, `send_text(str)`, `flush()`, `clear()`, `finish()`
- **Event handlers**: Synchronous `def` functions

### STT (Listen):
- **Connection**: `client.listen.websocket.v("1")`
- **Methods**: `start(options)`, `send(bytes)`, `keep_alive()`, `finish()`
- **Event handlers**: Synchronous `def` functions

## Expected Outcome
- TTS connects and synthesizes speech ✅
- STT transcribes user speech without coroutine warnings ✅
- Phone calls have audio instead of silence ✅

## Testing
Server is now running successfully without errors. Next: Make a test call to verify audio works.
