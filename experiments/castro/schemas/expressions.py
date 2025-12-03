"""Expression types for policy conditions.

Expressions are used in Condition nodes to determine which branch to take.
They support:
- Comparisons: ==, !=, <, <=, >, >=
- Logical operators: and, or, not
- Nesting: expressions can contain other expressions

Note: These are designed to work with OpenAI structured output which has
limitations on recursive schemas. The depth is managed at the tree level.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

from experiments.castro.schemas.values import PolicyValue, ContextField, LiteralValue


# Comparison operators as a literal type
ComparisonOperator = Literal["==", "!=", "<", "<=", ">", ">="]


class Comparison(BaseModel):
    """A comparison between two values.

    Examples:
        {"op": ">=", "left": {"field": "balance"}, "right": {"value": 0}}
        {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgency_threshold"}}
    """

    op: ComparisonOperator = Field(
        ...,
        description="Comparison operator: ==, !=, <, <=, >, >=",
    )
    left: PolicyValue = Field(
        ...,
        description="Left operand (field, literal, param, or compute)",
    )
    right: PolicyValue = Field(
        ...,
        description="Right operand (field, literal, param, or compute)",
    )


class AndExpression(BaseModel):
    """Logical AND of multiple conditions.

    Returns true only if ALL conditions are true.
    Uses short-circuit evaluation (stops at first false).

    Example:
        {"op": "and", "conditions": [<expr>, <expr>, ...]}
    """

    op: Literal["and"] = Field(
        "and",
        description="Must be 'and'",
    )
    conditions: list["Expression"] = Field(
        ...,
        description="List of conditions that must all be true",
        min_length=1,
    )


class OrExpression(BaseModel):
    """Logical OR of multiple conditions.

    Returns true if ANY condition is true.
    Uses short-circuit evaluation (stops at first true).

    Example:
        {"op": "or", "conditions": [<expr>, <expr>, ...]}
    """

    op: Literal["or"] = Field(
        "or",
        description="Must be 'or'",
    )
    conditions: list["Expression"] = Field(
        ...,
        description="List of conditions where at least one must be true",
        min_length=1,
    )


class NotExpression(BaseModel):
    """Logical NOT (negation) of a condition.

    Returns true if the inner condition is false.

    Example:
        {"op": "not", "condition": <expr>}
    """

    op: Literal["not"] = Field(
        "not",
        description="Must be 'not'",
    )
    condition: "Expression" = Field(
        ...,
        description="Condition to negate",
    )


# Expression union type - covers all expression variants
# Note: This creates a recursive type which Pydantic handles via forward refs
Expression = Annotated[
    Union[Comparison, AndExpression, OrExpression, NotExpression],
    Field(discriminator="op"),
]

# Update forward references for recursive types
AndExpression.model_rebuild()
OrExpression.model_rebuild()
NotExpression.model_rebuild()
