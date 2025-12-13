# Policy Configuration

Policies control **how agents decide when and how to release payments**. Each agent has a policy that determines its behavior.

> **Note**: The `policy` field is **optional**. If omitted, agents default to `Fifo` (submit all transactions immediately). This is useful when policies are programmatically injected at runtime (e.g., by experiment runners or LLM optimization loops).

---

## Policy Types Overview

| Type | Description | Use Case |
|:-----|:------------|:---------|
| `Fifo` | Submit all transactions immediately | Baseline, passive agents |
| `Deadline` | Submit when deadline approaches | Simple urgency-based |
| `LiquidityAware` | Maintain target balance buffer | Conservative liquidity management |
| `LiquiditySplitting` | Split large payments | High-value transaction handling |
| `MockSplitting` | Deterministic splits for testing | Unit tests |
| `FromJson` | JSON DSL decision tree from file | Advanced, customizable strategies |
| `Inline` | Embedded JSON DSL decision tree (dict) | Dynamic testing, LLM experiments |
| `InlineJson` | JSON DSL decision tree (string) | LLM outputs, database-stored policies |

---

## Policy Schema (Union Type)

```yaml
policy:
  type: <PolicyType>
  # Additional fields depend on type
```

The `type` field determines which policy is used and what additional parameters are required.

---

## `Fifo` Policy

**Type**: `Fifo`
**Parameters**: None
**Behavior**: Submit all transactions to Queue 2 immediately when evaluated.

### Schema

```yaml
policy:
  type: Fifo
```

### Behavior

1. Agent evaluates Queue 1 (internal queue)
2. All transactions are immediately submitted to Queue 2 (RTGS)
3. No holding, no splitting, no cost optimization

### Use Cases

- Baseline comparison
- Passive counterparty agents
- BIS model replication
- Testing LSM without policy interference

### Example

```yaml
agents:
  - id: COUNTERPARTY
    opening_balance: 10000000
    policy:
      type: Fifo
```

---

## `Deadline` Policy

**Type**: `Deadline`
**Parameters**: `urgency_threshold`
**Behavior**: Hold transactions until deadline approaches, then submit.

### Schema

```yaml
policy:
  type: Deadline
  urgency_threshold: <int>    # Required, ticks > 0
```

### Fields

#### `urgency_threshold`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`

Number of ticks before deadline when transaction becomes "urgent" and is released.

### Behavior

1. Calculate `ticks_to_deadline = deadline_tick - current_tick`
2. If `ticks_to_deadline <= urgency_threshold`: Release
3. Otherwise: Hold

### Use Cases

- Delay-minimizing strategies
- When agents want to wait for incoming payments
- Testing deadline-based behavior

### Example

```yaml
agents:
  - id: PATIENT_BANK
    policy:
      type: Deadline
      urgency_threshold: 15    # Release when <= 15 ticks to deadline
```

---

## `LiquidityAware` Policy

**Type**: `LiquidityAware`
**Parameters**: `target_buffer`, `urgency_threshold`
**Behavior**: Maintain minimum balance buffer, override when urgent.

### Schema

```yaml
policy:
  type: LiquidityAware
  target_buffer: <int>        # Required, cents >= 0
  urgency_threshold: <int>    # Required, ticks > 0
```

### Fields

#### `target_buffer`

**Type**: `int` (cents)
**Required**: Yes
**Constraint**: `>= 0`

Minimum balance to maintain after releasing a transaction.

#### `urgency_threshold`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`

Ticks to deadline that overrides buffer requirement.

### Behavior

1. If `ticks_to_deadline <= urgency_threshold`: Release (urgent override)
2. If `balance - amount >= target_buffer`: Release (buffer maintained)
3. Otherwise: Hold

### Use Cases

- Conservative liquidity management
- Risk-averse agents
- Maintaining operational buffers

### Example

```yaml
agents:
  - id: CONSERVATIVE_BANK
    opening_balance: 10000000    # $100,000
    policy:
      type: LiquidityAware
      target_buffer: 500000      # Maintain $5,000 buffer
      urgency_threshold: 10      # Override buffer if <= 10 ticks to deadline
```

---

## `LiquiditySplitting` Policy

**Type**: `LiquiditySplitting`
**Parameters**: `max_splits`, `min_split_amount`
**Behavior**: Split large transactions that exceed available liquidity.

### Schema

```yaml
policy:
  type: LiquiditySplitting
  max_splits: <int>           # Required, 2-10
  min_split_amount: <int>     # Required, cents > 0
```

### Fields

#### `max_splits`

**Type**: `int`
**Required**: Yes
**Constraint**: `2 <= value <= 10`

Maximum number of parts to split a transaction into.

#### `min_split_amount`

**Type**: `int` (cents)
**Required**: Yes
**Constraint**: `> 0`

Minimum size for each split part.

### Behavior

1. Check if transaction is divisible (`divisible: true` in arrival config)
2. If not divisible: Release or Hold based on liquidity
3. If divisible and `amount > available_liquidity`:
   - Calculate optimal split count (respecting `max_splits` and `min_split_amount`)
   - Create child transactions
   - Submit children that can be afforded

### Use Cases

- High-value transaction handling
- Gradual settlement of large payments
- Improving LSM matching opportunities

### Example

```yaml
agents:
  - id: LARGE_VALUE_BANK
    policy:
      type: LiquiditySplitting
      max_splits: 4              # Split into max 4 parts
      min_split_amount: 50000    # Each part at least $500
    arrival_config:
      divisible: true            # Transactions can be split
```

---

## `MockSplitting` Policy

**Type**: `MockSplitting`
**Parameters**: `num_splits`
**Behavior**: Always split transactions into exactly N parts (for testing).

### Schema

```yaml
policy:
  type: MockSplitting
  num_splits: <int>           # Required, 2-10
```

### Fields

#### `num_splits`

**Type**: `int`
**Required**: Yes
**Constraint**: `2 <= value <= 10`

Exact number of parts to split into.

### Behavior

1. All divisible transactions are split into exactly `num_splits` parts
2. Non-divisible transactions are released immediately
3. No liquidity checking

### Use Cases

- Unit testing split mechanics
- Deterministic splitting for replay verification
- Testing LSM cycle behavior with splits

### Example

```yaml
agents:
  - id: TEST_SPLITTER
    policy:
      type: MockSplitting
      num_splits: 3              # Always split into 3 parts
```

---

## `FromJson` Policy

**Type**: `FromJson`
**Parameters**: `json_path`
**Behavior**: Load and execute a JSON DSL decision tree.

### Schema

```yaml
policy:
  type: FromJson
  json_path: <string>         # Required, path to JSON file
```

### Fields

#### `json_path`

**Type**: `str`
**Required**: Yes
**Constraint**: Valid file path

Path to JSON policy file, relative to `simulator/policies/` or absolute.

### Behavior

1. JSON file is loaded and parsed at simulation start
2. Policy tree is evaluated for each transaction in Queue 1
3. Supports:
   - `payment_tree`: Per-transaction decisions
   - `bank_tree`: Per-tick agent-level decisions
   - `strategic_collateral_tree`: Pre-settlement collateral management
   - `end_of_tick_collateral_tree`: Post-settlement collateral management

### JSON Policy Structure

See [docs/policy_dsl_guide.md](../../policy_dsl_guide.md) for complete DSL reference.

```json
{
  "version": "1.0",
  "policy_id": "my_policy",
  "description": "Example policy",
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "root",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "release",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "hold",
      "action": "Hold"
    }
  }
}
```

### Parameter Overrides

Policy parameters can be overridden per-agent:

```yaml
agents:
  - id: AGGRESSIVE_BANK
    policy:
      type: FromJson
      json_path: "simulator/policies/liquidity_aware.json"
      params:                    # Override JSON defaults
        urgency_threshold: 3.0   # More aggressive than default
        target_buffer: 50000.0   # Smaller buffer
```

### Available Decision Trees

| Tree | When Evaluated | Purpose |
|:-----|:---------------|:--------|
| `payment_tree` | Per transaction in Queue 1 | Release/Hold/Split decisions |
| `bank_tree` | Once per agent per tick | Set release budgets, state registers |
| `strategic_collateral_tree` | Before settlements | Proactive collateral posting |
| `end_of_tick_collateral_tree` | After settlements | Reactive collateral withdrawal |

### Use Cases

- Advanced strategy implementation
- Cost-aware optimization
- Time-based strategies
- State-dependent behavior
- Collateral management

### Example

```yaml
agents:
  - id: SOPHISTICATED_BANK
    policy:
      type: FromJson
      json_path: "simulator/policies/adaptive_liquidity_manager.json"
      params:
        urgency_threshold: 5.0
        target_buffer: 200000.0
        collateral_safety_margin: 1.2
```

---

## `Inline` Policy

**Type**: `Inline`
**Parameters**: `decision_trees`
**Behavior**: Embed a JSON DSL decision tree directly in configuration.

### Schema

```yaml
policy:
  type: Inline
  decision_trees: <dict>    # Required, embedded DSL structure
```

### Fields

#### `decision_trees`

**Type**: `dict`
**Required**: Yes

Embedded decision tree DSL structure, same format as `seed_policy.json` files used by `FromJson`.

### Behavior

1. Decision tree is embedded directly in YAML/dict configuration
2. At simulation start, serialized to JSON and passed to Rust engine
3. Identical execution semantics to `FromJson`
4. Supports all decision tree types (`payment_tree`, `bank_tree`, etc.)

### Use Cases

- **Dynamic policy testing**: Test policy variations without file I/O
- **LLM policy optimization**: Generate and evaluate policies programmatically
- **Parameter sweeps**: Vary policy structure across experiments
- **Unit testing**: Define test policies inline in test code

### Example

```yaml
agents:
  - id: DYNAMIC_BANK
    opening_balance: 10000000
    policy:
      type: Inline
      decision_trees:
        version: "1.0"
        policy_id: "inline_urgency"
        description: "Inline urgency-based policy"
        parameters:
          urgency_threshold: 5.0
        payment_tree:
          type: condition
          node_id: root
          condition:
            op: "<="
            left:
              field: ticks_to_deadline
            right:
              param: urgency_threshold
          on_true:
            type: action
            node_id: release
            action: Release
          on_false:
            type: action
            node_id: hold
            action: Hold
```

### Programmatic Example (Python)

```python
from payment_simulator.config.schemas import SimulationConfig, AgentConfig, InlinePolicy

# Dynamically generate policy
policy = InlinePolicy(
    decision_trees={
        "version": "1.0",
        "policy_id": "generated_policy",
        "payment_tree": {
            "type": "action",
            "node_id": "always_release",
            "action": "Release"
        }
    }
)

agent = AgentConfig(
    id="AGENT_A",
    opening_balance=10000000,
    policy=policy
)
```

### Feature Toggle Validation

`Inline` policies are validated against `policy_feature_toggles`, just like `FromJson` policies. If the embedded decision tree uses forbidden categories, the simulation will not start.

---

## `InlineJson` Policy

**Type**: `InlineJson`
**Parameters**: `json_string`
**Behavior**: Parse and execute a JSON DSL decision tree from a raw JSON string.

### Schema

```yaml
policy:
  type: InlineJson
  json_string: '{"version":"2.0","policy_id":"test",...}'  # JSON string
```

### Fields

#### `json_string`

**Type**: `str`
**Required**: Yes
**Constraint**: Valid JSON that parses to a policy structure

A raw JSON string containing the complete policy definition.

### Behavior

1. JSON string is validated on configuration load
2. At simulation start, passed directly to Rust engine as `FromJson` policy
3. Identical execution semantics to `Inline` (but accepts string instead of dict)

### Use Cases

- **LLM-generated policies**: LLMs output JSON as strings, not Python dicts
- **Database-stored policies**: Policies retrieved from database are strings
- **API-submitted policies**: External services send JSON string payloads
- **Castro experiment injection**: Optimization loop injects policies as JSON strings

### Example (YAML)

```yaml
agents:
  - id: LLM_OPTIMIZED_BANK
    opening_balance: 10000000
    policy:
      type: InlineJson
      json_string: |
        {
          "version": "2.0",
          "policy_id": "llm_policy_v1",
          "parameters": {"urgency_threshold": 5.0},
          "payment_tree": {
            "type": "condition",
            "node_id": "root",
            "condition": {
              "op": "<=",
              "left": {"field": "ticks_to_deadline"},
              "right": {"param": "urgency_threshold"}
            },
            "on_true": {"type": "action", "node_id": "release", "action": "Release"},
            "on_false": {"type": "action", "node_id": "hold", "action": "Hold"}
          }
        }
```

### Example (Python)

```python
from payment_simulator.config.schemas import AgentConfig, InlineJsonPolicy
import json

# Policy generated by LLM or retrieved from database
policy_dict = {
    "version": "2.0",
    "policy_id": "optimized_policy",
    "payment_tree": {
        "type": "action",
        "node_id": "always_release",
        "action": "Release"
    }
}

# InlineJson takes string, not dict
policy = InlineJsonPolicy(json_string=json.dumps(policy_dict))

agent = AgentConfig(
    id="AGENT_A",
    opening_balance=10000000,
    policy=policy
)
```

### Difference from `Inline`

| Aspect | `Inline` | `InlineJson` |
|:-------|:---------|:-------------|
| Input type | `dict` (Python dictionary) | `str` (JSON string) |
| Use case | YAML configs, Python code | LLM output, database, APIs |
| Validation | Pydantic validates structure | JSON parsed then validated |

### Feature Toggle Validation

`InlineJson` policies are validated against `policy_feature_toggles`, just like other policy types.

---

## Policy Selection Guide

| Scenario | Recommended Policy |
|:---------|:-------------------|
| Passive counterparty | `Fifo` |
| Simple urgency-based | `Deadline` |
| Conservative bank | `LiquidityAware` |
| High-value payments | `LiquiditySplitting` |
| Complex strategies (file-based) | `FromJson` |
| Complex strategies (embedded dict) | `Inline` |
| LLM-generated policies | `InlineJson` |
| Database-stored policies | `InlineJson` |
| Testing | `MockSplitting` |

---

## Navigation

**Previous**: [Agents](agents.md)
**Next**: [Arrivals](arrivals.md)
