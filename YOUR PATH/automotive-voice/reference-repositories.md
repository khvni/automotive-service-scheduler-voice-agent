# Reference Repositories - Code Snippets & Inspiration

## Overview
These repositories provide production-ready code patterns that can be directly adapted for our automotive voice agent. Each repo solves specific problems we'll encounter.

---

## 1. twilio-samples/speech-assistant-openai-realtime-api-python
**URL:** https://github.com/twilio-samples/speech-assistant-openai-realtime-api-python

**Primary Use Cases:**
- **Feature 8:** Main Voice WebSocket Handler
- **Feature 9:** Twilio Webhooks & Call Routing

**Key Code to Reference:**
- `main.py` (lines 1-300) - Complete FastAPI + WebSocket implementation
- WebSocket connection handling between Twilio and OpenAI
- Interruption/barge-in handling pattern (lines 141-168)
- TwiML response generation for incoming calls
- Session state management (stream_sid, call_sid tracking)
- Mark queue pattern for audio synchronization

**What to Copy:**
```python
# Twilio Media Stream event handling
if data['event'] == 'media':
    audio_append = {
        "type": "input_audio_buffer.append",
        "audio": data['media']['payload']
    }

# Interruption handling
async def handle_speech_started_event():
    if mark_queue and response_start_timestamp_twilio is not None:
        elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
        # Truncate audio...
```

**Tech Stack:** Python, FastAPI, websockets, asyncio

---

## 2. twilio-samples/speech-assistant-openai-realtime-api-node
**URL:** https://github.com/twilio-samples/speech-assistant-openai-realtime-api-node

**Primary Use Cases:**
- **Feature 8:** WebSocket handler (Node.js reference for comparison)

**Key Code to Reference:**
- `index.js` - Same patterns as Python version but in Node.js
- Event-driven architecture using EventEmitter
- Useful for understanding Twilio Media Stream protocol

**Note:** We're using Python, but this shows alternative implementation patterns.

---

## 3. openai/openai-realtime-twilio-demo
**URL:** https://github.com/openai/openai-realtime-twilio-demo

**Primary Use Cases:**
- **Feature 5:** OpenAI integration patterns (though we're NOT using Realtime API)

**Key Code to Reference:**
- `websocket-server/` - WebSocket server architecture
- Session management patterns
- Error handling for WebSocket connections

**Important Note:** We are NOT using OpenAI Realtime API. Only reference the WebSocket architecture patterns, not the OpenAI-specific code.

---

## 4. deepgram/deepgram-twilio-streaming-voice-agent
**URL:** https://github.com/deepgram/deepgram-twilio-streaming-voice-agent

**Primary Use Cases:**
- **Feature 3:** Deepgram STT Integration ⭐⭐⭐
- **Feature 4:** Deepgram TTS Integration ⭐⭐⭐
- **Feature 8:** Barge-in detection
- **Feature 5:** LLM integration (uses OpenAI GPT-3.5-turbo)

**Key Code to Reference:**
- `server.js` (lines 1-350) - **MOST IMPORTANT REFERENCE**

**Deepgram STT Setup (lines 230-290):**
```javascript
const deepgram = deepgramClient.listen.live({
    model: "nova-2-phonecall",  // ← Use this model
    language: "en",
    smart_format: true,
    encoding: "mulaw",          // ← Phone audio format
    sample_rate: 8000,          // ← Phone sample rate
    channels: 1,
    interim_results: true,      // ← CRITICAL for barge-in
    endpointing: 300,           // ← Speech detection
    utterance_end_ms: 1000
});
```

**Deepgram TTS Setup (lines 165-210):**
```javascript
const deepgramTTSWebsocketURL = 'wss://api.deepgram.com/v1/speak?encoding=mulaw&sample_rate=8000&container=none';

// Streaming TTS
deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Speak', 'text': chunk_message }));
deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Flush' }));
```

**Barge-in Detection (line 310):**
```javascript
// Interim results trigger barge-in
if (transcript !== "" && !data.is_final) {
    if (speaking) {
        // Clear Twilio audio playback
        const messageJSON = JSON.stringify({
            "event": "clear",
            "streamSid": streamSid,
        });
        mediaStream.connection.sendUTF(messageJSON);
        deepgramTTSWebsocket.send(JSON.stringify({ 'type': 'Clear' }));
        speaking = false;
    }
}
```

**LLM Integration (lines 137-160):**
```javascript
// Streaming LLM response
const stream = openai.beta.chat.completions.stream({
    model: 'gpt-3.5-turbo',
    stream: true,
    messages: [...]
});

for await (const chunk of stream) {
    chunk_message = chunk.choices[0].delta.content;
    if (chunk_message) {
        // Send to TTS immediately (streaming)
        mediaStream.deepgramTTSWebsocket.send(
            JSON.stringify({ 'type': 'Speak', 'text': chunk_message })
        );
    }
}
```

**Performance Timing (lines 183-190):**
```javascript
// Time-to-first-byte tracking
if (firstByte) {
    const end = Date.now();
    const duration = end - ttsStart;
    console.warn('>>> deepgram TTS: Time to First Byte = ', duration);
    firstByte = false;
}
```

**What to Copy:**
- Deepgram STT/TTS configuration (translate to Python)
- Barge-in detection logic
- Streaming TTS pattern
- Performance timing patterns

**Tech Stack:** Node.js, but patterns translate to Python

---

## 5. duohub-ai/google-calendar-voice-agent
**URL:** https://github.com/duohub-ai/google-calendar-voice-agent

**Primary Use Cases:**
- **Feature 7:** Google Calendar Integration ⭐⭐⭐
- **Feature 5:** LLM function calling patterns
- **Feature 10:** Conversation flow design

**Key Code to Reference:**

**bot.py (lines 1-280):**
- Pipecat framework usage (optional reference, we're using custom)
- Function calling schema definition (lines 42-130)
- System prompt engineering (lines 172-190)

**calendar_service.py (CRITICAL - lines 1-350):**

**OAuth2 Setup (lines 82-95):**
```python
def get_calendar_service(self):
    creds = Credentials(
        token=None,
        refresh_token=self.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=self.client_id,
        client_secret=self.client_secret,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    service = build('calendar', 'v3', credentials=creds)
    return service
```

**Get Free Availability (lines 145-180):**
```python
async def get_free_availability(self, start_time_str, end_time_str):
    service = self.get_calendar_service()

    start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=self.aedt)
    end_time = datetime.fromisoformat(end_time_str).replace(tzinfo=self.aedt)

    # Freebusy query
    body = {
        'timeMin': start_time_utc.isoformat(),
        'timeMax': end_time_utc.isoformat(),
        'items': [{'id': 'primary'}]
    }

    freebusy_response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.freebusy().query(body=body).execute()
    )

    # Calculate free slots from busy periods
    free_slots = self._process_freebusy_response(freebusy_response, start_time, end_time)
```

**Create Calendar Event (lines 112-144):**
```python
async def create_calendar_event(self, title, start_time_str, description='', attendees=None):
    service = self.get_calendar_service()

    start_time = self._parse_start_time(start_time_str)
    end_time = start_time + timedelta(minutes=30)

    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_time_utc.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time_utc.isoformat(),
            'timeZone': 'UTC',
        },
    }

    event = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
    )
```

**Update/Cancel Events (lines 182-250):**
```python
async def update_calendar_event(self, event_id, title=None, description=None, start_time_str=None):
    service = self.get_calendar_service()

    # Get existing event
    event = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.events().get(calendarId='primary', eventId=event_id).execute()
    )

    # Update fields
    if title:
        event['summary'] = title
    # ... update other fields

    updated_event = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=event,
            sendUpdates='all'
        ).execute()
    )
```

**Timezone Handling (lines 255-265):**
```python
def _parse_start_time(self, start_time_str):
    now = datetime.now(self.aedt)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "this afternoon" in start_time_str.lower():
        return today.replace(hour=14, minute=0)
    else:
        return datetime.fromisoformat(start_time_str).replace(tzinfo=self.aedt)
```

**What to Copy:**
- Entire calendar_service.py (translate Pipecat-specific parts to our architecture)
- OAuth2 refresh token pattern
- Async wrapper for blocking Google API calls
- Freebusy calculation logic
- Timezone handling

**Tech Stack:** Python, Pipecat (we'll adapt without Pipecat)

---

## 6. Barty-Bart/openai-realtime-api-voice-assistant-V2
**URL:** https://github.com/Barty-Bart/openai-realtime-api-voice-assistant-V2

**Primary Use Cases:**
- **Feature 5:** Function calling patterns ⭐⭐
- **Feature 8:** Session management
- **Feature 9:** Webhook integration patterns

**Key Code to Reference:**

**index.js (lines 1-700):**

**Session Management (lines 30-40):**
```javascript
const sessions = new Map();

let session = {
    transcript: '',
    streamSid: null,
    callerNumber: callerNumber,
    callDetails: twilioParams,
    firstMessage: firstMessage
};
sessions.set(sessionId, session);
```

**Function Calling Definition (lines 237-280):**
```javascript
tools: [
    {
        type: "function",
        name: "question_and_answer",
        description: "Get answers to customer questions about automotive services",
        parameters: {
            type: "object",
            properties: {
                "question": { "type": "string" }
            },
            required: ["question"]
        }
    },
    {
        type: "function",
        name: "book_tow",
        description: "Book a tow service for a customer",
        parameters: {
            type: "object",
            properties: {
                "address": { "type": "string" }
            },
            required: ["address"]
        }
    }
]
```

**Inline Function Execution (lines 360-430):**
```javascript
if (response.type === 'response.function_call_arguments.done') {
    const functionName = response.name;
    const args = JSON.parse(response.arguments);

    if (functionName === 'question_and_answer') {
        const question = args.question;

        // Inline webhook call
        const webhookResponse = await sendToWebhook({
            route: "3",
            data1: question,
            data2: threadId
        });

        const parsedResponse = JSON.parse(webhookResponse);
        const answerMessage = parsedResponse.message;

        // Return result to OpenAI
        const functionOutputEvent = {
            type: "conversation.item.create",
            item: {
                type: "function_call_output",
                role: "system",
                output: answerMessage,
            }
        };
        openAiWs.send(JSON.stringify(functionOutputEvent));
    }
}
```

**Transcript Logging (lines 620-650):**
```javascript
// Log agent response
if (response.type === 'response.done') {
    const agentMessage = response.response.output[0]?.content?.find(
        content => content.transcript
    )?.transcript || 'Agent message not found';
    session.transcript += `Agent: ${agentMessage}\n`;
}

// Log user transcription
if (response.type === 'conversation.item.input_audio_transcription.completed') {
    const userMessage = response.transcript.trim();
    session.transcript += `User: ${userMessage}\n`;
}
```

**What to Copy:**
- Session management pattern (translate to Redis)
- Function calling schema structure
- Inline function execution pattern
- Transcript logging approach

**Important Note:** This uses OpenAI Realtime API which we're NOT using. Only copy the session management and function calling patterns.

**Tech Stack:** Node.js, Fastify

---

## 7. mjunaidca/appointment-agent
**URL:** https://github.com/mjunaidca/appointment-agent

**Primary Use Cases:**
- **Feature 10:** Conversation flow architecture
- **Feature 12:** Testing patterns

**Key Code to Reference:**
- `src/` - LangGraph-based agent architecture
- `pyproject.toml` - Dependency management example
- Testing structure (if available in repo)

**Note:** Uses LangGraph which we're not using, but good for understanding state machine patterns.

**Tech Stack:** Python, LangGraph

---

## 8. twentyhq/twenty
**URL:** https://github.com/twentyhq/twenty

**Primary Use Cases:**
- **Context only** - We decided NOT to use Twenty CRM
- Reference if building admin UI (Feature 14)

**Key Code to Reference:**
- `packages/` - Monorepo structure (if considering future expansion)
- GraphQL schema patterns (if adding API later)

**Note:** We're using custom Postgres + SQLAlchemy instead. Only reference for UI inspiration.

**Tech Stack:** TypeScript, NestJS, React, GraphQL

---

## Additional GitHub Resources Referenced

### 9. Google Calendar API Quickstart (Python)
**URL:** https://developers.google.com/workspace/calendar/api/quickstart/python

**Use Case:** Feature 7 - OAuth2 setup for Google Calendar

**What to Copy:**
- OAuth2 flow setup
- credentials.json structure
- Token refresh patterns

---

## Repository Usage Guide

### When Starting Each Feature:

**Feature 3 (Deepgram STT):**
```bash
Read: deepgram/deepgram-twilio-streaming-voice-agent
Focus on: server.js lines 230-290 (STT config)
          server.js lines 298-330 (transcript handling)
```

**Feature 4 (Deepgram TTS):**
```bash
Read: deepgram/deepgram-twilio-streaming-voice-agent
Focus on: server.js lines 165-210 (TTS WebSocket)
          server.js lines 183-190 (performance timing)
```

**Feature 5 (GPT-4o):**
```bash
Read: deepgram/deepgram-twilio-streaming-voice-agent (LLM integration)
      Barty-Bart/openai-realtime-api-voice-assistant-V2 (function calling)
Focus on: deepgram server.js lines 137-160 (streaming LLM)
          Barty-Bart index.js lines 237-280 (tool definitions)
          Barty-Bart index.js lines 360-430 (inline execution)
```

**Feature 7 (Google Calendar):**
```bash
Read: duohub-ai/google-calendar-voice-agent
Focus on: calendar_service.py (entire file - lines 1-350)
          bot.py lines 42-130 (tool definitions)
COPY DIRECTLY: OAuth2 setup, freebusy logic, event CRUD operations
```

**Feature 8 (WebSocket Handler):**
```bash
Read: twilio-samples/speech-assistant-openai-realtime-api-python
      deepgram/deepgram-twilio-streaming-voice-agent
Focus on: twilio-samples main.py lines 1-300 (full pipeline)
          deepgram server.js lines 310-320 (barge-in)
COPY DIRECTLY: Event handling, interruption logic
```

**Feature 9 (Webhooks):**
```bash
Read: twilio-samples/speech-assistant-openai-realtime-api-python
Focus on: main.py lines 38-63 (incoming call handler)
COPY DIRECTLY: TwiML response generation
```

---

## How to Use GitHub MCP

When implementing each feature, use the GitHub MCP to:

```python
# Example: Read Deepgram STT implementation
mcp__github__get_file_contents(
    owner="deepgram",
    repo="deepgram-twilio-streaming-voice-agent",
    path="server.js"
)

# Example: Read Google Calendar service
mcp__github__get_file_contents(
    owner="duohub-ai",
    repo="google-calendar-voice-agent",
    path="calendar_service.py"
)

# Example: Read Twilio webhook handler
mcp__github__get_file_contents(
    owner="twilio-samples",
    repo="speech-assistant-openai-realtime-api-python",
    path="main.py"
)
```

---

## Translation Notes

### Node.js → Python Patterns

**WebSocket:**
```javascript
// Node.js
const ws = new WebSocket(url, options);
ws.on('message', handler);
```
```python
# Python
async with websockets.connect(url, extra_headers=headers) as ws:
    async for message in ws:
        await handler(message)
```

**Async Executor (Google API):**
```javascript
// Node.js (blocking call)
const result = service.events().insert(...).execute();
```
```python
# Python (async wrapper)
result = await asyncio.get_event_loop().run_in_executor(
    None,
    lambda: service.events().insert(...).execute()
)
```

**JSON Streaming:**
```javascript
// Node.js
for await (const chunk of stream) {
    process(chunk);
}
```
```python
# Python
async for chunk in stream:
    await process(chunk)
```

---

## Priority Repositories (Must Read)

1. **deepgram/deepgram-twilio-streaming-voice-agent** ⭐⭐⭐
   - Single most important reference
   - Complete STT → LLM → TTS pipeline
   - Barge-in detection
   - Performance optimization patterns

2. **duohub-ai/google-calendar-voice-agent** ⭐⭐⭐
   - Copy calendar_service.py almost entirely
   - Production-ready Google Calendar integration

3. **twilio-samples/speech-assistant-openai-realtime-api-python** ⭐⭐⭐
   - WebSocket handler architecture
   - Twilio Media Stream event handling

4. **Barty-Bart/openai-realtime-api-voice-assistant-V2** ⭐⭐
   - Function calling patterns
   - Session management

---

**Last Updated:** 2025-01-12
**Status:** Reference guide complete