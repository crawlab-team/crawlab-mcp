"""
Factory function for creating LLM providers.
"""

import importlib
import os
from typing import Any, Dict, Optional

from ..utils.constants import LLM_PROVIDER_TYPE, PROVIDER_CONFIG
from .azure_openai import AzureOpenAIProvider
from .base import BaseLLMProvider
from .openai_compatible import OpenAICompatibleProvider

# Import Anthropic provider conditionally
try:
    from .anthropic import ANTHROPIC_AVAILABLE, AnthropicProvider
except ImportError:
    ANTHROPIC_AVAILABLE = False


def create_llm_provider(
    provider_type: Optional[str] = None, config: Optional[Dict[str, Any]] = None
) -> BaseLLMProvider:
    """
    Create an LLM provider based on configuration.

    Args:
        provider_type: Type of provider to create. If None, will try to determine from environment.
        config: Configuration for the provider. If None, will use environment variables.

    Returns:
        An instance of BaseLLMProvider.
    """
    # Use environment variable if provider_type not specified
    if not provider_type:
        provider_type = os.getenv("LLM_PROVIDER_TYPE", LLM_PROVIDER_TYPE).lower()

    # Use empty dict if config not specified
    config = config or {}

    # Get provider configuration from constants
    if provider_type in PROVIDER_CONFIG:
        provider_config = PROVIDER_CONFIG[provider_type].copy()

        # Override with user-provided config
        for key, value in config.items():
            provider_config[key] = value

        # Get provider class name and create appropriate instance
        class_name = provider_config.pop("class_name")

        # Special handling for Anthropic provider
        if class_name == "AnthropicProvider" and not ANTHROPIC_AVAILABLE:
            print(
                "Warning: Anthropic package not available. Using OpenAI-compatible provider instead."
            )
            print(
                "To use the native Anthropic provider, install the anthropic package: pip install anthropic"
            )
            provider_name = provider_config.pop("provider_name", "ANTHROPIC")
            return OpenAICompatibleProvider(provider_name=provider_name, **provider_config)

        # Create appropriate provider instance
        if class_name == "AzureOpenAIProvider":
            return AzureOpenAIProvider()
        elif class_name == "OpenAICompatibleProvider":
            provider_name = provider_config.pop("provider_name", None)
            return OpenAICompatibleProvider(provider_name=provider_name, **provider_config)
        elif class_name == "AnthropicProvider":
            provider_name = provider_config.pop("provider_name", "ANTHROPIC")
            return AnthropicProvider(provider_name=provider_name, **provider_config)
        else:
            # Try to dynamically import and instantiate other provider classes
            try:
                module = importlib.import_module(".." + class_name.lower(), __name__)
                provider_class = getattr(module, class_name)
                return provider_class(**provider_config)
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Unable to instantiate provider class {class_name}: {str(e)}")
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")
