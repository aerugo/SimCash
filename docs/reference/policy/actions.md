# Action Types

> **Reference: All Actions with Parameters and Constraints**

## Overview

Actions are the terminal decisions in policy trees. Each tree type supports specific action types.

## Action Categories

| Category | Tree(s) | Actions |
|----------|---------|---------|
| Payment | `payment_tree` | Release, ReleaseWithCredit, Split, PaceAndRelease, StaggerSplit, Hold, Drop, Reprioritize, WithdrawFromRtgs, ResubmitToRtgs |
| Bank | `bank_tree` | SetReleaseBudget, SetState, AddState, NoAction |
| Collateral | `strategic_collateral_tree`, `end_of_tick_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral |

---

# Payment Actions

## Release

**Purpose**: Submit the full transaction to RTGS Queue 2 for settlement.

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Release",
  "parameters": {
    "priority_flag": {"value": "HIGH"},      // Optional
    "timed_for_tick": {"value": 15}          // Optional
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `priority_flag` | string | No | Priority override: "HIGH" (10), "MEDIUM" (5), "LOW" (1) |
| `timed_for_tick` | number | No | Target tick for release (for LSM coordination) |

**Resulting Decision**: `ReleaseDecision::SubmitFull`

**Implementation**: `interpreter.rs:642-683`

---

## ReleaseWithCredit

**Purpose**: Submit transaction, using credit/overdraft if needed. Functionally same as Release (credit usage handled by settlement engine).

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "ReleaseWithCredit"
}
```

**Parameters**: Same as Release

**Resulting Decision**: `ReleaseDecision::SubmitFull`

**Implementation**: `interpreter.rs:685-723`

---

## Split / PaceAndRelease

**Purpose**: Split transaction into N equal parts and submit all children immediately.

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Split",
  "parameters": {
    "num_splits": {"value": 4}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `num_splits` | number | **Yes** | Number of parts to split into (must be >= 2) |

**Constraints**:
- `num_splits >= 2` (error if less)
- Each child gets `parent_amount / num_splits`
- Last child gets remainder to ensure exact sum
- Split friction cost: `split_friction_cost × (num_splits - 1)`

**Resulting Decision**: `ReleaseDecision::SubmitPartial`

**Example: Dynamic split count**
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Split",
  "parameters": {
    "num_splits": {
      "compute": {
        "op": "max",
        "values": [
          {
            "compute": {
              "op": "ceil",
              "value": {
                "compute": {
                  "op": "/",
                  "left": {"field": "remaining_amount"},
                  "right": {"field": "effective_liquidity"}
                }
              }
            }
          },
          {"value": 2}
        ]
      }
    }
  }
}
```

**Implementation**: `interpreter.rs:725-759`

---

## StaggerSplit

**Purpose**: Split transaction and release children with staggered timing.

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "StaggerSplit",
  "parameters": {
    "num_splits": {"value": 5},
    "stagger_first_now": {"value": 2},
    "stagger_gap_ticks": {"value": 3},
    "priority_boost_children": {"value": 2}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `num_splits` | number | **Yes** | Number of parts (must be >= 2) |
| `stagger_first_now` | number | **Yes** | Children to release immediately |
| `stagger_gap_ticks` | number | **Yes** | Ticks between subsequent releases |
| `priority_boost_children` | number | **Yes** | Priority boost for children (0-255, capped at 10) |

**Timing Example**:
With `num_splits=5`, `stagger_first_now=2`, `stagger_gap_ticks=3`:
- Children 1-2: Released at tick T (immediate)
- Child 3: Released at tick T+3
- Child 4: Released at tick T+6
- Child 5: Released at tick T+9

**Constraints**:
- `num_splits >= 2`
- `stagger_first_now <= num_splits`
- `stagger_gap_ticks >= 0`
- All children inherit parent's deadline

**Resulting Decision**: `ReleaseDecision::StaggerSplit`

**Implementation**: `interpreter.rs:761-809`

---

## Hold

**Purpose**: Keep transaction in Queue 1 for re-evaluation next tick.

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Hold",
  "parameters": {
    "reason": {"value": "InsufficientLiquidity"}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reason` | string | No | Hold reason for logging/debugging |

**Valid Reason Values**:
| Value | Description |
|-------|-------------|
| `"InsufficientLiquidity"` | Not enough funds to pay |
| `"AwaitingInflows"` | Waiting for expected incoming payments |
| `"LowPriority"` | Other transactions more urgent |
| `"NearDeadline"` | Approaching deadline but not yet urgent |
| Any other string | Treated as custom reason |

**Resulting Decision**: `ReleaseDecision::Hold`

**Implementation**: `interpreter.rs:811-846`

---

## Drop

**Purpose**: Remove transaction from simulation (deprecated - use Hold instead).

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Drop"
}
```

**Parameters**: None

**Note**: This action is **DEPRECATED**. Transactions should eventually settle, not be dropped. Used only for expired transactions.

**Resulting Decision**: `ReleaseDecision::Drop`

**Implementation**: `interpreter.rs:848`

---

## Reprioritize

**Purpose**: Change transaction priority without moving from Queue 1.

**Valid In**: `payment_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Reprioritize",
  "parameters": {
    "new_priority": {"value": 10}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `new_priority` | number | **Yes** | New priority (0-255, capped at 10) |

**Use Cases**:
- Escalate priority as deadline approaches
- De-prioritize when liquidity is tight
- Boost overdue transactions

**Resulting Decision**: `ReleaseDecision::Reprioritize`

**Implementation**: `interpreter.rs:850-868`

---

## WithdrawFromRtgs

**Purpose**: Remove transaction from RTGS Queue 2 back to Queue 1.

**Valid In**: `payment_tree` (for transactions already in Queue 2)

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "WithdrawFromRtgs"
}
```

**Parameters**: None

**Prerequisites**:
- Transaction must be in Queue 2 (`is_in_queue2 == 1`)
- Use `evaluate_single()` method for Queue 2 transactions

**Resulting Decision**: `ReleaseDecision::WithdrawFromRtgs`

**Implementation**: `interpreter.rs:890-892`

---

## ResubmitToRtgs

**Purpose**: Change RTGS priority of transaction in Queue 2.

**Valid In**: `payment_tree` (for transactions already in Queue 2)

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "ResubmitToRtgs",
  "parameters": {
    "rtgs_priority": {"value": "HighlyUrgent"}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rtgs_priority` | string | **Yes** | New RTGS priority class |

**Valid Priority Values**:
| Value | Description |
|-------|-------------|
| `"HighlyUrgent"` | Highest priority in TARGET2 model |
| `"Urgent"` | Medium priority |
| `"Normal"` | Standard priority |

**Note**: Transaction loses FIFO position and moves to back of new priority class.

**Resulting Decision**: `ReleaseDecision::ResubmitToRtgs`

**Implementation**: `interpreter.rs:894-932`

---

# Bank Actions

## SetReleaseBudget

**Purpose**: Set limits on total and per-counterparty releases for the tick.

**Valid In**: `bank_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "B1",
  "action": "SetReleaseBudget",
  "parameters": {
    "max_value_to_release": {"value": 500000},
    "focus_counterparties": {"value": ["BANK_A", "BANK_B"]},
    "max_per_counterparty": {"value": 100000}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `max_value_to_release` | number | **Yes** | Total budget for tick (cents) |
| `focus_counterparties` | array | No | Allowed counterparties (null = all allowed) |
| `max_per_counterparty` | number | No | Max per counterparty (null = unlimited) |

**Budget Enforcement**:
When payment_tree returns `Release`:
1. Check total budget → `Hold` if exceeded
2. Check counterparty in focus list → `Hold` if not
3. Check per-counterparty limit → `Hold` if exceeded
4. Deduct from budget if all pass

**Resulting Decision**: `BankDecision::SetReleaseBudget`

**Implementation**: `interpreter.rs:1137-1193`

---

## SetState

**Purpose**: Set a state register to a specific value.

**Valid In**: `bank_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "B1",
  "action": "SetState",
  "parameters": {
    "key": {"value": "bank_state_cooldown"},
    "value": {"value": 5.0},
    "reason": {"value": "Initialize cooldown timer"}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | **Yes** | Register name (MUST start with `bank_state_`) |
| `value` | number | **Yes** | New value |
| `reason` | string | No | Explanation for audit trail |

**Constraints**:
- Key MUST start with `bank_state_` prefix
- Maximum 10 registers per agent
- Registers reset at end of day

**Resulting Decision**: `BankDecision::SetState`

**Implementation**: `interpreter.rs:1195-1230`

---

## AddState

**Purpose**: Add (or subtract) from a state register value.

**Valid In**: `bank_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "B1",
  "action": "AddState",
  "parameters": {
    "key": {"value": "bank_state_counter"},
    "value": {"value": 1.0},
    "reason": {"value": "Increment release counter"}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | **Yes** | Register name (MUST start with `bank_state_`) |
| `value` | number | **Yes** | Delta to add (negative to subtract) |
| `reason` | string | No | Explanation for audit trail |

**Behavior**:
- If register doesn't exist, starts from 0.0
- Adds delta to current value

**Resulting Decision**: `BankDecision::AddState`

**Implementation**: `interpreter.rs:1232-1267`

---

## NoAction

**Purpose**: Take no bank-level action this tick.

**Valid In**: `bank_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "B1",
  "action": "NoAction"
}
```

**Parameters**: None

**Note**: Any unrecognized action in bank_tree also becomes NoAction.

**Resulting Decision**: `BankDecision::NoAction`

**Implementation**: `interpreter.rs:1269-1275`

---

# Collateral Actions

## PostCollateral

**Purpose**: Post collateral to increase available liquidity.

**Valid In**: `strategic_collateral_tree`, `end_of_tick_collateral_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "SC1",
  "action": "PostCollateral",
  "parameters": {
    "amount": {"field": "queue1_liquidity_gap"},
    "reason": {"value": "UrgentLiquidityNeed"},
    "auto_withdraw_after_ticks": {"value": 10}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `amount` | number | **Yes** | Amount to post (cents) |
| `reason` | string | No | Reason for posting |
| `auto_withdraw_after_ticks` | number | No | Auto-withdraw after N ticks |

**Valid Reason Values**:
| Value | Description |
|-------|-------------|
| `"UrgentLiquidityNeed"` | Immediate liquidity shortfall |
| `"PreemptivePosting"` | Preparing for anticipated needs |
| `"DeadlineEmergency"` | Imminent deadline requires liquidity |
| `"CostOptimization"` | Trading off costs |

**Behavior**:
- If amount <= 0, treated as HoldCollateral
- Capped at `remaining_collateral_capacity`
- `auto_withdraw_after_ticks`: system auto-withdraws after N ticks

**Resulting Decision**: `CollateralDecision::Post`

**Implementation**: `interpreter.rs:969-999`

---

## WithdrawCollateral

**Purpose**: Withdraw collateral to reduce opportunity cost.

**Valid In**: `strategic_collateral_tree`, `end_of_tick_collateral_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "EOT1",
  "action": "WithdrawCollateral",
  "parameters": {
    "amount": {"field": "excess_collateral"},
    "reason": {"value": "CostOptimization"}
  }
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `amount` | number | **Yes** | Amount to withdraw (cents) |
| `reason` | string | No | Reason for withdrawal |

**Valid Reason Values**:
| Value | Description |
|-------|-------------|
| `"LiquidityRestored"` | Balance recovered, collateral unnecessary |
| `"EndOfDayCleanup"` | EOD excess collateral withdrawal |
| `"CostOptimization"` | Reducing collateral cost |

**Behavior**:
- If amount <= 0, treated as HoldCollateral
- Capped at `posted_collateral`
- Cannot withdraw below `required_collateral_for_usage`

**Resulting Decision**: `CollateralDecision::Withdraw`

**Implementation**: `interpreter.rs:1001-1018`

---

## HoldCollateral

**Purpose**: Make no change to collateral this tick.

**Valid In**: `strategic_collateral_tree`, `end_of_tick_collateral_tree`

**JSON Syntax**:
```json
{
  "type": "action",
  "node_id": "SC1",
  "action": "HoldCollateral"
}
```

**Parameters**: None

**Resulting Decision**: `CollateralDecision::Hold`

**Implementation**: `interpreter.rs:1020-1023`

---

# Action Validity Matrix

| Action | payment_tree | bank_tree | strategic_collateral | end_of_tick_collateral |
|--------|:------------:|:---------:|:--------------------:|:---------------------:|
| Release | ✅ | ❌ | ❌ | ❌ |
| ReleaseWithCredit | ✅ | ❌ | ❌ | ❌ |
| Split | ✅ | ❌ | ❌ | ❌ |
| PaceAndRelease | ✅ | ❌ | ❌ | ❌ |
| StaggerSplit | ✅ | ❌ | ❌ | ❌ |
| Hold | ✅ | ❌ | ❌ | ❌ |
| Drop | ✅ | ❌ | ❌ | ❌ |
| Reprioritize | ✅ | ❌ | ❌ | ❌ |
| WithdrawFromRtgs | ✅ | ❌ | ❌ | ❌ |
| ResubmitToRtgs | ✅ | ❌ | ❌ | ❌ |
| SetReleaseBudget | ❌ | ✅ | ❌ | ❌ |
| SetState | ❌ | ✅ | ❌ | ❌ |
| AddState | ❌ | ✅ | ❌ | ❌ |
| NoAction | ❌ | ✅ | ❌ | ❌ |
| PostCollateral | ❌ | ❌ | ✅ | ✅ |
| WithdrawCollateral | ❌ | ❌ | ✅ | ✅ |
| HoldCollateral | ❌ | ❌ | ✅ | ✅ |

---

# Source Code Reference

| Component | File | Line |
|-----------|------|------|
| ActionType enum | `backend/src/policy/tree/types.rs` | 275-347 |
| ReleaseDecision enum | `backend/src/policy/mod.rs` | 82-294 |
| BankDecision enum | `backend/src/policy/mod.rs` | 412-506 |
| CollateralDecision enum | `backend/src/policy/mod.rs` | 321-349 |
| build_decision() | `backend/src/policy/tree/interpreter.rs` | 622-933 |
| build_bank_decision() | `backend/src/policy/tree/interpreter.rs` | 1107-1276 |
| build_collateral_decision() | `backend/src/policy/tree/interpreter.rs` | 949-1044 |
