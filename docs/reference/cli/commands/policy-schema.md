# policy-schema

Generate policy schema documentation.

## Synopsis

```bash
payment-sim policy-schema [OPTIONS]
```

## Description

The `policy-schema` command generates comprehensive documentation for the policy DSL (Domain Specific Language). It extracts schema information directly from the Rust backend and formats it as markdown or JSON.

This command is useful for:

- Generating up-to-date policy reference documentation
- Exploring available policy elements (actions, expressions, fields)
- Filtering schema to specific categories or tree types
- Exporting schema for external tools or documentation systems

## Options

### Output Format

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--format` | `-f` | Enum | `markdown` | Output format: `json` or `markdown`. |
| `--output` | `-o` | Path | stdout | Output file (default: stdout). |
| `--no-examples` | - | Boolean | `false` | Exclude JSON examples from output. |
| `--compact` | - | Boolean | `false` | Compact output with fewer details. |

### Filtering

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--category` | `-c` | List | All | Filter to specific categories (repeatable). |
| `--exclude-category` | `-x` | List | None | Exclude specific categories (repeatable). |
| `--tree` | `-t` | List | All | Filter to elements valid in specific trees. |
| `--section` | `-s` | List | All | Include only specific sections. |
| `--scenario` | - | Path | None | Apply scenario's feature toggles as filters. |

## Categories

Categories group related schema elements:

### Expression Categories

| Category | Description |
|----------|-------------|
| `ComparisonOperator` | Comparison operators (gt, lt, eq, etc.) |
| `LogicalOperator` | Logical operators (and, or, not) |

### Computation Categories

| Category | Description |
|----------|-------------|
| `BinaryArithmetic` | Two-operand arithmetic (add, sub, mul, div) |
| `NaryArithmetic` | N-operand arithmetic (sum, product) |
| `UnaryMath` | Single-operand math (abs, neg) |
| `TernaryMath` | Three-operand math (clamp) |

### Value Categories

| Category | Description |
|----------|-------------|
| `ValueType` | Value types (constant, field, computation) |

### Action Categories

| Category | Description |
|----------|-------------|
| `PaymentAction` | Payment processing actions (submit, hold, drop, split) |
| `BankAction` | Bank-level actions (set_release_budget) |
| `CollateralAction` | Collateral management actions (post, withdraw) |
| `RtgsAction` | RTGS-specific actions |

### Field Categories

| Category | Description |
|----------|-------------|
| `TransactionField` | Transaction fields (amount, priority, deadline) |
| `AgentField` | Agent fields (balance, queue_size) |
| `QueueField` | Queue fields (pending_count, total_value) |
| `CollateralField` | Collateral fields (posted, available) |
| `CostField` | Cost fields (delay_cost, overdraft_cost) |
| `TimeField` | Time fields (current_tick, current_day) |
| `LsmField` | LSM fields (bilateral_offset_potential) |
| `ThroughputField` | Throughput fields (payments_settled_today) |
| `StateRegisterField` | State register fields (custom user-defined) |
| `SystemField` | System fields (global state) |
| `DerivedField` | Computed derived fields |

### Node/Tree Categories

| Category | Description |
|----------|-------------|
| `NodeType` | Decision tree node types |
| `TreeType` | Policy tree types |

## Tree Types

Policy elements can be filtered by tree context:

| Tree | Description |
|------|-------------|
| `payment_tree` | Per-payment decision tree |
| `bank_tree` | Per-bank decision tree (runs each tick) |
| `strategic_collateral_tree` | Strategic collateral management tree |
| `end_of_tick_collateral_tree` | End-of-tick collateral cleanup tree |

## Sections

Schema can be filtered by section:

| Section | Description |
|---------|-------------|
| `trees` | Tree type definitions |
| `nodes` | Node type definitions |
| `expressions` | Expression operators |
| `values` | Value type definitions |
| `computations` | Computation operators |
| `actions` | Action definitions |
| `fields` | Context field definitions |

## Examples

### Full Documentation

```bash
# Full markdown documentation to stdout
payment-sim policy-schema

# Save to file
payment-sim policy-schema --output schema.md

# Full JSON schema
payment-sim policy-schema --format json --output schema.json
```

### Filtering by Section

```bash
# Only actions section
payment-sim policy-schema --section actions

# Actions and fields
payment-sim policy-schema --section actions --section fields

# JSON format for actions only
payment-sim policy-schema --section actions --format json
```

### Filtering by Category

```bash
# Only payment actions
payment-sim policy-schema --category PaymentAction

# Transaction and agent fields
payment-sim policy-schema --category TransactionField --category AgentField

# Exclude collateral actions
payment-sim policy-schema --exclude-category CollateralAction

# All fields except derived
payment-sim policy-schema --section fields --exclude-category DerivedField
```

### Filtering by Tree

```bash
# Elements valid in payment tree
payment-sim policy-schema --tree payment_tree

# Elements valid in bank tree
payment-sim policy-schema --tree bank_tree

# Collateral tree elements
payment-sim policy-schema --tree strategic_collateral_tree --tree end_of_tick_collateral_tree
```

### Compact Output

```bash
# Compact markdown (less detail)
payment-sim policy-schema --compact

# Compact without examples
payment-sim policy-schema --compact --no-examples
```

### Combined Filters

```bash
# Payment actions for payment tree, compact JSON
payment-sim policy-schema \
  --category PaymentAction \
  --tree payment_tree \
  --format json \
  --compact

# All fields except derived, as markdown without examples
payment-sim policy-schema \
  --section fields \
  --exclude-category DerivedField \
  --no-examples
```

### Scenario Feature Toggles

When a scenario file specifies `policy_feature_toggles`, use `--scenario` to automatically apply those restrictions:

```yaml
# scenario.yaml
policy_feature_toggles:
  include:
    - PaymentAction
    - TransactionField
    - AgentField
```

```bash
# Generate schema showing only categories allowed by scenario
payment-sim policy-schema --scenario scenario.yaml

# Combine with other filters (CLI filters merge with scenario toggles)
payment-sim policy-schema --scenario scenario.yaml --section actions
```

This is useful for:
- Generating documentation for a restricted policy environment
- Understanding what policy elements are available in a specific scenario
- Creating policy templates that conform to scenario restrictions

See [Feature Toggles](../../scenario/feature-toggles.md) for complete documentation.

## Output Format

### Markdown Format

```markdown
# Policy Schema Reference

> Generated: 2024-01-15T10:30:00Z
> Version: 1.0.0

## Actions

### Payment Action

#### `submit`

Submit the transaction to RTGS for immediate settlement.

**Semantics**: Moves transaction from queue to RTGS processing

**Valid in**: `payment_tree`

**Example**:
```json
{"action": "submit"}
```

*Source: backend/src/policy/actions.rs:45*

...
```

### JSON Format

```json
{
  "version": "1.0.0",
  "generated_at": "2024-01-15T10:30:00Z",
  "tree_types": [...],
  "node_types": [...],
  "expressions": [...],
  "values": [...],
  "computations": [...],
  "actions": [
    {
      "name": "Submit",
      "json_key": "submit",
      "category": "PaymentAction",
      "description": "Submit the transaction to RTGS...",
      "semantics": "Moves transaction from queue to RTGS...",
      "valid_in_trees": ["payment_tree"],
      "parameters": [],
      "example_json": {"action": "submit"},
      "source_location": "backend/src/policy/actions.rs:45"
    }
  ],
  "fields": [...]
}
```

## Use Cases

### Generate Policy Reference Docs

```bash
# Generate full reference
payment-sim policy-schema --output docs/reference/policy/auto-generated.md

# Update after code changes
payment-sim policy-schema --output docs/reference/policy/schema.md
```

### Explore Available Actions

```bash
# What actions can I use in payment tree?
payment-sim policy-schema --section actions --tree payment_tree

# What collateral actions exist?
payment-sim policy-schema --category CollateralAction
```

### Export for External Tools

```bash
# JSON for code generation
payment-sim policy-schema --format json --output schema.json

# Compact JSON for API
payment-sim policy-schema --format json --compact --no-examples
```

### Documentation Automation

```bash
# CI/CD: Regenerate docs on schema changes
payment-sim policy-schema --output docs/policy-schema.md
git diff --exit-code docs/policy-schema.md || (git add docs/policy-schema.md && git commit -m "Update policy schema docs")
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (schema extraction failed) |

## Related Documentation

- [Policy Reference](../../policy/index.md) - Complete policy DSL documentation
- [Policy Configuration](../../scenario/policies.md) - Configuring policies in scenarios
- [Feature Toggles](../../scenario/feature-toggles.md) - Scenario feature toggle configuration

## Implementation Details

**File**: `api/payment_simulator/cli/commands/policy_schema.py`

The schema is extracted from the Rust backend via the `get_policy_schema()` FFI function, which uses Rust reflection to enumerate all policy elements.
