# Overnight Background Tasks - Automotive Voice Agent

## Context

This is a 48-hour POC for an AI-powered voice agent for Otto's Auto (automotive dealership). The system handles inbound calls for appointment scheduling and outbound reminder calls.

**Current Status:** Core features 1-13 implemented, code review completed, critical fixes applied.

## Architecture Overview

**Technology Stack:**
- **Runtime:** Python, FastAPI, asyncio
- **Audio Pipeline:** Twilio Media Streams → Deepgram STT (nova-2-phonecall) → GPT-4o → Deepgram TTS → Twilio
- **State Management:** Redis (session state, customer cache)
- **Database:** Neon Postgres + SQLAlchemy
- **Calendar:** Google Calendar API (real integration)

**Project Structure:**
```
automotive-voice/
├── server/app/           # FastAPI application
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Core services (STT, TTS, OpenAI, Redis, DB)
│   ├── routes/          # WebSocket handler, webhooks
│   └── tools/           # CRM tools, calendar tools
├── worker/              # Cron worker for outbound calls
├── scripts/             # Database init, mock data, tests
└── tests/               # Test suites
```

## Critical Analysis Required

You are a senior software engineer conducting a critical functionality review. Your task is to:

1. **Test Actual Functionality** - Don't assume code works, verify it
2. **Identify Integration Issues** - Test how components work together
3. **Fix Real Bugs** - Not cosmetic issues, actual broken functionality
4. **Validate Critical Paths** - Voice pipeline, database ops, API integrations

## Background Tasks for Overnight Processing

### Task 1: Critical Functionality Validation (Priority: CRITICAL)

**Objective:** Test and fix actual broken functionality in core voice pipeline

**Focus Areas:**
1. **WebSocket Handler** (`server/app/routes/voice.py`)
   - Test Twilio Media Stream connection actually works
   - Verify audio streaming (Twilio → Deepgram → Twilio)
   - Test barge-in detection actually triggers
   - Fix any async/concurrency bugs
   - Validate session cleanup on disconnect

2. **Deepgram Integration** (`server/app/services/deepgram_stt.py`, `deepgram_tts.py`)
   - Test WebSocket connections to Deepgram actually establish
   - Verify audio format conversions work (base64 ↔ mulaw)
   - Test interim vs final transcript handling
   - Fix any connection timeout issues

3. **OpenAI Tool Execution** (`server/app/services/openai_service.py`, `tool_router.py`)
   - Test tool calls actually execute (not just defined)
   - Verify recursive tool execution works with depth limit
   - Test error handling when tools fail
   - Validate conversation history doesn't corrupt

**Acceptance Criteria:**
- WebSocket accepts real Twilio connection
- Audio flows end-to-end without errors
- Tools execute and return results to LLM
- No unhandled exceptions in core pipeline

**Output:** Document what was broken, what was fixed, with test evidence

---

### Task 2: Database and Redis Integration Testing (Priority: HIGH)

**Objective:** Verify database operations and caching actually work under load

**Focus Areas:**
1. **Database Operations** (`server/app/tools/crm_tools.py`)
   - Test customer lookup with real database queries
   - Test appointment booking creates both DB + Calendar entries
   - Verify foreign key constraints work
   - Test concurrent operations don't corrupt data
   - Validate transaction rollbacks on errors

2. **Redis Caching** (`server/app/services/redis_client.py`)
   - Test cache hits/misses actually improve performance
   - Verify session state persists across requests
   - Test TTL expiration works correctly
   - Validate atomic operations (Lua scripts)
   - Test Redis connection pool under load

3. **Data Integrity**
   - Test appointment rescheduling updates both DB and Calendar
   - Verify cancellations clean up properly
   - Test orphaned records don't accumulate

**Acceptance Criteria:**
- Database queries execute without errors
- Redis caching provides measurable speedup
- No data corruption under concurrent operations
- Foreign keys enforce referential integrity

**Output:** Performance benchmarks and any data integrity fixes

---

### Task 3: Google Calendar Integration Verification (Priority: HIGH)

**Objective:** Verify Google Calendar integration actually works end-to-end

**Focus Areas:**
1. **OAuth2 Flow** (`server/app/services/calendar_service.py`)
   - Test refresh token actually refreshes credentials
   - Verify token expiration handling works
   - Test unauthorized/expired token recovery

2. **Calendar Operations** (`server/app/tools/calendar_tools.py`)
   - Test freebusy query returns accurate availability
   - Verify event creation actually appears in Google Calendar
   - Test event updates/cancellations sync correctly
   - Validate timezone conversion (UTC ↔ America/New_York)

3. **Error Handling**
   - Test network failure recovery
   - Verify rate limiting doesn't break operations
   - Test quota exceeded scenarios

**Acceptance Criteria:**
- Events created via code appear in Google Calendar UI
- Freebusy returns real availability data
- Timezone conversions are correct
- Errors are handled gracefully

**Output:** Working Calendar integration with test events created

---

### Task 4: End-to-End Voice Call Simulation (Priority: MEDIUM)

**Objective:** Simulate complete voice call flows without real Twilio calls

**Focus Areas:**
1. **Call Flow Simulation**
   - Simulate new customer appointment booking flow
   - Simulate existing customer rescheduling flow
   - Simulate appointment cancellation flow
   - Test verification protocol (DOB, VIN checks)

2. **Conversation State Machine** (`server/app/services/conversation_manager.py`)
   - Test state transitions work correctly
   - Verify slot collection persists across turns
   - Test error recovery when user gives invalid input
   - Validate escalation triggers work

3. **System Prompts** (`server/app/services/system_prompts.py`)
   - Verify prompts produce appropriate LLM responses
   - Test personalization with customer context
   - Validate intent detection accuracy

**Acceptance Criteria:**
- Complete call flows execute without errors
- State machine transitions correctly
- LLM produces contextually appropriate responses
- Conversation history maintains coherence

**Output:** Test transcripts showing successful call flows

---

### Task 5: Performance and Resource Management (Priority: MEDIUM)

**Objective:** Identify and fix performance bottlenecks and resource leaks

**Focus Areas:**
1. **Memory Leaks**
   - Check WebSocket connections are properly closed
   - Verify Deepgram connections clean up on errors
   - Test Redis connections don't leak
   - Check database connections are released

2. **Performance Bottlenecks**
   - Profile slow database queries
   - Identify N+1 query problems
   - Test Redis caching effectiveness
   - Measure actual latencies vs targets

3. **Resource Limits**
   - Test behavior under connection pool exhaustion
   - Verify graceful degradation when services unavailable
   - Test rate limiting doesn't cause failures

**Acceptance Criteria:**
- No memory leaks over 1000+ operations
- Database queries meet performance targets
- Connections properly cleaned up
- Graceful degradation when limits hit

**Output:** Performance report with before/after metrics

---

### Task 6: Error Handling and Edge Cases (Priority: MEDIUM)

**Objective:** Test error handling for real-world failure scenarios

**Focus Areas:**
1. **Network Failures**
   - Test Deepgram connection drops mid-call
   - Test Google Calendar API timeouts
   - Test Redis connection failures
   - Test database connection losses

2. **Invalid Input Handling**
   - Test malformed phone numbers
   - Test invalid dates for appointments
   - Test VIN validation with bad data
   - Test SQL injection attempts (should fail safely)

3. **Concurrent Operations**
   - Test double-booking prevention
   - Test concurrent customer lookups
   - Test race conditions in session management

**Acceptance Criteria:**
- No unhandled exceptions for common failures
- Invalid input rejected gracefully
- Concurrent operations don't corrupt data
- Security vulnerabilities blocked

**Output:** List of edge cases tested and fixes applied

---

## Reference Repositories (Use GitHub MCP)

Before fixing issues, read production code from:

1. **deepgram/deepgram-twilio-streaming-voice-agent**
   - Focus: `server.js` lines 230-330 (STT/TTS setup, barge-in)

2. **duohub-ai/google-calendar-voice-agent**
   - Focus: `calendar_service.py` (OAuth2, freebusy, event CRUD)

3. **twilio-samples/speech-assistant-openai-realtime-api-python**
   - Focus: `main.py` (WebSocket handler, interruption handling)

## Constraints and Guidelines

**CRITICAL SAFETY RULES:**
- Do NOT delete or restructure existing code without testing
- Do NOT make cosmetic changes (formatting, comments, etc.)
- Do NOT add features - only fix broken functionality
- Do NOT use emojis in code or commit messages
- Do NOT commit changes unless tests pass

**Testing Requirements:**
- Test before fixing (prove something is broken)
- Test after fixing (prove fix works)
- Document what was broken and evidence of fix
- Create test cases for regressions

**Resource Management:**
- Batch operations where possible (reduce API calls)
- Use existing test fixtures (don't regenerate mock data)
- Limit GitHub MCP reads to essential files only
- Use context7 sparingly for specific library questions

## Deliverables

For each task, create a report with:

1. **What Was Tested:** Specific functionality tested
2. **What Was Broken:** Actual bugs found with evidence
3. **What Was Fixed:** Code changes with file paths
4. **Test Evidence:** Logs, outputs, or test results proving fix works
5. **Remaining Issues:** Known problems that couldn't be fixed

**Save Reports To:**
- `/Users/khani/Desktop/projs/automotive-voice/TASK_[N]_REPORT.md`

**Commit Strategy:**
- One commit per significant fix
- Descriptive commit messages: "fix: [specific issue] in [component]"
- Update allpepper-memory-bank with fix summaries

## Priority Order

Execute tasks in this order:
1. Task 1 (Critical Functionality) - Most important
2. Task 2 (Database/Redis) - Foundation for everything
3. Task 3 (Google Calendar) - External integration
4. Task 4 (Voice Flow Simulation) - User experience
5. Task 5 (Performance) - Optimization
6. Task 6 (Error Handling) - Edge cases

Stop if you encounter blocking issues that need human review.

## Success Criteria

By morning, we should have:
- ✅ Verified core voice pipeline actually works
- ✅ Fixed any broken integrations (DB, Redis, Calendar)
- ✅ Documented actual bugs found and fixed
- ✅ Test evidence for all fixes
- ✅ No critical functionality broken

**Focus on functionality over perfection. Fix real bugs, not hypothetical issues.**
