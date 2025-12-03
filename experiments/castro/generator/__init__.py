# Policy generation using PydanticAI
#
# PydanticAI handles all LLM provider abstraction. Just use a model string:
#   - openai:gpt-4o
#   - anthropic:claude-3-5-sonnet-20241022
#   - google-gla:gemini-1.5-pro
#   - ollama:llama3.1:8b
#
# Usage:
#   from experiments.castro.generator import PolicyAgent, generate_policy
#
#   # Simple one-liner
#   policy = generate_policy("payment_tree", "Optimize for low costs")
#
#   # With agent for multiple generations
#   agent = PolicyAgent(model="anthropic:claude-3-5-sonnet-20241022")
#   policy = agent.generate("payment_tree", "Prioritize high-value payments")

from experiments.castro.generator.policy_agent import (
    PolicyAgent,
    PolicyDeps,
    generate_policy,
)

from experiments.castro.generator.validation import (
    ValidationResult,
    validate_policy_structure,
)

__all__ = [
    # Main API
    "PolicyAgent",
    "PolicyDeps",
    "generate_policy",
    # Validation
    "ValidationResult",
    "validate_policy_structure",
]
