# Policy generation using PydanticAI
#
# PydanticAI handles all LLM provider abstraction. Just use a model string:
#   - openai:gpt-4o
#   - anthropic:claude-3-5-sonnet-20241022
#   - google-gla:gemini-1.5-pro
#   - ollama:llama3.1:8b
#
# Usage:
#   from experiments.castro.generator import RobustPolicyAgent
#   from experiments.castro.schemas.parameter_config import (
#       ParameterSpec, ScenarioConstraints
#   )
#
#   constraints = ScenarioConstraints(
#       allowed_parameters=[ParameterSpec("urgency", 0, 20, 3, "Urgency")],
#       allowed_fields=["balance", "ticks_to_deadline"],
#       allowed_actions=["Release", "Hold"],
#   )
#
#   agent = RobustPolicyAgent(constraints=constraints)
#   policy = agent.generate_policy("Optimize for low costs")

from experiments.castro.generator.validation import (
    ValidationResult,
    validate_policy_structure,
)

# Import new robust agent (doesn't require pydantic_ai at import time)
from experiments.castro.generator.robust_policy_agent import (
    RobustPolicyAgent,
    RobustPolicyDeps,
    generate_robust_policy,
)

__all__ = [
    # New API (ScenarioConstraints-based)
    "RobustPolicyAgent",
    "RobustPolicyDeps",
    "generate_robust_policy",
    # Validation
    "ValidationResult",
    "validate_policy_structure",
]
