import os

from dotenv import load_dotenv

load_dotenv()

CRAWLAB_API_BASE_URL = os.getenv("CRAWLAB_API_BASE_URL", "http://localhost:8080/api")
CRAWLAB_API_TOKEN = os.getenv("CRAWLAB_API_TOKEN", "")
CRAWLAB_USERNAME = os.getenv("CRAWLAB_USERNAME", "admin")
CRAWLAB_PASSWORD = os.getenv("CRAWLAB_PASSWORD", "admin")

# LLM Provider Configuration
# Default provider type (azure_openai, openai, anthropic, claude, together, groq, mistral, aliyun_qwen, custom)
LLM_PROVIDER_TYPE = os.getenv("LLM_PROVIDER_TYPE", "azure_openai")

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
AZURE_OPENAI_MODEL_NAME = os.getenv("AZURE_OPENAI_MODEL_NAME", "")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")

# Anthropic/Claude Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-sonnet-20240229")

# Together AI Configuration
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
TOGETHER_BASE_URL = os.getenv("TOGETHER_BASE_URL", "https://api.together.xyz")
TOGETHER_MODEL_NAME = os.getenv("TOGETHER_MODEL_NAME", "togethercomputer/llama-2-70b-chat")

# Groq Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3-8b-8192")

# Mistral Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
MISTRAL_MODEL_NAME = os.getenv("MISTRAL_MODEL_NAME", "mistral-large-latest")

# Aliyun Qwen Configuration
ALIYUN_QWEN_API_KEY = os.getenv("ALIYUN_QWEN_API_KEY", "")
ALIYUN_QWEN_BASE_URL = os.getenv(
    "ALIYUN_QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
ALIYUN_QWEN_MODEL_NAME = os.getenv("ALIYUN_QWEN_MODEL_NAME", "qwen-plus")

# DeepSeek Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

# Custom OpenAI-compatible provider
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "")
CUSTOM_BASE_URL = os.getenv("CUSTOM_BASE_URL", "")
CUSTOM_MODEL_NAME = os.getenv("CUSTOM_MODEL_NAME", "")

PYTHON_KEYWORDS = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
}

# Provider configuration mapping
# This maps provider types to their configuration parameters
PROVIDER_CONFIG = {
    "azure_openai": {
        "api_key": AZURE_OPENAI_API_KEY,
        "endpoint": AZURE_OPENAI_ENDPOINT,
        "api_version": AZURE_OPENAI_API_VERSION,
        "model_name": AZURE_OPENAI_MODEL_NAME,
        "class_name": "AzureOpenAIProvider",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "base_url": OPENAI_BASE_URL,
        "model_name": OPENAI_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "OPENAI",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "anthropic": {
        "api_key": ANTHROPIC_API_KEY,
        "base_url": ANTHROPIC_BASE_URL,
        "model_name": ANTHROPIC_MODEL_NAME,
        "class_name": "AnthropicProvider",
        "provider_name": "ANTHROPIC",
        "supports_tools": True,
        "requires_packages": ["anthropic"],
    },
    "claude": {
        "api_key": ANTHROPIC_API_KEY,
        "base_url": ANTHROPIC_BASE_URL,
        "model_name": ANTHROPIC_MODEL_NAME,
        "class_name": "AnthropicProvider",
        "provider_name": "CLAUDE",
        "supports_tools": True,
        "requires_packages": ["anthropic"],
    },
    "together": {
        "api_key": TOGETHER_API_KEY,
        "base_url": TOGETHER_BASE_URL,
        "model_name": TOGETHER_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "TOGETHER",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "groq": {
        "api_key": GROQ_API_KEY,
        "base_url": GROQ_BASE_URL,
        "model_name": GROQ_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "GROQ",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "mistral": {
        "api_key": MISTRAL_API_KEY,
        "base_url": MISTRAL_BASE_URL,
        "model_name": MISTRAL_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "MISTRAL",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "aliyun_qwen": {
        "api_key": ALIYUN_QWEN_API_KEY,
        "base_url": ALIYUN_QWEN_BASE_URL,
        "model_name": ALIYUN_QWEN_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "ALIYUN_QWEN",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "deepseek": {
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "model_name": DEEPSEEK_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "DEEPSEEK",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
    "custom": {
        "api_key": CUSTOM_API_KEY,
        "base_url": CUSTOM_BASE_URL,
        "model_name": CUSTOM_MODEL_NAME,
        "class_name": "OpenAICompatibleProvider",
        "provider_name": "CUSTOM",
        "supports_tools": True,
        "requires_packages": ["openai"],
    },
}

# Models known to support tools/function calling
MODELS_WITH_TOOL_SUPPORT = {
    # OpenAI models
    "gpt-3.5-turbo": True,
    "gpt-3.5-turbo-0125": True,
    "gpt-4": True,
    "gpt-4-0125-preview": True,
    "gpt-4-turbo": True,
    "gpt-4-turbo-preview": True,
    "gpt-4o": True,
    "gpt-4o-mini": True,
    # Anthropic models
    "claude-3-opus-20240229": True,
    "claude-3-sonnet-20240229": True,
    "claude-3-haiku-20240307": True,
    # Groq models
    "llama-3-8b-8192": True,
    "mixtral-8x7b-32768": True,
    # Mistral models
    "mistral-large-latest": True,
    "mistral-medium-latest": True,
    "mistral-small-latest": True,
    # Aliyun Qwen models
    "qwen-plus": True,
    "qwen-max": True,
    "qwen-turbo": True,
    # DeepSeek models
    "deepseek-chat": True,
    "deepseek-coder": True,
    "deepseek-v3": True,
    "deepseek-r1": True,
}

# Regular expression patterns for models that support tools/function calling
MODEL_TOOL_SUPPORT_PATTERNS = [
    # OpenAI models (gpt-3.5-turbo and gpt-4 families)
    r"^gpt-3\.5-turbo",
    r"^gpt-4",
    # Anthropic models (claude-3 family)
    r"^claude-3",
    # Groq models
    r"^llama-3",
    r"^mixtral-",
    # Mistral models
    r"^mistral-(large|medium|small)",
    # Aliyun Qwen models
    r"^qwen-",
    # DeepSeek models
    r"^deepseek-chat",
    r"^deepseek-coder",
    r"^deepseek-v3",
    r"^deepseek-r1",
    r"^deepseek-ai/deepseek-",
]
