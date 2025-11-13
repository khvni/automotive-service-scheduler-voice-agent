# Feature 5: OpenAI GPT-4o Integration - Planning Complete

## Planning Summary

Completed comprehensive research and planning for Feature 5: OpenAI GPT-4o Integration.

## Research Sources Used

### 1. Reference Repository Analysis
- **Repo:** Barty-Bart/openai-realtime-api-voice-assistant-V2
- **File:** index.js (lines 237-430)
- **Key Insights:**
  - Function calling pattern with inline execution
  - Tool result injection back to LLM
  - Recursive pattern: tool call → execute → inject result → generate verbal response
  - System message structure and conversation guidelines

### 2. OpenAI Python SDK Documentation
- **Source:** Context7 MCP (openai/openai-python)
- **Topics:** Chat completions, streaming, function calling
- **Key Insights:**
  - `client.chat.completions.create()` with `stream=True`
  - Tool calls in streaming: accumulate deltas
  - Message format for tool_calls and tool results
  - AsyncOpenAI for WebSocket compatibility

### 3. Memory Bank Review
- **File:** call-flows-and-scripts.md
- **Key Insights:**
  - Conversation flows for inbound/outbound calls
  - System prompt requirements per scenario
  - Tool usage patterns (lookup → book → confirm)
  - Customer verification protocols

### 4. Existing Codebase Analysis
- **DeepgramSTTService pattern:** Async service with event handlers
- **CRM tools:** Already implemented (lookup_customer, book_appointment, etc.)
- **Configuration:** OpenAI settings already in place

## Key Architecture Decisions

### Decision 1: Standard Chat Completions API (NOT Realtime API)

**Rationale:**
- More control over orchestration (STT → LLM → TTS)
- Better function calling support with structured output
- Proven pattern from reference repo
- Easier token usage tracking
- Conversation history fully under our control

**Trade-offs:**
- Need to handle streaming ourselves
- No built-in audio I/O (but we have Deepgram for that)

### Decision 2: Inline Tool Execution

**Rationale:**
- Lower latency (<300ms vs >500ms with queues)
- Simpler code flow
- Immediate feedback to LLM

**Implementation:**
- When tool_calls detected in stream → execute immediately
- Add tool result to conversation history
- Call OpenAI again to generate verbal response

### Decision 3: Streaming Responses

**Rationale:**
- ~500ms to first token vs ~2s for full response
- Send text chunks to TTS immediately
- Better perceived latency

**Implementation:**
- Use AsyncOpenAI with `stream=True`
- Process content deltas as they arrive
- Accumulate tool call deltas

## Implementation Plan Created

### Document Location
`/Users/khani/Desktop/projs/automotive-voice/feature-5-openai-gpt4o-implementation-plan.md`

### Plan Contents
1. **Architecture Overview** - Data flow diagram with all components
2. **Class Structure** - Complete OpenAIService class with all methods
3. **Tool Schema Design** - 7 tool definitions for function calling
4. **Conversation History Management** - Message format and history window
5. **Streaming Implementation** - Response parsing and routing
6. **Tool Execution Router** - ToolRouter class for handler mapping
7. **System Prompt Engineering** - Dynamic prompts for different scenarios
8. **Integration Points** - How to connect with STT, TTS, WebSocket handler
9. **Token Usage Tracking** - Token counting and conversation trimming
10. **Error Handling** - Retry logic and graceful degradation
11. **Implementation Steps** - 4 phases with detailed tasks
12. **Files to Create/Modify** - Complete file list
13. **Testing Strategy** - Unit, integration, and performance tests
14. **Success Criteria** - Functional, performance, and quality requirements

### Estimated Implementation Time
**Total: 5-7 hours**
- Phase 1: Core OpenAI Service (2-3 hours)
- Phase 2: Tool Definitions & Router (1-2 hours)
- Phase 3: System Prompts (1 hour)
- Phase 4: Testing (1 hour)

## Files to Create

1. **`server/app/services/openai_service.py`** (350 lines)
   - OpenAIService class
   - Methods: set_system_prompt, register_tool, generate_response
   - Streaming response parsing
   - Tool execution logic

2. **`server/app/services/tool_definitions.py`** (200 lines)
   - 7 tool schemas in OpenAI function calling format
   - lookup_customer, get_available_slots, book_appointment, etc.

3. **`server/app/services/tool_router.py`** (250 lines)
   - ToolRouter class
   - Maps function names to Python handlers
   - Database session injection
   - Error handling

4. **`server/app/services/system_prompts.py`** (200 lines)
   - build_system_prompt() function
   - Dynamic prompt generation based on call type
   - Customer/appointment context injection

5. **`scripts/test_openai_service.py`** (150 lines)
   - Unit tests for OpenAIService
   - Integration tests with real API
   - Performance measurement tests

## Tool Schemas Defined

Seven tools for function calling:

1. **lookup_customer** - Look up customer by phone number
2. **get_available_slots** - Check appointment availability
3. **book_appointment** - Book a service appointment
4. **get_upcoming_appointments** - Get customer's upcoming appointments
5. **cancel_appointment** - Cancel an appointment
6. **reschedule_appointment** - Move appointment to new time
7. **decode_vin** - Get vehicle information from VIN

Each tool has:
- Clear description for LLM
- JSON schema for parameters
- Required fields specified
- Enum values where applicable

## Integration Pattern

```
Twilio Audio
    ↓
DeepgramSTT (Feature 3 ✅)
    ↓ transcript
OpenAIService (Feature 5 ⏳)
    ├→ Tool calls → ToolRouter → CRM/Calendar
    └→ Text deltas
        ↓
DeepgramTTS (Feature 4 ⏳)
    ↓ audio
Twilio Audio
```

## System Prompt Strategy

Three main prompt types:

1. **Inbound New Customer**
   - Focus: Collection, welcoming, appointment booking
   - Context: No customer history

2. **Inbound Existing Customer**
   - Focus: Personalized service, reference history
   - Context: Customer name, last service, vehicles

3. **Outbound Reminder**
   - Focus: Brief, respectful of time, confirmation
   - Context: Appointment details

All prompts include:
- Role definition (Sophie, receptionist)
- Persona traits (friendly, professional, efficient)
- Conversation guidelines
- Business information
- Available tools

## Key Patterns Extracted

### From Reference Repository (Barty-Bart)

1. **Function Calling Flow:**
```javascript
// Detect function call
if (response.type === 'response.function_call_arguments.done') {
    // Execute tool
    const result = await executeFunction(name, args);

    // Add result to conversation
    addFunctionOutput(result);

    // Generate verbal response
    createResponse();
}
```

2. **System Message Structure:**
```
### Role
[Who the assistant is]

### Persona
[How they should behave]

### Conversation Guidelines
[Rules for interaction]

### Function Calling
[Available tools]
```

3. **Tool Result Injection:**
```javascript
// Add tool result as system message
{
    type: "function_call_output",
    role: "system",
    output: JSON.stringify(result)
}

// Trigger new response generation
{
    type: "response.create",
    instructions: "Respond based on: [result]"
}
```

### Adapted for Python + Standard API

1. **Streaming Delta Processing:**
```python
async for chunk in response_stream:
    delta = chunk.choices[0].delta

    # Handle content
    if delta.content:
        yield {"type": "content_delta", "text": delta.content}

    # Handle tool calls
    if delta.tool_calls:
        # Accumulate tool call deltas
        # Execute when complete
```

2. **Tool Execution Pattern:**
```python
# Add tool call to history
messages.append({
    "role": "assistant",
    "tool_calls": [...]
})

# Execute tool
result = await handler(**args)

# Add result to history
messages.append({
    "role": "tool",
    "tool_call_id": call_id,
    "content": result
})

# Call OpenAI again for verbal response
await generate_response()
```

## Dependencies

### Blocks These Features:
- Feature 8: WebSocket Handler (needs OpenAI for orchestration)
- Feature 10: Conversation Flow (needs system prompts)

### Blocked By:
- None (can start immediately)

### Can Work In Parallel With:
- Feature 4: Deepgram TTS (for end-to-end testing later)
- Feature 6: CRM Tools (ToolRouter can use existing implementations)
- Feature 7: Google Calendar (same as above)

## Success Criteria

### Functional
- ✅ OpenAI service connects and generates responses
- ✅ Streaming works with <500ms to first token
- ✅ Function calling works for all 7 tools
- ✅ Tool execution returns results to LLM
- ✅ LLM generates verbal response after tools
- ✅ Conversation history maintained
- ✅ System prompts inject correctly
- ✅ Token usage tracked

### Performance
- Time to first token: <500ms
- Full response: <3 seconds (non-tool)
- Tool + response: <5 seconds total
- Memory: <100MB per conversation

### Quality
- Error handling for API failures
- Retry logic for transient errors
- Graceful degradation when tools fail
- Clear logging for debugging
- Type hints and docstrings

## Risks Identified

### High Risk
1. **API Rate Limits** - Mitigation: Retry with exponential backoff
2. **Tool Execution Latency** - Mitigation: Optimize DB queries, timeouts
3. **Token Overflow** - Mitigation: Conversation trimming

### Medium Risk
1. **Tool Execution Errors** - Mitigation: Graceful error handling
2. **Inconsistent Responses** - Mitigation: Careful prompt engineering

### Low Risk
1. **Model Deprecation** - Mitigation: Easy model swapping

## Next Steps

### For Implementation Agent:

1. **Start with Phase 1: Core OpenAI Service**
   - Create `openai_service.py`
   - Implement basic methods
   - Test with simple prompts
   - Add streaming response handling
   - Test tool execution

2. **Phase 2: Tool Definitions & Router**
   - Create tool schemas
   - Implement ToolRouter
   - Connect to existing CRM tools
   - Test each tool

3. **Phase 3: System Prompts**
   - Build prompt templates
   - Add context injection
   - Test prompt generation

4. **Phase 4: Testing**
   - Unit tests
   - Integration tests
   - Performance measurement

### Testing Approach:

1. **Mock First** - Test with mock OpenAI responses
2. **Real API Second** - Test with real API key
3. **Measure Performance** - Track response times
4. **End-to-End** - Integration with STT/TTS (Feature 8)

## Knowledge Captured

### OpenAI API Patterns
- Streaming chat completions
- Function calling format
- Tool result injection
- Message history management
- Token counting strategies

### Reference Implementation Insights
- Inline tool execution pattern
- System message structure
- Function calling flow
- Tool result handling
- Conversation management

### Automotive Domain Knowledge
- Customer lookup flow
- Appointment booking process
- Service types and scheduling
- Conversation patterns
- Verification protocols

## Estimated ROI

### Time Investment: 5-7 hours
### Value Delivered:
- Core conversational AI capability
- Function calling for 7 CRM/Calendar tools
- Dynamic system prompts for different scenarios
- Streaming for low-latency responses
- Foundation for Features 8, 10

### Enables:
- Real conversational voice agent
- Automated appointment booking
- Customer service automation
- Multi-turn conversations with context
- Tool-augmented responses

## Conclusion

Planning complete. The implementation plan is comprehensive, detailed, and ready for execution. All research has been done, patterns identified, and architecture decisions documented.

The next agent can start implementation immediately with clear guidance on:
- What to build (classes, methods, files)
- How to build it (patterns, code examples)
- Why it's designed this way (rationale, trade-offs)
- How to test it (unit, integration, performance)

**Status:** ✅ Planning Complete
**Next Action:** Implement Phase 1 (Core OpenAI Service)
**Estimated Time:** 5-7 hours total
**Priority:** High (blocks Features 8, 10)
