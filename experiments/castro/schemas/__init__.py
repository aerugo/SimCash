# Pydantic AI Structured Output Schemas for Policy Generation
"""
This package provides depth-limited Pydantic models for generating
valid policy trees via OpenAI structured output.

Key components:
- values: PolicyValue, ContextField, LiteralValue, ParameterRef
- operators: Comparison operators for expressions
- expressions: Depth-limited expression models (ExpressionL0-L3)
- actions: Action types with parameters
- tree: Depth-limited tree node models (TreeNodeL0-L5)
- generator: Dynamic schema generation based on feature toggles
- registry: Action/field registries per tree type
"""

# Values are always available
from experiments.castro.schemas.values import (
    ContextField,
    LiteralValue,
    ParameterRef,
    ComputeValue,
    PolicyValue,
)

__all__ = [
    "ContextField",
    "LiteralValue",
    "ParameterRef",
    "ComputeValue",
    "PolicyValue",
]

# Import expressions if available
try:
    from experiments.castro.schemas.expressions import (
        ComparisonOperator,
        Comparison,
    )
    __all__.extend(["ComparisonOperator", "Comparison"])
except ImportError:
    pass

# Import actions if available
try:
    from experiments.castro.schemas.actions import (
        ActionType,
        ActionModel,
    )
    __all__.extend(["ActionType", "ActionModel"])
except ImportError:
    pass
