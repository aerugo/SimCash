# Python Schema Access

Programmatic access to cost and policy schema documentation from Python.

## Overview

The `payment_simulator.schemas` module provides functions to retrieve filtered and formatted schema documentation for cost types and policy elements. It exposes the same functionality as the CLI commands [`payment-sim cost-schema`](../cli/commands/cost-schema.md) and [`payment-sim policy-schema`](../cli/commands/policy-schema.md).

## Installation

The schema functions are included in the `payment_simulator` package:

```python
from payment_simulator.schemas import (
    # Formatted/filtered access (recommended)
    get_cost_schema_formatted,
    get_policy_schema_formatted,
    # Raw JSON string access
    get_cost_schema,
    get_policy_schema,
)
```

## Functions

### get_cost_schema_formatted

Get cost schema documentation with optional filtering and formatting.

```python
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
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | `"json"` or `"markdown"` | `"markdown"` | Output format |
| `include_categories` | `list[str]` | `None` | Only include costs in these categories |
| `exclude_categories` | `list[str]` | `None` | Exclude costs in these categories |
| `include_names` | `list[str]` | `None` | Only include costs with these names |
| `exclude_names` | `list[str]` | `None` | Exclude costs with these names |
| `no_examples` | `bool` | `False` | Exclude example calculations from markdown |
| `compact` | `bool` | `False` | Use compact table format for markdown |

#### Valid Categories

- `"PerTick"` - Costs accrued every tick
- `"OneTime"` - Costs incurred once per event
- `"Daily"` - Costs incurred at end of day
- `"Modifier"` - Multipliers that modify other costs

#### Returns

- If `format="markdown"`: Returns a `str` containing markdown documentation
- If `format="json"`: Returns a `dict` containing the filtered schema

#### Examples

```python
from payment_simulator.schemas import get_cost_schema_formatted

# Full markdown documentation
markdown = get_cost_schema_formatted()
print(markdown)

# Only per-tick costs as JSON dict
data = get_cost_schema_formatted(
    format="json",
    include_categories=["PerTick"],
)
for cost in data["cost_types"]:
    print(f"{cost['name']}: {cost['description']}")

# Compact table excluding modifiers
compact_md = get_cost_schema_formatted(
    compact=True,
    exclude_categories=["Modifier"],
)

# Specific costs only
specific = get_cost_schema_formatted(
    format="json",
    include_names=["overdraft_bps_per_tick", "deadline_penalty"],
)
```

### get_policy_schema_formatted

Get policy schema documentation with optional filtering and formatting.

```python
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
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | `"json"` or `"markdown"` | `"markdown"` | Output format |
| `include_categories` | `list[str]` | `None` | Only include elements in these categories |
| `exclude_categories` | `list[str]` | `None` | Exclude elements in these categories |
| `include_trees` | `list[str]` | `None` | Only include elements valid in these tree types |
| `include_sections` | `list[str]` | `None` | Only include these schema sections |
| `no_examples` | `bool` | `False` | Exclude JSON examples from markdown |
| `compact` | `bool` | `False` | Use compact output with fewer details |

#### Valid Categories

**Actions:**
- `"PaymentAction"`, `"BankAction"`, `"CollateralAction"`, `"RtgsAction"`

**Fields:**
- `"TransactionField"`, `"AgentField"`, `"QueueField"`, `"CollateralField"`
- `"CostField"`, `"TimeField"`, `"LsmField"`, `"ThroughputField"`
- `"StateRegisterField"`, `"SystemField"`, `"DerivedField"`

**Expressions:**
- `"ComparisonOperator"`, `"LogicalOperator"`

**Computations:**
- `"BinaryArithmetic"`, `"NaryArithmetic"`, `"UnaryMath"`, `"TernaryMath"`

**Other:**
- `"ValueType"`, `"NodeType"`, `"TreeType"`

#### Valid Tree Types

- `"payment_tree"` - Per-payment decision tree
- `"bank_tree"` - Per-bank decision tree (runs each tick)
- `"strategic_collateral_tree"` - Strategic collateral management
- `"end_of_tick_collateral_tree"` - End-of-tick collateral cleanup

#### Valid Sections

- `"trees"`, `"nodes"`, `"expressions"`, `"values"`, `"computations"`, `"actions"`, `"fields"`

#### Returns

- If `format="markdown"`: Returns a `str` containing markdown documentation
- If `format="json"`: Returns a `dict` containing the filtered schema

#### Examples

```python
from payment_simulator.schemas import get_policy_schema_formatted

# Full markdown documentation
markdown = get_policy_schema_formatted()

# Only actions for payment tree as JSON
actions_data = get_policy_schema_formatted(
    format="json",
    include_sections=["actions"],
    include_trees=["payment_tree"],
)
for action in actions_data["actions"]:
    print(f"{action['json_key']}: {action['description']}")

# Transaction and agent fields only
fields_md = get_policy_schema_formatted(
    include_categories=["TransactionField", "AgentField"],
    compact=True,
)

# Exclude collateral-related elements
no_collateral = get_policy_schema_formatted(
    exclude_categories=["CollateralAction", "CollateralField"],
)
```

### Raw Functions

For advanced use cases, raw JSON string access is also available:

```python
from payment_simulator.schemas import get_cost_schema, get_policy_schema
import json

# Returns JSON string from Rust FFI
cost_json = get_cost_schema()
cost_data = json.loads(cost_json)

policy_json = get_policy_schema()
policy_data = json.loads(policy_json)
```

## Use Cases

### Building LLM Prompts

Generate context-appropriate schema documentation for AI prompts:

```python
from payment_simulator.schemas import (
    get_cost_schema_formatted,
    get_policy_schema_formatted,
)

def build_policy_prompt(tree_type: str) -> str:
    """Build prompt with relevant policy schema for a specific tree."""
    # Get actions and fields valid for this tree
    schema_md = get_policy_schema_formatted(
        include_sections=["actions", "fields"],
        include_trees=[tree_type],
        compact=True,
        no_examples=True,
    )

    return f"""You are designing a {tree_type} policy.

Available elements:
{schema_md}

Create a policy that optimizes settlement efficiency.
"""

def build_cost_explanation_prompt() -> str:
    """Build prompt with cost documentation."""
    cost_md = get_cost_schema_formatted(
        include_categories=["PerTick", "OneTime"],
        no_examples=False,
    )

    return f"""Explain how these costs affect bank behavior:

{cost_md}
"""
```

### Documentation Generation

Generate up-to-date documentation files:

```python
from pathlib import Path
from payment_simulator.schemas import get_cost_schema_formatted

# Generate cost reference docs
cost_docs = get_cost_schema_formatted(no_examples=False)
Path("docs/costs.md").write_text(cost_docs)

# Generate compact reference card
compact_ref = get_cost_schema_formatted(compact=True)
Path("docs/cost-reference-card.md").write_text(compact_ref)
```

### Programmatic Analysis

Analyze schema structure programmatically:

```python
from payment_simulator.schemas import get_cost_schema_formatted

# Get all costs as structured data
data = get_cost_schema_formatted(format="json")

# Find costs with specific characteristics
per_tick_costs = [
    c for c in data["cost_types"]
    if c["category"] == "PerTick"
]

# Get all cost names
all_names = [c["name"] for c in data["cost_types"]]

# Find costs with examples
with_examples = [
    c for c in data["cost_types"]
    if c.get("example")
]
```

### Filtering Based on Scenario

Match CLI filtering behavior programmatically:

```python
from payment_simulator.schemas import get_cost_schema_formatted
from payment_simulator.config import load_config

# Load scenario to get its cost toggles
config = load_config("scenario.yaml")

# Apply same filters as scenario
include_cats = None
exclude_cats = []

if config.cost_feature_toggles:
    if config.cost_feature_toggles.include:
        include_cats = config.cost_feature_toggles.include
    if config.cost_feature_toggles.exclude:
        exclude_cats = config.cost_feature_toggles.exclude

# Get filtered schema
schema = get_cost_schema_formatted(
    format="json",
    include_categories=include_cats,
    exclude_categories=exclude_cats,
)
```

## CLI Equivalents

| Python Call | CLI Equivalent |
|-------------|----------------|
| `get_cost_schema_formatted()` | `payment-sim cost-schema` |
| `get_cost_schema_formatted(format="json")` | `payment-sim cost-schema --format json` |
| `get_cost_schema_formatted(include_categories=["PerTick"])` | `payment-sim cost-schema --category PerTick` |
| `get_cost_schema_formatted(exclude_names=["foo"])` | `payment-sim cost-schema --exclude foo` |
| `get_cost_schema_formatted(compact=True)` | `payment-sim cost-schema --compact` |
| `get_policy_schema_formatted(include_trees=["payment_tree"])` | `payment-sim policy-schema --tree payment_tree` |
| `get_policy_schema_formatted(include_sections=["actions"])` | `payment-sim policy-schema --section actions` |

## Related Documentation

- [Cost Schema CLI](../cli/commands/cost-schema.md) - CLI command documentation
- [Policy Schema CLI](../cli/commands/policy-schema.md) - CLI command documentation
- [Cost Configuration](../scenario/costs.md) - Configuring costs in scenarios
- [Policy Configuration](../scenario/policies.md) - Configuring policies in scenarios
