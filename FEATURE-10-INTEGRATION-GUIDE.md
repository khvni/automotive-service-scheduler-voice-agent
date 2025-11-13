# Feature 10: WebSocket Integration Guide

**Purpose:** Complete integration of ConversationManager with WebSocket handler

---

## Integration Overview

The ConversationManager needs to be integrated into `server/app/routes/voice.py` to orchestrate real-time conversations during Twilio calls.

---

## Step 1: Add Import

At the top of `server/app/routes/voice.py`, add:

```python
from app.services.conversation_manager import (
    ConversationManager,
    CallType,
    create_inbound_new_manager,
    create_inbound_existing_manager,
)
```

---

## Step 2: Initialize Conversation Manager

In `handle_media_stream()`, add `conversation_manager` to the session state variables:

```python
# Session state
call_sid: Optional[str] = None
stream_sid: Optional[str] = None
caller_phone: Optional[str] = None
is_speaking = False
conversation_manager: Optional[ConversationManager] = None  # ADD THIS
```

---

## Step 3: Create Manager on Call Start

In the `receive_from_twilio()` function, replace the customer lookup and prompt personalization section with:

```python
# Inside the "elif event == 'start':" block, REPLACE the existing customer lookup code:

# Initialize conversation manager based on customer lookup
if caller_phone:
    try:
        from app.tools.crm_tools import lookup_customer

        customer = await lookup_customer(db, caller_phone)

        if customer:
            # Existing customer - use conversation manager
            logger.info(f"Existing customer found: {customer['first_name']} {customer['last_name']}")
            conversation_manager = create_inbound_existing_manager(
                caller_phone=caller_phone,
                customer_data=customer
            )
        else:
            # New customer
            logger.info(f"New customer calling: {caller_phone}")
            conversation_manager = create_inbound_new_manager(
                caller_phone=caller_phone
            )

        # Set system prompt from conversation manager
        system_prompt = conversation_manager.get_system_prompt()
        openai.set_system_prompt(system_prompt)
        logger.info(f"Conversation manager initialized: {conversation_manager.call_type.value}")

    except Exception as e:
        logger.warning(f"Could not initialize conversation manager: {e}")
        # Fallback to basic prompt
        openai.set_system_prompt(SYSTEM_PROMPT)
else:
    # No caller phone - use general prompt
    logger.info("No caller phone available, using general prompt")
    conversation_manager = ConversationManager(
        call_type=CallType.INBOUND_GENERAL,
        caller_phone=None
    )
    openai.set_system_prompt(conversation_manager.get_system_prompt())
```

---

## Step 4: Update State on Each Turn

In `process_transcripts()`, after the user message is captured, add conversation manager processing:

```python
# Inside "elif transcript_type == 'final' and transcript_data.get('speech_final'):"
user_message = transcript_text
logger.info(f"USER: {user_message}")

# Add to conversation history
openai.add_user_message(user_message)

# UPDATE CONVERSATION MANAGER STATE (ADD THIS)
if conversation_manager:
    try:
        # Process message and update state
        new_state = conversation_manager.process_message(user_message)
        logger.info(f"Conversation state: {new_state.value}")

        # Check for escalation
        if conversation_manager.should_escalate(user_message):
            logger.warning(f"Escalation triggered: {conversation_manager.escalation_reason}")
            # TODO: Implement human handoff logic
            # For now, inform user that we're transferring
            escalation_message = "I understand this needs more attention. Let me connect you with our service advisor."
            await tts.send_text(escalation_message)
            await tts.flush()
            # Stream audio to caller...

    except Exception as e:
        logger.error(f"Error processing conversation state: {e}")

# Generate AI response with streaming
is_speaking = True
response_text = ""
```

---

## Step 5: Update Prompt After AI Response (Optional)

After the AI generates a response, you can optionally update the system prompt based on the new state:

```python
# After "elif event['type'] == 'done':"
logger.info(f"ASSISTANT: {response_text}")

# Flush TTS to finalize audio generation
await tts.flush()

# UPDATE SYSTEM PROMPT FOR NEXT TURN (OPTIONAL)
if conversation_manager:
    try:
        updated_prompt = conversation_manager.get_system_prompt()
        openai.set_system_prompt(updated_prompt)
        logger.debug("System prompt updated for next turn")
    except Exception as e:
        logger.error(f"Error updating system prompt: {e}")

break
```

---

## Step 6: Store Conversation State in Redis

In the Redis session update section, add conversation state:

```python
# Update session in Redis with conversation history
if call_sid:
    try:
        session_data = {
            "conversation_history": openai.get_conversation_history(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # ADD CONVERSATION STATE (ADD THIS)
        if conversation_manager:
            session_data["conversation_state"] = conversation_manager.get_conversation_summary()

        await update_session(call_sid, session_data)
    except Exception as e:
        logger.warning(f"Failed to update session in Redis: {e}")
```

---

## Step 7: Store Final State on Cleanup

In the `finally` block, store final conversation state:

```python
# Save final session state to Redis
if call_sid and openai:
    try:
        final_session_data = {
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "conversation_history": openai.get_conversation_history(),
            "total_tokens": openai.get_token_usage(),
            "status": "completed"
        }

        # ADD FINAL CONVERSATION STATE (ADD THIS)
        if conversation_manager:
            final_session_data["conversation_summary"] = conversation_manager.get_conversation_summary()
            final_session_data["escalation_triggered"] = conversation_manager.escalation_triggered
            if conversation_manager.escalation_reason:
                final_session_data["escalation_reason"] = conversation_manager.escalation_reason

        await update_session(call_sid, final_session_data)
        logger.info(f"Final session state saved for call: {call_sid}")
    except Exception as e:
        logger.warning(f"Failed to save final session state: {e}")
```

---

## Complete Integration Example

Here's what the key sections should look like after integration:

### On Call Start

```python
elif event == 'start':
    call_sid = data['start']['callSid']
    stream_sid = data['start']['streamSid']

    custom_params = data['start'].get('customParameters', {})
    caller_phone = custom_params.get('From') or data['start'].get('from')

    logger.info(f"Call started - SID: {call_sid}, Stream: {stream_sid}, From: {caller_phone}")

    # Initialize session in Redis
    await set_session(call_sid, {
        "stream_sid": stream_sid,
        "caller_phone": caller_phone,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "conversation_history": [],
    })

    # Initialize conversation manager
    if caller_phone:
        try:
            from app.tools.crm_tools import lookup_customer
            customer = await lookup_customer(db, caller_phone)

            if customer:
                logger.info(f"Existing customer: {customer['first_name']} {customer['last_name']}")
                conversation_manager = create_inbound_existing_manager(
                    caller_phone=caller_phone,
                    customer_data=customer
                )
            else:
                logger.info(f"New customer: {caller_phone}")
                conversation_manager = create_inbound_new_manager(caller_phone=caller_phone)

            system_prompt = conversation_manager.get_system_prompt()
            openai.set_system_prompt(system_prompt)
            logger.info(f"Manager initialized: {conversation_manager.call_type.value}")

        except Exception as e:
            logger.warning(f"Could not initialize conversation manager: {e}")
            openai.set_system_prompt(SYSTEM_PROMPT)
    else:
        conversation_manager = ConversationManager(
            call_type=CallType.INBOUND_GENERAL,
            caller_phone=None
        )
        openai.set_system_prompt(conversation_manager.get_system_prompt())
```

### On Each User Message

```python
elif transcript_type == 'final' and transcript_data.get('speech_final'):
    user_message = transcript_text
    logger.info(f"USER: {user_message}")

    # Add to conversation history
    openai.add_user_message(user_message)

    # Process conversation state
    if conversation_manager:
        try:
            new_state = conversation_manager.process_message(user_message)
            logger.info(f"State: {new_state.value}, Intent: {conversation_manager.intent.value if conversation_manager.intent else 'None'}")

            # Check for escalation
            if conversation_manager.should_escalate(user_message):
                logger.warning(f"ESCALATION: {conversation_manager.escalation_reason}")
                # Handle escalation (future: transfer to human)
        except Exception as e:
            logger.error(f"Error in conversation manager: {e}")

    # Generate AI response
    is_speaking = True
    response_text = ""
    logger.info("Generating OpenAI response...")

    async for event in openai.generate_response(stream=True):
        # ... existing response handling ...
```

---

## Testing Integration

### Test 1: New Customer Call

```bash
# Call your Twilio number
# Say: "Hi, I need to schedule an oil change"

# Check logs for:
# - "New customer calling: +15551234567"
# - "Manager initialized: inbound_new"
# - "State: intent_detection, Intent: schedule_appointment"
# - "State: slot_collection"
```

### Test 2: Existing Customer Call

```bash
# Call from a number in the database
# Say: "Hi, I need brake service"

# Check logs for:
# - "Existing customer: John Smith"
# - "Manager initialized: inbound_existing"
# - AI greeting by name: "Hi John!"
# - "State: intent_detection, Intent: schedule_appointment"
```

### Test 3: Escalation

```bash
# During any call
# Say: "I want to speak to a manager"

# Check logs for:
# - "ESCALATION: manager_request"
# - "State: escalation"
# - Agent: "Let me connect you with our service advisor"
```

### Test 4: General Inquiry

```bash
# Call and say: "What are your hours?"

# Check logs for:
# - "State: intent_detection, Intent: check_hours"
# - "State: execution" (skips slot collection)
# - Agent provides hours immediately
```

---

## Monitoring

### Log Analysis

Key log messages to monitor:

```python
# State transitions
"Conversation state: slot_collection"
"State: intent_detection, Intent: schedule_appointment"

# Escalations
"ESCALATION: manager_request"
"Escalation triggered: anger"

# Errors
"Error in conversation manager: ..."
"Could not initialize conversation manager: ..."
```

### Redis Session Data

Check Redis for conversation summaries:

```python
{
    "conversation_summary": {
        "call_type": "inbound_existing",
        "state": "closing",
        "intent": "schedule_appointment",
        "turn_count": 8,
        "collected_slots": {
            "service_type": "oil change",
            "preferred_date": "tomorrow",
            "preferred_time": "2pm"
        },
        "escalation_triggered": false
    }
}
```

---

## Troubleshooting

### Issue: Manager not initialized

**Symptom:** Logs show "Could not initialize conversation manager"

**Fix:** Check that:
- `lookup_customer()` is working
- Database connection is active
- Phone number format is correct

### Issue: State not transitioning

**Symptom:** State stuck in GREETING or INTENT_DETECTION

**Fix:** Check that:
- `process_message()` is being called
- User messages are being passed correctly
- Intent patterns match user input

### Issue: Escalation not triggered

**Symptom:** Manager request not detected

**Fix:** Check that:
- `should_escalate()` is being called
- Escalation patterns match user input (regex)
- State changes to ESCALATION

---

## Next Steps After Integration

1. **Test all 6 flows** with real Twilio calls
2. **Monitor state transitions** in logs
3. **Tune intent patterns** based on real conversations
4. **Implement human handoff** for escalations
5. **Add analytics** to track flow completion rates
6. **Optimize slot collection** based on user behavior

---

## Support

If you encounter issues during integration:

1. Check logs for error messages
2. Verify conversation manager is initialized
3. Test state transitions with simple messages
4. Review the test scripts for expected behavior
5. Check Redis for session state

---

**Integration Guide Version:** 1.0
**Last Updated:** January 12, 2025
**Related Files:**
- `server/app/services/conversation_manager.py`
- `server/app/routes/voice.py`
- `FEATURE-10-SUMMARY.md`
