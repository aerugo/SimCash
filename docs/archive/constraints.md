# Policy Constraints System (Archived)

> **Source:** `experiments/castro/schemas/` and `experiments/castro/parameter_sets.py`
> **Deleted in:** commit `c7c3513` (chore: Remove old castro code, rename new-castro to castro)
> **Recovered:** 2025-12-12

This document preserves the constraint system used to define what parameters, fields, and actions are allowed in policy generation scenarios. The system enabled dynamic LLM prompt generation and Pydantic model validation.

---

## Table of Contents

1. [Overview](#overview)
2. [Core Data Structures](#core-data-structures)
3. [Pre-defined Constraint Sets](#pre-defined-constraint-sets)
4. [Complete Field Registry](#complete-field-registry)
5. [Complete Action Registry](#complete-action-registry)
6. [Usage Examples](#usage-examples)

---

## Overview

The constraint system served three purposes:

1. **LLM Prompt Generation** - The `ScenarioConstraints` object was used to dynamically generate the system prompt, telling the LLM exactly which parameters, fields, and actions it could use.

2. **Pydantic Model Generation** - Constraints were used to create dynamic Pydantic models that enforced valid policy structure at parse time.

3. **Scenario Customization** - Different experiments could use different constraint sets (e.g., Castro-aligned vs. full SimCash capabilities).

### Design Philosophy

- **Whitelist approach** - Only explicitly allowed elements can be used
- **Validation at constraint definition** - Invalid fields/actions are caught immediately
- **Parameter bounds enforcement** - Each parameter has min/max/default values
- **Tree-type awareness** - Different trees allow different actions

---

## Core Data Structures

### ParameterSpec

Defines a single policy parameter that the LLM can tune:

```python
class ParameterSpec(BaseModel):
    """Specification for a single policy parameter."""

    name: str           # Parameter name (valid Python identifier)
    min_value: float    # Minimum allowed value (inclusive)
    max_value: float    # Maximum allowed value (inclusive)
    default: float      # Default value if not specified
    description: str    # Human-readable description for LLM prompt
```

**Validation Rules:**
- `min_value < max_value`
- `min_value <= default <= max_value`

**Example:**
```python
ParameterSpec(
    name="urgency_threshold",
    min_value=0.0,
    max_value=20.0,
    default=3.0,
    description="Ticks before deadline when payment becomes urgent",
)
```

### ScenarioConstraints

Defines all allowed elements for a scenario:

```python
class ScenarioConstraints(BaseModel):
    """Constraints defining allowed policy elements for a scenario."""

    allowed_parameters: list[ParameterSpec]  # Parameters LLM can define/use
    allowed_fields: list[str]                # Context fields LLM can reference
    allowed_actions: list[str]               # Actions for payment_tree
    allowed_bank_actions: list[str] | None   # Actions for bank_tree (None = disabled)
    allowed_collateral_actions: list[str] | None  # Actions for collateral trees
```

**Validation Rules:**
- All fields must exist in the SimCash field registry
- All actions must exist in the SimCash action registry
- No duplicate parameter names
- At least one field and one action required

**Helper Methods:**
```python
constraints.get_parameter_names()        # -> ["urgency_threshold", "liquidity_buffer"]
constraints.get_parameter_by_name("urgency_threshold")  # -> ParameterSpec or None
```

---

## Pre-defined Constraint Sets

Four constraint sets were defined for common scenarios:

### CASTRO_CONSTRAINTS

Aligned with Castro et al. (2025) paper "Estimating Policy Functions in Payment Systems Using Reinforcement Learning":

```python
CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            min_value=0.0,
            max_value=1.0,
            default=0.25,
            description="Fraction x_0 of collateral B to post as initial liquidity. "
                       "Castro notation: ℓ₀ = x₀ · B. This is the ONLY collateral decision.",
        ),
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description="Ticks before deadline when payment becomes urgent. "
                       "Maps to Castro's intraday payment fraction x_t decision.",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description="Multiplier for required liquidity before releasing. "
                       "Helps enforce Castro's constraint: P_t · x_t ≤ ℓ_{t-1}.",
        ),
    ],
    allowed_fields=[
        # Time context (critical for Castro's t=0 decision)
        "system_tick_in_day", "ticks_remaining_in_day", "day_progress_fraction", "current_tick",
        # Agent liquidity state (ℓ_t in Castro notation)
        "balance", "effective_liquidity",
        # Transaction context (P_t in Castro notation)
        "ticks_to_deadline", "remaining_amount", "amount", "priority", "is_past_deadline",
        # Queue state (accumulated demand Σ P_t)
        "queue1_total_value", "queue1_liquidity_gap", "outgoing_queue_size",
        # Collateral (B in Castro notation - for initial allocation)
        "max_collateral_capacity", "posted_collateral", "remaining_collateral_capacity",
    ],
    allowed_actions=["Release", "Hold"],
    allowed_bank_actions=["NoAction"],
    allowed_collateral_actions=["PostCollateral", "HoldCollateral"],
)
```

**What Castro Constraints Prohibit:**
- `Split`, `ReleaseWithCredit`, `PaceAndRelease`, `StaggerSplit` (continuous payments assumed)
- `WithdrawCollateral` (no mid-day collateral changes)
- `SetReleaseBudget`, `SetState`, `AddState` (no complex bank logic)
- LSM fields, credit fields, throughput fields (not in Castro's model)

### MINIMAL_CONSTRAINTS

Bare minimum for simple policies:

```python
MINIMAL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description="Ticks before deadline when payment becomes urgent",
        ),
    ],
    allowed_fields=[
        "balance", "effective_liquidity",
        "ticks_to_deadline", "remaining_amount",
        "ticks_remaining_in_day",
    ],
    allowed_actions=["Release", "Hold"],
)
```

### STANDARD_CONSTRAINTS

Common parameters for typical experiments:

```python
STANDARD_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec("urgency_threshold", 0, 20, 3.0, "..."),
        ParameterSpec("liquidity_buffer", 0.5, 3.0, 1.0, "..."),
        ParameterSpec("initial_collateral_fraction", 0, 1.0, 0.25, "..."),
        ParameterSpec("eod_urgency_boost", 0, 10, 2.0, "..."),
    ],
    allowed_fields=[
        # 19 fields including balance, queue, time, and collateral
    ],
    allowed_actions=["Release", "Hold", "Split"],
    allowed_bank_actions=BANK_ACTIONS,
    allowed_collateral_actions=COLLATERAL_ACTIONS,
)
```

### FULL_CONSTRAINTS

All SimCash capabilities:

```python
FULL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        # 10 parameters covering all aspects
        ParameterSpec("urgency_threshold", ...),
        ParameterSpec("liquidity_buffer", ...),
        ParameterSpec("initial_collateral_fraction", ...),
        ParameterSpec("eod_urgency_boost", ...),
        ParameterSpec("eod_start_fraction", ...),
        ParameterSpec("queue_pressure_threshold", ...),
        ParameterSpec("min_reserve_fraction", ...),
        ParameterSpec("split_threshold_fraction", ...),
        ParameterSpec("split_count", ...),
        ParameterSpec("high_priority_threshold", ...),
    ],
    allowed_fields=PAYMENT_TREE_FIELDS,  # All 146+ fields
    allowed_actions=PAYMENT_ACTIONS,      # All 10 payment actions
    allowed_bank_actions=BANK_ACTIONS,
    allowed_collateral_actions=COLLATERAL_ACTIONS,
)
```

### Accessing Constraint Sets

```python
from experiments.castro.parameter_sets import (
    CASTRO_CONSTRAINTS,
    MINIMAL_CONSTRAINTS,
    STANDARD_CONSTRAINTS,
    FULL_CONSTRAINTS,
    get_constraints,
)

# Direct access
constraints = CASTRO_CONSTRAINTS

# By name
constraints = get_constraints("castro")  # or "minimal", "standard", "full"
```

---

## Complete Field Registry

Fields are organized by category and tree type availability.

### Transaction Fields (payment_tree only)

These fields provide information about the specific transaction being evaluated:

| Field | Description |
|-------|-------------|
| `amount` | Original transaction amount (cents) |
| `remaining_amount` | Amount left to settle (after partial settlement) |
| `settled_amount` | Amount already settled |
| `arrival_tick` | Tick when transaction entered the system |
| `deadline_tick` | Tick by which transaction must settle |
| `priority` | Transaction priority (0-10, higher = more urgent) |
| `is_split` | Whether this is a split transaction |
| `is_past_deadline` | Whether deadline has passed |
| `is_overdue` | Whether transaction is overdue |
| `is_in_queue2` | Whether transaction is in RTGS queue |
| `overdue_duration` | Ticks past deadline |
| `ticks_to_deadline` | Ticks remaining until deadline |
| `queue_age` | Ticks since entering queue |
| `cost_delay_this_tx_one_tick` | Delay cost for holding this transaction one more tick |
| `cost_overdraft_this_amount_one_tick` | Overdraft cost for releasing this amount |

### Agent/Balance Fields (all trees)

| Field | Description |
|-------|-------------|
| `balance` | Current account balance (cents) |
| `credit_limit` | Maximum credit available |
| `available_liquidity` | Balance + credit headroom |
| `credit_used` | Amount of credit currently used |
| `effective_liquidity` | Actual liquidity available for payments |
| `credit_headroom` | Remaining credit capacity |
| `is_using_credit` | Whether agent is using credit |
| `liquidity_buffer` | Safety margin in liquidity |
| `liquidity_pressure` | Ratio of queue to liquidity |
| `is_overdraft_capped` | Whether at overdraft limit |

### Queue Fields (all trees)

| Field | Description |
|-------|-------------|
| `outgoing_queue_size` | Number of transactions in outgoing queue |
| `queue1_total_value` | Total value of queued outgoing payments |
| `queue1_liquidity_gap` | Amount of liquidity needed to clear queue |
| `headroom` | Liquidity above queue requirements |
| `incoming_expected_count` | Expected incoming transaction count |

### Queue 2 (RTGS) Fields (all trees)

| Field | Description |
|-------|-------------|
| `rtgs_queue_size` | Number of transactions in RTGS queue |
| `rtgs_queue_value` | Total value in RTGS queue |
| `queue2_size` | Alias for rtgs_queue_size |
| `queue2_count_for_agent` | Agent's transactions in Queue 2 |
| `queue2_nearest_deadline` | Nearest deadline in Queue 2 |
| `ticks_to_nearest_queue2_deadline` | Ticks to nearest Queue 2 deadline |

### Collateral Fields (all trees)

| Field | Description |
|-------|-------------|
| `posted_collateral` | Amount of collateral currently posted |
| `max_collateral_capacity` | Maximum collateral available |
| `remaining_collateral_capacity` | Collateral not yet posted |
| `collateral_utilization` | Fraction of collateral in use |
| `collateral_haircut` | Haircut rate on collateral |
| `unsecured_cap` | Maximum unsecured exposure |
| `allowed_overdraft_limit` | Maximum overdraft allowed |
| `overdraft_headroom` | Remaining overdraft capacity |
| `overdraft_utilization` | Fraction of overdraft used |
| `required_collateral_for_usage` | Collateral needed for current usage |
| `excess_collateral` | Collateral above requirements |

### Cost Rate Fields (all trees)

| Field | Description |
|-------|-------------|
| `cost_overdraft_bps_per_tick` | Overdraft cost rate (basis points/tick) |
| `cost_delay_per_tick_per_cent` | Delay cost rate |
| `cost_collateral_bps_per_tick` | Collateral opportunity cost |
| `cost_split_friction` | Cost per split operation |
| `cost_deadline_penalty` | One-time penalty at deadline |
| `cost_eod_penalty` | End-of-day penalty rate |

### Time/System Fields (all trees)

| Field | Description |
|-------|-------------|
| `current_tick` | Current simulation tick |
| `system_ticks_per_day` | Ticks in a business day |
| `system_current_day` | Current day number |
| `system_tick_in_day` | Tick within current day (0 to ticks_per_day-1) |
| `ticks_remaining_in_day` | Ticks left in current day |
| `day_progress_fraction` | Fraction of day elapsed (0.0 to 1.0) |
| `is_eod_rush` | Whether in end-of-day rush period |
| `total_agents` | Number of agents in simulation |

### LSM Fields (payment_tree only)

For LSM-aware policies that consider netting opportunities:

| Field | Description |
|-------|-------------|
| `my_q2_out_value_to_counterparty` | Value owed to this transaction's counterparty in Queue 2 |
| `my_q2_in_value_from_counterparty` | Value owed from counterparty |
| `my_bilateral_net_q2` | Net position with counterparty |
| `my_q2_out_value_top_N` | Value to top N counterparty (1-5) |
| `my_q2_in_value_top_N` | Value from top N counterparty (1-5) |
| `my_bilateral_net_q2_top_N` | Net with top N counterparty (1-5) |
| `tx_counterparty_id` | ID of transaction counterparty |
| `tx_is_top_counterparty` | Whether counterparty is top exposure |

### Throughput Fields (all trees)

| Field | Description |
|-------|-------------|
| `system_queue2_pressure_index` | System-wide Queue 2 pressure |
| `my_throughput_fraction_today` | Agent's throughput as fraction of target |
| `expected_throughput_fraction_by_now` | Expected throughput by current time |
| `throughput_gap` | Difference from expected throughput |

### State Register Fields (all trees)

User-defined state variables set by `SetState` / `AddState` actions:

| Field | Description |
|-------|-------------|
| `bank_state_cooldown` | Cooldown counter |
| `bank_state_counter` | Generic counter |
| `bank_state_budget_used` | Budget tracking |
| `bank_state_mode` | Mode flag |

### Fields by Tree Type

| Tree Type | Available Fields |
|-----------|------------------|
| `payment_tree` | All fields (146+) including transaction and LSM fields |
| `bank_tree` | Common fields only (90+) - no transaction context |
| `strategic_collateral_tree` | Same as bank_tree |
| `end_of_tick_collateral_tree` | Same as bank_tree |

---

## Complete Action Registry

### Payment Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `Release` | Submit payment to RTGS for immediate settlement | None |
| `Hold` | Keep payment in queue for later | None |
| `Split` | Divide payment into smaller parts | `num_parts`, `amounts` |
| `Drop` | Remove payment from queue entirely | None |
| `Reprioritize` | Change payment priority | `new_priority` |
| `ReleaseWithCredit` | Release using credit line | None |
| `PaceAndRelease` | Release over multiple ticks | `pace_ticks` |
| `StaggerSplit` | Split and release parts over time | `num_parts`, `interval` |
| `WithdrawFromRtgs` | Pull back from RTGS queue | None |
| `ResubmitToRtgs` | Resubmit to RTGS | None |

### Bank Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `SetReleaseBudget` | Limit total release value this tick | `max_value_to_release` (REQUIRED) |
| `SetState` | Set a state register value | `register`, `value` |
| `AddState` | Add to a state register | `register`, `delta` |
| `NoAction` | Take no bank-level action | None |

### Collateral Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `PostCollateral` | Increase posted collateral | `amount`, `reason` |
| `WithdrawCollateral` | Decrease posted collateral | `amount` |
| `HoldCollateral` | Make no collateral change | None |

### Actions by Tree Type

| Tree Type | Valid Actions |
|-----------|---------------|
| `payment_tree` | Release, Hold, Split, Drop, Reprioritize, ReleaseWithCredit, PaceAndRelease, StaggerSplit, WithdrawFromRtgs, ResubmitToRtgs |
| `bank_tree` | SetReleaseBudget, SetState, AddState, NoAction |
| `strategic_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral |
| `end_of_tick_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral |

**Critical Distinction:**
- `Hold` is a PAYMENT action (keep transaction in queue)
- `HoldCollateral` is a COLLATERAL action (don't change collateral)
- `NoAction` is a BANK action (don't set budget/state)

These are NOT interchangeable - using the wrong action type in a tree causes validation failure.

---

## Usage Examples

### Creating Custom Constraints

```python
from experiments.castro.schemas.parameter_config import (
    ParameterSpec,
    ScenarioConstraints,
)

# Define a custom constraint set for a specific experiment
my_constraints = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="urgency_threshold",
            min_value=1,
            max_value=10,
            default=3.0,
            description="Ticks before deadline to release urgently",
        ),
        ParameterSpec(
            name="split_threshold",
            min_value=0.0,
            max_value=1.0,
            default=0.5,
            description="Payment-to-liquidity ratio triggering split",
        ),
    ],
    allowed_fields=[
        "balance",
        "effective_liquidity",
        "ticks_to_deadline",
        "remaining_amount",
        "priority",
        "queue1_total_value",
        "ticks_remaining_in_day",
    ],
    allowed_actions=["Release", "Hold", "Split"],
    allowed_bank_actions=None,  # Disable bank_tree
    allowed_collateral_actions=None,  # Disable collateral trees
)
```

### Using Constraints with RobustPolicyAgent

```python
from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

# Create agent with Castro constraints
agent = RobustPolicyAgent(
    constraints=CASTRO_CONSTRAINTS,
    model="gpt-4o",
    castro_mode=True,
)

# The system prompt is automatically generated from constraints
print(agent.get_system_prompt())

# Generate a policy
policy = agent.generate_policy(
    instruction="Minimize delay costs while avoiding overdrafts",
    current_cost=50000,
    settlement_rate=0.85,
)
```

### Validating a Constraint Set

```python
from experiments.castro.schemas.parameter_config import ScenarioConstraints

# This will raise ValueError because "fake_field" doesn't exist
try:
    bad_constraints = ScenarioConstraints(
        allowed_parameters=[],
        allowed_fields=["balance", "fake_field"],  # Error!
        allowed_actions=["Release"],
    )
except ValueError as e:
    print(f"Validation failed: {e}")
    # Output: Validation failed: unknown field(s): {'fake_field'}
```

---

## Related Documentation

- [Policy Agent LLM Prompt](./policy_agent_prompt.md) - The prompt generated from constraints
- Root `CLAUDE.md` - Policy DSL reference in the main project documentation

---

*Recovered from git history, commit `c7c3513^`*
