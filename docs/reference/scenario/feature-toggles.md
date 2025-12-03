# Policy Feature Toggles

> Restrict which policy DSL features are available in a scenario

## Overview

Scenario authors can control which policy DSL features are available in a given scenario by specifying `policy_feature_toggles` in the scenario configuration. This allows:

- **Simplified scenarios**: Research scenarios that only allow basic payment actions
- **Feature-gated experiments**: Testing policies with/without advanced features like collateral
- **Compliance testing**: Ensuring policies don't use certain features
- **Educational use**: Gradually introducing policy features to learners

## Configuration

The `policy_feature_toggles` section supports two mutually exclusive options:

### Include List

Only allow specific categories:

```yaml
policy_feature_toggles:
  include:
    - PaymentAction
    - TransactionField
    - TimeField
    - ComparisonOperator
```

When an include list is specified, **only** the listed categories are allowed. Any policy using categories not in the list will be rejected.

### Exclude List

Allow all except specific categories:

```yaml
policy_feature_toggles:
  exclude:
    - CollateralAction
    - CollateralField
    - StateRegisterField
```

When an exclude list is specified, all categories are allowed **except** those listed.

### Validation Rule

A scenario can only have an `include` OR an `exclude` list, not both. Specifying both will result in a configuration error.

## Available Categories

Categories group related schema elements:

### Expression Categories

| Category | Description |
|----------|-------------|
| `ComparisonOperator` | Comparison operators (==, !=, <, <=, >, >=) |
| `LogicalOperator` | Logical operators (and, or, not) |

### Computation Categories

| Category | Description |
|----------|-------------|
| `BinaryArithmetic` | Two-operand arithmetic (+, -, *, /) |
| `NaryArithmetic` | N-operand arithmetic (sum, min, max) |
| `UnaryMath` | Single-operand math (abs, neg) |
| `TernaryMath` | Three-operand math (clamp) |

### Value Categories

| Category | Description |
|----------|-------------|
| `ValueType` | Value types (constant, field, param, compute) |

### Action Categories

| Category | Description |
|----------|-------------|
| `PaymentAction` | Payment processing (Release, Hold, Drop, Split, Reprioritize) |
| `BankAction` | Bank-level actions (SetReleaseBudget) |
| `CollateralAction` | Collateral management (PostCollateral, WithdrawCollateral) |
| `RtgsAction` | RTGS-specific actions (WithdrawFromQueue2, ResubmitToRtgs) |

### Field Categories

| Category | Description |
|----------|-------------|
| `TransactionField` | Transaction fields (amount, priority, deadline) |
| `AgentField` | Agent fields (balance, credit_limit) |
| `QueueField` | Queue fields (queue1_size, queue2_value) |
| `CollateralField` | Collateral fields (posted_collateral, available_credit) |
| `CostField` | Cost fields (cost_delay_this_tx_one_tick, cost_overdraft) |
| `TimeField` | Time fields (current_tick, ticks_to_deadline, is_eod_rush) |
| `LsmField` | LSM fields (bilateral_offset_potential, cycle_count) |
| `ThroughputField` | Throughput fields (arrivals_this_tick, settlements_this_tick) |
| `StateRegisterField` | State register fields (register_a, register_b, etc.) |
| `SystemField` | System fields (total_system_liquidity, num_agents) |
| `DerivedField` | Computed derived fields (urgency_score, liquidity_pressure) |

### Node/Tree Categories

| Category | Description |
|----------|-------------|
| `NodeType` | Decision tree node types |
| `TreeType` | Policy tree types |

## CLI Integration

### Validating Policies

Use the `validate-policy` command with `--scenario` to check if a policy is valid for a scenario's toggles:

```bash
# Validate policy against scenario's feature toggles
payment-sim validate-policy policy.json --scenario scenario.yaml
```

If the policy uses forbidden categories, the command will output:

```
Validation Errors
Type               Message
ForbiddenCategory  Policy uses forbidden categories: CollateralAction. Allowed categories: PaymentAction.

Forbidden categories used: CollateralAction

Policy validation failed with 1 error(s)
```

### Viewing Allowed Schema

Use the `policy-schema` command with `--scenario` to see only the schema elements allowed by the scenario:

```bash
# Show schema filtered by scenario's feature toggles
payment-sim policy-schema --scenario scenario.yaml

# JSON format with scenario filtering
payment-sim policy-schema --scenario scenario.yaml --format json

# Combine with other filters
payment-sim policy-schema --scenario scenario.yaml --section actions
```

### Running Simulations

When running a simulation with `payment-sim run`, policies using `FromJson` or `Inline` types are automatically validated against the scenario's feature toggles:

```bash
payment-sim run --config scenario.yaml
```

If an agent's JSON policy uses forbidden categories, the simulation will not start and an error will be displayed.

## Examples

### Research Scenario (Simple Policies Only)

Allow only basic payment actions and time-based decisions:

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10
  rng_seed: 42

policy_feature_toggles:
  include:
    - PaymentAction
    - TransactionField
    - TimeField
    - ComparisonOperator
    - LogicalOperator

agents:
  - id: BANK_A
    opening_balance: 10000000
    policy:
      type: FromJson
      json_path: policies/deadline_aware.json  # Must not use collateral, state registers, etc.
```

### Production Scenario (No Experimental Features)

Allow all features except experimental/advanced ones:

```yaml
policy_feature_toggles:
  exclude:
    - StateRegisterField
    - DerivedField
    - SystemField
```

### Teaching Scenario (Progressive Complexity)

Level 1 - Basic concepts:

```yaml
policy_feature_toggles:
  include:
    - PaymentAction  # Only Release, Hold
```

Level 2 - Add comparisons:

```yaml
policy_feature_toggles:
  include:
    - PaymentAction
    - ComparisonOperator
    - TransactionField  # amount, priority
    - TimeField  # deadline
```

Level 3 - Add arithmetic:

```yaml
policy_feature_toggles:
  include:
    - PaymentAction
    - ComparisonOperator
    - BinaryArithmetic
    - TransactionField
    - TimeField
    - AgentField  # balance
    - CostField  # cost calculations
```

## Built-in Policies

Note that feature toggles only apply to `FromJson` and `Inline` policies. Built-in policies (Fifo, Deadline, LiquidityAware, etc.) are not subject to feature toggle validation because they are implemented in Rust and don't use the policy DSL.

## Implementation Details

**Config Schema**: `api/payment_simulator/config/schemas.py` - `PolicyFeatureToggles` class

**Validation Function**: `api/payment_simulator/policy/validation.py` - `validate_policy_for_scenario()`

**Category Extraction**: `api/payment_simulator/policy/analysis.py` - `extract_categories_from_policy()`

---

*Last updated: 2025-12-03*
