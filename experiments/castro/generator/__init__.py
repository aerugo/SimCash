# LLM integration for structured policy generation

from experiments.castro.generator.providers import (
    LLMProvider,
    StructuredOutputRequest,
    StructuredOutputResponse,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    get_provider,
)

from experiments.castro.generator.client import (
    PolicyContext,
    GenerationResult,
    StructuredPolicyGenerator,
)

from experiments.castro.generator.validation import (
    ValidationResult,
    validate_policy_structure,
    validate_policy_with_cli,
)

# PydanticAI integration (optional, requires pydantic-ai package)
try:
    from experiments.castro.generator.pydantic_ai_provider import (
        PydanticAIProvider,
        PydanticAIConfig,
        create_policy_agent,
        openai_provider,
        anthropic_provider,
        google_provider,
        ollama_provider,
    )
    _PYDANTIC_AI_AVAILABLE = True
except ImportError:
    _PYDANTIC_AI_AVAILABLE = False

__all__ = [
    # Provider protocol and implementations
    "LLMProvider",
    "StructuredOutputRequest",
    "StructuredOutputResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "OllamaProvider",
    "get_provider",
    # PydanticAI (when available)
    "PydanticAIProvider",
    "PydanticAIConfig",
    "create_policy_agent",
    "openai_provider",
    "anthropic_provider",
    "google_provider",
    "ollama_provider",
    # Policy generation
    "PolicyContext",
    "GenerationResult",
    "StructuredPolicyGenerator",
    # Validation
    "ValidationResult",
    "validate_policy_structure",
    "validate_policy_with_cli",
]
