"""
LLM providers module for Crawlab MCP.
This module contains classes for different LLM providers with a common interface.
"""

from .azure_openai import AzureOpenAIProvider
from .base import BaseLLMProvider
from .factory import create_llm_provider
from .openai_compatible import OpenAICompatibleProvider

# Conditionally import Anthropic provider if available
try:
    from .anthropic import AnthropicProvider

    __anthropic_available__ = True
except ImportError:
    # Create a placeholder if Anthropic is not available
    AnthropicProvider = None
    __anthropic_available__ = False

__all__ = [
    "BaseLLMProvider",
    "AzureOpenAIProvider",
    "OpenAICompatibleProvider",
    "create_llm_provider",
]

# Add Anthropic provider if available
if __anthropic_available__:
    __all__.append("AnthropicProvider")
