"""
Base LLM provider class that defines the interface for all LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the LLM provider with necessary configurations."""
        pass

    @abstractmethod
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
        """
        Generate a chat completion using the LLM provider.

        Args:
            messages: List of message objects with role and content.
            model: Model ID to use for completion.
            temperature: Sampling temperature between 0 and 2.
            max_tokens: Maximum number of tokens to generate.
            tools: List of tool objects the model may call. Format varies by provider.
                   For OpenAI-compatible providers, this follows the OpenAI function calling format.
            tool_choice: Controls which (if any) tool is called by the model.
                         May be ignored by providers that don't support tool selection.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Response from the LLM provider, normalized to a consistent format:
            {
                "choices": [
                    {
                        "message": {
                            "content": str,  # The response content
                            "role": str,     # The role (usually "assistant")
                            "tool_calls": List[Dict] or None  # Tool calls if any
                        },
                        "index": int,
                        "finish_reason": str
                    }
                ]
            }

            Note: The tool_calls format follows OpenAI's format but may be empty or None
            for providers that don't support tools or if no tools were called.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the default model name for this provider."""
        pass

    def has_tool_support(self) -> bool:
        """
        Check if this provider supports tool/function calling.

        Returns:
            True if the provider supports tools, False otherwise.
        """
        return True  # Default implementation assumes tool support
