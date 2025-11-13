"""
OpenAI GPT-4o service for conversational AI with function calling.

This service handles streaming response generation, function calling with inline
execution, conversation history management, and token usage tracking using the
standard Chat Completions API.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List, Callable, AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    OpenAI GPT-4o service for conversational AI with function calling.

    Uses standard Chat Completions API with streaming for:
    - Real-time response generation
    - Function calling with inline execution
    - Conversation history management
    - Token usage tracking

    Example usage:
        service = OpenAIService(api_key="sk-...")
        service.set_system_prompt("You are a helpful assistant")
        service.register_tool(name="tool1", ...)
        service.add_user_message("Hello")

        async for event in service.generate_response(stream=True):
            if event["type"] == "content_delta":
                print(event["text"])
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
            temperature: Sampling temperature 0.0-2.0 (default: 0.8)
            max_tokens: Maximum tokens per response (default: 1000)
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
            name: Function name (e.g., "lookup_customer")
            description: What the function does
            parameters: JSON schema for parameters
            handler: Async function to execute when called

        Example:
            async def my_tool(arg1: str) -> Dict:
                return {"result": arg1}

            service.register_tool(
                name="my_tool",
                description="Does something useful",
                parameters={"type": "object", "properties": {...}},
                handler=my_tool
            )
        """
        # Store handler
        self.tool_registry[name] = handler

        # Store schema in OpenAI format
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

        Yields events with one of these types:
            - "content_delta": Text chunk for TTS
                {"type": "content_delta", "text": str}
            - "tool_call": Tool execution started
                {"type": "tool_call", "name": str, "arguments": str, "call_id": str}
            - "tool_result": Tool execution completed
                {"type": "tool_result", "result": str, "call_id": str}
            - "error": Error occurred
                {"type": "error", "message": str}
            - "done": Response complete
                {"type": "done", "finish_reason": str, "usage": dict}

        Pattern:
            1. Stream text deltas for TTS immediately
            2. When tool call detected, execute inline
            3. Add tool result to history
            4. Recursively call again to generate verbal response

        Args:
            stream: Whether to use streaming (default: True)

        Yields:
            Event dicts as described above
        """
        try:
            # Create chat completion request
            request_params = {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": stream,
            }

            # Add tools if registered
            if self.tool_schemas:
                request_params["tools"] = self.tool_schemas
                request_params["tool_choice"] = "auto"

            # Make API call
            response_stream = await self.client.chat.completions.create(**request_params)

            # Process stream
            accumulated_content = ""
            tool_calls_accumulator = []

            async for chunk in response_stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Handle content (text) deltas
                if delta.content:
                    accumulated_content += delta.content
                    yield {
                        "type": "content_delta",
                        "text": delta.content,
                    }

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        # Initialize tool call accumulator if needed
                        if tc_delta.index >= len(tool_calls_accumulator):
                            tool_calls_accumulator.append({
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            })

                        # Accumulate tool call data
                        if tc_delta.id:
                            tool_calls_accumulator[tc_delta.index]["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            tool_calls_accumulator[tc_delta.index]["name"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_calls_accumulator[tc_delta.index]["arguments"] += tc_delta.function.arguments

                # Handle finish reason
                if finish_reason:
                    # Track usage if available
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

                            # Notify that tool is being called
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

                            # Notify that tool completed
                            yield {
                                "type": "tool_result",
                                "result": result,
                                "call_id": tool_call["id"],
                            }

                        # Make recursive call to generate verbal response based on tool results
                        logger.info("Tool execution complete, generating verbal response")
                        async for event in self.generate_response(stream=stream):
                            yield event
                        return

                    elif finish_reason == "stop":
                        # Natural completion - add to history
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

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
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
            JSON string of result (or error)
        """
        try:
            # Parse arguments
            args = json.loads(function_arguments)

            # Get handler
            handler = self.tool_registry.get(function_name)
            if not handler:
                error_result = {"error": f"Function {function_name} not found"}
                return json.dumps(error_result)

            # Execute handler
            logger.info(f"Executing tool: {function_name} with args: {args}")
            result = await handler(**args)

            # Return as JSON string
            return json.dumps(result)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON arguments for {function_name}: {e}")
            return json.dumps({"error": f"Invalid arguments: {str(e)}"})
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get full conversation history.

        Returns:
            List of message dicts (copy, not reference)
        """
        return self.messages.copy()

    def clear_history(self, keep_system: bool = True) -> None:
        """
        Clear conversation history.

        Args:
            keep_system: Whether to keep system prompt (default: True)
        """
        if keep_system and self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        else:
            self.messages = []
            self.system_prompt = None

        # Reset token counters
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

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

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses rough estimate: ~4 characters per token.
        For accurate counting, use tiktoken library.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def get_conversation_token_count(self) -> int:
        """
        Estimate total tokens in conversation history.

        Returns:
            Estimated token count
        """
        total = 0
        for msg in self.messages:
            content = msg.get("content")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
        return total

    def should_trim_history(self, max_tokens: int = 4000) -> bool:
        """
        Check if conversation history should be trimmed.

        Args:
            max_tokens: Maximum token threshold (default: 4000)

        Returns:
            True if history exceeds threshold
        """
        return self.get_conversation_token_count() > max_tokens

    def trim_history(self, max_messages: int = 20, keep_system: bool = True) -> None:
        """
        Trim conversation history to prevent token overflow.

        Strategy:
        - Always keep system message if specified
        - Keep most recent N messages
        - Ensure tool_call and tool_result pairs are kept together

        Args:
            max_messages: Maximum number of messages to keep (default: 20)
            keep_system: Whether to preserve system message (default: True)
        """
        if len(self.messages) <= max_messages:
            return

        # Separate system message
        system_msg = None
        other_msgs = self.messages

        if keep_system and self.messages and self.messages[0]["role"] == "system":
            system_msg = self.messages[0]
            other_msgs = self.messages[1:]

        # Keep most recent messages
        trimmed = other_msgs[-max_messages:]

        # Prepend system message
        if system_msg:
            self.messages = [system_msg] + trimmed
        else:
            self.messages = trimmed

        logger.info(f"Conversation history trimmed to {len(self.messages)} messages")
