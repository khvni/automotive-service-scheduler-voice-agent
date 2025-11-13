# Deepgram + Twilio Voice Agent Integration Analysis

## Date: 2025-11-13

## Executive Summary

Analyzed official Deepgram repositories and reference implementations to understand the correct architecture for building Twilio + Deepgram voice agents. The key finding is that there are **two distinct approaches**:

1. **Manual STT + LLM + TTS Pipeline** (Node.js reference: deepgram-twilio-streaming-voice-agent)
2. **Deepgram Voice Agent API** (Python reference: sts-twilio)

Our current implementation uses approach #1 (manual pipeline). This analysis provides the exact patterns needed to fix our implementation.

---

## Repository Analysis

### 1. deepgram/deepgram-twilio-streaming-voice-agent (PRIMARY REFERENCE)

**Language:** Node.js (but patterns apply to Python)
**SDK Version:** @deepgram/sdk v3.4.4
**Architecture:** Manual STT → LLM → TTS pipeline

#### Key Components:

**A. Deepgram STT Setup (Speech-to-Text)**

```javascript
// Imports
const { createClient, LiveTranscriptionEvents } = require("@deepgram/sdk");

// Client creation
const deepgramClient = createClient(process.env.DEEPGRAM_API_KEY);

// STT connection setup
const deepgram = deepgramClient.listen.live({
    model: "nova-2-phonecall",
    language: "en",
    smart_format: true,
    encoding: "mulaw",
    sample_rate: 8000,
    channels: 1,
    multichannel: false,
    no_delay: true,
    interim_results: true,
    endpointing: 300,
    utterance_end_ms: 1000
});

// Event handlers
deepgram.addListener(LiveTranscriptionEvents.Open, async () => {
    console.log("deepgram STT: Connected");
});

deepgram.addListener(LiveTranscriptionEvents.Transcript, (data) => {
    const transcript = data.channel.alternatives[0].transcript;
    if (data.is_final) {
        if (data.speech_final) {
            // Send to LLM
            promptLLM(mediaStream, utterance);
        }
    } else {
        // Handle interim results for barge-in detection
        if (speaking) {
            // Clear Twilio audio playback
            // Stop TTS generation
        }
    }
});

deepgram.addListener(LiveTranscriptionEvents.UtteranceEnd, (data) => {
    // Fallback for speech_final
});
```

**Python SDK Equivalent (from deepgram-python-sdk docs):**

```python
from deepgram import DeepgramClient, LiveTranscriptionEvents

client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

# Create live transcription connection
connection = client.listen.live.connect(
    model="nova-2-phonecall",
    language="en",
    smart_format=True,
    encoding="mulaw",
    sample_rate=8000,
    channels=1,
    no_delay=True,
    interim_results=True,
    endpointing=300,
    utterance_end_ms=1000
)

# Event handlers
def on_message(self, result, **kwargs):
    sentence = result.channel.alternatives[0].transcript
    if len(sentence) > 0:
        if result.is_final:
            if result.speech_final:
                # Send to LLM
                pass
            else:
                # Partial final
                pass
        else:
            # Interim - check for barge-in
            if self.speaking:
                # Clear audio
                pass

connection.on(LiveTranscriptionEvents.Transcript, on_message)
```

**B. Deepgram TTS Setup (Text-to-Speech)**

**CRITICAL FINDING:** They use WebSocket API, NOT REST API for TTS

```javascript
// TTS WebSocket connection
const WebSocket = require('ws');
const deepgramTTSWebsocketURL = 'wss://api.deepgram.com/v1/speak?encoding=mulaw&sample_rate=8000&container=none';

const setupDeepgramWebsocket = (mediaStream) => {
    const options = {
        headers: {
            Authorization: `Token ${process.env.DEEPGRAM_API_KEY}`
        }
    };
    const ws = new WebSocket(deepgramTTSWebsocketURL, options);

    ws.on('open', function open() {
        console.log('deepgram TTS: Connected');
    });

    ws.on('message', function incoming(data) {
        if (speaking) {
            // Check if JSON message (metadata) or binary (audio)
            try {
                let json = JSON.parse(data.toString());
                console.log('deepgram TTS: ', data.toString());
                return;
            } catch (e) {
                // Binary audio data
            }
            
            // Convert to base64 for Twilio
            const payload = data.toString('base64');
            const message = {
                event: 'media',
                streamSid: streamSid,
                media: {
                    payload,
                },
            };
            mediaStream.connection.sendUTF(JSON.stringify(message));
        }
    });

    return ws;
};

// Sending text to TTS (streaming from LLM)
for await (const chunk of stream) {
    chunk_message = chunk.choices[0].delta.content;
    if (chunk_message) {
        // Send each token to TTS immediately
        mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 
            'type': 'Speak', 
            'text': chunk_message 
        }));
    }
}
// Signal end of text
mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Flush' }));
```

**Python SDK Equivalent (from websockets-reference.md):**

```python
from deepgram import DeepgramClient
from deepgram.core.events import EventType

client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

# Create TTS WebSocket connection
tts_connection = client.speak.v1.connect(
    model="aura-2-asteria-en",  # or other models
    encoding="mulaw",
    sample_rate=8000
)

def on_audio_message(message):
    if isinstance(message, bytes):
        # Audio data - convert to base64 for Twilio
        payload = base64.b64encode(message).decode('ascii')
        twilio_message = {
            'event': 'media',
            'streamSid': stream_sid,
            'media': {'payload': payload}
        }
        twilio_ws.send(json.dumps(twilio_message))
    else:
        # Metadata message
        print(f"TTS event: {message.type}")

tts_connection.on(EventType.MESSAGE, on_audio_message)
tts_connection.start_listening()

# Send text to TTS
from deepgram.extensions.types.sockets import SpeakV1TextMessage
tts_connection.send_text(SpeakV1TextMessage(text="Hello, world!"))

# Flush and close
from deepgram.extensions.types.sockets import SpeakV1ControlMessage
tts_connection.send_control(SpeakV1ControlMessage(type="Flush"))
```

**C. Twilio Media Stream Handling**

```javascript
processMessage(message) {
    if (message.type === "utf8") {
        let data = JSON.parse(message.utf8Data);
        
        if (data.event === "start") {
            streamSid = data.streamSid;
        }
        
        if (data.event === "media") {
            if (data.media.track == "inbound") {
                // Decode and send to STT
                let rawAudio = Buffer.from(data.media.payload, 'base64');
                this.deepgram.send(rawAudio);
            }
        }
        
        if (data.event === "close") {
            this.close();
        }
    }
}
```

**D. Barge-In Handling**

```javascript
// When interim transcript detected during speaking
if (speaking) {
    console.log('twilio: clear audio playback', streamSid);
    
    // Clear Twilio's audio buffer
    const messageJSON = JSON.stringify({
        "event": "clear",
        "streamSid": streamSid,
    });
    mediaStream.connection.sendUTF(messageJSON);
    
    // Clear TTS queue
    mediaStream.deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Clear' }));
    
    speaking = false;
}
```

---

### 2. deepgram-devs/sts-twilio (Python, Deepgram Voice Agent API)

**Language:** Python
**Architecture:** All-in-one Deepgram Voice Agent API
**Status:** Uses Deepgram's managed agent service (STT + LLM + TTS bundled)

**Key Pattern:**

```python
def sts_connect():
    api_key = os.getenv('DEEPGRAM_API_KEY')
    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws

# Configuration sent once
config_message = {
    "type": "Settings",
    "audio": {
        "input": {
            "encoding": "mulaw",
            "sample_rate": 8000,
        },
        "output": {
            "encoding": "mulaw",
            "sample_rate": 8000,
            "container": "none",
        },
    },
    "agent": {
        "language": "en",
        "listen": {
            "provider": {"type": "deepgram", "model": "nova-3"}
        },
        "think": {
            "provider": {"type": "open_ai", "model": "gpt-4o-mini"},
            "prompt": "You are a helpful AI assistant."
        },
        "speak": {
            "provider": {"type": "deepgram", "model": "aura-2-thalia-en"}
        },
        "greeting": "Hello! How can I help you today?"
    }
}

# Just forward audio back and forth
# Deepgram handles everything
```

**Note:** This is simpler but less flexible. Good for quick prototypes, but our project needs custom LLM logic (Anthropic Claude with tool calling).

---

### 3. Barty-Bart/openai-realtime-api-voice-assistant-V2

**Language:** Node.js
**Architecture:** Uses OpenAI's Realtime API (different from our approach)

**Key Differences:**
- Uses OpenAI's all-in-one realtime API (audio in, audio out)
- Not directly applicable to our Deepgram + Anthropic setup
- Useful for understanding WebSocket patterns and Twilio integration

**Relevant Pattern:**
- How they handle Twilio media streams is similar
- Good reference for session management
- Shows how to queue first message until WS ready

---

## Critical Findings for Our Implementation

### 1. MAJOR BUG: We're Using REST API for TTS

**Current (WRONG):**
```python
# In deepgram_tts.py
response = requests.post(url, headers=headers, json=payload, stream=True)
for chunk in response.iter_content(chunk_size=1024):
    audio_chunks.append(chunk)
```

**Should Be (CORRECT):**
```python
# Use WebSocket API
tts_connection = client.speak.v1.connect(
    model="aura-2-asteria-en",
    encoding="mulaw",
    sample_rate=8000
)

# Stream text chunks to TTS
for text_chunk in llm_response:
    tts_connection.send_text(SpeakV1TextMessage(text=text_chunk))

# Flush
tts_connection.send_control(SpeakV1ControlMessage(type="Flush"))
```

**Why This Matters:**
- REST API returns complete audio file (high latency)
- WebSocket API streams audio chunks as they're generated
- Enables true streaming: LLM token → TTS chunk → Twilio → User
- Much faster time-to-first-byte

### 2. Deepgram SDK Imports (Python)

**Current imports needed:**
```python
from deepgram import DeepgramClient, LiveTranscriptionEvents
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import (
    SpeakV1TextMessage,
    SpeakV1ControlMessage,
    ListenV1MediaMessage,
    ListenV1ControlMessage
)
```

### 3. STT Configuration for Phone Calls

**Optimal settings for Twilio (8kHz mulaw):**
```python
connection = client.listen.live.connect(
    model="nova-2-phonecall",  # Optimized for phone audio
    language="en",
    smart_format=True,
    encoding="mulaw",
    sample_rate=8000,
    channels=1,
    no_delay=True,
    interim_results=True,
    endpointing=300,
    utterance_end_ms=1000
)
```

### 4. Correct Flow Architecture

```
Twilio Call → FastAPI WebSocket
    ↓
Receive media (base64 mulaw)
    ↓
Decode base64 → raw mulaw bytes
    ↓
Send to Deepgram STT (WebSocket)
    ↓
Get transcript (speech_final=True)
    ↓
Send to Anthropic Claude
    ↓
Stream response tokens
    ↓
Send each token to Deepgram TTS (WebSocket)
    ↓
Receive audio chunks (mulaw bytes)
    ↓
Encode to base64
    ↓
Send to Twilio (media event)
    ↓
User hears audio
```

### 5. Message Format Examples

**Twilio → Our Server:**
```json
{
    "event": "media",
    "streamSid": "MZ...",
    "media": {
        "track": "inbound",
        "chunk": "1",
        "timestamp": "12345",
        "payload": "base64_encoded_mulaw_audio"
    }
}
```

**Our Server → Twilio:**
```json
{
    "event": "media",
    "streamSid": "MZ...",
    "media": {
        "payload": "base64_encoded_mulaw_audio"
    }
}
```

**Clear Buffer (Barge-In):**
```json
{
    "event": "clear",
    "streamSid": "MZ..."
}
```

### 6. SDK Version Requirements

From Node.js reference and Python SDK analysis:
- **Node.js:** @deepgram/sdk@^3.4.4
- **Python:** deepgram-sdk@^5.0.0 (latest, includes WebSocket TTS)

Our current version: `deepgram-sdk==3.8.0`
- **Action Required:** Check if v3.8.0 has WebSocket TTS support
- If not, upgrade to latest v5.x

---

## Recommendations

### Immediate Fixes

1. **Replace REST TTS with WebSocket TTS**
   - File: `/server/app/services/deepgram_tts.py`
   - Switch to `client.speak.v1.connect()` pattern
   - Stream audio chunks as they arrive

2. **Verify SDK Version**
   - Check current version supports WebSocket TTS
   - Upgrade to v5.x if needed

3. **Add Proper Event Handlers**
   - STT: Handle interim_results for barge-in
   - TTS: Handle binary audio chunks
   - Both: Add error handlers

4. **Implement Barge-In**
   - Detect interim transcripts during speaking
   - Send "clear" to Twilio
   - Send "Clear" control to TTS WebSocket

### Architecture Improvements

1. **Connection Management**
   - Keep TTS WebSocket alive per call
   - Don't recreate for each response
   - Reuse within call session

2. **Error Handling**
   - Add WebSocket reconnection logic
   - Handle partial audio gracefully
   - Log all events for debugging

3. **Performance Optimization**
   - Buffer size tuning
   - Async I/O throughout
   - Monitor latency metrics

---

## Code Examples for Our Implementation

### Updated deepgram_tts.py (WebSocket Version)

```python
from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import (
    SpeakV1TextMessage,
    SpeakV1ControlMessage
)
import asyncio
import base64
import os

class DeepgramTTSWebSocket:
    def __init__(self):
        self.client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))
        self.connection = None
        self.audio_queue = asyncio.Queue()
        
    async def connect(self):
        """Establish WebSocket connection to Deepgram TTS"""
        self.connection = self.client.speak.v1.connect(
            model="aura-2-asteria-en",
            encoding="mulaw",
            sample_rate=8000
        )
        
        def on_message(message):
            if isinstance(message, bytes):
                # Audio chunk received
                self.audio_queue.put_nowait(message)
            else:
                print(f"TTS event: {getattr(message, 'type', 'Unknown')}")
        
        def on_error(error):
            print(f"TTS error: {error}")
            
        self.connection.on(EventType.MESSAGE, on_message)
        self.connection.on(EventType.ERROR, on_error)
        
        await self.connection.start_listening()
        
    async def synthesize_stream(self, text_stream):
        """
        Stream text to TTS and yield audio chunks
        
        Args:
            text_stream: Async generator yielding text chunks
            
        Yields:
            bytes: mulaw audio chunks
        """
        async def send_text():
            async for text_chunk in text_stream:
                if text_chunk:
                    await self.connection.send_text(
                        SpeakV1TextMessage(text=text_chunk)
                    )
            # Signal end
            await self.connection.send_control(
                SpeakV1ControlMessage(type="Flush")
            )
        
        # Start sending text
        send_task = asyncio.create_task(send_text())
        
        # Yield audio chunks as they arrive
        while True:
            try:
                audio_chunk = await asyncio.wait_for(
                    self.audio_queue.get(), 
                    timeout=5.0
                )
                yield audio_chunk
            except asyncio.TimeoutError:
                if send_task.done():
                    break
                    
    async def close(self):
        """Close the WebSocket connection"""
        if self.connection:
            await self.connection.send_control(
                SpeakV1ControlMessage(type="Close")
            )
```

### Updated STT Integration

```python
from deepgram import DeepgramClient, LiveTranscriptionEvents

class DeepgramSTTWebSocket:
    def __init__(self, on_transcript, on_barge_in):
        self.client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))
        self.connection = None
        self.on_transcript = on_transcript
        self.on_barge_in = on_barge_in
        self.speaking = False
        self.is_finals = []
        
    async def connect(self):
        """Establish WebSocket connection to Deepgram STT"""
        self.connection = self.client.listen.live.connect(
            model="nova-2-phonecall",
            language="en",
            smart_format=True,
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            no_delay=True,
            interim_results=True,
            endpointing=300,
            utterance_end_ms=1000
        )
        
        def on_message(result, **kwargs):
            transcript = result.channel.alternatives[0].transcript
            if transcript:
                if result.is_final:
                    self.is_finals.append(transcript)
                    if result.speech_final:
                        utterance = " ".join(self.is_finals)
                        self.is_finals = []
                        # Send to LLM
                        asyncio.create_task(self.on_transcript(utterance))
                else:
                    # Interim result - check for barge-in
                    if self.speaking:
                        asyncio.create_task(self.on_barge_in())
                        self.speaking = False
        
        self.connection.on(LiveTranscriptionEvents.Transcript, on_message)
        await self.connection.start()
        
    async def send_audio(self, audio_bytes):
        """Send audio to STT"""
        if self.connection:
            await self.connection.send(audio_bytes)
            
    def set_speaking(self, speaking):
        """Update speaking state for barge-in detection"""
        self.speaking = speaking
```

---

## Conclusion

The primary issue with our implementation is using REST API for TTS instead of WebSocket API. This causes:
- High latency (wait for complete audio generation)
- No streaming (can't start playing while generating)
- Poor user experience

Switching to WebSocket TTS pattern from the official Deepgram reference will enable true streaming and dramatically reduce latency.

**Next Steps:**
1. Verify Deepgram SDK version supports WebSocket TTS
2. Rewrite deepgram_tts.py using WebSocket pattern
3. Update call handler to use streaming TTS
4. Test latency improvements
5. Add barge-in support
