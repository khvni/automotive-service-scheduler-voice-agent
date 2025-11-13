# Feature 5 Implementation Plan: OpenAI GPT-4o Integration

## Executive Summary

This document provides a comprehensive plan for implementing Feature 5: OpenAI GPT-4o Integration for the automotive voice agent. The implementation uses **standard OpenAI Chat Completions API** (NOT Realtime API) with custom orchestration for streaming responses, function calling, and conversation management.

**Key Architecture Decision:** We're using the standard Chat Completions API with streaming instead of the Realtime API because:
1. More control over the orchestration between STT → LLM → TTS
2. Better function calling support with structured output
3. Proven pattern from reference repo (Barty-Bart's implementation)
4. Easier to implement token usage tracking and conversation history management

---

## Architecture Overview

### Data Flow Diagram

```
┌─────────────┐
│   Twilio    │
│ Media Stream│
└──────┬──────┘
       │ mulaw audio
       ↓
┌─────────────────┐
│  Deepgram STT   │ ← Feature 3 (DONE)
│ (nova-2-phone)  │
└──────┬──────────┘
       │ text transcript
       ↓
┌─────────────────────────────────────────┐
│         OpenAIService (Feature 5)       │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Conversation History Manager    │  │
│  │  - System prompt injection       │  │
│  │  - Message list management       │  │
│  │  - Token counting                │  │
│  └────────────┬─────────────────────┘  │
│               ↓                         │
│  ┌──────────────────────────────────┐  │
│  │  Chat Completions API Client     │  │
│  │  - Stream: true                  │  │
│  │  - Tools: function definitions   │  │
│  │  - model: gpt-4o                 │  │
│  └────────────┬─────────────────────┘  │
│               ↓                         │
│  ┌──────────────────────────────────┐  │
│  │  Response Parser & Router        │  │
│  │  - Text chunks → TTS queue       │  │
│  │  - Tool calls → Tool router      │  │
│  │  - finish_reason handling        │  │
│  └────────────┬─────────────────────┘  │
└───────────────┼─────────────────────────┘
                │
        ┌───────┴────────┐
        ↓                ↓
┌──────────────┐  ┌──────────────────┐
│ Tool Router  │  │  Deepgram TTS    │ ← Feature 4 (PENDING)
│ (Feature 6)  │  │  (aura-voice)    │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       │ tool_result       │ mulaw audio
       └──────────┬────────┘
                  ↓
         ┌─────────────────┐
         │  Twilio Stream  │
         │   (playback)    │
         └─────────────────┘
```

### Conversation Flow Pattern (from Reference Repo)

Based on Barty-Bart's index.js implementation (lines 237-430), the pattern is:

1. **User speaks** → STT → text
2. **Add user message** to conversation history
3. **Call OpenAI** with streaming enabled + function definitions
4. **Process stream events**:
   - `delta.content` → Send text chunks to TTS immediately
   - `function_call_arguments.done` → Execute tool inline
   - Add tool result as new message to history
   - Call OpenAI again to generate response based on tool result
5. **Response complete** → Wait for next user input

**Critical Pattern:** Tool execution is INLINE (not queued), and after tool execution, we immediately call OpenAI again with the tool result to generate the assistant's verbal response.

---

## Class Structure

### Primary Class: OpenAIService

```python
# File: server/app/services/openai_service.py

from typing import Optional, Dict, Any, List, Callable, AsyncGenerator
from openai import AsyncOpenAI
import logging
import asyncio

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    OpenAI GPT-4o service for conversational AI with function calling.

    Uses standard Chat Completions API with streaming for:
    - Real-time response generation
    - Function calling with inline execution
    - Conversation history management
    - Token usage tracking
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        temperature: float = 0.8,
        max_tokens: int = 1000,
    ):
        """
        Initialize OpenAI service.

        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4o)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens per response
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Conversation state
        self.messages: List[Dict[str, Any]] = []
        self.system_prompt: Optional[str] = None

        # Tool registry
        self.tool_registry: Dict[str, Callable] = {}
        self.tool_schemas: List[Dict[str, Any]] = []

        # Usage tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        logger.info(f"OpenAIService initialized with model: {model}")

    def set_system_prompt(self, prompt: str) -> None:
        """
        Set or update system prompt.

        Args:
            prompt: System instruction for assistant behavior
        """
        self.system_prompt = prompt

        # Update messages list
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = prompt
        else:
            self.messages.insert(0, {"role": "system", "content": prompt})

        logger.info("System prompt set")

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
    ) -> None:
        """
        Register a function/tool that the LLM can call.

        Args:
            name: Function name
            description: What the function does
            parameters: JSON schema for parameters
            handler: Async function to execute when called
        """
        # Store handler
        self.tool_registry[name] = handler

        # Store schema
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        }
        self.tool_schemas.append(schema)

        logger.info(f"Registered tool: {name}")

    def add_user_message(self, content: str) -> None:
        """
        Add user message to conversation history.

        Args:
            content: User's message text
        """
        self.messages.append({
            "role": "user",
            "content": content,
        })
        logger.debug(f"User message added: {content[:50]}...")

    def add_assistant_message(self, content: str) -> None:
        """
        Add assistant message to conversation history.

        Args:
            content: Assistant's message text
        """
        self.messages.append({
            "role": "assistant",
            "content": content,
        })
        logger.debug(f"Assistant message added: {content[:50]}...")

    def add_tool_call_message(
        self,
        tool_call_id: str,
        function_name: str,
        function_arguments: str,
    ) -> None:
        """
        Add tool call message to conversation history.

        Args:
            tool_call_id: Unique ID for this tool call
            function_name: Name of function being called
            function_arguments: JSON string of arguments
        """
        self.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": function_arguments,
                }
            }]
        })
        logger.debug(f"Tool call message added: {function_name}")

    def add_tool_result_message(
        self,
        tool_call_id: str,
        result: str,
    ) -> None:
        """
        Add tool execution result to conversation history.

        Args:
            tool_call_id: ID of the tool call this result is for
            result: JSON string of tool execution result
        """
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })
        logger.debug(f"Tool result added for call_id: {tool_call_id}")

    async def generate_response(
        self,
        stream: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate AI response with streaming.

        Yields:
            Dict with one of:
                - {"type": "content_delta", "text": str}
                - {"type": "tool_call", "name": str, "arguments": str, "call_id": str}
                - {"type": "tool_result", "result": str, "call_id": str}
                - {"type": "error", "message": str}
                - {"type": "done", "finish_reason": str, "usage": dict}

        Pattern:
            1. Stream text deltas for TTS
            2. When tool call detected, execute inline
            3. Add tool result to history
            4. Call again to generate verbal response
        """
        try:
            # First API call
            response_stream = await self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tool_schemas if self.tool_schemas else None,
                tool_choice="auto" if self.tool_schemas else None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=stream,
            )

            # Process stream
            accumulated_content = ""
            tool_calls_accumulator = []

            async for chunk in response_stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Handle content (text)
                if delta.content:
                    accumulated_content += delta.content
                    yield {
                        "type": "content_delta",
                        "text": delta.content,
                    }

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        # Initialize tool call accumulator
                        if tc_delta.index >= len(tool_calls_accumulator):
                            tool_calls_accumulator.append({
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            })

                        # Accumulate
                        if tc_delta.id:
                            tool_calls_accumulator[tc_delta.index]["id"] = tc_delta.id
                        if tc_delta.function.name:
                            tool_calls_accumulator[tc_delta.index]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_accumulator[tc_delta.index]["arguments"] += tc_delta.function.arguments

                # Handle finish
                if finish_reason:
                    # Track usage
                    if hasattr(chunk, 'usage') and chunk.usage:
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

                    # Process based on finish reason
                    if finish_reason == "tool_calls":
                        # Execute tools inline
                        for tool_call in tool_calls_accumulator:
                            # Add tool call to history
                            self.add_tool_call_message(
                                tool_call_id=tool_call["id"],
                                function_name=tool_call["name"],
                                function_arguments=tool_call["arguments"],
                            )

                            # Execute tool
                            yield {
                                "type": "tool_call",
                                "name": tool_call["name"],
                                "arguments": tool_call["arguments"],
                                "call_id": tool_call["id"],
                            }

                            # Execute handler
                            result = await self._execute_tool(
                                tool_call["name"],
                                tool_call["arguments"],
                            )

                            # Add result to history
                            self.add_tool_result_message(
                                tool_call_id=tool_call["id"],
                                result=result,
                            )

                            yield {
                                "type": "tool_result",
                                "result": result,
                                "call_id": tool_call["id"],
                            }

                        # Make second API call to generate verbal response
                        logger.info("Tool execution complete, generating verbal response")
                        async for event in self.generate_response(stream=stream):
                            yield event
                        return

                    elif finish_reason == "stop":
                        # Natural completion
                        if accumulated_content:
                            self.add_assistant_message(accumulated_content)

                        yield {
                            "type": "done",
                            "finish_reason": finish_reason,
                            "usage": {
                                "prompt_tokens": self.total_prompt_tokens,
                                "completion_tokens": self.total_completion_tokens,
                            }
                        }
                        return

                    else:
                        # Other finish reasons (length, content_filter, etc.)
                        logger.warning(f"Unexpected finish_reason: {finish_reason}")
                        yield {
                            "type": "done",
                            "finish_reason": finish_reason,
                            "usage": {
                                "prompt_tokens": self.total_prompt_tokens,
                                "completion_tokens": self.total_completion_tokens,
                            }
                        }
                        return

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            yield {
                "type": "error",
                "message": str(e),
            }

    async def _execute_tool(
        self,
        function_name: str,
        function_arguments: str,
    ) -> str:
        """
        Execute a registered tool/function.

        Args:
            function_name: Name of function to call
            function_arguments: JSON string of arguments

        Returns:
            JSON string of result
        """
        import json

        try:
            # Parse arguments
            args = json.loads(function_arguments)

            # Get handler
            handler = self.tool_registry.get(function_name)
            if not handler:
                return json.dumps({"error": f"Function {function_name} not found"})

            # Execute
            logger.info(f"Executing tool: {function_name} with args: {args}")
            result = await handler(**args)

            # Return as JSON string
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}")
            return json.dumps({"error": str(e)})

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get full conversation history.

        Returns:
            List of message dicts
        """
        return self.messages.copy()

    def clear_history(self, keep_system: bool = True) -> None:
        """
        Clear conversation history.

        Args:
            keep_system: Whether to keep system prompt
        """
        if keep_system and self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        else:
            self.messages = []

        logger.info("Conversation history cleared")

    def get_token_usage(self) -> Dict[str, int]:
        """
        Get token usage statistics.

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens
        """
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
        }
```

---

## Tool Schema Design

### Tool Schema Format (OpenAI Function Calling)

Based on the reference repo and OpenAI docs, tool schemas follow this structure:

```python
{
    "type": "function",
    "function": {
        "name": "lookup_customer",
        "description": "Look up customer information by phone number",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Customer's phone number (10 digits)"
                }
            },
            "required": ["phone_number"]
        }
    }
}
```

### Tool Definitions for Automotive Voice Agent

```python
# File: server/app/services/tool_definitions.py

from typing import Dict, Any

# Tool schemas for OpenAI function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up customer information by phone number. Returns customer details, vehicles, and service history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Customer's phone number (10 digits, format: 555-123-4567 or 5551234567)"
                    }
                },
                "required": ["phone_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Get available appointment time slots for a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to check availability (format: YYYY-MM-DD)"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Type of service (e.g., 'oil_change', 'brake_service', 'inspection')",
                        "enum": ["oil_change", "brake_service", "tire_rotation", "inspection", "general_service"]
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a service appointment for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID (from lookup_customer result)"
                    },
                    "vehicle_id": {
                        "type": "integer",
                        "description": "Vehicle ID (from lookup_customer result)"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Type of service to book"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Appointment start time (ISO format: 2025-01-15T09:00:00)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any special notes or customer concerns"
                    }
                },
                "required": ["customer_id", "vehicle_id", "service_type", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_appointments",
            "description": "Get upcoming appointments for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID"
                    }
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "Appointment ID to cancel"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation",
                        "enum": ["schedule_conflict", "got_service_elsewhere", "vehicle_sold", "issue_resolved", "other"]
                    }
                },
                "required": ["appointment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new time",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "Appointment ID to reschedule"
                    },
                    "new_start_time": {
                        "type": "string",
                        "description": "New appointment start time (ISO format)"
                    }
                },
                "required": ["appointment_id", "new_start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "decode_vin",
            "description": "Decode a vehicle VIN number to get make, model, year information",
            "parameters": {
                "type": "object",
                "properties": {
                    "vin": {
                        "type": "string",
                        "description": "17-character VIN number"
                    }
                },
                "required": ["vin"]
            }
        }
    }
]
```

---

## Conversation History Management

### Message Format

OpenAI Chat Completions API expects messages in this format:

```python
[
    # System message (optional but recommended)
    {
        "role": "system",
        "content": "You are Sophie, a friendly receptionist at Bart's Automotive..."
    },

    # User message
    {
        "role": "user",
        "content": "I need to schedule an oil change"
    },

    # Assistant message
    {
        "role": "assistant",
        "content": "I'd be happy to help you schedule an oil change..."
    },

    # Tool call (assistant wants to call a function)
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_available_slots",
                    "arguments": "{\"date\": \"2025-01-15\"}"
                }
            }
        ]
    },

    # Tool result (function execution result)
    {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "{\"slots\": [{\"time\": \"09:00\", \"available\": true}, ...]}"
    },

    # Assistant response after tool result
    {
        "role": "assistant",
        "content": "I have availability at 9:00 AM and 11:00 AM. Which works better?"
    }
]
```

### Conversation Window Management

To prevent token limit issues:

```python
def trim_conversation_history(
    messages: List[Dict],
    max_messages: int = 20,
    keep_system: bool = True
) -> List[Dict]:
    """
    Trim conversation history to prevent token overflow.

    Strategy:
    - Always keep system message
    - Keep most recent N messages
    - Ensure tool_call and tool_result pairs are kept together
    """
    if len(messages) <= max_messages:
        return messages

    # Separate system message
    system_msg = None
    other_msgs = messages

    if keep_system and messages[0]["role"] == "system":
        system_msg = messages[0]
        other_msgs = messages[1:]

    # Keep most recent messages
    trimmed = other_msgs[-max_messages:]

    # Prepend system message
    if system_msg:
        trimmed.insert(0, system_msg)

    return trimmed
```

---

## Streaming vs Non-Streaming Response Handling

### Streaming (Recommended for Low Latency)

**Advantages:**
- Send text to TTS immediately as it's generated
- Lower perceived latency (~500ms to first token vs ~2s for full response)
- Better user experience for long responses

**Implementation:**

```python
async def handle_streaming_response(openai_service, tts_service):
    """
    Process streaming response from OpenAI.

    Pattern:
    1. For each text delta → send to TTS immediately
    2. For tool calls → execute inline, then continue streaming
    """
    async for event in openai_service.generate_response(stream=True):
        if event["type"] == "content_delta":
            # Send text chunk to TTS immediately
            await tts_service.send_text(event["text"])

        elif event["type"] == "tool_call":
            logger.info(f"Executing tool: {event['name']}")
            # Tool execution happens inside generate_response()
            # Just log for monitoring

        elif event["type"] == "tool_result":
            logger.info(f"Tool result: {event['result'][:100]}...")
            # After tool execution, generate_response will automatically
            # call OpenAI again with the result

        elif event["type"] == "error":
            logger.error(f"Error: {event['message']}")
            await tts_service.send_text("I'm sorry, I encountered an error.")

        elif event["type"] == "done":
            logger.info(f"Response complete: {event['finish_reason']}")
            logger.info(f"Token usage: {event['usage']}")
```

### Non-Streaming (Fallback)

**Use cases:**
- Debugging
- Testing
- When TTS doesn't support streaming

```python
async def handle_non_streaming_response(openai_service, tts_service):
    """Non-streaming response handling."""
    full_response = ""

    async for event in openai_service.generate_response(stream=False):
        if event["type"] == "content_delta":
            full_response += event["text"]
        elif event["type"] == "done":
            # Send full response to TTS at once
            await tts_service.send_text(full_response)
```

---

## Tool Execution Router

### Tool Router Pattern

```python
# File: server/app/services/tool_router.py

from typing import Dict, Any, Callable
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.crm_tools import lookup_customer, create_customer
from app.tools.calendar_tools import get_available_slots, book_appointment, cancel_appointment
from app.tools.vin_tools import decode_vin

logger = logging.getLogger(__name__)


class ToolRouter:
    """
    Routes function calls to appropriate handlers.

    Responsibilities:
    - Map function names to Python functions
    - Provide database session to tools
    - Handle errors gracefully
    - Format results for OpenAI
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize tool router.

        Args:
            db_session: Database session for tool execution
        """
        self.db = db_session

        # Tool registry
        self.tools: Dict[str, Callable] = {
            "lookup_customer": self._lookup_customer,
            "get_available_slots": self._get_available_slots,
            "book_appointment": self._book_appointment,
            "get_upcoming_appointments": self._get_upcoming_appointments,
            "cancel_appointment": self._cancel_appointment,
            "reschedule_appointment": self._reschedule_appointment,
            "decode_vin": self._decode_vin,
        }

    async def execute(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            function_name: Name of function to execute
            **kwargs: Function arguments

        Returns:
            Dict with result or error
        """
        try:
            handler = self.tools.get(function_name)
            if not handler:
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}"
                }

            logger.info(f"Executing tool: {function_name}")
            result = await handler(**kwargs)

            return {
                "success": True,
                "data": result
            }

        except Exception as e:
            logger.error(f"Error executing {function_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # Tool implementations

    async def _lookup_customer(self, phone_number: str) -> Dict[str, Any]:
        """Look up customer by phone."""
        from app.tools.crm_tools import lookup_customer

        customer = await lookup_customer(self.db, phone_number)
        if not customer:
            return {
                "found": False,
                "message": "No customer found with that phone number"
            }

        return {
            "found": True,
            "customer": customer
        }

    async def _get_available_slots(
        self,
        date: str,
        service_type: str = "general_service"
    ) -> Dict[str, Any]:
        """Get available appointment slots."""
        from app.tools.calendar_tools import get_freebusy
        from datetime import datetime, timedelta

        # Parse date
        start_date = datetime.fromisoformat(date)
        end_date = start_date + timedelta(days=1)

        slots = await get_freebusy(start_date, end_date)

        return {
            "date": date,
            "available_slots": slots
        }

    async def _book_appointment(
        self,
        customer_id: int,
        vehicle_id: int,
        service_type: str,
        start_time: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Book an appointment."""
        from app.tools.calendar_tools import book_slot
        from datetime import datetime

        # Parse time
        start_datetime = datetime.fromisoformat(start_time)

        # TODO: Get customer and vehicle info for event details
        event = await book_slot(
            start_time=start_datetime,
            duration_minutes=60,  # TODO: Make configurable by service type
            customer_name=f"Customer {customer_id}",  # TODO: Fetch actual name
            service_type=service_type,
        )

        # TODO: Create appointment record in database

        return {
            "booked": True,
            "appointment_id": event["event_id"],
            "start_time": start_time,
            "service_type": service_type
        }

    async def _get_upcoming_appointments(
        self,
        customer_id: int
    ) -> Dict[str, Any]:
        """Get upcoming appointments for customer."""
        # TODO: Implement database query
        return {
            "customer_id": customer_id,
            "appointments": []
        }

    async def _cancel_appointment(
        self,
        appointment_id: int,
        reason: str
    ) -> Dict[str, Any]:
        """Cancel an appointment."""
        # TODO: Implement cancellation
        return {
            "cancelled": True,
            "appointment_id": appointment_id,
            "reason": reason
        }

    async def _reschedule_appointment(
        self,
        appointment_id: int,
        new_start_time: str
    ) -> Dict[str, Any]:
        """Reschedule an appointment."""
        # TODO: Implement rescheduling
        return {
            "rescheduled": True,
            "appointment_id": appointment_id,
            "new_start_time": new_start_time
        }

    async def _decode_vin(self, vin: str) -> Dict[str, Any]:
        """Decode VIN number."""
        from app.tools.vin_tools import decode_vin

        vehicle_info = await decode_vin(vin)
        if not vehicle_info:
            return {
                "valid": False,
                "message": "Invalid VIN or unable to decode"
            }

        return {
            "valid": True,
            "vehicle": vehicle_info
        }
```

---

## System Prompt Engineering

### Dynamic System Prompt Builder

```python
# File: server/app/services/system_prompts.py

from typing import Optional, Dict, Any
from datetime import datetime


def build_system_prompt(
    call_type: str,  # "inbound_new", "inbound_existing", "outbound_reminder"
    customer_context: Optional[Dict[str, Any]] = None,
    appointment_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build dynamic system prompt based on call context.

    Args:
        call_type: Type of call scenario
        customer_context: Customer information (if existing customer)
        appointment_context: Appointment details (if outbound call)

    Returns:
        System prompt string
    """
    base_prompt = """
### Role
You are Sophie, an AI assistant working as a receptionist at Bart's Automotive.
Your role is to help customers with service appointments, answer questions about
our services, and provide excellent customer service.

### Persona
- You've been working at Bart's Automotive for over 5 years
- You're knowledgeable about cars and automotive services
- Your tone is friendly, professional, and efficient
- You keep conversations focused and concise
- You ask only one question at a time
- You respond promptly to avoid wasting the customer's time

### Conversation Guidelines
- Always be polite and maintain a medium-paced speaking style
- When the conversation veers off-topic, gently redirect
- Use the customer's first name when speaking to them
- Confirm critical details by repeating them back
- If you don't know something, offer to have someone call them back

### Business Information
- Business name: Bart's Automotive
- Hours: Monday-Friday 8AM-6PM, Saturday 9AM-3PM, Closed Sunday
- Services: Oil changes, brake service, tire service, inspections, engine diagnostics, general repairs
- Address: 123 Main Street, Springfield, IL 62701

### Function Calling
You have access to these tools:
- lookup_customer: Look up customer by phone number
- get_available_slots: Check available appointment times
- book_appointment: Book a service appointment
- get_upcoming_appointments: Check customer's upcoming appointments
- cancel_appointment: Cancel an appointment
- reschedule_appointment: Move appointment to new time
- decode_vin: Get vehicle information from VIN

Use these tools when needed to help customers efficiently.
"""

    # Add context based on call type
    if call_type == "inbound_new":
        context = """
### Current Situation
This is a NEW CUSTOMER calling. Their phone number is not in our system.

### Your Goal
1. Welcome them warmly
2. Understand what service they need
3. Collect their information:
   - First and last name
   - Phone number (confirm)
   - Email address
   - Vehicle information (year, make, model, VIN if available)
4. Schedule their appointment
5. Confirm all details clearly
"""

    elif call_type == "inbound_existing" and customer_context:
        context = f"""
### Current Situation
This is an EXISTING CUSTOMER: {customer_context.get('name')}

### Customer Context
- Last service: {customer_context.get('last_service_date', 'No previous service')}
- Vehicles on file: {customer_context.get('vehicles', 'No vehicles listed')}
- Customer since: {customer_context.get('customer_since', 'Unknown')}

### Your Goal
1. Greet them by name warmly
2. Reference their history if relevant
3. Understand their needs
4. Help them schedule/modify appointments efficiently
"""

    elif call_type == "outbound_reminder" and appointment_context:
        context = f"""
### Current Situation
You are CALLING THE CUSTOMER to remind them about their appointment.

### Appointment Details
- Customer: {appointment_context.get('customer_name')}
- Service: {appointment_context.get('service_type')}
- Time: {appointment_context.get('appointment_time')}
- Vehicle: {appointment_context.get('vehicle')}

### Your Goal
1. Greet them briefly (respect their time)
2. Remind them of their appointment tomorrow
3. Confirm they can still make it
4. Reschedule if needed
5. Keep it brief and professional
"""

    else:
        context = """
### Current Situation
This is an inbound call. Determine the customer's needs and help accordingly.
"""

    return base_prompt + "\n" + context


# Example system prompts for different scenarios

INBOUND_NEW_CUSTOMER_PROMPT = build_system_prompt("inbound_new")

INBOUND_EXISTING_CUSTOMER_PROMPT = """
You are Sophie, a friendly receptionist at Bart's Automotive. {customer_name}
is calling - they've been a customer since {customer_since}.

CUSTOMER CONTEXT:
- Last service: {last_service} on {last_service_date}
- Vehicles: {vehicles}
- Upcoming appointments: {upcoming_appointments}

Your goal is to greet them by name, understand their needs, and help them
efficiently with appointments or service questions. Reference their history
when relevant to provide personalized service.
"""

OUTBOUND_REMINDER_PROMPT = """
You are Sophie from Bart's Automotive. You're calling {customer_name} to
remind them about their appointment TOMORROW.

APPOINTMENT DETAILS:
- Service: {service_type}
- Time: {appointment_time}
- Vehicle: {vehicle}

Your goal:
1. Greet them briefly (respect their time)
2. Remind them of the appointment
3. Confirm they can still make it
4. Reschedule if needed

Keep it brief and professional - they're busy.
"""
```

---

## Integration Points

### How OpenAI Service Connects to Other Components

```python
# File: server/app/routes/voice.py (WebSocket handler)

from app.services.openai_service import OpenAIService
from app.services.deepgram_stt import DeepgramSTTService
from app.services.deepgram_tts import DeepgramTTSService  # Feature 4
from app.services.tool_router import ToolRouter
from app.services.system_prompts import build_system_prompt


@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    """
    Main WebSocket handler for voice calls.

    Integration flow:
    1. Initialize services (STT, OpenAI, TTS, ToolRouter)
    2. Set system prompt
    3. Register tools with OpenAI service
    4. Process audio loop:
       a. Twilio audio → STT
       b. STT transcript → OpenAI
       c. OpenAI response → TTS
       d. TTS audio → Twilio
    """
    await websocket.accept()

    # Get database session
    db_session = await get_db_session()

    # Initialize services
    stt = DeepgramSTTService(api_key=settings.DEEPGRAM_API_KEY)
    openai_svc = OpenAIService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        temperature=0.8,
    )
    tts = DeepgramTTSService(api_key=settings.DEEPGRAM_API_KEY)
    tool_router = ToolRouter(db_session=db_session)

    # Set system prompt
    system_prompt = build_system_prompt("inbound_new")
    openai_svc.set_system_prompt(system_prompt)

    # Register tools
    for tool_schema in TOOL_SCHEMAS:
        func_def = tool_schema["function"]
        openai_svc.register_tool(
            name=func_def["name"],
            description=func_def["description"],
            parameters=func_def["parameters"],
            handler=lambda **kwargs: tool_router.execute(
                function_name=func_def["name"],
                **kwargs
            )
        )

    # Connect services
    await stt.connect()
    await tts.connect()

    try:
        # Main audio processing loop
        while True:
            # 1. Get audio from Twilio
            data = await websocket.receive_json()

            if data["event"] == "media":
                audio_payload = data["media"]["payload"]

                # 2. Send to STT
                await stt.send_audio(base64.b64decode(audio_payload))

                # 3. Check for transcript
                transcript = await stt.get_transcript()
                if transcript and transcript["speech_final"]:
                    user_text = transcript["text"]
                    logger.info(f"User said: {user_text}")

                    # 4. Add to conversation
                    openai_svc.add_user_message(user_text)

                    # 5. Generate AI response
                    async for event in openai_svc.generate_response(stream=True):
                        if event["type"] == "content_delta":
                            # 6. Send text to TTS
                            await tts.send_text(event["text"])

                            # 7. Get audio from TTS
                            audio_chunk = await tts.get_audio()
                            if audio_chunk:
                                # 8. Send to Twilio
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": base64.b64encode(audio_chunk).decode()
                                    }
                                })

                        elif event["type"] == "tool_call":
                            logger.info(f"Tool call: {event['name']}")

                        elif event["type"] == "done":
                            logger.info("Response complete")

            elif data["event"] == "stop":
                break

    finally:
        await stt.close()
        await tts.close()
        await db_session.close()
```

---

## Token Usage Tracking

### Token Counter Implementation

```python
# File: server/app/services/openai_service.py (add to class)

class OpenAIService:
    # ... (existing code)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Rule of thumb: ~4 characters per token
        For accurate counting, use tiktoken library
        """
        return len(text) // 4

    def get_conversation_token_count(self) -> int:
        """
        Estimate total tokens in conversation history.
        """
        total = 0
        for msg in self.messages:
            if isinstance(msg.get("content"), str):
                total += self.estimate_tokens(msg["content"])
        return total

    def should_trim_history(self, max_tokens: int = 4000) -> bool:
        """
        Check if conversation history should be trimmed.
        """
        return self.get_conversation_token_count() > max_tokens
```

---

## Error Handling

### Error Handling Strategy

```python
# File: server/app/services/openai_service.py

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

class OpenAIService:
    # ... (existing code)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_response(self, stream: bool = True):
        """
        Generate response with retry logic.
        """
        try:
            # ... (existing implementation)
            pass

        except openai.APIError as e:
            # API errors (500, 503, etc.)
            logger.error(f"OpenAI API error: {e}")
            yield {
                "type": "error",
                "message": "I'm having trouble connecting to my servers. Please try again."
            }

        except openai.RateLimitError as e:
            # Rate limit exceeded
            logger.error(f"OpenAI rate limit: {e}")
            yield {
                "type": "error",
                "message": "I'm experiencing high demand. Please hold for a moment."
            }

        except openai.InvalidRequestError as e:
            # Invalid request (bad params)
            logger.error(f"Invalid request: {e}")
            yield {
                "type": "error",
                "message": "I apologize, but I encountered an issue. Let me transfer you to someone who can help."
            }

        except Exception as e:
            # Catch-all
            logger.error(f"Unexpected error: {e}")
            yield {
                "type": "error",
                "message": "I apologize for the inconvenience. Let me have someone call you back."
            }
```

---

## Implementation Steps

### Step-by-Step Implementation Plan

#### Phase 1: Core OpenAI Service (2-3 hours)

**Step 1.1: Create OpenAIService class** (45 min)
- [ ] Create `server/app/services/openai_service.py`
- [ ] Implement `__init__`, `set_system_prompt`, `register_tool`
- [ ] Implement conversation history methods
- [ ] Add token usage tracking
- [ ] Test with simple prompts

**Step 1.2: Implement streaming response** (1 hour)
- [ ] Implement `generate_response()` with streaming
- [ ] Handle content deltas
- [ ] Handle tool calls
- [ ] Add finish_reason handling
- [ ] Test with mock streaming

**Step 1.3: Add tool execution** (45 min)
- [ ] Implement `_execute_tool()` method
- [ ] Add tool call message formatting
- [ ] Add tool result message formatting
- [ ] Test recursive call pattern (tool → result → verbal response)

**Step 1.4: Error handling** (30 min)
- [ ] Add retry logic with tenacity
- [ ] Handle API errors gracefully
- [ ] Add timeout handling
- [ ] Test error scenarios

#### Phase 2: Tool Definitions & Router (1-2 hours)

**Step 2.1: Create tool schemas** (30 min)
- [ ] Create `server/app/services/tool_definitions.py`
- [ ] Define all tool schemas (7 tools)
- [ ] Validate schema format
- [ ] Document tool descriptions

**Step 2.2: Implement ToolRouter** (1 hour)
- [ ] Create `server/app/services/tool_router.py`
- [ ] Implement tool registry pattern
- [ ] Connect to existing CRM tools
- [ ] Add error handling for tool execution
- [ ] Test each tool individually

**Step 2.3: Format tool results** (30 min)
- [ ] Implement result formatting
- [ ] Handle null/missing data
- [ ] Format for LLM consumption
- [ ] Test with various scenarios

#### Phase 3: System Prompts & Context (1 hour)

**Step 3.1: Build system prompts** (30 min)
- [ ] Create `server/app/services/system_prompts.py`
- [ ] Implement base prompt template
- [ ] Add context builders for each call type
- [ ] Reference call-flows-and-scripts.md

**Step 3.2: Dynamic prompt injection** (30 min)
- [ ] Implement customer context injection
- [ ] Implement appointment context injection
- [ ] Test prompt generation
- [ ] Validate tone and instructions

#### Phase 4: Integration Testing (1 hour)

**Step 4.1: Unit tests** (30 min)
- [ ] Test OpenAIService methods
- [ ] Test ToolRouter execution
- [ ] Test system prompt generation
- [ ] Mock OpenAI API responses

**Step 4.2: Integration test** (30 min)
- [ ] Create `scripts/test_openai_service.py`
- [ ] Test full conversation flow
- [ ] Test tool calling chain
- [ ] Measure response times

---

## Files to Create/Modify

### New Files

1. **`server/app/services/openai_service.py`** (350 lines)
   - OpenAIService class
   - Streaming response handling
   - Tool execution logic
   - Conversation management

2. **`server/app/services/tool_definitions.py`** (200 lines)
   - Tool schema definitions
   - Parameter descriptions
   - Validation rules

3. **`server/app/services/tool_router.py`** (250 lines)
   - ToolRouter class
   - Tool execution handlers
   - Error handling

4. **`server/app/services/system_prompts.py`** (200 lines)
   - System prompt templates
   - Context builders
   - Dynamic injection

5. **`scripts/test_openai_service.py`** (150 lines)
   - Unit tests
   - Integration tests
   - Mock conversations

### Files to Modify

1. **`server/app/services/__init__.py`**
   - Export OpenAIService
   - Export ToolRouter

2. **`server/app/config.py`**
   - Already has OPENAI_API_KEY
   - Already has OPENAI_MODEL
   - No changes needed

3. **`server/requirements.txt`**
   - Already has openai==1.57.2
   - Add tenacity==9.0.0 (already present)
   - No changes needed

4. **`server/app/routes/voice.py`** (modify in Feature 8)
   - Integration point for OpenAI service
   - Will be modified in Feature 8

---

## Testing Strategy

### Unit Tests

```python
# File: scripts/test_openai_service.py

import asyncio
import pytest
from app.services.openai_service import OpenAIService
from app.services.tool_router import ToolRouter


@pytest.mark.asyncio
async def test_openai_service_init():
    """Test OpenAI service initialization."""
    service = OpenAIService(api_key="test-key")
    assert service.model == "gpt-4o"
    assert service.temperature == 0.8
    assert len(service.messages) == 0


@pytest.mark.asyncio
async def test_set_system_prompt():
    """Test system prompt setting."""
    service = OpenAIService(api_key="test-key")
    service.set_system_prompt("You are a helpful assistant")

    assert len(service.messages) == 1
    assert service.messages[0]["role"] == "system"


@pytest.mark.asyncio
async def test_add_messages():
    """Test message history management."""
    service = OpenAIService(api_key="test-key")

    service.add_user_message("Hello")
    assert len(service.messages) == 1
    assert service.messages[0]["role"] == "user"

    service.add_assistant_message("Hi there!")
    assert len(service.messages) == 2
    assert service.messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_tool_registration():
    """Test tool registration."""
    service = OpenAIService(api_key="test-key")

    async def mock_tool(arg: str):
        return {"result": arg}

    service.register_tool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        handler=mock_tool,
    )

    assert "test_tool" in service.tool_registry
    assert len(service.tool_schemas) == 1


@pytest.mark.asyncio
async def test_streaming_response():
    """Test streaming response generation (mock)."""
    # This test requires mocking the OpenAI API
    # or using a test API key
    pass


@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool execution flow."""
    # Mock tool execution
    pass
```

### Integration Test

```python
# File: scripts/test_openai_integration.py

import asyncio
from app.services.openai_service import OpenAIService
from app.services.tool_router import ToolRouter
from app.services.system_prompts import build_system_prompt
from app.config import settings


async def test_full_conversation():
    """
    Test full conversation flow with OpenAI.

    Scenario: Customer calls to book oil change
    """
    # Initialize service
    service = OpenAIService(
        api_key=settings.OPENAI_API_KEY,
        model="gpt-4o",
    )

    # Set system prompt
    prompt = build_system_prompt("inbound_new")
    service.set_system_prompt(prompt)

    # Simulate conversation
    print("\n=== Starting Conversation ===\n")

    # User: Initial greeting
    service.add_user_message("Hi, I need to schedule an oil change")

    # Generate response
    full_response = ""
    async for event in service.generate_response(stream=True):
        if event["type"] == "content_delta":
            print(event["text"], end="", flush=True)
            full_response += event["text"]
        elif event["type"] == "done":
            print(f"\n\n[Tokens used: {event['usage']}]")

    print(f"\n\nAssistant: {full_response}\n")

    # Continue conversation...
    # (Add more turns to test booking flow)


if __name__ == "__main__":
    asyncio.run(test_full_conversation())
```

### Performance Testing

```python
# Measure response latency

import time

async def measure_latency():
    """Measure time to first token and total response time."""
    service = OpenAIService(api_key=settings.OPENAI_API_KEY)
    service.set_system_prompt("You are a helpful assistant.")
    service.add_user_message("Say hello")

    start_time = time.time()
    first_token_time = None

    async for event in service.generate_response(stream=True):
        if event["type"] == "content_delta" and first_token_time is None:
            first_token_time = time.time() - start_time
            print(f"Time to first token: {first_token_time:.3f}s")

        if event["type"] == "done":
            total_time = time.time() - start_time
            print(f"Total response time: {total_time:.3f}s")
```

---

## Estimated Time

### Breakdown

| Task | Estimated Time |
|------|----------------|
| Phase 1: Core OpenAI Service | 2-3 hours |
| Phase 2: Tool Definitions & Router | 1-2 hours |
| Phase 3: System Prompts | 1 hour |
| Phase 4: Testing | 1 hour |
| **Total** | **5-7 hours** |

### Critical Path

1. **OpenAIService class** → Required for all other work
2. **Streaming response** → Core functionality
3. **Tool execution** → Function calling support
4. **ToolRouter** → Connects to CRM/Calendar tools
5. **System prompts** → Conversation quality
6. **Testing** → Validation

### Dependencies

**Blocks:**
- Feature 8 (WebSocket Handler) - Needs OpenAI service for orchestration
- Feature 10 (Conversation Flow) - Needs system prompts and tool calling

**Blocked by:**
- Feature 4 (Deepgram TTS) - Needed for end-to-end testing but not required for OpenAI implementation

**Can work in parallel with:**
- Feature 6 (CRM Tools) - ToolRouter can use mock handlers during development
- Feature 7 (Google Calendar) - Same as above

---

## Success Criteria

### Functional Requirements

- [ ] OpenAI service successfully connects and generates responses
- [ ] Streaming responses work with <500ms to first token
- [ ] Function calling works for all 7 tool definitions
- [ ] Tool execution completes and returns results to LLM
- [ ] LLM generates verbal response after tool execution
- [ ] Conversation history maintained correctly
- [ ] System prompts inject correctly
- [ ] Token usage tracked accurately

### Performance Requirements

- [ ] Time to first token: <500ms (target)
- [ ] Full response generation: <3 seconds for non-tool calls
- [ ] Tool execution + verbal response: <5 seconds total
- [ ] Memory usage: <100MB per conversation
- [ ] No memory leaks in long conversations

### Quality Requirements

- [ ] Error handling for API failures
- [ ] Retry logic for transient errors
- [ ] Graceful degradation when tools fail
- [ ] Clear logging for debugging
- [ ] Type hints and docstrings for all methods

### Integration Requirements

- [ ] Compatible with DeepgramSTTService pattern
- [ ] Ready for DeepgramTTSService integration
- [ ] Database session handling for tools
- [ ] WebSocket-friendly async design

---

## Known Limitations & Future Enhancements

### Current Limitations

1. **No barge-in handling** - OpenAI service doesn't handle interruptions (handled in Feature 8)
2. **Fixed conversation window** - No intelligent summarization yet
3. **No caching** - Could cache system prompts and tool schemas
4. **No parallel tool calls** - Executes tools sequentially
5. **Basic error recovery** - Could be more sophisticated

### Future Enhancements

1. **Conversation summarization** - Summarize old messages to stay under token limit
2. **Tool result caching** - Cache frequent queries (customer lookup)
3. **Parallel tool execution** - When tools don't depend on each other
4. **Adaptive prompting** - Adjust system prompt based on conversation state
5. **A/B testing framework** - Test different prompts and temperatures
6. **Cost optimization** - Use cheaper models for simple queries
7. **Streaming tool calls** - Stream tool results as they execute

---

## Risk Analysis

### High Risk Items

1. **API Rate Limits**
   - **Risk:** Hitting OpenAI rate limits during high call volume
   - **Mitigation:** Implement rate limiting, retry with exponential backoff
   - **Monitoring:** Track API errors and response times

2. **Tool Execution Latency**
   - **Risk:** Tool execution takes too long, user perceives delay
   - **Mitigation:** Optimize database queries, add timeout limits
   - **Monitoring:** Track tool execution times

3. **Token Overflow**
   - **Risk:** Conversation history exceeds token limit
   - **Mitigation:** Implement conversation trimming, summarization
   - **Monitoring:** Track conversation token counts

### Medium Risk Items

1. **Tool Execution Errors**
   - **Risk:** Tool fails, LLM gets error response
   - **Mitigation:** Graceful error handling, fallback responses
   - **Monitoring:** Log tool execution failures

2. **Inconsistent Responses**
   - **Risk:** LLM generates off-brand or inappropriate responses
   - **Mitigation:** Careful system prompt engineering, testing
   - **Monitoring:** Review conversation logs

### Low Risk Items

1. **Model Deprecation**
   - **Risk:** gpt-4o model deprecated
   - **Mitigation:** Design for easy model swapping
   - **Monitoring:** Track OpenAI announcements

---

## Reference Implementation Patterns

### From Barty-Bart Repository (index.js)

**Key patterns extracted:**

1. **Tool Call Detection** (lines 262-270):
```javascript
if (response.type === 'response.function_call_arguments.done') {
    const functionName = response.name;
    const args = JSON.parse(response.arguments);
    // Execute tool...
}
```

2. **Tool Result Handling** (lines 307-320):
```javascript
const functionOutputEvent = {
    type: "conversation.item.create",
    item: {
        type: "function_call_output",
        role: "system",
        output: answerMessage,
    }
};
openAiWs.send(JSON.stringify(functionOutputEvent));

// Trigger response generation
openAiWs.send(JSON.stringify({
    type: "response.create",
    response: {
        modalities: ["text", "audio"],
        instructions: `Respond based on: ${answerMessage}`,
    }
}));
```

3. **System Message Configuration** (lines 30-55):
```javascript
const SYSTEM_MESSAGE = `
### Role
You are an AI assistant named Sophie, working at Bart's Automotive...

### Conversation Guidelines
- Always be polite and maintain a medium-paced speaking style
- When the conversation veers off-topic, gently bring it back...
`;
```

### Adaptation for Python + Standard API

**Key differences:**

1. **Realtime API → Chat Completions API**
   - Realtime: WebSocket with audio
   - Chat: HTTP POST with text
   - Our approach: Streaming for low latency

2. **Function Calling Format**
   - Realtime: Custom event format
   - Chat: Standard `tool_calls` in response
   - Our approach: Parse streaming deltas

3. **Conversation Management**
   - Realtime: Server maintains state
   - Chat: Client sends full history
   - Our approach: Maintain message list locally

---

## Memory Bank Update

After implementation, update the memory bank:

```markdown
# Feature 5: OpenAI GPT-4o Integration - Completion

## Implementation Summary

Completed implementation of OpenAI GPT-4o integration for the automotive voice agent.

### What Was Built

1. **OpenAIService class** (`server/app/services/openai_service.py`)
   - Streaming response generation
   - Function calling with inline execution
   - Conversation history management
   - Token usage tracking

2. **ToolRouter** (`server/app/services/tool_router.py`)
   - Function name → Python handler mapping
   - Database session injection
   - Error handling for tool failures

3. **Tool Definitions** (`server/app/services/tool_definitions.py`)
   - 7 tool schemas for OpenAI function calling
   - Comprehensive parameter validation

4. **System Prompts** (`server/app/services/system_prompts.py`)
   - Dynamic prompt generation
   - Context injection for different call types

### Architecture Decisions

- **Standard Chat Completions API** instead of Realtime API
  - Rationale: Better control, proven pattern, easier function calling

- **Inline tool execution** instead of queue-based
  - Rationale: Lower latency (<300ms vs >500ms)

- **Streaming responses** for low latency
  - Rationale: ~500ms to first token vs ~2s for full response

### Performance Results

- Time to first token: [TBD]
- Tool execution latency: [TBD]
- Token usage per conversation: [TBD]

### Integration Status

- ✅ Connects to existing CRM tools
- ✅ Compatible with STT service pattern
- ⏳ Ready for TTS integration (Feature 4)
- ⏳ Ready for WebSocket handler (Feature 8)

### Known Issues

- [List any issues encountered]

### Next Steps

1. Implement Feature 4 (Deepgram TTS)
2. Integrate in Feature 8 (WebSocket Handler)
3. Test end-to-end conversation flow
```

---

## Conclusion

This implementation plan provides a comprehensive roadmap for Feature 5: OpenAI GPT-4o Integration. The design follows proven patterns from the reference repository while adapting them for Python and the standard Chat Completions API.

**Key Success Factors:**

1. **Streaming for low latency** - Critical for conversational experience
2. **Inline tool execution** - Keeps latency under 300ms
3. **Flexible system prompts** - Enables context-aware conversations
4. **Robust error handling** - Graceful degradation when issues occur
5. **Clean integration points** - Works with existing services

**Next Agent Instructions:**

1. Start with Phase 1 (Core OpenAI Service)
2. Test each method individually before moving on
3. Use mock responses for initial testing
4. Create integration test with real API key once basics work
5. Measure and log response times throughout
6. Update memory bank after completion

**Estimated Timeline:** 5-7 hours

**Dependencies:** None (can start immediately)

**Blocks:** Features 8 (WebSocket Handler), 10 (Conversation Flow)

---

**Document Status:** Complete and ready for implementation
**Created:** 2025-01-12
**Author:** Planning Agent
**Next Action:** Implement Phase 1 (Core OpenAI Service)
