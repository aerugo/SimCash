"""Schema injection helpers for LLM optimization prompts.

This module provides functions to extract and format policy and cost
schema documentation for injection into LLM prompts. The schemas are
filtered based on scenario constraints to only show what's allowed.

Key invariant: Only allowed elements are shown to the LLM to reduce
hallucination and enforce scenario constraints.
"""

from __future__ import annotations

import json
from typing import Any

from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import ParameterSpec
from payment_simulator.backends import get_cost_schema as _get_cost_schema_raw
from payment_simulator.backends import get_policy_schema as _get_policy_schema_raw


def get_filtered_policy_schema(
    constraints: ScenarioConstraints,
    include_examples: bool = True,
) -> str:
    """Generate policy schema documentation filtered by constraints.

    Filters the complete Rust policy schema to only include elements
    that are allowed by the scenario constraints. This prevents the
    LLM from generating invalid policies with disallowed actions,
    fields, or parameters.

    Args:
        constraints: Scenario constraints defining what's allowed.
        include_examples: Whether to include JSON examples.

    Returns:
        Formatted markdown/text schema documentation.
    """
    # Get raw schema from Rust
    raw_schema = json.loads(_get_policy_schema_raw())

    sections: list[str] = []

    # Section 1: Header
    sections.append("## POLICY FORMAT SPECIFICATION\n")
    sections.append(
        "This section defines the valid syntax for policy trees. "
        "Only use elements documented below.\n"
    )

    # Section 2: Parameters (from constraints)
    if constraints.allowed_parameters:
        sections.append("### ALLOWED PARAMETERS\n")
        sections.append(
            "Define these in the `parameters` object, reference with `{\"param\": \"name\"}`:\n"
        )
        sections.append(format_parameter_bounds(constraints.allowed_parameters))
        sections.append("")

    # Section 3: Fields (from constraints)
    if constraints.allowed_fields:
        sections.append("### ALLOWED FIELDS\n")
        sections.append(
            "Reference with `{\"field\": \"name\"}`. Only these fields are valid:\n"
        )
        sections.append(format_field_list(constraints.allowed_fields))
        sections.append("")

    # Section 4: Actions per tree type
    sections.append("### ALLOWED ACTIONS BY TREE TYPE\n")
    sections.append(_format_allowed_actions(constraints, raw_schema, include_examples))

    # Section 5: Value Types (always needed)
    sections.append("### VALUE TYPES\n")
    sections.append(_format_value_types(raw_schema, include_examples))

    # Section 6: Comparison and Logical Operators (always needed)
    sections.append("### COMPARISON OPERATORS\n")
    sections.append(_format_expressions(raw_schema, include_examples))

    # Section 7: Computations (always needed)
    sections.append("### ARITHMETIC OPERATIONS\n")
    sections.append(_format_computations(raw_schema, include_examples))

    # Section 8: Node ID reminder (critical)
    sections.append("### CRITICAL REQUIREMENT: node_id\n")
    sections.append(
        "**Every node in the policy tree MUST have a unique `node_id` string field!**\n"
    )
    sections.append("Example:\n")
    sections.append("```json")
    sections.append(
        '{"type": "action", "node_id": "A1_release", "action": "Release"}'
    )
    sections.append("```\n")
    sections.append(
        "Without unique node_ids, the policy will fail validation.\n"
    )

    # Section 9: Compute wrapper reminder
    sections.append("### CRITICAL: Arithmetic Expressions\n")
    sections.append(
        "All arithmetic expressions MUST be wrapped in `{\"compute\": {...}}`:\n"
    )
    sections.append("```json")
    sections.append("// WRONG:")
    sections.append('{"op": "*", "left": {"field": "balance"}, "right": {"value": 0.5}}')
    sections.append("")
    sections.append("// CORRECT:")
    sections.append(
        '{"compute": {"op": "*", "left": {"field": "balance"}, "right": {"value": 0.5}}}'
    )
    sections.append("```\n")

    return "\n".join(sections)


def get_filtered_cost_schema(
    cost_rates: dict[str, Any] | None = None,
) -> str:
    """Generate cost schema documentation.

    Formats the cost schema from Rust with optional specific rate values
    from the scenario configuration.

    Args:
        cost_rates: Optional cost rate values from scenario config.

    Returns:
        Formatted markdown/text cost documentation.
    """
    # Get raw schema from Rust
    raw_schema = json.loads(_get_cost_schema_raw())

    sections: list[str] = []

    sections.append("## COST PARAMETERS\n")
    sections.append(
        "These are the costs that determine the objective function. "
        "Your goal is to minimize total cost.\n"
    )

    # Group costs by category
    per_tick_costs: list[dict[str, Any]] = []
    one_time_costs: list[dict[str, Any]] = []
    daily_costs: list[dict[str, Any]] = []
    modifiers: list[dict[str, Any]] = []

    for cost_type in raw_schema.get("cost_types", []):
        category = cost_type.get("category", "")
        if category == "PerTick":
            per_tick_costs.append(cost_type)
        elif category == "OneTime":
            one_time_costs.append(cost_type)
        elif category == "Daily":
            daily_costs.append(cost_type)
        elif category == "Modifier":
            modifiers.append(cost_type)

    # Per-tick costs
    if per_tick_costs:
        sections.append("### Per-Tick Costs\n")
        sections.append("These costs accrue every tick:\n")
        for cost in per_tick_costs:
            sections.append(_format_cost_element(cost, cost_rates))
        sections.append("")

    # One-time costs
    if one_time_costs:
        sections.append("### One-Time Penalties\n")
        sections.append("These penalties are charged once when triggered:\n")
        for cost in one_time_costs:
            sections.append(_format_cost_element(cost, cost_rates))
        sections.append("")

    # Daily costs
    if daily_costs:
        sections.append("### End-of-Day Costs\n")
        sections.append("These costs are charged at the end of each day:\n")
        for cost in daily_costs:
            sections.append(_format_cost_element(cost, cost_rates))
        sections.append("")

    # Modifiers
    if modifiers:
        sections.append("### Cost Modifiers\n")
        sections.append("These modify other costs:\n")
        for cost in modifiers:
            sections.append(_format_cost_element(cost, cost_rates))
        sections.append("")

    return "\n".join(sections)


def format_parameter_bounds(
    params: list[ParameterSpec],
) -> str:
    """Format parameter specifications as readable text.

    Args:
        params: List of parameter specifications.

    Returns:
        Formatted parameter list with bounds and descriptions.
    """
    if not params:
        return ""

    lines: list[str] = []

    for param in params:
        # Format: name [min-max]: description
        bounds = ""
        if param.min_value is not None and param.max_value is not None:
            bounds = f" [range: {param.min_value}-{param.max_value}]"
        elif param.min_value is not None:
            bounds = f" [min: {param.min_value}]"
        elif param.max_value is not None:
            bounds = f" [max: {param.max_value}]"

        description = param.description or "No description"
        lines.append(f"- **{param.name}**{bounds}: {description}")

    return "\n".join(lines)


def format_field_list(
    fields: list[str],
    group_by_category: bool = False,
) -> str:
    """Format field list as readable text.

    Args:
        fields: List of allowed field names.
        group_by_category: Whether to group by schema category (not implemented).

    Returns:
        Formatted field list.
    """
    if not fields:
        return ""

    # Simple formatted list
    lines: list[str] = []
    for field in sorted(fields):
        lines.append(f"- `{field}`")

    return "\n".join(lines)


def format_action_list(
    tree_type: str,
    actions: list[str],
) -> str:
    """Format action list for a tree type.

    Args:
        tree_type: Tree type (payment_tree, bank_tree, etc.)
        actions: List of allowed actions.

    Returns:
        Formatted action list with descriptions.
    """
    tree_display = tree_type.replace("_", " ").title()

    if not actions:
        return f"**{tree_display}**: Not enabled in this scenario.\n"

    lines: list[str] = []
    lines.append(f"**{tree_display}**:")

    for action in actions:
        lines.append(f"  - `{action}`")

    return "\n".join(lines)


# =============================================================================
# Private Helper Functions
# =============================================================================


def _format_allowed_actions(
    constraints: ScenarioConstraints,
    raw_schema: dict[str, Any],
    include_examples: bool,
) -> str:
    """Format allowed actions with descriptions from Rust schema."""
    lines: list[str] = []

    # Build lookup from Rust schema
    action_docs: dict[str, dict[str, Any]] = {}
    for action in raw_schema.get("actions", []):
        action_docs[action["name"]] = action

    # Payment tree
    payment_actions = constraints.allowed_actions.get("payment_tree", [])
    if payment_actions:
        lines.append("#### payment_tree\n")
        lines.append("Actions for deciding what to do with each transaction:\n")
        for action_name in payment_actions:
            lines.append(_format_action_with_doc(action_name, action_docs, include_examples))
    else:
        lines.append("#### payment_tree\n")
        lines.append("Not enabled in this scenario.\n")

    # Bank tree
    bank_actions = constraints.allowed_actions.get("bank_tree", [])
    if bank_actions:
        lines.append("\n#### bank_tree\n")
        lines.append("Bank-level actions evaluated once per tick:\n")
        for action_name in bank_actions:
            lines.append(_format_action_with_doc(action_name, action_docs, include_examples))

    # Strategic collateral tree
    strategic_actions = constraints.allowed_actions.get("strategic_collateral_tree", [])
    if strategic_actions:
        lines.append("\n#### strategic_collateral_tree\n")
        lines.append("Collateral management actions:\n")
        for action_name in strategic_actions:
            lines.append(_format_action_with_doc(action_name, action_docs, include_examples))

    # End-of-tick collateral tree
    eot_actions = constraints.allowed_actions.get("end_of_tick_collateral_tree", [])
    if eot_actions:
        lines.append("\n#### end_of_tick_collateral_tree\n")
        lines.append("End-of-tick collateral decisions:\n")
        for action_name in eot_actions:
            lines.append(_format_action_with_doc(action_name, action_docs, include_examples))

    return "\n".join(lines)


def _format_action_with_doc(
    action_name: str,
    action_docs: dict[str, dict[str, Any]],
    include_examples: bool,
) -> str:
    """Format a single action with documentation from Rust schema."""
    doc = action_docs.get(action_name, {})
    description = doc.get("description", "No description available")
    semantics = doc.get("semantics", "")
    parameters = doc.get("parameters", [])

    lines: list[str] = []
    lines.append(f"- **{action_name}**: {description}")

    if semantics:
        lines.append(f"  - *Semantics*: {semantics}")

    if parameters:
        lines.append("  - *Parameters*:")
        for param in parameters:
            param_name = param.get("name", "")
            param_desc = param.get("description", "")
            required = "required" if param.get("required", False) else "optional"
            lines.append(f"    - `{param_name}` ({required}): {param_desc}")

    if include_examples and doc.get("example_json"):
        example = json.dumps(doc["example_json"], indent=2)
        lines.append(f"  - *Example*:\n    ```json\n    {example}\n    ```")

    return "\n".join(lines) + "\n"


def _format_value_types(
    raw_schema: dict[str, Any],
    include_examples: bool,
) -> str:
    """Format value type documentation."""
    lines: list[str] = []
    lines.append("Four ways to specify values in conditions and parameters:\n")

    values = raw_schema.get("values", [])
    for value_type in values:
        name = value_type.get("name", "")
        description = value_type.get("description", "")
        json_key = value_type.get("json_key", "")

        lines.append(f"- **{name}** (`{json_key}`): {description}")

        if include_examples and value_type.get("example_json"):
            example = json.dumps(value_type["example_json"])
            lines.append(f"  - Example: `{example}`")

    lines.append("")
    return "\n".join(lines)


def _format_expressions(
    raw_schema: dict[str, Any],
    include_examples: bool,
) -> str:
    """Format expression operator documentation."""
    lines: list[str] = []

    expressions = raw_schema.get("expressions", [])

    # Comparison operators
    comparison_ops = [e for e in expressions if e.get("category") == "ComparisonOperator"]
    if comparison_ops:
        lines.append("**Comparison Operators:**\n")
        for op in comparison_ops:
            name = op.get("name", "")
            json_key = op.get("json_key", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}` ({name}): {desc}")
        lines.append("")

    # Logical operators
    logical_ops = [e for e in expressions if e.get("category") == "LogicalOperator"]
    if logical_ops:
        lines.append("**Logical Operators:**\n")
        for op in logical_ops:
            name = op.get("name", "")
            json_key = op.get("json_key", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}` ({name}): {desc}")

            if include_examples and op.get("example_json"):
                example = json.dumps(op["example_json"], indent=2)
                lines.append(f"  ```json\n  {example}\n  ```")
        lines.append("")

    return "\n".join(lines)


def _format_computations(
    raw_schema: dict[str, Any],
    include_examples: bool,
) -> str:
    """Format computation operator documentation."""
    lines: list[str] = []

    computations = raw_schema.get("computations", [])

    # Group by category
    binary_ops = [c for c in computations if c.get("category") == "BinaryArithmetic"]
    nary_ops = [c for c in computations if c.get("category") == "NaryArithmetic"]
    unary_ops = [c for c in computations if c.get("category") == "UnaryMath"]
    ternary_ops = [c for c in computations if c.get("category") == "TernaryMath"]

    if binary_ops:
        lines.append("**Binary Operators** (`+`, `-`, `*`, `/`):\n")
        for op in binary_ops:
            json_key = op.get("json_key", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}`: {desc}")
        lines.append("")

    if nary_ops:
        lines.append("**N-ary Operators** (take multiple values):\n")
        for op in nary_ops:
            json_key = op.get("json_key", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}`: {desc}")
        lines.append("")

    if unary_ops:
        lines.append("**Unary Operators** (single value):\n")
        for op in unary_ops:
            json_key = op.get("json_key", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}`: {desc}")
        lines.append("")

    if ternary_ops:
        lines.append("**Special Operators**:\n")
        for op in ternary_ops:
            json_key = op.get("json_key", "")
            name = op.get("name", "")
            desc = op.get("description", "")
            lines.append(f"- `{json_key}` ({name}): {desc}")
        lines.append("")

    # Add example
    lines.append("**Example** (compute wrapper required):\n")
    lines.append("```json")
    lines.append('{')
    lines.append('  "compute": {')
    lines.append('    "op": "*",')
    lines.append('    "left": {"field": "balance"},')
    lines.append('    "right": {"value": 0.5}')
    lines.append('  }')
    lines.append('}')
    lines.append("```\n")

    return "\n".join(lines)


def _format_cost_element(
    cost: dict[str, Any],
    cost_rates: dict[str, Any] | None,
) -> str:
    """Format a single cost element with optional actual value."""
    name = cost.get("name", "")
    display_name = cost.get("display_name", name)
    description = cost.get("description", "")
    formula = cost.get("formula", "")
    default_value = cost.get("default_value", "")

    # Get actual value if provided
    actual_value = None
    if cost_rates and name in cost_rates:
        actual_value = cost_rates[name]

    lines: list[str] = []
    lines.append(f"**{display_name}** (`{name}`)")
    lines.append(f"  - {description}")
    lines.append(f"  - Formula: `{formula}`")

    if actual_value is not None:
        lines.append(f"  - Current value: `{actual_value}`")
    else:
        lines.append(f"  - Default: `{default_value}`")

    # Include example if available
    example = cost.get("example")
    if example:
        scenario = example.get("scenario", "")
        result = example.get("result", "")
        calculation = example.get("calculation", "")
        lines.append(f"  - Example: {scenario}")
        lines.append(f"    - Calculation: {calculation}")
        lines.append(f"    - Result: {result}")

    return "\n".join(lines) + "\n"
