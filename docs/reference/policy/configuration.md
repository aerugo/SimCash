# Policy Configuration

> **Reference: Configuring Policies in YAML and JSON**

## Overview

Policies are configured at two levels:
1. **Policy JSON files** - Define decision tree structure and default parameters
2. **Simulation YAML files** - Assign policies to agents and override parameters

---

## Policy JSON File Structure

### Full Schema

```json
{
  "version": "1.0",
  "policy_id": "<unique_identifier>",
  "description": "<human_readable_description>",

  "parameters": {
    "<param_name>": <f64_value>,
    ...
  },

  "bank_tree": <TreeNode | null>,
  "payment_tree": <TreeNode | null>,
  "strategic_collateral_tree": <TreeNode | null>,
  "end_of_tick_collateral_tree": <TreeNode | null>
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Schema version (currently "1.0") |
| `policy_id` | string | Unique identifier for this policy |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | null | Human-readable description |
| `parameters` | object | `{}` | Named constants for tree evaluation |
| `bank_tree` | TreeNode | null | Bank-level decision tree |
| `payment_tree` | TreeNode | null | Payment release decision tree |
| `strategic_collateral_tree` | TreeNode | null | Pre-settlement collateral tree |
| `end_of_tick_collateral_tree` | TreeNode | null | Post-settlement collateral tree |

### Minimal Policy
```json
{
  "version": "1.0",
  "policy_id": "always_release",
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  }
}
```

### Full Policy Example
```json
{
  "version": "1.0",
  "policy_id": "comprehensive_policy",
  "description": "Full policy with all four trees",

  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0,
    "max_budget_per_tick": 500000.0,
    "collateral_trigger_gap": 200000.0
  },

  "bank_tree": {
    "type": "action",
    "node_id": "B1_SetBudget",
    "action": "SetReleaseBudget",
    "parameters": {
      "max_value_to_release": {"param": "max_budget_per_tick"}
    }
  },

  "payment_tree": {
    "type": "condition",
    "node_id": "N1_CheckUrgent",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_Release",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "A2_Hold",
      "action": "Hold"
    }
  },

  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_CheckGap",
    "condition": {
      "op": ">",
      "left": {"field": "queue1_liquidity_gap"},
      "right": {"param": "collateral_trigger_gap"}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_Post",
      "action": "PostCollateral",
      "parameters": {
        "amount": {"field": "queue1_liquidity_gap"},
        "reason": {"value": "UrgentLiquidityNeed"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_Hold",
      "action": "HoldCollateral"
    }
  },

  "end_of_tick_collateral_tree": {
    "type": "condition",
    "node_id": "EOT1_CheckExcess",
    "condition": {
      "op": ">",
      "left": {"field": "excess_collateral"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "action",
      "node_id": "EOT2_Withdraw",
      "action": "WithdrawCollateral",
      "parameters": {
        "amount": {"field": "excess_collateral"},
        "reason": {"value": "CostOptimization"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "EOT3_Hold",
      "action": "HoldCollateral"
    }
  }
}
```

---

## Simulation YAML Configuration

### Agent Policy Assignment

```yaml
agents:
  - id: BANK_A
    opening_balance: 5000000
    unsecured_cap: 2000000
    max_collateral: 10000000

    policy:
      type: FromJson
      json_path: "simulator/policies/liquidity_aware.json"
      params:
        urgency_threshold: 10.0    # Override default
        target_buffer: 200000.0    # Override default
```

### Policy Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Policy type (see below) |
| `json_path` | string | Conditional | Path to policy JSON file |
| `params` | object | No | Parameter overrides |

### Policy Types

| Type | Description |
|------|-------------|
| `FromJson` | Load from JSON file with optional param overrides |
| `Fifo` | Built-in FIFO policy (no JSON needed) |
| `Deadline` | Built-in deadline-based policy |
| `LiquidityAware` | Built-in liquidity-aware policy |

### FromJson Policy
```yaml
policy:
  type: FromJson
  json_path: "simulator/policies/my_policy.json"
  params:
    threshold: 5.0
```

### Built-in Policy with Parameters
```yaml
policy:
  type: LiquidityAware
  params:
    target_buffer: 100000
    urgency_threshold: 5
```

---

## Parameter Overrides

### How Override Works

1. **Default**: JSON file's `parameters` object
2. **Override**: YAML's `params` object
3. **Merged**: YAML overrides win, JSON defaults fill gaps

### Example

**Policy JSON**:
```json
{
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 50000.0,
    "max_splits": 4.0
  }
}
```

**Simulation YAML**:
```yaml
policy:
  type: FromJson
  json_path: "policy.json"
  params:
    urgency_threshold: 10.0
    # target_buffer not specified, uses default
```

**Resulting Parameters**:
```json
{
  "urgency_threshold": 10.0,   // From YAML
  "target_buffer": 50000.0,    // From JSON (default)
  "max_splits": 4.0            // From JSON (default)
}
```

---

## Available Policy Files

Located in `simulator/policies/`:

| File | Description | Key Parameters |
|------|-------------|----------------|
| `fifo.json` | Simple FIFO submission | None |
| `liquidity_aware.json` | Preserves liquidity buffer | `urgency_threshold`, `target_buffer` |
| `liquidity_splitting.json` | Splits large payments | `split_threshold`, `target_buffer` |
| `time_aware_test.json` | Time-of-day based strategy | `morning_rush_tick`, `eod_start_tick` |
| `target2_priority_aware.json` | Dual priority handling | `priority_threshold` |
| `target2_priority_escalator.json` | Auto-escalate priority | `escalation_ticks` |
| `target2_conservative_offsetter.json` | LSM-aware offset detection | `offset_threshold` |
| `target2_crisis_risk_denier.json` | Conservative crisis mode | `crisis_buffer` |
| `momentum_investment_bank.json` | Aggressive momentum-based | `momentum_threshold` |
| `balanced_cost_optimizer.json` | Cost-benefit trade-off | `cost_tolerance` |

---

## Complete Simulation Configuration Example

```yaml
# simulation_config.yaml

# Global simulation settings
ticks_per_day: 100
num_days: 5
seed: 12345
eod_rush_threshold: 0.8

# Cost configuration
cost_config:
  overdraft_bps_per_tick: 0.5
  delay_cost_per_tick_per_cent: 0.0001
  collateral_cost_per_tick_bps: 0.1
  split_friction_cost: 100
  deadline_penalty: 10000
  eod_penalty_per_transaction: 50000
  overdue_delay_multiplier: 5.0

# RTGS configuration
rtgs_config:
  priority_mode: true
  lsm_enabled: true
  lsm_algorithm: "sequential"
  bilateral_limit: 5
  multilateral_limit: 10

# Queue configuration
queue_config:
  queue1_ordering: "priority_deadline"

# Priority escalation
priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 20
  max_boost: 3

# Agents
agents:
  - id: BANK_A
    opening_balance: 10000000
    unsecured_cap: 5000000
    max_collateral: 20000000
    collateral_haircut: 0.1

    policy:
      type: FromJson
      json_path: "simulator/policies/liquidity_aware.json"
      params:
        urgency_threshold: 10.0
        target_buffer: 500000.0

    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: LogNormal
        mean: 200000
        std_dev: 100000
        min: 10000
        max: 2000000
      priority_distribution:
        type: Categorical
        values: [3, 5, 7, 9]
        weights: [0.2, 0.5, 0.2, 0.1]
      deadline_range: [30, 60]
      counterparty_weights:
        BANK_B: 0.35
        BANK_C: 0.40
        BANK_D: 0.25

  - id: BANK_B
    opening_balance: 8000000
    unsecured_cap: 4000000
    max_collateral: 15000000

    policy:
      type: FromJson
      json_path: "simulator/policies/balanced_cost_optimizer.json"

    arrival_config:
      rate_per_tick: 0.4
      amount_distribution:
        type: Uniform
        min: 50000
        max: 500000
      priority_distribution:
        type: Fixed
        value: 5
      deadline_range: [20, 50]
      counterparty_weights:
        BANK_A: 0.50
        BANK_C: 0.30
        BANK_D: 0.20
```

---

## Pydantic Validation Models

### AgentConfig
```python
class AgentConfig(BaseModel):
    id: str
    opening_balance: int  # cents
    unsecured_cap: int = 0
    max_collateral: int = 0
    collateral_haircut: float = 0.0

    policy: PolicyConfig
    arrival_config: Optional[ArrivalConfig] = None
```

### PolicyConfig
```python
class PolicyConfig(BaseModel):
    type: str  # "FromJson", "Fifo", "Deadline", etc.
    json_path: Optional[str] = None
    params: Optional[Dict[str, float]] = None
```

### ArrivalConfig
```python
class ArrivalConfig(BaseModel):
    rate_per_tick: float
    amount_distribution: AmountDistribution
    priority_distribution: Optional[PriorityDistribution] = None
    deadline_range: Tuple[int, int]
    counterparty_weights: Dict[str, float]
```

### Distribution Types
```python
# Amount distributions
class NormalDistribution(BaseModel):
    type: Literal["Normal"]
    mean: float
    std_dev: float
    min: Optional[float] = None
    max: Optional[float] = None

class LogNormalDistribution(BaseModel):
    type: Literal["LogNormal"]
    mean: float
    std_dev: float
    min: Optional[float] = None
    max: Optional[float] = None

class UniformDistribution(BaseModel):
    type: Literal["Uniform"]
    min: float
    max: float

class ExponentialDistribution(BaseModel):
    type: Literal["Exponential"]
    lambda_: float
    min: Optional[float] = None
    max: Optional[float] = None

# Priority distributions
class FixedPriorityDistribution(BaseModel):
    type: Literal["Fixed"]
    value: int

class CategoricalPriorityDistribution(BaseModel):
    type: Literal["Categorical"]
    values: List[int]
    weights: List[float]

class UniformPriorityDistribution(BaseModel):
    type: Literal["Uniform"]
    min: int
    max: int
```

---

## Policy Loading Process

### 1. Parse YAML Configuration
```python
config = SimulationConfig.from_yaml("config.yaml")
```

### 2. Create Policy for Each Agent
```python
for agent_config in config.agents:
    policy = PolicyFactory.create(
        policy_type=agent_config.policy.type,
        json_path=agent_config.policy.json_path,
        params=agent_config.policy.params
    )
    agent.set_policy(policy)
```

### 3. Policy Factory Logic
```python
def create(policy_type, json_path, params):
    if policy_type == "FromJson":
        return TreePolicy.from_file(json_path, params)
    elif policy_type == "Fifo":
        return TreePolicy.from_file("policies/fifo.json", params)
    # ... etc
```

### 4. Validation During Load
- JSON syntax validation
- Tree structure validation
- Field reference validation
- Parameter reference validation

