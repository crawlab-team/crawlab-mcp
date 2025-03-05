# Extending LLM Providers

This guide explains how to add new LLM providers to the Crawlab MCP system.

## Adding an OpenAI-Compatible Provider

For providers that follow the OpenAI API format (most do these days), you can easily add support by:

1. Update `constants.py` with environment variables for the new provider:

```python
# New provider configuration
NEW_PROVIDER_API_KEY = os.getenv("NEW_PROVIDER_API_KEY", "")
NEW_PROVIDER_BASE_URL = os.getenv("NEW_PROVIDER_BASE_URL", "https://api.new-provider.com/v1")
NEW_PROVIDER_MODEL_NAME = os.getenv("NEW_PROVIDER_MODEL_NAME", "default-model")
```

2. Add the new provider to the `factory.py` file:

```python
elif provider_type == "new_provider":
    return OpenAICompatibleProvider(
        provider_name="NEW_PROVIDER",
        **config
    )
```

3. Update the README.md file to include the new provider information.

4. Update the `.env.example` file with the new environment variables.

Done! The existing `OpenAICompatibleProvider` class should handle the API calls appropriately.

## Adding a Provider with a Custom API Format

For providers that use a significantly different API format (like Anthropic/Claude), you'll need to:

1. Create a new provider class that implements the `BaseLLMProvider` interface:

```python
class MyCustomProvider(BaseLLMProvider):
    """Custom provider implementation."""

    def __init__(self, api_key=None, model_name=None, **kwargs):
        """Initialize the custom provider."""
        self.api_key = api_key or os.getenv("MY_CUSTOM_API_KEY")
        self.model_name = model_name or os.getenv("MY_CUSTOM_MODEL_NAME")
        self.client = None
        
    async def initialize(self) -> None:
        """Initialize the client."""
        # Your initialization code here
        pass

    async def chat_completion(self, messages, model=None, **kwargs) -> Dict[str, Any]:
        """Generate a chat completion using the custom API."""
        # Custom implementation here
        
        # Return a standardized response format matching OpenAI
        return {
            "choices": [
                {
                    "message": {
                        "content": "Response text",
                        "role": "assistant",
                        "tool_calls": [] # If tools are supported
                    },
                    "index": 0,
                    "finish_reason": "stop"
                }
            ]
        }
    
    def get_model_name(self) -> str:
        """Get the default model name."""
        return self.model_name
        
    def has_tool_support(self) -> bool:
        """Check if this provider supports tool/function calling."""
        # Custom implementation based on your provider
        return False
```

2. Add the new provider to `__init__.py`:

```python
from .my_custom_provider import MyCustomProvider

__all__ = [
    # Existing providers...
    "MyCustomProvider",
]
```

3. Update `factory.py` to use your new provider:

```python
elif provider_type == "my_custom":
    return MyCustomProvider(**config)
```

4. Update the documentation and environment variables as described above.

## Handling Tool Calls

The most complex part of integrating a new provider is often handling tool calls. Providers have different ways of supporting function calling. Your implementation should:

1. Check if the provider actually supports tool calling (`has_tool_support`)
2. Convert the standard tool format to the provider's format (if needed)
3. Process the provider's response to extract any tool calls
4. Convert those tool calls back to the standard format used by the client

See the `AnthropicProvider` implementation for a good example of handling a provider with a custom tool format. 