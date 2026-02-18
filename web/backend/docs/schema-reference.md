# Schema Reference

*Field-by-field documentation for scenario YAML and policy JSON*

## Scenario YAML Schema

Scenarios are YAML files that fully configure a simulation run. Below is every top-level
field and its nested structure.

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `num_ticks` | int | Number of simulation ticks per day |
| `agents` | list | Array of agent (bank) configurations |
| `cost_rates` | object | Cost model parameters |
| `lsm_config` | object | Liquidity-saving mechanism settings |
| `events` | list | Scheduled scenario events |
| `seed` | int | RNG seed for reproducibility |

### agents[].* — Agent Configuration

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Agent identifier (e.g. "Bank_A") |
| `initial_balance` | int | Starting balance in cents |
| `arrival_config` | object | Payment arrival configuration |
| `policy` | object | Policy config: `Fifo`, `FromJson`, or `InlineJson` |

### agents[].arrival_config — Payment Arrivals

| Field | Type | Description |
|-------|------|-------------|
| `rate_per_tick` | float | Expected number of payments per tick (Poisson λ) |
| `amount_distribution` | object | Distribution for payment amounts |
| `counterparty_weights` | dict | Probability of sending to each counterparty (keys are agent names) |
| `deadline_range` | [int, int] | [min_ticks, max_ticks] for payment deadlines |

**amount_distribution** variants:

- `{type: "Uniform", min: 5000, max: 50000}`
- `{type: "LogNormal", mean: 10.0, std_dev: 1.0}`
- `{type: "Normal", mean: 25000, std_dev: 5000}`
- `{type: "Exponential", lambda: 0.001}`

### cost_rates — Cost Model

| Field | Type | Description |
|-------|------|-------------|
| `liquidity_cost_per_tick_bps` | float | Opportunity cost of committed funds (basis points per tick) |
| `delay_cost_per_tick_per_cent` | float | Cost per cent of unsettled payment per tick |
| `deadline_penalty` | int | Flat penalty per payment that misses its deadline (cents) |
| `eod_penalty_per_transaction` | int | Penalty per unsettled payment at end of day (cents) |

### lsm_config — Liquidity-Saving Mechanisms

| Field | Type | Description |
|-------|------|-------------|
| `enable_bilateral` | bool | Enable bilateral offsetting between agent pairs |
| `enable_cycles` | bool | Enable multilateral cycle detection |
| `max_cycle_length` | int | Maximum number of agents in a settlement cycle |
| `max_cycles_per_tick` | int | Maximum cycles resolved per tick |

### events[] — Scheduled Events

Each event has a `type` and a `schedule`:

- **Types:** `GlobalArrivalRateChange`, `DirectTransfer`, `QueuePriorityChange`, `CustomTransactionArrival`, `CollateralAdjustment`, `AgentArrivalRateChange`, `CounterpartyWeightChange`, `DeadlineWindowChange`
- **Schedule:** `{type: "OneTime", tick: 150}` or `{type: "Repeating", start_tick: 100, interval: 50}`

### Example: Minimal Scenario

```yaml
num_ticks: 12
seed: 42

agents:
  - name: Bank_A
    initial_balance: 5000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10.0
        std_dev: 1.0
      counterparty_weights:
        Bank_B: 1.0
      deadline_range: [5, 20]
    policy:
      type: Fifo

  - name: Bank_B
    initial_balance: 5000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: Uniform
        min: 5000
        max: 50000
      counterparty_weights:
        Bank_A: 1.0
      deadline_range: [5, 20]
    policy:
      type: Fifo

cost_rates:
  liquidity_cost_per_tick_bps: 83.0
  delay_cost_per_tick_per_cent: 0.0001
  deadline_penalty: 50000
  eod_penalty_per_transaction: 100000
```

### Example: Scenario with Events

```yaml
num_ticks: 12
seed: 99

agents:
  - name: Bank_A
    initial_balance: 10000000
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution: { type: Normal, mean: 25000, std_dev: 5000 }
      counterparty_weights: { Bank_B: 0.6, Bank_C: 0.4 }
      deadline_range: [4, 15]
    policy: { type: Fifo }
  # ... more agents ...

cost_rates:
  liquidity_cost_per_tick_bps: 83.0
  delay_cost_per_tick_per_cent: 0.0001
  deadline_penalty: 50000
  eod_penalty_per_transaction: 100000

lsm_config:
  enable_bilateral: true
  enable_cycles: false
  max_cycle_length: 4
  max_cycles_per_tick: 10

events:
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule: { type: OneTime, tick: 6 }
  - type: DirectTransfer
    from_agent: CentralBank
    to_agent: Bank_A
    amount: 5000000
    schedule: { type: OneTime, tick: 8 }
```

## Policy JSON Schema

Policies are JSON decision trees that control bank behavior. They can be referenced
from scenario YAML via `policy: {type: "FromJson", path: "..."}` or
inlined via `policy: {type: "InlineJson", json_string: "..."}`.

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Schema version, currently `"1.0"` or `"2.0"` |
| `policy_id` | string | Unique identifier for this policy |
| `parameters` | object | Named parameters referenced by `{"param": "name"}` in trees |
| `payment_tree` | TreeNode | Per-payment decision tree (Release / Hold / Split) |
| `bank_tree` | TreeNode | Per-tick bank-level decisions (budgets, state) |
| `strategic_collateral_tree` | TreeNode? | Optional: proactive collateral management |
| `end_of_tick_collateral_tree` | TreeNode? | Optional: reactive collateral cleanup |

### parameters.* — Common Parameters

| Field | Type | Description |
|-------|------|-------------|
| `initial_liquidity_fraction` | float | Fraction of pool to commit at start of day (0.0–1.0) |

Additional custom parameters can be defined and referenced via `{"param": "name"}` in tree conditions.

### TreeNode — Decision Tree Nodes

Every node is one of three types:

**Action node** — terminal leaf that executes an action:

```json
{
  "type": "action",
  "node_id": "release_all",
  "action": "Release"
}
```

Valid actions: `Release`, `Hold`, `Split`, `ReleaseWithCredit`, `PostCollateral`, `WithdrawCollateral`, `HoldCollateral`, `NoAction`, `SetReleaseBudget`, `SetState`, `AddState`

**Condition node** — branches on a comparison:

```json
{
  "type": "condition",
  "node_id": "check_deadline",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"value": 3}
  },
  "on_true": { "..." : "..." },
  "on_false": { "..." : "..." }
}
```

Operators: `==`, `!=`, `<`, `<=`, `>`, `>=`. Left/right can be `{"field": "..."}`, `{"value": n}`, `{"param": "..."}`, or `{"compute": {op, left, right}}`.

**Compound condition** — boolean logic over sub-conditions:

```json
{
  "op": "and",
  "conditions": [
    {"op": ">", "left": {"field": "amount"}, "right": {"value": 100000}},
    {"op": "<", "left": {"field": "balance"}, "right": {"value": 50000}}
  ]
}
```

Operators: `and`, `or`, `not` (single-element array for not).

### Example: FIFO Policy (simplest)

```json
{
  "version": "1.0",
  "policy_id": "fifo_policy",
  "parameters": { "initial_liquidity_fraction": 1.0 },
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  }
}
```

### Example: Deadline-Aware Policy

```json
{
  "version": "2.0",
  "policy_id": "deadline_aware_v1",
  "parameters": { "initial_liquidity_fraction": 0.085 },
  "payment_tree": {
    "type": "condition",
    "node_id": "root",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 2}
    },
    "on_true": {"type": "action", "node_id": "urgent", "action": "Release"},
    "on_false": {
      "type": "condition",
      "node_id": "check_balance",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {"compute": {"op": "*", "left": {"field": "amount"}, "right": {"value": 1.5}}}
      },
      "on_true": {"type": "action", "node_id": "flush", "action": "Release"},
      "on_false": {"type": "action", "node_id": "wait", "action": "Hold"}
    }
  },
  "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"}
}
```
