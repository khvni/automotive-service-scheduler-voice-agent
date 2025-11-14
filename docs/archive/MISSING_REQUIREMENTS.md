# Missing Requirements Analysis

**Date:** November 13, 2025
**Project:** Automotive Voice Agent POC
**Status:** Functional but incomplete for full assignment requirements

---

## ✅ What's Complete

### 1. **Core Conversational Functionality** ✅
- ✅ WebSocket handler for voice streaming
- ✅ STT integration (Deepgram)
- ✅ TTS integration (Deepgram)
- ✅ LLM integration (OpenAI GPT-4o)
- ✅ Conversation flow designed
- ✅ System prompts created
- ✅ Barge-in detection implemented

### 2. **External API Integration** ✅✅✅
- ✅ 7 CRM tools implemented
- ✅ NHTSA VIN decode API
- ✅ Twilio voice API
- ✅ Redis caching
- ✅ PostgreSQL database
- ✅ Google Calendar (structure, not OAuth complete)

### 3. **Avoid No-Code** ✅
- ✅ 100% code-based (Python, SQL)
- ✅ No drag-and-drop tools
- ✅ All configuration in files

---

## ⚠️ What's Missing/Incomplete

### 1. **Error Handling Demonstration** ❌

**Requirement:**
> "Include basic error handling and demonstrate how the agent manages conversational ambiguity or unexpected input."

**Status:** Error handling EXISTS but not DEMONSTRATED

**What exists:**
- Try/catch blocks in all tools
- Database validation
- Input sanitization (phone, VIN, dates)
- Graceful degradation (Redis failure)

**What's missing:**
- ❌ No demo showing error recovery
- ❌ No demo showing invalid input handling
- ❌ No demo showing ambiguous conversation handling
- ❌ No documentation of error scenarios tested

**Fix needed:**
```bash
# Create Demo 3: Error Handling
demos/demo_3_error_scenarios.py
```

Should demonstrate:
- Invalid phone number → Error message
- Malformed VIN → Graceful fallback
- Double booking attempt → Conflict resolution
- Redis down → Continues without cache
- API timeout → Retry logic
- Ambiguous request → Clarification question

---

### 2. **Conversational Ambiguity Management** ❌

**Requirement:**
> "demonstrate how the agent manages conversational ambiguity"

**Status:** Logic EXISTS but not DEMONSTRATED

**What exists:**
- Conversation state machine (722 lines in `conversation_manager.py`)
- Intent detection patterns
- Slot collection logic
- Escalation detection

**What's missing:**
- ❌ Not integrated into main voice handler
- ❌ No demo showing ambiguity resolution
- ❌ No example of multi-turn clarification
- ❌ No proof it works in real conversation

**Examples of ambiguity to demonstrate:**
- User: "I need service" → AI: "What type of service? Oil change, brakes, inspection?"
- User: "Next week" → AI: "Which day next week works best for you?"
- User: "The blue car" → AI: "I see you have a blue Honda and blue Toyota. Which one?"
- User: "Something's wrong with it" → AI: "Can you describe what's happening? Noise, vibration, dashboard light?"

**Fix needed:**
- Integrate `conversation_manager.py` into `voice.py`
- OR create standalone demo showing ambiguity handling
- Document 3-5 ambiguous scenarios and how they're resolved

---

### 3. **Presentation Slides** ❌

**Requirement:**
> "Prepare a concise presentation (3-5 slides, ~15 minutes)"

**Status:** Outline EXISTS, slides DON'T EXIST

**What exists:**
- DEMO_SUMMARY.md has detailed slide outline
- Content for all 5 slides written
- Talking points documented

**What's missing:**
- ❌ No actual PowerPoint/Keynote/Google Slides file
- ❌ No architecture diagrams in presentation format
- ❌ No screenshot of demos
- ❌ No visual aids

**Required slides:**
1. **Slide 1:** Customer scenario and rationale
2. **Slide 2:** Technical architecture with diagram
3. **Slide 3:** Technology choices and justifications
4. **Slide 4:** Demo results (screenshots or live)
5. **Slide 5:** What's complete vs. what's next

**Fix needed:**
```bash
# Create presentation file
docs/POC_Presentation.pptx  # or .key or Google Slides link
```

---

### 4. **Google Calendar Integration** ⚠️

**Status:** Partially implemented

**What exists:**
- Calendar service file (`calendar_service.py`)
- OAuth2 structure
- Freebusy query logic
- Event CRUD functions

**What's missing:**
- ⚠️ OAuth flow not complete
- ⚠️ Refresh token generation not documented
- ⚠️ Integration commented out in tools (marked "Feature 7")

**Comments in code:**
- `crm_tools.py:290` - "Note: Feature 7 will create Google Calendar event"
- `crm_tools.py:536` - "Note: Feature 7 will delete Google Calendar event"
- `crm_tools.py:622` - "Note: Feature 7 will update Google Calendar event"

**Impact:** MEDIUM (not critical for POC, but mentioned in architecture)

**Fix needed:**
- Complete OAuth flow OR remove from architecture claims
- If keeping: Document it as "designed but not integrated"
- If removing: Update architecture diagrams

---

### 5. **Live Phone Call Demonstration** ⚠️

**Status:** UPDATED - Now supported with `--make-call` flag!

**What exists:**
- ✅ Demo 2 updated to make real calls
- ✅ Uses YOUR_TEST_NUMBER from .env
- ✅ Twilio API integration functional
- ✅ Safety confirmation before dialing

**How to use:**
```bash
# Make sure server is running
cd server && uvicorn app.main:app --reload

# In another terminal, start ngrok
ngrok http 8000

# Update .env with ngrok URL
BASE_URL=https://your-ngrok-url.ngrok.io

# Run demo with real call
cd demos
python demo_2_outbound_reminder.py --make-call
```

**What's still missing:**
- ⚠️ Requires manual setup (server + ngrok)
- ⚠️ Not automated in CI/CD
- ⚠️ No recording of actual call conversation

**Impact:** LOW (can demonstrate in person)

---

## 📊 Requirements Checklist

| Requirement | Status | Evidence | Gap |
|-------------|--------|----------|-----|
| **Functional proof-of-concept** | ✅ Partial | 2 working demos | No live audio demo |
| **Core conversational functionality** | ✅ Yes | Simulated in demos | Not tested with audio |
| **Essential external API integration** | ✅✅✅ Excellent | 7 tools + NHTSA + Twilio | None |
| **Error handling** | ⚠️ Exists | Code review | Not demonstrated |
| **Conversational ambiguity** | ❌ Not shown | State machine exists | Not integrated/demonstrated |
| **Avoid no-code** | ✅✅✅ Perfect | 100% code | None |
| **Presentation (3-5 slides)** | ❌ Missing | Outline only | Need actual slides |

---

## 🎯 Priority Fixes

### Priority 1: Create Presentation Slides ⭐⭐⭐
**Impact:** HIGH - Required deliverable
**Effort:** 2 hours
**Files:** `docs/POC_Presentation.pptx`

**Content:**
- Slide 1: Problem (dealership needs) + Solution (voice agent)
- Slide 2: Architecture diagram from docs
- Slide 3: Tech stack + justifications
- Slide 4: Demo screenshots + results
- Slide 5: Complete vs. Next Steps

### Priority 2: Demonstrate Error Handling ⭐⭐
**Impact:** MEDIUM - Assignment requirement
**Effort:** 3 hours
**Files:** `demos/demo_3_error_scenarios.py`

**Scenarios to demonstrate:**
1. Invalid phone number
2. Malformed VIN
3. Double booking attempt
4. Redis failure (simulate by stopping Redis)
5. API timeout

### Priority 3: Demonstrate Ambiguity Handling ⭐⭐
**Impact:** MEDIUM - Assignment requirement
**Effort:** 2 hours (if integrating) OR 1 hour (if documenting)

**Options:**
A. Integrate `conversation_manager.py` into `voice.py`
B. Create document showing how it would work
C. Add to presentation slides as "designed architecture"

### Priority 4: Document Google Calendar Status ⭐
**Impact:** LOW - Nice to have
**Effort:** 30 minutes

**Action:** Update docs to clarify:
- "Google Calendar integration designed but OAuth not complete"
- Remove from "what's working" claims
- Add to "next steps" in presentation

---

## 🔧 How to Fix Priority Items

### Fix 1: Create Presentation Slides

**Option A: PowerPoint**
```bash
# Use template from docs/DEMO_SUMMARY.md
# Create 5 slides in PowerPoint
# Save as docs/POC_Presentation.pptx
```

**Option B: Google Slides**
```bash
# Create presentation at slides.google.com
# Share link in README.md
# Export as PDF to docs/POC_Presentation.pdf
```

**Option C: Markdown Slides (Reveal.js)**
```bash
# Create docs/slides.md
# Use Reveal.js or Marp for markdown slides
# Can present from terminal or browser
```

### Fix 2: Error Handling Demo

Create `demos/demo_3_error_scenarios.py`:

```python
#!/usr/bin/env python3
"""
DEMO 3: ERROR HANDLING & EDGE CASES

Demonstrates how the system handles:
- Invalid inputs
- API failures
- Race conditions
- Ambiguous requests
"""

async def demo_invalid_phone():
    """Show graceful handling of invalid phone number."""
    result = await lookup_customer(db, "invalid-phone")
    # Shows validation error message

async def demo_malformed_vin():
    """Show VIN validation and error message."""
    result = await decode_vin("INVALID")
    # Shows validation error, suggests correct format

async def demo_double_booking():
    """Show conflict detection when slot unavailable."""
    # Book slot
    # Try to book same slot again
    # Shows conflict message

async def demo_redis_failure():
    """Show graceful degradation when Redis is down."""
    # Stop Redis: brew services stop redis
    # System continues without cache
    # Queries go straight to database

async def demo_api_timeout():
    """Show retry logic for external API failure."""
    # Simulate NHTSA API timeout
    # Shows retry attempts
    # Eventually returns error message
```

### Fix 3: Ambiguity Documentation

Create `docs/AMBIGUITY_HANDLING.md`:

```markdown
# Conversational Ambiguity Handling

## Designed State Machine

The system uses a conversation state machine to handle ambiguity:

### Example 1: Vague Service Request
User: "I need service"
AI: "I'd be happy to help! What type of service do you need?"
    - Oil change
    - Brake service
    - Tire rotation
    - State inspection
    - General maintenance

### Example 2: Unclear Timing
User: "Next week sometime"
AI: "Sure! Which day next week works best for you?"
User: "Wednesday"
AI: "Great! Morning or afternoon?"

### Example 3: Multiple Vehicles
User: "My car needs service"
AI: "I see you have two vehicles registered:
    1. 2018 Honda Civic
    2. 2020 Toyota Camry
    Which one needs service?"

## Implementation Status

- ✅ State machine designed (conversation_manager.py)
- ✅ Intent detection patterns
- ✅ Slot collection logic
- ⚠️ Not yet integrated into main voice handler
- 📋 Planned for production integration
```

---

## 📈 Impact on POC Score

### Current Score: 8.5/10

**With all fixes:**
- Create presentation: +0.5
- Error demo: +0.5
- Ambiguity demo: +0.5
- **Potential score: 10/10**

### Without fixes:
- Missing presentation: -1.0 (required deliverable)
- No error demo: -0.5 (requirement not shown)
- No ambiguity demo: -0.5 (requirement not shown)
- **Score stays: 7.5/10**

---

## 📝 Recommendations

### For Presentation:

**Be honest about scope:**
1. "I built a functional POC that demonstrates core capabilities"
2. "Error handling is implemented but not fully demonstrated today"
3. "Ambiguity handling is designed (show state machine) but not yet integrated"
4. "Here's what works now, here's what's next"

**Emphasize strengths:**
- Strong architecture
- 7 working tools
- Real database operations
- Twilio integration configured
- Can make actual calls with `--make-call` flag

**Acknowledge gaps:**
- Error scenarios not demonstrated (but code exists)
- State machine designed but not wired up
- Google Calendar OAuth incomplete

### For Demo:

**Live demonstration path:**
1. Run Demo 1 (inbound simulation)
2. Run Demo 2 with `--make-call` flag (if time permits)
3. Show code for error handling
4. Show conversation_manager.py design
5. Discuss next steps

**Safe demonstration path (if technical issues):**
1. Run Demo 1 (proven to work)
2. Run Demo 2 without call (show Twilio setup)
3. Walk through code examples
4. Show architecture diagrams
5. Be transparent about what's demonstrated vs. designed

---

## ⏱️ Time Estimates

| Task | Estimate | Priority |
|------|----------|----------|
| Create presentation slides | 2 hours | ⭐⭐⭐ Must have |
| Demo 3: Error scenarios | 3 hours | ⭐⭐ Should have |
| Ambiguity documentation | 1 hour | ⭐⭐ Should have |
| Google Calendar cleanup | 30 min | ⭐ Nice to have |
| Live call testing | 1 hour | ⭐ Nice to have |
| **Total** | **7.5 hours** | |

---

## 🎓 Bottom Line

**What you have:**
- Functional POC with working demos ✅
- Strong architecture and code quality ✅
- External API integrations ✅
- Path to live phone call testing ✅

**What you're missing for full credit:**
- Presentation slides (required) ❌
- Error handling demonstration (required) ❌
- Ambiguity handling demonstration (required) ❌

**Recommendation:**
1. **Minimum viable:** Create slides (2 hours)
2. **Better:** Slides + error demo (5 hours)
3. **Best:** All three fixes (7.5 hours)

**Realistic for presentation:**
- If you have 2 hours: Do slides only, be honest about gaps
- If you have 5 hours: Do slides + error demo
- If you have 8 hours: Complete all fixes

---

**Updated:** November 13, 2025
**Status:** Documented and prioritized
