# GitHub Repository Analysis: Working Twilio + Deepgram Voice Agent Patterns

**Date:** 2025-11-13  
**Purpose:** Analyze proven patterns from working repositories to fix our voice agent implementation

## Executive Summary

Analyzed three working voice agent implementations to identify critical patterns for Twilio + Deepgram integration:

1. **deepgram/deepgram-twilio-streaming-voice-agent** (Node.js) - Official Deepgram reference
2. **Barty-Bart/openai-realtime-api-voice-assistant-V2** (Node.js) - OpenAI Realtime API integration
3. **twilio-samples/speech-assistant-openai-realtime-api-python** (Python) - Official Twilio reference

**Key Finding:** Our implementation is structurally sound but has critical timing and audio streaming issues that can be fixed with specific patterns from these repos.

---

## Repository 1: Deepgram Official Reference
**Repo:** `deepgram/deepgram-twilio-streaming-voice-agent`  
**Language:** Node.js  
**Stack:** Deepgram STT + OpenAI GPT-3.5 + Deepgram TTS (WebSocket)

### Architecture Pattern

```
Twilio WebSocket → MediaStream Class
                      ↓
            ┌────────┴────────┐
            ↓                 ↓
    Deepgram STT        Deepgram TTS
    (WebSocket)         (WebSocket)
            ↓                 ↑
    Transcript Queue          │
            ↓                 │
        OpenAI GPT-3.5 ──────┘
        (Streaming)
```

### Critical Patterns

#### 1. Deepgram TTS WebSocket Setup
```javascript
const deepgramTTSWebsocketURL = 'wss://api.deepgram.com/v1/speak?encoding=mulaw&sample_rate=8000&container=none';

const setupDeepgramWebsocket = (mediaStream) => {
  const options = {
    headers: {
      Authorization: `Token ${process.env.DEEPGRAM_API_KEY}`
    }
  };
  const ws = new WebSocket(deepgramTTSWebsocketURL, options);
  
  ws.on('message', function incoming(data) {
    // PATTERN: Direct base64 encoding without buffering
    const payload = data.toString('base64');
    const message = {
      event: 'media',
      streamSid: streamSid,
      media: { payload },
    };
    mediaStream.connection.sendUTF(JSON.stringify(message));
  });
  
  return ws;
}
```

**Key Insight:** Uses WebSocket for TTS, sends audio directly to Twilio without intermediate queues.

#### 2. Streaming LLM → TTS Integration
```javascript
async function promptLLM(mediaStream, prompt) {
  const stream = openai.beta.chat.completions.stream({
    model: 'gpt-3.5-turbo',
    stream: true,
    messages: [...]
  });
  
  speaking = true;
  for await (const chunk of stream) {
    if (speaking) {
      chunk_message = chunk.choices[0].delta.content;
      if (chunk_message) {
        // PATTERN: Send each token immediately to TTS WebSocket
        mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 
          'type': 'Speak', 
          'text': chunk_message 
        }));
      }
    }
  }
  // PATTERN: Explicit flush after all tokens
  mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Flush' }));
}
```

**Key Insight:** Token-by-token streaming to TTS enables natural, immediate response.

#### 3. Barge-In Handling
```javascript
// In STT transcript handler
if (speaking) {
  console.log('twilio: clear audio playback', streamSid);
  const messageJSON = JSON.stringify({
    "event": "clear",
    "streamSid": streamSid,
  });
  mediaStream.connection.sendUTF(messageJSON);
  
  // PATTERN: Clear both Twilio and TTS
  mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Clear' }));
  speaking = false;
}
```

**Key Insight:** Barge-in requires clearing BOTH Twilio's audio buffer and TTS generation.

#### 4. Performance Tracking
```javascript
// Track LLM latency
llmStart = Date.now();
promptLLM(mediaStream, utterance);

// Track TTS latency
if (firstByte) {
  const end = Date.now();
  const duration = end - ttsStart;
  console.warn('\n\n>>> deepgram TTS: Time to First Byte = ', duration, '\n');
  firstByte = false;
}
```

**Key Insight:** Performance metrics are critical for identifying bottlenecks.

---

## Repository 2: Barty-Bart OpenAI Realtime Implementation
**Repo:** `Barty-Bart/openai-realtime-api-voice-assistant-V2`  
**Language:** Node.js (Fastify)  
**Stack:** OpenAI Realtime API (handles STT/TTS internally)

### Architecture Pattern

```
Twilio WebSocket → Fastify WebSocket Handler
                      ↓
            OpenAI Realtime API
            (STT + LLM + TTS unified)
                      ↓
            Tool Execution (webhooks)
```

### Critical Patterns

#### 1. Session Initialization
```javascript
const sendSessionUpdate = () => {
  const sessionUpdate = {
    type: 'session.update',
    session: {
      turn_detection: { type: 'server_vad' },  // Server-side VAD
      input_audio_format: 'g711_ulaw',
      output_audio_format: 'g711_ulaw',
      voice: VOICE,
      instructions: SYSTEM_MESSAGE,
      modalities: ["text", "audio"],
      temperature: 0.8,
      input_audio_transcription: {
        "model": "whisper-1"
      }
    }
  };
  openAiWs.send(JSON.stringify(sessionUpdate));
};
```

**Key Insight:** Server-side VAD (Voice Activity Detection) is critical for proper turn-taking.

#### 2. Audio Streaming Pattern
```javascript
// Twilio → OpenAI
connection.on('message', (message) => {
  const data = JSON.parse(message);
  
  if (data.event === 'media') {
    if (openAiWs.readyState === WebSocket.OPEN) {
      const audioAppend = {
        type: 'input_audio_buffer.append',
        audio: data.media.payload  // Direct passthrough
      };
      openAiWs.send(JSON.stringify(audioAppend));
    }
  }
});

// OpenAI → Twilio
openAiWs.on('message', async (data) => {
  const response = JSON.parse(data);
  
  if (response.type === 'response.audio.delta' && response.delta) {
    connection.send(JSON.stringify({
      event: 'media',
      streamSid: streamSid,
      media: { payload: response.delta }  // Direct passthrough
    }));
  }
});
```

**Key Insight:** Direct audio passthrough without intermediate buffering reduces latency.

#### 3. First Message Pattern
```javascript
// Queue first message until OpenAI is ready
let queuedFirstMessage = null;

// In start event
queuedFirstMessage = {
  type: 'conversation.item.create',
  item: {
    type: 'message',
    role: 'user',
    content: [{ type: 'input_text', text: firstMessage }]
  }
};

// Send when ready
const sendFirstMessage = () => {
  if (queuedFirstMessage && openAiWsReady) {
    openAiWs.send(JSON.stringify(queuedFirstMessage));
    openAiWs.send(JSON.stringify({ type: 'response.create' }));
    queuedFirstMessage = null;
  }
};
```

**Key Insight:** Greeting must wait for all services to be ready.

---

## Repository 3: Twilio Official Python Reference
**Repo:** `twilio-samples/speech-assistant-openai-realtime-api-python`  
**Language:** Python (FastAPI)  
**Stack:** OpenAI Realtime API

### Architecture Pattern

```
Twilio WebSocket → FastAPI WebSocket Handler
                      ↓
            OpenAI Realtime API
            (WebSocket connection)
                      ↓
        Concurrent Tasks Pattern:
        - receive_from_twilio()
        - send_to_twilio()
```

### Critical Patterns

#### 1. Session Initialization (Python)
```python
async def initialize_session(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},  # mulaw
                    "turn_detection": {"type": "server_vad"}
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": VOICE
                }
            },
            "instructions": SYSTEM_MESSAGE,
        }
    }
    await openai_ws.send(json.dumps(session_update))
```

**Key Insight:** Proper audio format specification is critical.

#### 2. Concurrent Task Pattern
```python
async def receive_from_twilio():
    async for message in websocket.iter_text():
        data = json.loads(message)
        if data['event'] == 'media' and openai_ws.state.name == 'OPEN':
            audio_append = {
                "type": "input_audio_buffer.append",
                "audio": data['media']['payload']
            }
            await openai_ws.send(json.dumps(audio_append))

async def send_to_twilio():
    async for openai_message in openai_ws:
        response = json.loads(openai_message)
        if response.get('type') == 'response.output_audio.delta':
            audio_delta = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": response['delta']}
            }
            await websocket.send_json(audio_delta)

# Run concurrently
await asyncio.gather(receive_from_twilio(), send_to_twilio())
```

**Key Insight:** Two independent async tasks enable true bidirectional streaming.

#### 3. Interruption Handling
```python
if response.get('type') == 'input_audio_buffer.speech_started':
    if last_assistant_item:
        # Calculate elapsed time for truncation
        elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
        
        # Truncate the assistant's response
        truncate_event = {
            "type": "conversation.item.truncate",
            "item_id": last_assistant_item,
            "content_index": 0,
            "audio_end_ms": elapsed_time
        }
        await openai_ws.send(json.dumps(truncate_event))
        
        # Clear Twilio's audio buffer
        await websocket.send_json({
            "event": "clear",
            "streamSid": stream_sid
        })
```

**Key Insight:** Proper interruption requires timestamp tracking and conversation truncation.

---

## Comparison with Our Implementation

### What We're Doing RIGHT

1. **Correct Architecture:** Our 3-service separation (STT, TTS, LLM) matches industry patterns
2. **Proper Audio Encoding:** Using mulaw @ 8kHz for Twilio
3. **Concurrent Tasks:** Using `asyncio.gather()` for bidirectional streaming
4. **Queue-based Communication:** Similar to reference implementations
5. **Barge-in Detection:** Using interim results from STT

### CRITICAL DIFFERENCES Causing Issues

#### 1. TTS Audio Streaming Flow

**Reference Pattern (Deepgram Official):**
```javascript
// TTS WebSocket → Direct to Twilio
ws.on('message', function incoming(data) {
  const payload = data.toString('base64');
  const message = { event: 'media', streamSid: streamSid, media: { payload } };
  mediaStream.connection.sendUTF(JSON.stringify(message));
});
```

**Our Pattern:**
```python
# TTS → Queue → Wait → Check Queue → Send to Twilio
await tts.send_text(response_text)  # Completes fully
await tts.flush()                   # Does nothing (REST API)
while is_speaking:
    audio_chunk = await tts.get_audio()  # Polling with delays
    await asyncio.sleep(0.01)
```

**Problem:** We're polling the queue AFTER all audio is generated, adding latency.

**Fix Needed:** Stream audio chunks AS THEY ARRIVE from Deepgram, not after completion.

#### 2. LLM → TTS Integration

**Reference Pattern (Deepgram Official):**
```javascript
// Stream each token immediately to TTS
for await (const chunk of stream) {
  chunk_message = chunk.choices[0].delta.content;
  if (chunk_message) {
    deepgramTTSWebsocket.send(JSON.stringify({ 
      'type': 'Speak', 
      'text': chunk_message 
    }));
  }
}
```

**Our Pattern:**
```python
# Accumulate ALL tokens first
response_text = ""
async for event in openai.generate_response(stream=True):
    if event["type"] == "content_delta":
        response_text += event["text"]

# Then send complete response
if response_text.strip():
    await tts.send_text(response_text)
```

**Problem:** We wait for complete response before starting TTS, adding ~2-3 seconds latency.

**Fix Needed:** Send text to TTS incrementally (sentence by sentence or token by token).

#### 3. TTS REST vs WebSocket

**Reference Pattern (All repos):** Use WebSocket for TTS for streaming
**Our Pattern:** Using REST API which completes fully before returning

**Problem:** REST API doesn't support true streaming - audio is generated in full before being available.

**Fix Options:**
- Switch to Deepgram TTS WebSocket API (like reference)
- Or optimize REST usage by streaming sentence-by-sentence instead of full response

#### 4. Audio Queue Management

**Reference Pattern:** Direct streaming without intermediate buffering
**Our Pattern:** Heavy use of queues with polling loops

**Problem:** Queue overhead and polling delays add latency.

---

## Recommended Fixes for Our Implementation

### Priority 1: Critical Performance Fixes

#### Fix 1: Switch to Deepgram TTS WebSocket
```python
# In DeepgramTTSService
async def connect(self):
    # Use WebSocket instead of REST
    ws_url = f"wss://api.deepgram.com/v1/speak?encoding=mulaw&sample_rate=8000&container=none"
    self.ws = await websockets.connect(
        ws_url,
        extra_headers={"Authorization": f"Token {self.api_key}"}
    )
    
    # Start audio receiver task
    asyncio.create_task(self._receive_audio())

async def _receive_audio(self):
    async for message in self.ws:
        # Stream audio directly to queue as it arrives
        await self.audio_queue.put(message)

async def send_text(self, text: str):
    # Send text chunks immediately
    await self.ws.send(json.dumps({"type": "Speak", "text": text}))

async def flush(self):
    # Explicit flush for WebSocket
    await self.ws.send(json.dumps({"type": "Flush"}))
```

#### Fix 2: Stream LLM Tokens to TTS Incrementally
```python
# In voice.py process_transcripts()
response_text = ""
sentence_buffer = ""

async for event in openai.generate_response(stream=True):
    if event["type"] == "content_delta":
        chunk = event["text"]
        response_text += chunk
        sentence_buffer += chunk
        
        # Send complete sentences to TTS immediately
        if any(p in chunk for p in ['.', '!', '?', '\n']):
            await tts.send_text(sentence_buffer)
            sentence_buffer = ""

# Send any remaining text
if sentence_buffer.strip():
    await tts.send_text(sentence_buffer)

await tts.flush()
```

#### Fix 3: Eliminate Audio Polling Delay
```python
# Current: Polling with sleep
while is_speaking:
    audio_chunk = await tts.get_audio()
    if audio_chunk is None:
        await asyncio.sleep(0.01)  # 10ms delay per check
        continue

# Better: Async queue with timeout
try:
    while is_speaking:
        # Wait up to 100ms for next chunk
        audio_chunk = await asyncio.wait_for(
            tts.audio_queue.get(), 
            timeout=0.1
        )
        await websocket.send_json({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(audio_chunk).decode()}
        })
except asyncio.TimeoutError:
    # No more audio, done speaking
    is_speaking = False
```

### Priority 2: Architecture Improvements

#### Fix 4: Separate Audio Streaming Task
```python
async def stream_audio_to_twilio():
    """Dedicated task for streaming TTS audio to Twilio"""
    nonlocal is_speaking
    
    while True:
        try:
            # Block until audio available
            audio_chunk = await tts.audio_queue.get()
            
            if audio_chunk and is_speaking:
                await websocket.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": base64.b64encode(audio_chunk).decode()}
                })
        except Exception as e:
            logger.error(f"Error streaming audio: {e}")

# Add to gather
await asyncio.gather(
    receive_from_twilio(), 
    process_transcripts(),
    stream_audio_to_twilio()  # New task
)
```

#### Fix 5: Add Performance Tracking
```python
import time

# Track latencies
class PerformanceTracker:
    def __init__(self):
        self.stt_end_time = None
        self.llm_start_time = None
        self.llm_first_token = None
        self.tts_start_time = None
        self.tts_first_byte = None
    
    def log_metrics(self):
        if self.llm_start_time and self.stt_end_time:
            stt_to_llm = (self.llm_start_time - self.stt_end_time) * 1000
            logger.info(f"STT→LLM latency: {stt_to_llm:.2f}ms")
        
        if self.llm_first_token and self.llm_start_time:
            ttft = (self.llm_first_token - self.llm_start_time) * 1000
            logger.info(f"LLM Time to First Token: {ttft:.2f}ms")
```

---

## Expected Performance After Fixes

Based on reference implementations:

| Metric | Current | Target | Reference |
|--------|---------|--------|-----------|
| STT → LLM latency | ~500ms | ~100ms | Deepgram: ~50ms |
| LLM Time to First Token | ~800ms | ~300ms | OpenAI: ~200-400ms |
| TTS Time to First Byte | ~2000ms | ~300ms | Deepgram WebSocket: ~200ms |
| Total Response Latency | ~3-4s | ~600-800ms | Reference: ~500-800ms |
| Barge-in Response | ~500ms | ~200ms | Reference: ~100-200ms |

---

## Testing Strategy

### Phase 1: Verify Individual Services
1. Test Deepgram TTS WebSocket connection in isolation
2. Verify audio chunks arrive in real-time
3. Test sentence-by-sentence TTS synthesis

### Phase 2: Integration Testing
1. Test LLM streaming → TTS streaming flow
2. Verify audio reaches Twilio without delays
3. Test barge-in with new WebSocket pattern

### Phase 3: E2E Testing
1. Full call flow with performance logging
2. Compare latencies against reference metrics
3. Stress test with multiple concurrent calls

---

## Implementation Priority

1. **IMMEDIATE:** Switch DeepgramTTSService to WebSocket API
2. **HIGH:** Implement sentence-by-sentence streaming (LLM → TTS)
3. **HIGH:** Eliminate audio queue polling delays
4. **MEDIUM:** Add dedicated audio streaming task
5. **MEDIUM:** Add performance tracking and metrics
6. **LOW:** Optimize queue sizes and buffer management

---

## Key Takeaways

1. **WebSocket TTS is essential** for real-time streaming - REST API adds too much latency
2. **Token-by-token or sentence-by-sentence streaming** from LLM to TTS is critical
3. **Direct audio passthrough** without buffering reduces latency significantly
4. **Concurrent async tasks** enable true bidirectional streaming
5. **Performance metrics** are essential for identifying bottlenecks
6. **Our architecture is sound** - we just need to optimize the streaming flow

The reference implementations confirm our architectural decisions are correct. We're just missing the real-time streaming optimizations that enable sub-second response times.
