"""
Anthropic/Claude provider implementation with custom tool handling.
"""

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Union

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic/Claude provider implementation with tool support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: str = "ANTHROPIC",
    ):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: API key for Anthropic. If None, will try to get from environment.
            base_url: Base URL for API calls. If None, will use default.
            model_name: Model name to use. If None, will try to get from environment.
            provider_name: Name of the provider (for environment variable naming).
        """
        self.provider_name = provider_name
        self.client = None

        # Get configuration from environment variables or use provided values
        self.api_key = api_key or os.getenv(f"{self.provider_name}_API_KEY")
        self.base_url = base_url or os.getenv(f"{self.provider_name}_BASE_URL")
        self.model_name = model_name or os.getenv(
            f"{self.provider_name}_MODEL_NAME", "claude-3-sonnet-20240229"
        )

        # Tool-related state
        self.tool_map = {}  # Maps our tool IDs to tool definitions

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "The anthropic package is not installed. "
                "Please install it with 'pip install anthropic'"
            )

        if not self.api_key:
            raise ValueError(f"API key is required for {self.provider_name} provider")

        # Create client with appropriate configuration
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any], Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate a chat completion using Anthropic/Claude."""
        if not self.client:
            await self.initialize()

        # Use default model if not specified
        model_to_use = model or self.model_name

        # Convert OpenAI message format to Anthropic message format
        anthropic_messages = self._convert_to_anthropic_messages(messages)

        # Set up request parameters
        request_params = {
            "model": model_to_use,
            "messages": anthropic_messages,
        }

        # Add system prompt if provided
        system = kwargs.pop("system", "")
        if system:
            request_params["system"] = system

        # Add tools if provided and supported
        if tools and self.has_tool_support():
            # Store tools for later reference
            self._register_tools(tools)

            # Convert OpenAI-style tools to Anthropic-style tools
            anthropic_tools = self._convert_to_anthropic_tools(tools)
            if anthropic_tools:
                request_params["tools"] = anthropic_tools

        # Add optional parameters if specified
        if temperature is not None:
            request_params["temperature"] = temperature
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens

        # Add any other kwargs
        request_params.update(kwargs)

        # Create message
        response = await self.client.messages.create(**request_params)

        # Extract and process tool calls from the response
        content = response.content
        tool_calls = []

        for block in content:
            if block.type == "tool_use":
                # Convert Claude's tool_use to OpenAI's tool_calls format
                tool_id = str(uuid.uuid4())
                tool_calls.append(
                    {
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )

        # Return in normalized format matching OpenAI's format
        return {
            "choices": [
                {
                    "message": {
                        "content": self._extract_text_content(content),
                        "role": "assistant",
                        "tool_calls": tool_calls or None,
                    },
                    "index": 0,
                    "finish_reason": response.stop_reason,
                }
            ]
        }

    def get_model_name(self) -> str:
        """Get the default model name."""
        return self.model_name

    def has_tool_support(self) -> bool:
        """Check if this provider supports tool/function calling."""
        # Claude 3 models support tools
        claude3_models = ["claude-3", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
        for model in claude3_models:
            if model in self.model_name.lower():
                return True
        return False

    def _register_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Store tools for later reference."""
        self.tool_map = {}
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                self.tool_map[func.get("name")] = func

    def _convert_to_anthropic_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Anthropic format."""
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map OpenAI roles to Anthropic roles
            if role == "system":
                # System messages are handled separately in Anthropic
                continue
            elif role == "assistant":
                anthropic_role = "assistant"

                # Handle tool calls in assistant messages
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    # Create content with tool_use blocks
                    content_blocks = []

                    # Add text content if present
                    if content:
                        content_blocks.append({"type": "text", "text": content})

                    # Add tool_use blocks
                    for tool_call in tool_calls:
                        if tool_call.get("type") == "function":
                            function = tool_call.get("function", {})
                            name = function.get("name", "")
                            arguments = function.get("arguments", "{}")

                            try:
                                input_data = json.loads(arguments)
                            except json.JSONDecodeError:
                                input_data = {}

                            content_blocks.append(
                                {"type": "tool_use", "name": name, "input": input_data}
                            )

                    anthropic_messages.append({"role": anthropic_role, "content": content_blocks})
                    continue
            elif role == "tool":
                # Convert tool messages to user messages with tool results
                tool_call_id = msg.get("tool_call_id", "unknown")
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "content": content,
                            }
                        ],
                    }
                )
                continue
            else:
                anthropic_role = "user"

            # Add regular message
            anthropic_messages.append({"role": anthropic_role, "content": content})

        return anthropic_messages

    def _convert_to_anthropic_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI tool format to Anthropic tool format."""
        anthropic_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                name = func.get("name", "")
                description = func.get("description", "")
                parameters = func.get("parameters", {})

                anthropic_tool = {
                    "name": name,
                    "description": description,
                    "input_schema": parameters,
                }

                anthropic_tools.append(anthropic_tool)

        return anthropic_tools

    def _extract_text_content(self, content: List[Dict[str, Any]]) -> str:
        """Extract text content from Claude's content blocks."""
        text_parts = []

        for block in content:
            if block.type == "text":
                text_parts.append(block.text)

        return "\n".join(text_parts)
