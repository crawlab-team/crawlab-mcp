"""
OpenAI-compatible provider implementation for various LLM services that follow the OpenAI API format.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from ..utils.tools import model_supports_tools
from .base import BaseLLMProvider

# Configure logging for LLM providers
logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible provider implementation for various LLM services."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
        supports_tools: Optional[bool] = None,
        **kwargs,  # Catch any other parameters not explicitly defined
    ):
        """
        Initialize an OpenAI-compatible provider.

        Args:
            api_key: API key for the provider. If None, will try to get from environment.
            base_url: Base URL for API calls. If None, will try to get from environment.
            model_name: Model name to use. If None, will try to get from environment.
            provider_name: Name of the provider (for environment variable naming).
            supports_tools: Whether this provider supports tools/function calling.
            **kwargs: Additional parameters that may be passed in but not used.
        """
        self.provider_name = provider_name.upper() if provider_name else "OPENAI"
        self.client = None
        self.supports_tools = supports_tools

        # Get configuration from environment variables or use provided values
        self.api_key = api_key or os.getenv(f"{self.provider_name}_API_KEY")
        self.base_url = base_url or os.getenv(f"{self.provider_name}_BASE_URL")
        self.model_name = model_name or os.getenv(
            f"{self.provider_name}_MODEL_NAME", "gpt-3.5-turbo"
        )

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        logger.info(f"Initializing {self.provider_name} provider")

        if not self.api_key:
            logger.warning(
                f"No API key provided for {self.provider_name}. Attempting to use default credentials."
            )

        if self.base_url:
            logger.info(f"Using custom base URL: {self.base_url}")

        try:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"{self.provider_name} client initialized successfully")
            logger.info(f"Using model: {self.model_name}")

            # Log whether this model supports tools
            if self.supports_tools is not None:
                logger.info(f"Tool support explicitly set to: {self.supports_tools}")
            else:
                supports = self._model_supports_tools(self.model_name)
                logger.info(f"Detected tool support for model {self.model_name}: {supports}")
        except Exception as e:
            logger.error(
                f"Failed to initialize {self.provider_name} client: {str(e)}", exc_info=True
            )
            raise

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
        Generate a chat completion using an OpenAI-compatible API.

        Args:
            messages: List of message objects with role and content.
            model: Model ID to use for completion.
            temperature: Sampling temperature between 0 and 2.
            max_tokens: Maximum number of tokens to generate.
            tools: List of tool objects the model may call.
            tool_choice: Controls which (if any) tool is called by the model.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Response from the OpenAI-compatible API.
        """
        if not self.client:
            logger.info("Client not initialized, initializing now")
            await self.initialize()

        # Use default model if not specified
        model_to_use = model or self.model_name
        logger.info(
            f"Making chat completion request to {self.provider_name} with model {model_to_use}"
        )

        # Log message count and roles (but not content for privacy)
        message_roles = [msg.get("role", "unknown") for msg in messages]
        logger.debug(f"Request contains {len(messages)} messages with roles: {message_roles}")

        # Basic parameters that all OpenAI-compatible providers should support
        request_params = {
            "model": model_to_use,
            "messages": messages,
        }

        # Add optional parameters if provided
        if temperature is not None:
            request_params["temperature"] = temperature
            logger.debug(f"Using temperature: {temperature}")
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
            logger.debug(f"Using max_tokens: {max_tokens}")

        # Check if this model supports tools
        if tools and self._model_supports_tools(model_to_use):
            request_params["tools"] = tools
            logger.info(f"Including {len(tools)} tools in request")

            if tool_choice is not None:
                request_params["tool_choice"] = tool_choice
                logger.debug(f"Using tool_choice: {tool_choice}")
        elif tools:
            logger.warning(
                f"Tools provided but model {model_to_use} does not support tools. Ignoring tools."
            )

        # Add any additional parameters
        request_params.update(kwargs)

        # Log any additional parameters (excluding messages for privacy)
        additional_params = {k: v for k, v in kwargs.items() if k != "messages"}
        if additional_params:
            logger.debug(f"Additional parameters: {additional_params}")

        # Make the API call with timing
        start_time = time.time()
        try:
            logger.debug("Sending request to API")
            response = self.client.chat.completions.create(**request_params)

            # Convert to dict for consistency
            response_dict = response.model_dump()

            # Calculate and log request time
            request_time = time.time() - start_time
            logger.info(f"API request completed in {request_time:.2f} seconds")

            # Log response summary
            choices = response_dict.get("choices", [])
            if choices:
                first_choice = choices[0]
                finish_reason = first_choice.get("finish_reason")

                # Check if there are tool calls
                message = first_choice.get("message", {})
                tool_calls = message.get("tool_calls", [])

                if tool_calls:
                    tool_names = [
                        tc.get("function", {}).get("name", "unknown") for tc in tool_calls
                    ]
                    logger.info(f"Response contains {len(tool_calls)} tool calls: {tool_names}")
                else:
                    logger.info(f"Response completed with finish_reason: {finish_reason}")

                # Log token usage
                usage = response_dict.get("usage", {})
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    logger.info(
                        f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
                    )

            return response_dict
        except Exception as e:
            request_time = time.time() - start_time
            logger.error(
                f"API request failed after {request_time:.2f} seconds: {str(e)}", exc_info=True
            )
            raise

    def _model_supports_tools(self, model_name: str) -> bool:
        """Check if the model supports tools/function calling."""
        # If explicitly set, use that value
        if self.supports_tools is not None:
            return self.supports_tools

        # Otherwise use the utility function
        supports = model_supports_tools(model_name)
        logger.debug(f"Model {model_name} tool support check: {supports}")
        return supports

    def get_model_name(self) -> str:
        """Get the current model name."""
        return self.model_name

    def has_tool_support(self) -> bool:
        """Check if the current model supports tools/function calling."""
        return self._model_supports_tools(self.model_name)
