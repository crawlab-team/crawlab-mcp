# LLM Providers for Crawlab MCP

This module provides a flexible way to use different LLM (Large Language Model) providers with the Crawlab MCP client.

## Supported Providers

The following LLM providers are supported:

| Provider     | Type           | Description                         | Tool Support              |
|--------------|----------------|-------------------------------------|---------------------------|
| Azure OpenAI | `azure_openai` | Microsoft's Azure-hosted OpenAI API | Yes (GPT-3.5/4)           |
| OpenAI       | `openai`       | OpenAI's API (GPT models)           | Yes (GPT-3.5/4)           |
| Anthropic    | `anthropic`    | Anthropic's API for Claude models   | Limited*                  |
| Claude       | `claude`       | Alias for Anthropic                 | Limited*                  |
| Together AI  | `together`     | Together AI API for various models  | Partial (model-dependent) |
| Groq         | `groq`         | Groq API for fast LLM inference     | Yes (Llama/Mixtral)       |
| Mistral      | `mistral`      | Mistral AI API                      | Yes (most models)         |
| Aliyun Qwen  | `aliyun_qwen`  | Alibaba Cloud Qwen models API       | Yes (Qwen models)         |
| DeepSeek     | `deepseek`     | DeepSeek AI API                     | Yes (Chat/Coder models)   |
| Custom       | `custom`       | Any OpenAI-compatible API           | Varies                    |

*Anthropic/Claude uses a different format for tools, so the OpenAI-style function calling is not directly compatible.

## Tool Support

Tool support (function calling) varies across different LLM providers and models. The system attempts to handle this
gracefully:

1. For each provider, we check if it supports tool/function calling
2. For models within a provider, we check if they support tools
3. If tools are not supported, they're automatically disabled
4. In case of runtime errors with tools, the system falls back to non-tool mode

### Tool Support by Provider:

1. **Azure OpenAI & OpenAI**: Full support with GPT-3.5-Turbo and GPT-4 models
2. **Together.ai**: Supports most models except some (like Falcon)
3. **Groq**: Supports Llama-3 and Mixtral models
4. **Mistral AI**: Supports function calling on Mistral Large/Medium/Small models
5. **Aliyun Qwen**: Supports function calling on Qwen-Max, Qwen-Plus, and Qwen-Turbo models
6. **DeepSeek**: Supports function calling on DeepSeek Chat, Coder, V3, and R1 models
7. **Anthropic/Claude**: Uses a different tool format, not compatible with OpenAI-style function calling

## Configuration

You can configure the LLM provider in two ways:

1. Using environment variables (recommended)
2. Programmatically by passing configuration to the `create_llm_provider` function

### Environment Variables Configuration

Set the following environment variables to configure your LLM provider:

```
# Set the provider type
LLM_PROVIDER_TYPE=openai  # Options: azure_openai, openai, anthropic, claude, together, groq, mistral, aliyun_qwen, custom

# Provider-specific variables
# Each provider needs its own set of environment variables
```

#### Azure OpenAI

```
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_VERSION=2023-05-15
AZURE_OPENAI_MODEL_NAME=your_deployment_name
```

#### OpenAI

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # Default, change for custom endpoints
OPENAI_MODEL_NAME=gpt-3.5-turbo  # or any other model
```

#### Anthropic/Claude

```
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL_NAME=claude-3-sonnet-20240229  # or any other model
```

#### Together AI

```
TOGETHER_API_KEY=your_api_key
TOGETHER_BASE_URL=https://api.together.xyz
TOGETHER_MODEL_NAME=togethercomputer/llama-2-70b-chat  # or any other model
```

#### Groq

```
GROQ_API_KEY=your_api_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL_NAME=llama-3-8b-8192  # or any other model
```

#### Mistral

```
MISTRAL_API_KEY=your_api_key
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_MODEL_NAME=mistral-large-latest  # or any other model
```

#### Aliyun Qwen

```
ALIYUN_QWEN_API_KEY=your_api_key
ALIYUN_QWEN_BASE_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
ALIYUN_QWEN_MODEL_NAME=qwen-max  # or qwen-plus, qwen-turbo, etc.
```

#### DeepSeek

```
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL_NAME=deepseek-chat  # or deepseek-coder
```

#### Custom OpenAI-compatible Provider

```
CUSTOM_API_KEY=your_api_key
CUSTOM_BASE_URL=https://your-custom-url.com/v1
CUSTOM_MODEL_NAME=your-model-name
```

### Programmatic Configuration

You can also configure the LLM provider programmatically:

```python
from crawlab_mcp.llm_providers import create_llm_provider

# Create a provider with explicit configuration
llm_provider = create_llm_provider(
    provider_type="openai",
    config={
        "api_key": "your_api_key",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-3.5-turbo",
    }
)

# Initialize the provider
await llm_provider.initialize()

# Use the provider
response = await llm_provider.chat_completion(messages=[{"role": "user", "content": "Hello!"}])
```

## Adding New Providers

To add a new OpenAI-compatible provider:

1. Update the `factory.py` file to include the new provider type
2. Add provider-specific environment variables to `constants.py`
3. Update this README with the new provider information

For providers with substantially different APIs, you may need to create a new provider class that implements the
`BaseLLMProvider` interface.