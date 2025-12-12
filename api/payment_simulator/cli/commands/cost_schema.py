"""CLI command for generating cost schema documentation."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer

from payment_simulator.backends import get_cost_schema


class OutputFormat(str, Enum):
    """Output format options."""

    json = "json"
    markdown = "markdown"


class CostCategory(str, Enum):
    """Cost categories for filtering."""

    PerTick = "PerTick"
    OneTime = "OneTime"
    Daily = "Daily"
    Modifier = "Modifier"


def cost_schema(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.markdown,
    category: Annotated[
        list[CostCategory] | None,
        typer.Option(
            "--category", "-c", help="Filter to specific categories (can be repeated)"
        ),
    ] = None,
    exclude_category: Annotated[
        list[CostCategory] | None,
        typer.Option(
            "--exclude-category",
            "-x",
            help="Exclude specific categories (can be repeated)",
        ),
    ] = None,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include", "-i", help="Include only specific cost names (can be repeated)"
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude", "-e", help="Exclude specific cost names (can be repeated)"
        ),
    ] = None,
    scenario: Annotated[
        Path | None,
        typer.Option("--scenario", help="Filter schema based on scenario's cost_feature_toggles"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file (default: stdout)"),
    ] = None,
    no_examples: Annotated[
        bool,
        typer.Option("--no-examples", help="Exclude examples from output"),
    ] = False,
    compact: Annotated[
        bool,
        typer.Option("--compact", help="Compact output (table format only)"),
    ] = False,
) -> None:
    """Generate cost schema documentation.

    Examples:

        # Full markdown documentation
        payment-sim cost-schema

        # Per-tick costs only
        payment-sim cost-schema --category PerTick

        # Exclude modifier costs
        payment-sim cost-schema --exclude-category Modifier

        # Include only specific costs
        payment-sim cost-schema --include overdraft_bps_per_tick --include deadline_penalty

        # Exclude specific costs
        payment-sim cost-schema --exclude priority_delay_multipliers

        # JSON format for tools
        payment-sim cost-schema --format json

        # Compact table
        payment-sim cost-schema --compact

        # Filter based on scenario
        payment-sim cost-schema --scenario scenario.yaml

        # Save to file
        payment-sim cost-schema --output costs.md
    """
    # Get schema from Rust
    schema_json = get_cost_schema()
    schema = json.loads(schema_json)

    # Apply filters from CLI options
    include_categories = {c.value for c in category} if category else None
    exclude_categories = {c.value for c in exclude_category} if exclude_category else set()
    include_names = set(include) if include else None
    exclude_names = set(exclude) if exclude else set()

    # Apply scenario cost feature toggles if provided
    if scenario is not None:
        from payment_simulator.config import load_config

        try:
            config = load_config(str(scenario))
        except Exception as e:
            typer.echo(f"Error loading scenario: {e}", err=True)
            raise typer.Exit(code=1)

        if config.cost_feature_toggles is not None:
            toggles = config.cost_feature_toggles

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
        include_names=include_names,
        exclude_names=exclude_names,
    )

    # Format output
    if format == OutputFormat.json:
        result = json.dumps(filtered_schema, indent=2)
    else:  # markdown
        result = format_as_markdown(filtered_schema, no_examples=no_examples, compact=compact)

    # Output
    if output:
        output.write_text(result)
        typer.echo(f"Cost schema written to {output}")
    else:
        typer.echo(result)


def filter_schema(
    schema: dict[str, Any],
    include_categories: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    include_names: set[str] | None = None,
    exclude_names: set[str] | None = None,
) -> dict[str, Any]:
    """Filter schema based on options."""
    result = {
        "version": schema["version"],
        "generated_at": schema["generated_at"],
        "cost_types": [],
    }

    for cost in schema.get("cost_types", []):
        cost_category = cost.get("category")
        cost_name = cost.get("name")

        # Category include filter
        if include_categories and cost_category not in include_categories:
            continue

        # Category exclude filter
        if exclude_categories and cost_category in exclude_categories:
            continue

        # Name include filter
        if include_names and cost_name not in include_names:
            continue

        # Name exclude filter
        if exclude_names and cost_name in exclude_names:
            continue

        result["cost_types"].append(cost)

    return result


def format_as_markdown(
    schema: dict[str, Any],
    no_examples: bool = False,
    compact: bool = False,
) -> str:
    """Format schema as markdown documentation."""
    lines = ["# Cost Types Reference", ""]
    lines.append(f"> Generated: {schema['generated_at']}")
    lines.append(f"> Version: {schema['version']}")
    lines.append("")

    cost_types = schema.get("cost_types", [])

    if compact:
        # Table format
        lines.append("| Cost Type | Category | Default | Unit | Description |")
        lines.append("|-----------|----------|---------|------|-------------|")

        for cost in cost_types:
            name = cost.get("name", "")
            category = cost.get("category", "")
            default = cost.get("default_value", "")
            unit = cost.get("unit", "")
            # Truncate description for table
            desc = cost.get("display_name", "")
            lines.append(f"| `{name}` | {category} | {default} | {unit} | {desc} |")

        return "\n".join(lines)

    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for cost in cost_types:
        cat = cost.get("category", "Other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(cost)

    # Order categories
    category_order = ["PerTick", "OneTime", "Daily", "Modifier"]
    for cat in category_order:
        if cat not in by_category:
            continue

        lines.append(f"## {_format_category_name(cat)}")
        lines.append("")

        for cost in by_category[cat]:
            lines.append(_format_cost_markdown(cost, no_examples))

    return "\n".join(lines)


def _format_cost_markdown(cost: dict[str, Any], no_examples: bool) -> str:
    """Format a single cost type as markdown."""
    lines = []

    name = cost.get("name", "Unknown")
    display_name = cost.get("display_name", name)
    description = cost.get("description", "")

    lines.append(f"### {display_name} (`{name}`)")
    lines.append("")
    lines.append(description)
    lines.append("")

    # When incurred
    if incurred_at := cost.get("incurred_at"):
        lines.append(f"**When Incurred:** {incurred_at}")
        lines.append("")

    # Formula
    if formula := cost.get("formula"):
        lines.append("**Formula:**")
        lines.append("```")
        lines.append(formula)
        lines.append("```")
        lines.append("")

    # Default value
    default_value = cost.get("default_value", "")
    unit = cost.get("unit", "")
    if default_value:
        lines.append(f"**Default:** `{default_value}` ({unit})")
        lines.append("")

    # Data type
    if data_type := cost.get("data_type"):
        lines.append(f"**Type:** `{data_type}`")
        lines.append("")

    # Example
    if not no_examples and (example := cost.get("example")):
        lines.append("**Example:**")
        lines.append(f"- **Scenario:** {example.get('scenario', '')}")
        lines.append("- **Inputs:**")
        for input_name, input_value in example.get("inputs", []):
            lines.append(f"  - {input_name}: {input_value}")
        lines.append(f"- **Calculation:** {example.get('calculation', '')}")
        lines.append(f"- **Result:** {example.get('result', '')}")
        lines.append("")

    # Source location
    if source := cost.get("source_location"):
        lines.append(f"*Source: {source}*")
        lines.append("")

    # See also
    if see_also := cost.get("see_also"):
        see_also_str = ", ".join(f"`{s}`" for s in see_also)
        lines.append(f"**See also:** {see_also_str}")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def _format_category_name(category: str) -> str:
    """Format category enum value as readable name."""
    # Add space before capital letters
    formatted = re.sub(r"(?<!^)(?=[A-Z])", " ", category)

    # Add " Costs" suffix for clarity
    category_names = {
        "PerTick": "Per-Tick Costs",
        "OneTime": "One-Time Penalties",
        "Daily": "Daily Penalties",
        "Modifier": "Cost Modifiers",
    }

    return category_names.get(category, f"{formatted} Costs")
