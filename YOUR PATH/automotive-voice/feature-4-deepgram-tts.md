# Feature 4: Deepgram TTS Integration - COMPLETED

## Implementation Date
November 12, 2025

## Overview
Successfully implemented Deepgram Text-to-Speech (TTS) integration with WebSocket streaming, barge-in support, and Twilio phone compatibility.

## Files Created

### 1. server/app/services/tts_interface.py
**Purpose**: Abstract base class for TTS providers
**Key Features**:
- ABC-based interface for provider-agnostic TTS
- Enables swapping between Deepgram, ElevenLabs, Cartesia
- Methods: connect(), send_text(), flush(), clear(), get_audio(), disconnect()
- Properties: is_connected

**Design Pattern**: Follows same structure as deepgram_stt.py for consistency

### 2. server/app/services/deepgram_tts.py
**Purpose**: Deepgram TTS WebSocket implementation
**Key Features**:
- Implements TTSInterface abstract class
- Uses Deepgram Python SDK v3.8.0+
- AsyncDeepgramClient with async/await throughout
- Configuration:
  - Model: aura-2-asteria-en (natural female voice)
  - Encoding: mulaw (Twilio compatible)
  - Sample rate: 8000 Hz (phone quality)

**WebSocket Implementation**:
- Event handlers: OPEN, MESSAGE, CLOSE, ERROR
- Audio queue with asyncio.Queue()
- Streaming text support (chunk by chunk)
- Barge-in support with Clear command
- Flush command for finalizing synthesis

**Performance Tracking**:
- Time-to-first-byte (TTFB) measurement
- Audio chunk counting
- Detailed logging at debug/info levels

**Message Types**:
- SpeakV1TextMessage: Send text for synthesis
- SpeakV1ControlMessage: Control commands (Flush, Clear, Close)
- Audio data: Raw bytes (mulaw @ 8kHz)

### 3. scripts/test_deepgram_tts.py
**Purpose**: Comprehensive test suite for TTS service
**7 Test Cases**:
1. Connection establishment
2. Basic text synthesis (single chunk)
3. Streaming synthesis (multiple chunks)
4. Flush command
5. Clear command (barge-in simulation)
6. Performance metrics (TTFB)
7. Clean disconnection

**Features**:
- Async/await test framework
- Detailed logging and progress reporting
- Pass/fail summary
- Exit code based on results
- Uses environment variables for configuration

## Files Modified

### 1. server/app/services/__init__.py
**Changes**:
- Added DeepgramTTSService export
- Added TTSInterface export
- Updated __all__ list

### 2. server/app/config.py
**New Configuration**:
```python
DEEPGRAM_TTS_MODEL: str = "aura-2-asteria-en"
DEEPGRAM_TTS_ENCODING: str = "mulaw"
DEEPGRAM_TTS_SAMPLE_RATE: int = 8000
```

### 3. .env.example
**New Section**:
```bash
# Deepgram TTS Configuration
DEEPGRAM_TTS_MODEL=aura-2-asteria-en
DEEPGRAM_TTS_ENCODING=mulaw
DEEPGRAM_TTS_SAMPLE_RATE=8000
```

**Note**: Uses same DEEPGRAM_API_KEY as STT service

## Technical Details

### Deepgram SDK Usage
```python
from deepgram import AsyncDeepgramClient, DeepgramClientOptions
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import (
    SpeakV1SocketClientResponse,
    SpeakV1TextMessage,
    SpeakV1ControlMessage,
)
```

### Connection Pattern
```python
async with client.speak.v1.connect(
    model="aura-2-asteria-en",
    encoding="mulaw",
    sample_rate=8000
) as connection:
    connection.on(EventType.OPEN, handler)
    connection.on(EventType.MESSAGE, handler)
    await connection.start_listening()
    await connection.send_text(SpeakV1TextMessage(text="..."))
    await connection.send_control(SpeakV1ControlMessage(type="Flush"))
```

### Audio Streaming Flow
1. Send text chunks via send_text()
2. Audio generated in real-time
3. Audio bytes arrive in MESSAGE events
4. Audio queued in asyncio.Queue
5. Retrieved via get_audio() (non-blocking)
6. Flush signals end of text stream
7. Clear aborts synthesis (barge-in)

### Barge-in Implementation
When user interrupts:
1. Call clear()
2. Drains audio_queue
3. Sends Clear control message to Deepgram
4. Stops current synthesis
5. Ready for new text immediately

## Reference Materials Used

### 1. GitHub Reference
- Repo: deepgram/deepgram-twilio-streaming-voice-agent
- File: server.js lines 165-210
- Key patterns: WebSocket setup, event handlers, audio streaming

### 2. Deepgram Python SDK Docs
- Source: Context7 MCP (/deepgram/deepgram-python-sdk)
- Topics: TTS WebSocket API, async patterns, message types
- Version: v3.8.0+ (SDK v5.0.0+)

### 3. Existing Pattern
- File: server/app/services/deepgram_stt.py
- Followed same structure for consistency
- Similar error handling and logging

## Integration with Twilio

### Audio Format
- **Encoding**: mulaw (μ-law)
- **Sample Rate**: 8000 Hz
- **Channels**: 1 (mono)
- **Container**: none (raw audio)

### Streaming to Twilio
```python
# Get audio from TTS
audio_chunk = await tts.get_audio()

# Convert to base64 for Twilio
payload = base64.b64encode(audio_chunk).decode('utf-8')

# Send to Twilio WebSocket
message = {
    'event': 'media',
    'streamSid': stream_sid,
    'media': {'payload': payload}
}
```

### Barge-in with Twilio
```python
# Clear Twilio playback
twilio_message = {
    'event': 'clear',
    'streamSid': stream_sid
}

# Clear TTS queue
await tts.clear()
```

## Available Aura Models
- **aura-2-asteria-en**: Female voice (default)
- **aura-2-orpheus-en**: Male voice (deep)
- **aura-2-arcas-en**: Male voice (warm)
- **aura-2-athena-en**: Female voice (professional)
- **aura-2-hera-en**: Female voice (friendly)

Change via DEEPGRAM_TTS_MODEL environment variable.

## Performance Expectations
- **Time-to-First-Byte**: 50-200ms (typical)
- **Latency**: Streaming starts before full text is complete
- **Audio Quality**: Natural-sounding with Aura models
- **Throughput**: Handles real-time conversation speeds

## Error Handling
1. Connection failures: Logged and raised
2. Send failures: Logged and raised
3. WebSocket errors: Captured in ERROR event
4. Disconnection: Graceful cleanup with resource release

## Testing Strategy
Run comprehensive test suite:
```bash
python scripts/test_deepgram_tts.py
```

Expected output: 7/7 tests passed

## Next Steps (Feature 5)
- Integrate TTS with Twilio WebSocket handler
- Connect STT → LLM → TTS pipeline
- Implement conversation state management
- Add barge-in detection from STT interim results
- Test full voice conversation flow

## Lessons Learned
1. **Async Context Managers**: Use __aenter__/__aexit__ for connection management
2. **Event Handlers**: Message events can be bytes (audio) or JSON (control)
3. **Performance**: Track TTFB for user experience optimization
4. **Barge-in**: Clear both local queue and remote synthesis
5. **Testing**: Comprehensive test suite catches edge cases early

## Code Style Notes
- Matches deepgram_stt.py structure
- Comprehensive docstrings (Google style)
- Type hints throughout
- Async/await consistently used
- Detailed logging (debug, info, error levels)
- Error handling with try/except blocks
- Resource cleanup in disconnect()
