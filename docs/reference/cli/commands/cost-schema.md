# cost-schema

Generate cost types schema documentation.

## Synopsis

```bash
payment-sim cost-schema [OPTIONS]
```

## Description

The `cost-schema` command generates comprehensive documentation for all cost types in the simulation. It extracts schema information directly from the Rust backend and formats it as markdown or JSON.

This command is useful for:

- Generating up-to-date cost type reference documentation
- Exploring available costs and their calculation formulas
- Filtering costs by category or name
- Understanding cost defaults and when they are incurred
- Exporting schema for external tools or documentation systems

## Options

### Output Format

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--format` | `-f` | Enum | `markdown` | Output format: `json` or `markdown`. |
| `--output` | `-o` | Path | stdout | Output file (default: stdout). |
| `--no-examples` | - | Boolean | `false` | Exclude example calculations from output. |
| `--compact` | - | Boolean | `false` | Compact table format output. |

### Filtering

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--category` | `-c` | List | All | Filter to specific categories (repeatable). |
| `--exclude-category` | `-x` | List | None | Exclude specific categories (repeatable). |
| `--include` | `-i` | List | All | Include only specific cost names (repeatable). |
| `--exclude` | `-e` | List | None | Exclude specific cost names (repeatable). |
| `--scenario` | - | Path | None | Apply scenario's `cost_feature_toggles` as filters. |

## Categories

Cost types are organized into four categories:

| Category | Description |
|----------|-------------|
| `PerTick` | Costs accrued every simulation tick (overdraft, delay, collateral, liquidity) |
| `OneTime` | Costs incurred once when an event occurs (deadline penalty, split friction) |
| `Daily` | Costs incurred at end of day (EOD penalty for unsettled transactions) |
| `Modifier` | Multipliers that modify other costs (overdue multiplier, priority multipliers) |

## Cost Types

The simulation includes 9 cost types:

### Per-Tick Costs (4)

| Name | Description |
|------|-------------|
| `overdraft_bps_per_tick` | Cost for negative balance (basis points per tick) |
| `delay_cost_per_tick_per_cent` | Cost per tick per cent of unsettled transaction value |
| `collateral_cost_per_tick_bps` | Cost for posted collateral (basis points per tick) |
| `liquidity_cost_per_tick_bps` | Cost for holding excess liquidity (basis points per tick) |

### One-Time Costs (2)

| Name | Description |
|------|-------------|
| `deadline_penalty` | Penalty when transaction becomes overdue |
| `split_friction_cost` | Cost incurred when splitting a transaction |

### Daily Costs (1)

| Name | Description |
|------|-------------|
| `eod_penalty_per_transaction` | Penalty per unsettled transaction at end of day |

### Modifiers (2)

| Name | Description |
|------|-------------|
| `overdue_delay_multiplier` | Multiplier applied to delay costs for overdue transactions |
| `priority_delay_multipliers` | Per-priority-band multipliers for delay costs |

## Examples

### Full Documentation

```bash
# Full markdown documentation to stdout
payment-sim cost-schema

# Save to file
payment-sim cost-schema --output costs.md

# Full JSON schema
payment-sim cost-schema --format json --output costs.json
```

### Filtering by Category

```bash
# Only per-tick costs
payment-sim cost-schema --category PerTick

# Per-tick and one-time costs
payment-sim cost-schema --category PerTick --category OneTime

# All except modifiers
payment-sim cost-schema --exclude-category Modifier

# Multiple exclusions
payment-sim cost-schema --exclude-category Modifier --exclude-category Daily
```

### Filtering by Name

```bash
# Only specific costs
payment-sim cost-schema --include overdraft_bps_per_tick --include deadline_penalty

# Exclude specific costs
payment-sim cost-schema --exclude priority_delay_multipliers

# Combine name and category filters
payment-sim cost-schema --category PerTick --exclude liquidity_cost_per_tick_bps
```

### Compact Output

```bash
# Compact table format
payment-sim cost-schema --compact

# Compact without examples
payment-sim cost-schema --compact --no-examples

# Compact JSON
payment-sim cost-schema --format json --compact
```

### Scenario Feature Toggles

When a scenario file specifies `cost_feature_toggles`, use `--scenario` to automatically apply those restrictions:

```yaml
# scenario.yaml
cost_feature_toggles:
  include:
    - PerTick
    - OneTime
  exclude:
    - liquidity_cost_per_tick_bps
```

```bash
# Generate schema showing only costs allowed by scenario
payment-sim cost-schema --scenario scenario.yaml

# Combine with other filters (CLI filters merge with scenario toggles)
payment-sim cost-schema --scenario scenario.yaml --category PerTick
```

This is useful for:
- Generating documentation for a restricted cost environment
- Understanding what costs are active in a specific scenario
- Creating cost configurations that conform to scenario restrictions

## Output Format

### Markdown Format

```markdown
# Cost Types Reference

> Generated: 2024-01-15T10:30:00Z
> Version: 1.0

## Per-Tick Costs

### Overdraft Cost (`overdraft_bps_per_tick`)

Cost for using intraday credit when balance goes negative.

**When Incurred:** Each tick while agent balance is negative

**Formula:**
```
cost = abs(negative_balance) * bps_rate / 10000
```

**Default:** `5` (basis points per tick)

**Type:** `i64`

**Example:**
- **Scenario:** Bank with -$10,000 balance
- **Inputs:**
  - balance: -1000000 cents
  - rate: 5 bps
- **Calculation:** 1000000 * 5 / 10000 = 500
- **Result:** 500 cents ($5.00) per tick

*Source: simulator/src/costs/rates.rs:45*

---
...
```

### JSON Format

```json
{
  "version": "1.0",
  "generated_at": "2024-01-15T10:30:00Z",
  "cost_types": [
    {
      "name": "overdraft_bps_per_tick",
      "display_name": "Overdraft Cost",
      "category": "PerTick",
      "description": "Cost for using intraday credit...",
      "incurred_at": "Each tick while agent balance is negative",
      "formula": "cost = abs(negative_balance) * bps_rate / 10000",
      "default_value": "5",
      "unit": "basis points per tick",
      "data_type": "i64",
      "source_location": "simulator/src/costs/rates.rs:45",
      "see_also": ["delay_cost_per_tick_per_cent"],
      "example": {
        "scenario": "Bank with -$10,000 balance",
        "inputs": [["balance", "-1000000 cents"], ["rate", "5 bps"]],
        "calculation": "1000000 * 5 / 10000 = 500",
        "result": "500 cents ($5.00) per tick"
      }
    }
  ]
}
```

### Compact Table Format

When using `--compact`:

```markdown
# Cost Types Reference

> Generated: 2024-01-15T10:30:00Z
> Version: 1.0

| Cost Type | Category | Default | Unit | Description |
|-----------|----------|---------|------|-------------|
| `overdraft_bps_per_tick` | PerTick | 5 | basis points per tick | Overdraft Cost |
| `delay_cost_per_tick_per_cent` | PerTick | 1 | cents per tick per cent | Delay Cost |
...
```

## Programmatic Access

The cost schema can also be accessed programmatically from Python. See [Python Schema Access](../python/schemas.md) for details.

```python
from payment_simulator.schemas import get_cost_schema_formatted

# Same as: payment-sim cost-schema --category PerTick
markdown = get_cost_schema_formatted(include_categories=["PerTick"])

# Same as: payment-sim cost-schema --format json --exclude-category Modifier
data = get_cost_schema_formatted(
    format="json",
    exclude_categories=["Modifier"],
)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid scenario file, schema extraction failed) |

## Related Documentation

- [Policy Schema](policy-schema.md) - Policy DSL schema documentation
- [Python Schema Access](../python/schemas.md) - Programmatic schema access
- [Cost Configuration](../../scenario/costs.md) - Configuring costs in scenarios

## Implementation Details

**File**: `api/payment_simulator/cli/commands/cost_schema.py`

The schema is extracted from the Rust backend via the `get_cost_schema()` FFI function, which uses the `CostSchemaDocumented` trait to enumerate all cost types with their documentation.
