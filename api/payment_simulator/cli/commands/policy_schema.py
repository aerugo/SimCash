"""CLI command for generating policy schema documentation."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer

from payment_simulator.backends import get_policy_schema


class OutputFormat(str, Enum):
    """Output format options."""
    json = "json"
    markdown = "markdown"


class SchemaSection(str, Enum):
    """Schema sections."""
    trees = "trees"
    nodes = "nodes"
    expressions = "expressions"
    values = "values"
    computations = "computations"
    actions = "actions"
    fields = "fields"


class SchemaCategory(str, Enum):
    """Categories for filtering schema elements."""
    # Expression categories
    ComparisonOperator = "ComparisonOperator"
    LogicalOperator = "LogicalOperator"
    # Computation categories
    BinaryArithmetic = "BinaryArithmetic"
    NaryArithmetic = "NaryArithmetic"
    UnaryMath = "UnaryMath"
    TernaryMath = "TernaryMath"
    # Value categories
    ValueType = "ValueType"
    # Action categories
    PaymentAction = "PaymentAction"
    BankAction = "BankAction"
    CollateralAction = "CollateralAction"
    RtgsAction = "RtgsAction"
    # Field categories
    TransactionField = "TransactionField"
    AgentField = "AgentField"
    QueueField = "QueueField"
    CollateralField = "CollateralField"
    CostField = "CostField"
    TimeField = "TimeField"
    LsmField = "LsmField"
    ThroughputField = "ThroughputField"
    StateRegisterField = "StateRegisterField"
    SystemField = "SystemField"
    DerivedField = "DerivedField"
    # Node and tree categories
    NodeType = "NodeType"
    TreeType = "TreeType"


class TreeType(str, Enum):
    """Policy tree types."""
    payment_tree = "payment_tree"
    bank_tree = "bank_tree"
    strategic_collateral_tree = "strategic_collateral_tree"
    end_of_tick_collateral_tree = "end_of_tick_collateral_tree"


def policy_schema(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.markdown,
    category: Annotated[
        list[SchemaCategory] | None,
        typer.Option("--category", "-c", help="Filter to specific categories (can be repeated)"),
    ] = None,
    exclude_category: Annotated[
        list[SchemaCategory] | None,
        typer.Option(
            "--exclude-category", "-x", help="Exclude specific categories (can be repeated)"
        ),
    ] = None,
    tree: Annotated[
        list[TreeType] | None,
        typer.Option("--tree", "-t", help="Filter to elements valid in specific trees"),
    ] = None,
    section: Annotated[
        list[SchemaSection] | None,
        typer.Option("--section", "-s", help="Include only specific sections"),
    ] = None,
    scenario: Annotated[
        Path | None,
        typer.Option(
            "--scenario",
            help="Filter schema based on scenario's feature toggles"
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file (default: stdout)"),
    ] = None,
    no_examples: Annotated[
        bool,
        typer.Option("--no-examples", help="Exclude JSON examples from output"),
    ] = False,
    compact: Annotated[
        bool,
        typer.Option("--compact", help="Compact output (fewer details)"),
    ] = False,
) -> None:
    """Generate policy schema documentation.

    Examples:

        # Full markdown documentation
        payment-sim policy-schema

        # Only actions, in JSON format
        payment-sim policy-schema --section actions --format json

        # Payment tree elements only
        payment-sim policy-schema --tree payment_tree

        # Exclude collateral actions
        payment-sim policy-schema --exclude-category CollateralAction

        # Schema filtered by scenario's feature toggles
        payment-sim policy-schema --scenario scenario.yaml
    """
    # Get schema from Rust
    schema_json = get_policy_schema()
    schema = json.loads(schema_json)

    # Apply filters from CLI options
    include_categories = {c.value for c in category} if category else None
    exclude_categories = {c.value for c in exclude_category} if exclude_category else set()
    include_trees = {t.value for t in tree} if tree else None
    include_sections = {s.value for s in section} if section else None

    # Apply scenario feature toggles if provided
    if scenario is not None:
        from payment_simulator.config import load_config

        try:
            config = load_config(str(scenario))
        except Exception as e:
            typer.echo(f"Error loading scenario: {e}", err=True)
            raise typer.Exit(code=1)

        if config.policy_feature_toggles is not None:
            toggles = config.policy_feature_toggles

            if toggles.include is not None:
                # Scenario has include list - merge with any CLI include
                scenario_includes = set(toggles.include)
                if include_categories is not None:
                    # Intersection of CLI and scenario includes
                    include_categories = include_categories & scenario_includes
                else:
                    include_categories = scenario_includes

            if toggles.exclude is not None:
                # Scenario has exclude list - merge with CLI excludes
                scenario_excludes = set(toggles.exclude)
                exclude_categories = exclude_categories | scenario_excludes

    # Filter schema
    filtered_schema = filter_schema(
        schema,
        include_categories=include_categories,
        exclude_categories=exclude_categories,
        include_trees=include_trees,
        include_sections=include_sections,
    )

    # Format output
    if format == OutputFormat.json:
        result = json.dumps(filtered_schema, indent=2)
    else:  # markdown
        result = format_as_markdown(
            filtered_schema,
            no_examples=no_examples,
            compact=compact
        )

    # Output
    if output:
        output.write_text(result)
        typer.echo(f"Schema written to {output}")
    else:
        typer.echo(result)


def filter_schema(
    schema: dict[str, Any],
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    include_trees: set[str] | None = None,
    include_sections: set[str] | None = None,
) -> dict[str, Any]:
    """Filter schema based on options."""
    result = {
        "version": schema["version"],
        "generated_at": schema["generated_at"],
    }

    section_mappings = [
        ("tree_types", "trees"),
        ("node_types", "nodes"),
        ("expressions", "expressions"),
        ("values", "values"),
        ("computations", "computations"),
        ("actions", "actions"),
        ("fields", "fields"),
    ]

    for schema_key, section_name in section_mappings:
        if include_sections and section_name not in include_sections:
            # Explicitly set to empty list for filtered-out sections
            result[schema_key] = []
            continue

        elements = schema.get(schema_key, [])
        filtered_elements = []

        for elem in elements:
            # Category filter
            if include_categories and elem.get("category") not in include_categories:
                continue
            if exclude_categories and elem.get("category") in exclude_categories:
                continue

            # Tree filter
            if include_trees:
                valid_trees = set(elem.get("valid_in_trees", []))
                if not (valid_trees & include_trees):
                    continue

            filtered_elements.append(elem)

        result[schema_key] = filtered_elements

    return result


def format_as_markdown(
    schema: dict[str, Any],
    no_examples: bool = False,
    compact: bool = False,
) -> str:
    """Format schema as markdown documentation."""
    lines = ["# Policy Schema Reference", ""]
    lines.append(f"> Generated: {schema['generated_at']}")
    lines.append(f"> Version: {schema['version']}")
    lines.append("")

    section_titles = {
        "tree_types": "Tree Types",
        "node_types": "Node Types",
        "expressions": "Expressions",
        "values": "Value Types",
        "computations": "Computations",
        "actions": "Actions",
        "fields": "Context Fields",
    }

    for section_key, title in section_titles.items():
        elements = schema.get(section_key, [])
        if not elements:
            continue

        lines.append(f"## {title}")
        lines.append("")

        # Group by category
        by_category: dict[str, list[dict[str, Any]]] = {}
        for elem in elements:
            cat = elem.get("category", "Other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(elem)

        for category, cat_elements in sorted(by_category.items()):
            lines.append(f"### {_format_category_name(category)}")
            lines.append("")

            for elem in cat_elements:
                lines.append(_format_element_markdown(elem, no_examples, compact))

    return "\n".join(lines)


def _format_element_markdown(
    elem: dict[str, Any], no_examples: bool, compact: bool
) -> str:
    """Format a single schema element as markdown."""
    lines = []

    name = elem.get("name", "Unknown")
    json_key = elem.get("json_key", name)
    description = elem.get("description", "")

    if json_key != name:
        lines.append(f"#### `{json_key}` ({name})")
    else:
        lines.append(f"#### `{name}`")
    lines.append("")
    lines.append(description)
    lines.append("")

    if not compact:
        if semantics := elem.get("semantics"):
            lines.append(f"**Semantics**: {semantics}")
            lines.append("")

        if data_type := elem.get("data_type"):
            unit = elem.get("unit", "")
            unit_str = f" ({unit})" if unit else ""
            lines.append(f"**Type**: `{data_type}`{unit_str}")
            lines.append("")

        if valid_trees := elem.get("valid_in_trees"):
            trees_str = ", ".join(f"`{t}`" for t in valid_trees)
            lines.append(f"**Valid in**: {trees_str}")
            lines.append("")

        if params := elem.get("parameters"):
            lines.append("**Parameters**:")
            lines.append("")
            for p in params:
                req = " (required)" if p.get("required") else ""
                lines.append(f"- `{p['name']}`: {p['param_type']}{req} - {p['description']}")
            lines.append("")

        if not no_examples and (example := elem.get("example_json")):
            lines.append("**Example**:")
            lines.append("```json")
            lines.append(json.dumps(example, indent=2))
            lines.append("```")
            lines.append("")

        if source := elem.get("source_location"):
            lines.append(f"*Source: {source}*")
            lines.append("")

    return "\n".join(lines)


def _format_category_name(category: str) -> str:
    """Format category enum value as readable name."""
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', category)
