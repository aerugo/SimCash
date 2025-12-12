# Castro Paper Alignment Mode (Archived)

> **Source:** `experiments/castro/generator/robust_policy_agent.py` and `experiments/castro/prompts/templates.py`
> **Deleted in:** commit `c7c3513` (chore: Remove old castro code, rename new-castro to castro)
> **Recovered:** 2025-12-12

This document preserves the Castro paper alignment content that was dynamically injected into LLM prompts when `castro_mode=True`. It explains the theoretical model from Castro et al. (2025) and how the simulator constraints enforce it.

---

## Table of Contents

1. [Overview](#overview)
2. [Castro Mode System Prompt Section](#castro-mode-system-prompt-section)
3. [Castro Payment Tree Context](#castro-payment-tree-context)
4. [Castro Collateral Tree Context](#castro-collateral-tree-context)
5. [CASTRO_CONSTRAINTS Definition](#castro_constraints-definition)

---

## Overview

The Castro experiments replicated findings from:

> **"Estimating Policy Functions in Payment Systems Using Reinforcement Learning"**
> Castro et al., 2025

The paper provides a game-theoretic analysis of strategic payment timing in Real-Time Gross Settlement (RTGS) systems. The LLM prompt included a special section when `castro_mode=True` to ensure generated policies adhered to the paper's model constraints.

### Key Model Differences from Full SimCash

| Feature | Castro Model | Full SimCash |
|---------|--------------|--------------|
| Collateral decisions | t=0 only | Any tick |
| Payment actions | Release, Hold | 10+ actions including Split |
| Bank-level logic | None | SetReleaseBudget, SetState, etc. |
| Credit lines | No | Yes |
| LSM/Netting | No | Yes |
| Mid-day collateral | No | Yes |

---

## Castro Mode System Prompt Section

This section was injected at the start of the LLM system prompt when `castro_mode=True`:

```
################################################################################
#                    CASTRO PAPER ALIGNMENT MODE                               #
#           (Replicating Castro et al. 2025 Payment System Game)               #
################################################################################

This experiment follows the rules from:
"Estimating Policy Functions in Payment Systems Using Reinforcement Learning"

CASTRO MODEL CONSTRAINTS:

1. INITIAL LIQUIDITY DECISION (t=0 ONLY):
   - Choose fraction x₀ ∈ [0,1] of collateral B at day start: ℓ₀ = x₀ · B
   - This is the ONLY collateral decision allowed
   - strategic_collateral_tree MUST guard PostCollateral with tick == 0

2. INTRADAY PAYMENT DECISIONS (t=1,...,T-1):
   - Each period, choose x_t ∈ [0,1] of payments to send
   - Release = send in full (x_t = 1)
   - Hold = delay to next period (x_t = 0)
   - Constraint: Can only send what liquidity covers: P_t · x_t ≤ ℓ_{t-1}

3. COST STRUCTURE (r_c < r_d < r_b):
   - r_c: Collateral opportunity cost (initial liquidity)
   - r_d: Delay cost per tick (waiting payments)
   - r_b: End-of-day borrowing cost (shortfall)

4. LIQUIDITY EVOLUTION:
   - ℓ_t = ℓ_{t-1} - (outflows) + (inflows)
   - With deferred crediting: inflows available NEXT period only

PROHIBITED IN CASTRO MODE:
  ✗ Split, PaceAndRelease, StaggerSplit (continuous payments assumed)
  ✗ ReleaseWithCredit (no interbank credit)
  ✗ WithdrawCollateral (no mid-day collateral reduction)
  ✗ PostCollateral after tick 0 (initial decision only)
  ✗ SetReleaseBudget, SetState, AddState (no complex bank logic)

REQUIRED STRATEGIC_COLLATERAL_TREE STRUCTURE:
```json
{
  "type": "condition",
  "node_id": "SC1",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
  "on_true": {
    "type": "action",
    "node_id": "SC2",
    "action": "PostCollateral",
    "parameters": {
      "amount": {
        "compute": {
          "op": "*",
          "left": {"field": "max_collateral_capacity"},
          "right": {"param": "initial_liquidity_fraction"}
        }
      }
    }
  },
  "on_false": {"type": "action", "node_id": "SC3", "action": "HoldCollateral"}
}
```

################################################################################
```

---

## Castro Payment Tree Context

This context was provided when generating or improving the `payment_tree` in Castro mode:

```
## Payment Tree Context (Castro Mode)

In Castro's model, the payment decision is binary:
- **Release** (x_t = 1): Send the payment in full this period
- **Hold** (x_t = 0): Delay the payment to the next period

Key decision factors:
1. **Urgency**: How many ticks until deadline? (ticks_to_deadline)
2. **Liquidity**: Can we afford to send? (effective_liquidity >= remaining_amount)
3. **Strategic delay**: Can we wait for incoming payments? (counter-party might send)

Cost implications:
- Releasing uses liquidity now (may need more initial collateral tomorrow)
- Holding incurs delay cost r_d per tick
- Failing to settle by EOD incurs borrowing cost r_b >> r_d

Optimal behavior depends on the other bank's policy:
- If other bank sends early → you receive liquidity → can release more
- If other bank delays → less incoming → need more initial liquidity
```

---

## Castro Collateral Tree Context

This context was provided when generating or improving the `strategic_collateral_tree` in Castro mode:

```
## Collateral Tree Context (Castro Mode)

CRITICAL CONSTRAINT: Collateral is ONLY set at t=0 (start of day).

The strategic_collateral_tree MUST:
1. Check if system_tick_in_day == 0
2. If true: PostCollateral with the initial liquidity amount
3. If false: HoldCollateral (no changes)

Required structure:
```json
{
  "type": "condition",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
  "on_true": {
    "type": "action",
    "action": "PostCollateral",
    "parameters": {
      "amount": {
        "compute": {
          "op": "*",
          "left": {"field": "max_collateral_capacity"},
          "right": {"param": "initial_liquidity_fraction"}
        }
      }
    }
  },
  "on_false": {"type": "action", "action": "HoldCollateral"}
}
```

The key parameter is initial_liquidity_fraction (x₀ ∈ [0,1]):
- Higher x₀ → more initial liquidity → less delay risk → higher collateral cost
- Lower x₀ → rely on incoming payments → risk of delay/borrowing costs

This is the core trade-off in Castro's initial liquidity game.
```

---

## CASTRO_CONSTRAINTS Definition

The `ScenarioConstraints` object that enforced Castro paper alignment:

```python
CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            min_value=0.0,
            max_value=1.0,
            default=0.25,
            description=(
                "Fraction x_0 of collateral B to post as initial liquidity. "
                "Castro notation: ℓ₀ = x₀ · B. This is the ONLY collateral decision."
            ),
        ),
        ParameterSpec(
            name="urgency_threshold",
            min_value=0,
            max_value=20,
            default=3.0,
            description=(
                "Ticks before deadline when payment becomes urgent and must be released. "
                "Maps to Castro's intraday payment fraction x_t decision."
            ),
        ),
        ParameterSpec(
            name="liquidity_buffer",
            min_value=0.5,
            max_value=3.0,
            default=1.0,
            description=(
                "Multiplier for required liquidity before releasing. "
                "Helps enforce Castro's constraint: P_t · x_t ≤ ℓ_{t-1}."
            ),
        ),
    ],
    allowed_fields=[
        # Time context (critical for Castro's t=0 decision)
        "system_tick_in_day",
        "ticks_remaining_in_day",
        "day_progress_fraction",
        "current_tick",
        # Agent liquidity state (ℓ_t in Castro notation)
        "balance",
        "effective_liquidity",
        # Transaction context (P_t in Castro notation)
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        "is_past_deadline",
        # Queue state (accumulated demand Σ P_t)
        "queue1_total_value",
        "queue1_liquidity_gap",
        "outgoing_queue_size",
        # Collateral (B in Castro notation - for initial allocation)
        "max_collateral_capacity",
        "posted_collateral",
        "remaining_collateral_capacity",
        # EXCLUDED: credit_*, lsm_*, throughput_*, state_register_*
        # These features don't exist in Castro's model
    ],
    allowed_actions=[
        "Release",  # x_t = 1: send payment in full
        "Hold",     # x_t = 0: delay payment to next period
        # EXCLUDED: Split, ReleaseWithCredit, PaceAndRelease, StaggerSplit,
        #           Drop, Reprioritize, WithdrawFromRtgs, ResubmitToRtgs
    ],
    allowed_bank_actions=["NoAction"],  # Disable bank-level budgeting complexity
    allowed_collateral_actions=[
        "PostCollateral",   # For initial allocation at t=0
        "HoldCollateral",   # For all other ticks (no changes)
        # EXCLUDED: WithdrawCollateral (no mid-day collateral reduction in Castro)
    ],
)
```

### Why These Constraints?

| Constraint | Reason |
|------------|--------|
| Only `Release`/`Hold` | Castro assumes continuous (divisible) payments; discrete splitting complicates the model |
| No `ReleaseWithCredit` | Castro's model has no interbank credit facilities |
| No `WithdrawCollateral` | Initial liquidity decision at t=0 is final for the day |
| `PostCollateral` guarded by tick==0 | Enforces the single initial decision |
| No `SetReleaseBudget` | Castro doesn't model bank-level budget constraints |
| Limited fields | Only fields that map to Castro's variables (ℓ_t, P_t, B) |

---

## Related Documentation

- [Policy Agent LLM Prompt](./policy_agent_prompt.md) - The main prompt template that conditionally includes this Castro section
- [Constraints System](./constraints.md) - The constraint infrastructure used to enforce these rules

---

*Recovered from git history, commit `c7c3513^`*
