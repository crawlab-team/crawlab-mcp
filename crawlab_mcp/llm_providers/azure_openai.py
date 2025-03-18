"""
Azure OpenAI provider implementation.
"""
import logging
from typing import Any, Dict, List, Optional, Union

from openai import AzureOpenAI, NotGiven

from ..utils.constants import PROVIDER_CONFIG
from ..utils.tools import model_supports_tools
from .base import BaseLLMProvider


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI provider implementation."""

    def __init__(self):
        """Initialize the Azure OpenAI provider."""
        self.client = None

        # Get configuration from constants
        azure_config = PROVIDER_CONFIG.get("azure_openai", {})
        self.api_key = azure_config.get("api_key")
        self.endpoint = azure_config.get("endpoint")
        self.api_version = azure_config.get("api_version")
        self.model_name = azure_config.get("model_name")

    async def initialize(self) -> None:
        """Initialize the Azure OpenAI client."""
        if not self.api_key:
            raise ValueError("API key is required for Azure OpenAI provider")
        if not self.endpoint:
            raise ValueError("Endpoint is required for Azure OpenAI provider")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )

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
        """Generate a chat completion using Azure OpenAI."""
        if not self.client:
            await self.initialize()

        # Use default model if not specified
        model_to_use = model or self.model_name

        # Handle NotGiven case for tool_choice
        if tool_choice == "none":
            tool_choice = NotGiven()

        # Check if model supports tools
        if tools and not self._model_supports_tools(model_to_use):
            # If model doesn't support tools, don't send tools parameter
            tools = None
            tool_choice = NotGiven()

        # Prepare request parameters
        request_params = {
            "model": model_to_use,
            "messages": messages,
        }

        # Add optional parameters if specified
        if temperature is not None:
            request_params["temperature"] = temperature
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens

        # Add tool parameters if supported
        if tools:
            request_params["tools"] = tools
            if tool_choice is not None and tool_choice != "none":
                request_params["tool_choice"] = tool_choice
        logging.info(f"Request params: {request_params}")

        # Add any other kwargs
        request_params.update(kwargs)

        # Create chat completion
        response = self.client.chat.completions.create(**request_params)
        return response.model_dump()

    def _model_supports_tools(self, model_name: str) -> bool:
        """Check if the specific model supports tools/function calling."""
        # Use the model_supports_tools function
        return model_supports_tools(model_name)

    def get_model_name(self) -> str:
        """Get the default model name."""
        return self.model_name

    def has_tool_support(self) -> bool:
        """Check if this provider supports tool/function calling."""
        return True
