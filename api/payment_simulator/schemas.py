"""Programmatic access to cost and policy schema documentation.

This module provides functions to retrieve filtered and formatted schema
documentation for cost types and policy elements. It exposes the same
functionality as the CLI commands `payment-sim cost-schema` and
`payment-sim policy-schema`.

Example usage:

    from payment_simulator.schemas import (
        get_cost_schema_formatted,
        get_policy_schema_formatted,
    )

    # Get full cost schema as markdown
    markdown = get_cost_schema_formatted()

    # Get filtered cost schema as JSON dict
    data = get_cost_schema_formatted(
        format="json",
        include_categories=["PerTick", "OneTime"],
    )

    # Get policy schema filtered by tree
    policy_md = get_policy_schema_formatted(
        include_trees=["payment_tree"],
        compact=True,
    )
"""

from __future__ import annotations

import json
from typing import Any, Literal

from payment_simulator.backends import get_cost_schema as _get_cost_schema_raw
from payment_simulator.backends import get_policy_schema as _get_policy_schema_raw

# Re-export the raw functions for advanced use
from payment_simulator.backends import get_cost_schema, get_policy_schema

# Import filtering/formatting functions from CLI modules
from payment_simulator.cli.commands.cost_schema import (
    filter_schema as _filter_cost_schema,
    format_as_markdown as _format_cost_markdown,
)
from payment_simulator.cli.commands.policy_schema import (
    filter_schema as _filter_policy_schema,
    format_as_markdown as _format_policy_markdown,
)

__all__ = [
    # Raw JSON functions
    "get_cost_schema",
    "get_policy_schema",
    # Formatted/filtered functions
    "get_cost_schema_formatted",
    "get_policy_schema_formatted",
]


def get_cost_schema_formatted(
    format: Literal["json", "markdown"] = "markdown",
    *,
    include_categories: list[str] | None = None,
    exclude_categories: list[str] | None = None,
    include_names: list[str] | None = None,
    exclude_names: list[str] | None = None,
    no_examples: bool = False,
    compact: bool = False,
) -> str | dict[str, Any]:
    """Get cost schema documentation with optional filtering and formatting.

    This provides the same functionality as `payment-sim cost-schema` but
    callable from Python code.

    Args:
        format: Output format - "markdown" for human-readable docs,
                "json" for structured data (returns dict).
        include_categories: Only include costs in these categories.
            Valid: "PerTick", "OneTime", "Daily", "Modifier"
        exclude_categories: Exclude costs in these categories.
        include_names: Only include costs with these names.
        exclude_names: Exclude costs with these names.
        no_examples: If True, exclude example calculations from markdown.
        compact: If True, produce compact table format for markdown.

    Returns:
        If format="markdown": A string containing markdown documentation.
        If format="json": A dict containing the filtered schema.

    Example:
        >>> # Full markdown documentation
        >>> md = get_cost_schema_formatted()

        >>> # Only per-tick costs as JSON
        >>> data = get_cost_schema_formatted(
        ...     format="json",
        ...     include_categories=["PerTick"],
        ... )
        >>> print(data["cost_types"][0]["name"])
        'overdraft_bps_per_tick'

        >>> # Compact table excluding modifiers
        >>> md = get_cost_schema_formatted(
        ...     compact=True,
        ...     exclude_categories=["Modifier"],
        ... )
    """
    # Get raw schema from Rust
    schema = json.loads(_get_cost_schema_raw())

    # Apply filters
    filtered = _filter_cost_schema(
        schema,
        include_categories=set(include_categories) if include_categories else None,
        exclude_categories=set(exclude_categories) if exclude_categories else set(),
        include_names=set(include_names) if include_names else None,
        exclude_names=set(exclude_names) if exclude_names else set(),
    )

    # Format output
    if format == "json":
        return filtered
    else:
        return _format_cost_markdown(filtered, no_examples=no_examples, compact=compact)


def get_policy_schema_formatted(
    format: Literal["json", "markdown"] = "markdown",
    *,
    include_categories: list[str] | None = None,
    exclude_categories: list[str] | None = None,
    include_trees: list[str] | None = None,
    include_sections: list[str] | None = None,
    no_examples: bool = False,
    compact: bool = False,
) -> str | dict[str, Any]:
    """Get policy schema documentation with optional filtering and formatting.

    This provides the same functionality as `payment-sim policy-schema` but
    callable from Python code.

    Args:
        format: Output format - "markdown" for human-readable docs,
                "json" for structured data (returns dict).
        include_categories: Only include elements in these categories.
            Examples: "PaymentAction", "TransactionField", "ComparisonOperator"
        exclude_categories: Exclude elements in these categories.
        include_trees: Only include elements valid in these tree types.
            Valid: "payment_tree", "bank_tree", "strategic_collateral_tree",
                   "end_of_tick_collateral_tree"
        include_sections: Only include these sections.
            Valid: "trees", "nodes", "expressions", "values",
                   "computations", "actions", "fields"
        no_examples: If True, exclude JSON examples from markdown.
        compact: If True, produce compact output with fewer details.

    Returns:
        If format="markdown": A string containing markdown documentation.
        If format="json": A dict containing the filtered schema.

    Example:
        >>> # Full markdown documentation
        >>> md = get_policy_schema_formatted()

        >>> # Only actions for payment tree
        >>> data = get_policy_schema_formatted(
        ...     format="json",
        ...     include_sections=["actions"],
        ...     include_trees=["payment_tree"],
        ... )

        >>> # Transaction fields only, compact
        >>> md = get_policy_schema_formatted(
        ...     include_categories=["TransactionField"],
        ...     compact=True,
        ... )
    """
    # Get raw schema from Rust
    schema = json.loads(_get_policy_schema_raw())

    # Apply filters
    filtered = _filter_policy_schema(
        schema,
        include_categories=set(include_categories) if include_categories else None,
        exclude_categories=set(exclude_categories) if exclude_categories else set(),
        include_trees=set(include_trees) if include_trees else None,
        include_sections=set(include_sections) if include_sections else None,
    )

    # Format output
    if format == "json":
        return filtered
    else:
        return _format_policy_markdown(filtered, no_examples=no_examples, compact=compact)
