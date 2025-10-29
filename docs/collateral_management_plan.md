# Collateral Management in Policy Layer - Implementation Plan

**Document Version**: 1.0
**Date**: 2025-10-29
**Status**: Planning
**Related Phase**: Phase 8 Completion + Enhancement

---

## Executive Summary

**Problem**: The Phase 8 collateral cost implementation calculates opportunity costs but provides no mechanism for policies to dynamically post/withdraw collateral. Agents with `posted_collateral` set in config pay costs continuously without ability to adapt to changing liquidity needs.

**Solution**: Extend the policy layer to enable collateral decisions alongside payment release decisions, plus add an end-of-tick collateral manager for automatic cleanup/emergency posting.

**Impact**: Transforms collateral from a static cost burden into a strategic liquidity management tool, enabling realistic intraday credit optimization.

---

## Table of Contents

1. [Current State](#1-current-state)
2. [Design Goals](#2-design-goals)
3. [Architecture Overview](#3-architecture-overview)
4. [Policy Layer Extensions](#4-policy-layer-extensions)
5. [DSL Extensions](#5-dsl-extensions)
6. [New Policy: liquidity_aware_with_collateral](#6-new-policy-liquidity_aware_with_collateral)
7. [End-of-Tick Collateral Manager](#7-end-of-tick-collateral-manager)
8. [Orchestrator Integration](#8-orchestrator-integration)
9. [Implementation Phases](#9-implementation-phases)
10. [Testing Strategy](#10-testing-strategy)
11. [Success Criteria](#11-success-criteria)
12. [Future Enhancements](#12-future-enhancements)

---

## 1. Current State

### 1.1 What Works

**Phase 8 Cost Model** (60% complete):
- ✅ Agent has `posted_collateral: i64` field
- ✅ Collateral increases `available_liquidity()`:
  ```rust
  available_liquidity = balance + credit_limit + posted_collateral
  ```
- ✅ Collateral accrues opportunity cost per tick:
  ```rust
  collateral_cost = posted_collateral × collateral_cost_per_tick_bps
  ```
- ✅ Collateral can be set via config (`AgentConfig.posted_collateral`)

### 1.2 What's Missing ❌

**Dynamic Management**:
- ❌ Policies cannot post/withdraw collateral
- ❌ No mechanism to change collateral during simulation
- ❌ FFI methods exist (`post_collateral`, `withdraw_collateral`) but only callable from Python API manually
- ❌ No policy DSL actions for collateral decisions
- ❌ No automatic collateral cleanup (agents pay costs even when not needed)

**Result**: Collateral is essentially **broken** - it costs money but agents can't optimize when to use it.

---

## 2. Design Goals

### 2.1 Core Objectives

1. **Enable Policy Control**: Policies should decide when to post/withdraw collateral based on agent state
2. **Separate Concerns**: Payment release decisions vs. collateral management decisions
3. **Automatic Cleanup**: End-of-tick manager handles obvious cases (withdraw when clearly not needed)
4. **Emergency Posting**: Automatic posting when deadline expiration imminent
5. **Backward Compatible**: Existing policies continue to work (collateral decisions optional)

### 2.2 Non-Goals (Deferred)

- **Haircut modeling**: Use 1:1 collateral-to-credit ratio (no haircut)
- **Collateral types**: Treat all collateral as homogeneous
- **Multi-currency**: Single currency only
- **Collateral pledging/unpledging delays**: Instant posting/withdrawal
- **Central bank collateral management**: No acceptance/rejection logic

---

## 3. Architecture Overview

### 3.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    TICK N EXECUTION                         │
└─────────────────────────────────────────────────────────────┘
                            │
        1. Arrivals         │
                            ▼
        2. Policy Evaluation
           ┌────────────────────────────────────┐
           │ Policy.evaluate()                  │
           │   Returns:                         │
           │   - Vec<ReleaseDecision>           │
           │   - CollateralDecision  ← NEW!     │
           └────────────────────────────────────┘
                            │
        3. Collateral Management ← NEW STEP!
           ┌────────────────────────────────────┐
           │ Execute collateral decisions       │
           │ - Post collateral (if capacity)    │
           │ - Withdraw collateral (if posted)  │
           │ - Log collateral events            │
           └────────────────────────────────────┘
                            │
        4. Queue 1 Processing (existing)
                            │
        5. Transaction Splitting (existing)
                            │
        6. RTGS Submission (existing)
                            │
        7. LSM Optimization (existing)
                            │
        8. End-of-Tick Collateral Cleanup ← NEW STEP!
           ┌────────────────────────────────────┐
           │ Automatic collateral management:   │
           │ - Withdraw if clearly not needed   │
           │ - Post if deadline emergency       │
           └────────────────────────────────────┘
                            │
        9. Cost Accrual (existing)
                            │
        10. Metrics Update (existing)
```

### 3.2 Component Responsibilities

**IMPORTANT: Two-Layer Architecture**

Collateral management operates on TWO independent layers:

1. **Policy Layer (STEP 2.5)** - Runs EARLY in tick, BEFORE settlements
   - **When**: After arrival generation, before RTGS submission
   - **Purpose**: Strategic, forward-looking collateral decisions
   - **Trigger**: Policy evaluation (every tick for every agent)
   - **Decisions**: Based on forecasts, risk appetite, expected flows
   - **Implementation**: `CashManagerPolicy::evaluate_collateral()`
   - **Status**: ✅ COMPLETE (Phase 1)

2. **End-of-Tick Manager (STEP 8)** - Runs LATE in tick, AFTER all settlements
   - **When**: After LSM optimization, before cost accrual
   - **Purpose**: Automatic cleanup and emergency posting
   - **Trigger**: Every tick for every agent (mandatory, not policy-dependent)
   - **Decisions**: Conservative reactive rules (obvious cases only)
   - **Implementation**: `CollateralManager::manage_collateral()`
   - **Status**: ❌ NOT IMPLEMENTED (Phase 4)

**Why Two Layers?**
- Policies can't see final settlement state (they run before settlements)
- Manager sees final state after all settlements complete
- Policies = strategic (optional, customizable)
- Manager = cleanup + emergency (mandatory, uniform)

| Component | Responsibility |
|-----------|---------------|
| **Policy (STEP 2.5)** | Strategic collateral decisions based on forecasts, urgency |
| **End-of-Tick Manager (STEP 8)** | Cleanup (withdraw excess), emergency (post for expiring) |
| **Orchestrator** | Execute collateral changes, enforce capacity limits |
| **Agent** | Track posted collateral, provide capacity info |
| **Event Log** | Record all collateral changes for analysis |

---

## 4. Policy Layer Extensions

### 4.1 New Type: CollateralDecision

**File**: `backend/src/policy/mod.rs`

```rust
/// Collateral management decision from cash manager policy
#[derive(Debug, Clone, PartialEq)]
pub enum CollateralDecision {
    /// Post additional collateral (amount in cents)
    Post { amount: i64, reason: CollateralReason },

    /// Withdraw collateral (amount in cents)
    Withdraw { amount: i64, reason: CollateralReason },

    /// Take no action (keep current collateral level)
    Hold,
}

/// Reason for collateral decision (for logging/analysis)
#[derive(Debug, Clone, PartialEq)]
pub enum CollateralReason {
    /// Need liquidity for urgent transactions
    UrgentLiquidityNeed,

    /// Preemptive posting for expected outflows
    PreemptivePosting,

    /// Liquidity restored, no longer needed
    LiquidityRestored,

    /// End of day, minimize overnight costs
    EndOfDayCleanup,

    /// Emergency: deadline expiration imminent
    DeadlineEmergency,

    /// Cost optimization (reduce opportunity cost)
    CostOptimization,
}
```

### 4.2 Updated CashManagerPolicy Trait

**File**: `backend/src/policy/mod.rs`

```rust
pub trait CashManagerPolicy: Send + Sync {
    /// Evaluate agent's queue and return release decisions
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision>;

    /// Evaluate agent's collateral needs (NEW METHOD)
    ///
    /// Called after evaluate_queue but before RTGS submission.
    /// Allows policies to post/withdraw collateral based on:
    /// - Current balance and credit usage
    /// - Pending transactions in Queue 1
    /// - Expected inflows
    /// - Queue 2 pressure
    ///
    /// Default implementation: Hold (no change)
    fn evaluate_collateral(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> CollateralDecision {
        CollateralDecision::Hold  // Default: do nothing
    }
}
```

**Backward Compatibility**: Existing policies that don't override `evaluate_collateral()` will use the default (Hold), so they continue to work unchanged.

### 4.3 Helper Methods for Agent

**File**: `backend/src/models/agent.rs`

```rust
impl Agent {
    /// Get maximum collateral capacity
    ///
    /// For now, return a configured max (e.g., 10x credit_limit).
    /// Future: make this a field in AgentConfig.
    pub fn max_collateral_capacity(&self) -> i64 {
        // Heuristic: can post up to 10x credit limit
        self.credit_limit * 10
    }

    /// Get remaining collateral capacity
    pub fn remaining_collateral_capacity(&self) -> i64 {
        self.max_collateral_capacity() - self.posted_collateral
    }

    /// Check if agent can post additional collateral
    pub fn can_post_collateral(&self, amount: i64) -> bool {
        amount > 0 && amount <= self.remaining_collateral_capacity()
    }

    /// Check if agent can withdraw collateral
    pub fn can_withdraw_collateral(&self, amount: i64) -> bool {
        amount > 0 && amount <= self.posted_collateral
    }

    /// Get liquidity gap: how much more liquidity needed to settle all Queue 1
    pub fn queue1_liquidity_gap(&self, state: &SimulationState) -> i64 {
        let mut total_needed = 0i64;
        for tx_id in self.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                total_needed += tx.remaining_amount();
            }
        }

        let available = self.available_liquidity();
        if total_needed > available {
            total_needed - available
        } else {
            0
        }
    }
}
```

---

## 5. DSL Extensions

### 5.1 New Action Types

**File**: `backend/src/policy/tree/types.rs`

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ActionType {
    Release,
    Hold,
    Split,
    Drop,

    // NEW: Collateral actions
    PostCollateral,
    WithdrawCollateral,
    HoldCollateral,  // Explicit "do nothing" for collateral
}
```

### 5.2 New Field Accessors

**File**: `backend/src/policy/tree/context.rs`

Add to `EvaluationContext`:

```rust
// Collateral state fields
"posted_collateral" => agent.posted_collateral() as f64,
"max_collateral_capacity" => agent.max_collateral_capacity() as f64,
"remaining_collateral_capacity" => agent.remaining_collateral_capacity() as f64,
"collateral_utilization" => {
    let max_cap = agent.max_collateral_capacity() as f64;
    if max_cap > 0.0 {
        (agent.posted_collateral() as f64) / max_cap
    } else {
        0.0
    }
},

// Liquidity gap fields
"queue1_liquidity_gap" => agent.queue1_liquidity_gap(state) as f64,
"queue1_total_value" => {
    let mut total = 0i64;
    for tx_id in agent.outgoing_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            total += tx.remaining_amount();
        }
    }
    total as f64
},

// Queue 2 pressure fields (requires state access)
"queue2_count_for_agent" => {
    state.rtgs_queue()
        .iter()
        .filter(|tx_id| {
            state.get_transaction(tx_id)
                .map(|tx| tx.sender() == agent.id())
                .unwrap_or(false)
        })
        .count() as f64
},
"queue2_nearest_deadline" => {
    state.rtgs_queue()
        .iter()
        .filter_map(|tx_id| state.get_transaction(tx_id))
        .filter(|tx| tx.sender() == agent.id())
        .map(|tx| tx.deadline())
        .min()
        .unwrap_or(usize::MAX) as f64
},
"ticks_to_nearest_queue2_deadline" => {
    let nearest = state.rtgs_queue()
        .iter()
        .filter_map(|tx_id| state.get_transaction(tx_id))
        .filter(|tx| tx.sender() == agent.id())
        .map(|tx| tx.deadline())
        .min()
        .unwrap_or(usize::MAX);

    if nearest == usize::MAX {
        f64::INFINITY
    } else {
        (nearest.saturating_sub(tick)) as f64
    }
},

// Cost-related fields
"collateral_cost_per_tick" => {
    (agent.posted_collateral() as f64) * cost_rates.collateral_cost_per_tick_bps
},
```

### 5.3 Action Parameter Schema

For `PostCollateral` and `WithdrawCollateral`, support these parameters:

```json
{
  "action": "PostCollateral",
  "parameters": {
    "amount": {"compute": {"op": "-", "left": {"field": "queue1_liquidity_gap"}, "right": {"field": "available_liquidity"}}},
    "reason": {"value": "UrgentLiquidityNeed"}
  }
}
```

```json
{
  "action": "WithdrawCollateral",
  "parameters": {
    "amount": {"field": "posted_collateral"},
    "reason": {"value": "LiquidityRestored"}
  }
}
```

---

## 6. Policy File Structure: Three-Tree Architecture

### 6.1 Overview

Each policy JSON file contains **three independent decision trees**:
1. **payment_tree**: Payment release decisions (Release/Hold/Drop)
2. **strategic_collateral_tree**: Strategic collateral decisions (Layer 1, STEP 2.5)
3. **end_of_tick_collateral_tree**: Reactive collateral decisions (Layer 2, STEP 8)

All three trees are optional. If omitted, the policy returns default "do nothing" decisions.

### 6.2 File Structure

**File**: `backend/policies/liquidity_aware_with_collateral.json`

```json
{
  "version": "1.0",
  "policy_id": "liquidity_aware_with_collateral",
  "description": "Liquidity-aware policy with dual-layer collateral management",

  "payment_tree": {
    "type": "condition",
    "node_id": "P1",
    "description": "Urgent transaction (deadline < 5 ticks)?",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "condition",
      "node_id": "P2",
      "description": "Can pay with available liquidity?",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {"field": "amount"}
      },
      "on_true": {
        "type": "action",
        "node_id": "PA1",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "PA2",
        "action": "Hold",
        "parameters": {"reason": {"value": "InsufficientLiquidity"}}
      }
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3",
      "description": "Balance after payment >= target buffer?",
      "condition": {
        "op": ">=",
        "left": {
          "compute": {
            "op": "-",
            "left": {"field": "balance"},
            "right": {"field": "amount"}
          }
        },
        "right": {"param": "target_buffer"}
      },
      "on_true": {
        "type": "action",
        "node_id": "PA3",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "PA4",
        "action": "Hold",
        "parameters": {"reason": {"value": "LowPriority"}}
      }
    }
  },

  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "S1",
    "description": "Have Queue 1 liquidity gap?",
    "condition": {
      "op": ">",
      "left": {"field": "queue1_liquidity_gap"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "S2",
      "description": "Urgent transactions (min deadline < 5 ticks)?",
      "condition": {
        "op": "<=",
        "left": {"field": "min_ticks_to_deadline"},
        "right": {"value": 5}
      },
      "on_true": {
        "type": "condition",
        "node_id": "S3",
        "description": "Have collateral capacity for gap?",
        "condition": {
          "op": ">=",
          "left": {"field": "remaining_collateral_capacity"},
          "right": {"field": "queue1_liquidity_gap"}
        },
        "on_true": {
          "type": "action",
          "node_id": "SA1",
          "action": "PostCollateral",
          "parameters": {
            "amount": {"field": "queue1_liquidity_gap"},
            "reason": {"value": "UrgentLiquidityNeed"}
          }
        },
        "on_false": {
          "type": "action",
          "node_id": "SA2",
          "action": "HoldCollateral"
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "SA3",
        "action": "HoldCollateral"
      }
    },
    "on_false": {
      "type": "condition",
      "node_id": "S4",
      "description": "Have posted collateral AND balance healthy?",
      "condition": {
        "op": "and",
        "operands": [
          {
            "op": ">",
            "left": {"field": "posted_collateral"},
            "right": {"value": 0}
          },
          {
            "op": ">",
            "left": {"field": "balance"},
            "right": {
              "compute": {
                "op": "*",
                "left": {"param": "target_buffer"},
                "right": {"value": 1.5}
              }
            }
          }
        ]
      },
      "on_true": {
        "type": "action",
        "node_id": "SA4",
        "action": "WithdrawCollateral",
        "parameters": {
          "amount": {"field": "posted_collateral"},
          "reason": {"value": "LiquidityRestored"}
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "SA5",
        "action": "HoldCollateral"
      }
    }
  },

  "end_of_tick_collateral_tree": {
    "type": "condition",
    "node_id": "E1",
    "description": "Queue 2 empty for this agent?",
    "condition": {
      "op": "==",
      "left": {"field": "queue2_count_for_agent"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "E2",
      "description": "Headroom >= 2x Queue 1 value?",
      "condition": {
        "op": ">=",
        "left": {"field": "headroom"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "queue1_total_value"},
            "right": {"value": 2.0}
          }
        }
      },
      "on_true": {
        "type": "condition",
        "node_id": "E3",
        "description": "Have collateral posted?",
        "condition": {
          "op": ">",
          "left": {"field": "posted_collateral"},
          "right": {"value": 0}
        },
        "on_true": {
          "type": "action",
          "node_id": "EA1",
          "action": "WithdrawCollateral",
          "parameters": {
            "amount": {"field": "posted_collateral"},
            "reason": {"value": "EndOfDayCleanup"}
          }
        },
        "on_false": {
          "type": "action",
          "node_id": "EA2",
          "action": "HoldCollateral"
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "EA3",
        "action": "HoldCollateral"
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "EA4",
      "action": "HoldCollateral"
    }
  },

  "parameters": {
    "target_buffer": 500000.0,
    "urgency_threshold": 5.0
  }
}
```

### 6.3 Tree Behaviors

**Payment Tree**:
- Release if urgent (deadline < threshold) and can pay
- Release if non-urgent and balance - amount >= target_buffer
- Hold otherwise

**Strategic Collateral Tree** (Layer 1 - STEP 2.5):
- **Post**: Queue 1 has liquidity gap AND urgent transactions AND have capacity
- **Withdraw**: No liquidity gap AND balance > 1.5x target buffer AND collateral posted
- **Hold**: Otherwise

**End-of-Tick Collateral Tree** (Layer 2 - STEP 8):
- **Withdraw**: Queue 2 empty AND headroom >= 2x Queue 1 value AND collateral posted
- **Hold**: Otherwise

---

## 7. End-of-Tick Collateral Layer (Layer 2)

### 7.1 Purpose

**Reactive cleanup and emergency posting** implemented as JSON decision tree policy that runs AFTER all settlements but BEFORE cost accrual.

**Why Separate Layer**:
- Strategic layer (Layer 1) runs BEFORE settlements - can't see final state
- End-of-tick layer (Layer 2) runs AFTER settlements - sees final outcomes
- Layer 1 = Strategic/predictive (policy-dependent)
- Layer 2 = Reactive/conservative (can use system default or custom policy)

**Key Design Decision**: Both layers use the same JSON tree policy system - Layer 2 is NOT hardcoded Rust logic, it's a configurable decision tree.

### 7.2 Default Cleanup Policy

**File**: `backend/policies/defaults/end_of_tick_cleanup.json`

**Logic**: Withdraw collateral if Queue 2 is settled AND headroom is sufficient

**Conditions**:
1. Queue 2 empty for agent (`queue2_count_for_agent == 0`)
2. Headroom >= 2x Queue 1 value (`headroom >= 2 * queue1_total_value`)
3. Agent has posted collateral (`posted_collateral > 0`)

**Action**: Withdraw ALL collateral

**Reason**: `EndOfDayCleanup` - clearly not needed, stop paying opportunity cost

### 7.3 Custom End-of-Tick Policies

Agents can specify custom end-of-tick collateral trees in their policy files. Examples:

**Conservative** (system default): Only withdraw when very safe
**Aggressive**: Withdraw more readily, post for predicted needs
**Emergency-Only**: Never withdraw automatically, only post for deadline emergencies

### 7.4 Implementation

End-of-tick collateral decisions are implemented as the third tree in policy JSON files.

**Example: Default Cleanup Policy**

```json
{
  "version": "1.0",
  "policy_id": "default_end_of_tick_cleanup",
  "description": "Conservative cleanup: withdraw when Queue 2 settled and headroom sufficient",

  "payment_tree": null,
  "strategic_collateral_tree": null,

  "end_of_tick_collateral_tree": {
    "type": "condition",
    "node_id": "E1",
    "description": "Queue 2 empty for agent?",
    "condition": {
      "op": "==",
      "left": {"field": "queue2_count_for_agent"},
      "right": {"value": 0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "E2",
      "description": "Headroom >= 2x Queue 1 value?",
      "condition": {
        "op": ">=",
        "left": {"field": "headroom"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "queue1_total_value"},
            "right": {"value": 2.0}
          }
        }
      },
      "on_true": {
        "type": "condition",
        "node_id": "E3",
        "description": "Have collateral posted?",
        "condition": {
          "op": ">",
          "left": {"field": "posted_collateral"},
          "right": {"value": 0}
        },
        "on_true": {
          "type": "action",
          "node_id": "EA1",
          "action": "WithdrawCollateral",
          "parameters": {
            "amount": {"field": "posted_collateral"},
            "reason": {"value": "EndOfDayCleanup"}
          }
        },
        "on_false": {
          "type": "action",
          "node_id": "EA2",
          "action": "HoldCollateral"
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "EA3",
        "action": "HoldCollateral"
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "EA4",
      "action": "HoldCollateral"
    }
  }
}
```

**Key Implementation Points**:
- End-of-tick trees have access to same context fields as strategic trees
- Can use `queue2_count_for_agent`, `headroom`, `posted_collateral`, etc.
- Trees evaluated by `TreePolicy::evaluate_end_of_tick_collateral()` method
- Orchestrator calls this at STEP 8 (after LSM, before costs)

---

## 8. Orchestrator Integration

### 8.1 Updated Tick Loop

**File**: `backend/src/orchestrator/engine.rs`

The tick loop now has TWO collateral evaluation points:

```rust
// STEP 2: Policy Evaluation
for agent_id in agent_ids {
    let agent = self.state.get_agent(&agent_id).unwrap();

    // Evaluate payment tree (existing)
    let release_decisions = policy.evaluate_payment_tree(agent, &self.state, current_tick);

    // Store for execution
    self.pending_release_decisions.insert(agent_id.clone(), release_decisions);
}

// STEP 2.5: STRATEGIC COLLATERAL LAYER (Layer 1)
for agent_id in agent_ids {
    let agent = self.state.get_agent(&agent_id).unwrap();

    // Only TreePolicy supports collateral evaluation
    if let Some(tree_policy) = self.policies.get_mut(&agent_id)
        .and_then(|p| p.as_any_mut().downcast_mut::<TreePolicy>())
    {
        // Evaluate strategic collateral tree
        let decision = tree_policy.evaluate_strategic_collateral(
            agent, &self.state, current_tick, &self.cost_rates
        );

        // Execute immediately
        self.execute_collateral_decision(&agent_id, decision, current_tick)?;
    }
}

// STEP 3-7: Queue processing, splitting, RTGS, LSM
// ... (existing steps)

// STEP 8: END-OF-TICK COLLATERAL LAYER (Layer 2) - NEW!
for agent_id in agent_ids {
    let agent = self.state.get_agent(&agent_id).unwrap();

    if let Some(tree_policy) = self.policies.get_mut(&agent_id)
        .and_then(|p| p.as_any_mut().downcast_mut::<TreePolicy>())
    {
        // Evaluate end-of-tick collateral tree
        let decision = tree_policy.evaluate_end_of_tick_collateral(
            agent, &self.state, current_tick, &self.cost_rates
        );

        // Execute immediately
        self.execute_collateral_decision(&agent_id, decision, current_tick)?;
    }
}

// STEP 9: Cost Accrual (existing, includes collateral costs)
self.accrue_costs(current_tick);
```

**Key Points**:
- STEP 2.5 runs BEFORE settlements (strategic, forward-looking)
- STEP 8 runs AFTER settlements (reactive, sees final state)
- Both use same `execute_collateral_decision()` helper
- Both use tree evaluation (no hardcoded logic)

### 8.2 Execute Collateral Decisions

**Status**: ✅ Already Implemented (Phase 1)

The `execute_collateral_decision()` helper method handles:
- Validation (capacity checks, amount validation)
- State updates (post/withdraw collateral)
- Event logging (CollateralPost/CollateralWithdraw events with reason)

**Signature**:
```rust
fn execute_collateral_decision(
    &mut self,
    agent_id: &str,
    decision: CollateralDecision,
    tick: usize,
) -> Result<(), SimulationError>
```

This method matches on the CollateralDecision enum:
- `Post { amount, reason }` → validates capacity, posts collateral, logs event
- `Withdraw { amount, reason }` → validates amount available, withdraws, logs event
- `Hold` → no action

---

## 9. Implementation Phases

### Phase 1: Core Infrastructure ✅ **COMPLETE (2025-10-29)**

**Status**: Policy Layer ONLY (End-of-Tick Manager is Phase 4)

**What Was Implemented**:
1. ✅ Fixed Agent.available_liquidity() to include collateral
   - Formula: `balance + credit_limit + posted_collateral`
2. ✅ Added `CollateralDecision` enum (Post/Withdraw/Hold) and `CollateralReason` enum
3. ✅ Extended `CashManagerPolicy` trait with `evaluate_collateral()` method
   - Default implementation returns `Hold` (backward compatible)
4. ✅ Added helper methods to Agent:
   - `max_collateral_capacity()`, `remaining_collateral_capacity()`
   - `queue1_liquidity_gap()` - calculates liquidity shortfall
5. ✅ Added `CollateralPost` and `CollateralWithdraw` events to event log
6. ✅ Updated orchestrator to execute collateral decisions (STEP 2.5)
   - Runs after policy evaluation, before RTGS submission
   - Validates capacity constraints before execution
   - Logs events with reason and new total

**Files Modified**:
- `backend/src/policy/mod.rs` - Added types and trait method
- `backend/src/models/agent.rs` - Fixed liquidity formula, added helpers
- `backend/src/orchestrator/engine.rs` - Added STEP 2.5 execution logic
- `backend/src/models/event.rs` - Added collateral events

**Tests** (10 new tests, 134 total passing):
- ✅ Unit tests for Agent helper methods (capacity, liquidity gap)
- ✅ Agent collateral post/withdraw cycle tests
- ✅ Available liquidity includes collateral test
- ✅ All existing tests still pass (backward compatibility)

**Success Criteria** (ALL MET):
- ✅ Policies can return `CollateralDecision`
- ✅ Orchestrator executes decisions correctly
- ✅ Events logged properly with reason and new total
- ✅ Capacity limits enforced (validation before execution)
- ✅ Collateral increases available_liquidity correctly

**What This Phase Does NOT Include**:
- ❌ End-of-Tick Collateral Manager (Phase 4)
- ❌ DSL extensions for collateral actions (Phase 2)
- ❌ `liquidity_aware_with_collateral` policy (Phase 3)

---

### Phase 2: DSL Extensions (2-3 days)

**Tasks**:
1. Add `PostCollateral`, `WithdrawCollateral`, `HoldCollateral` action types
2. Add collateral-related field accessors to `EvaluationContext`
3. Add Queue 2 pressure fields (count, nearest deadline)
4. Update tree executor to handle collateral actions
5. Add validation for collateral action parameters

**Files Modified**:
- `backend/src/policy/tree/types.rs`
- `backend/src/policy/tree/context.rs`
- `backend/src/policy/tree/executor.rs`
- `backend/src/policy/tree/validation.rs`

**Tests**:
- DSL field accessor tests (collateral fields return correct values)
- Tree executor tests (collateral actions produce correct decisions)
- Validation tests (reject invalid collateral actions)

**Success Criteria**:
- JSON policies can specify collateral actions
- All new fields accessible in expressions
- Validation catches common errors
- Tree policies can post/withdraw collateral

---

### Phase 3: New Policy Implementation (2 days)

**Tasks**:
1. Create `liquidity_aware_with_collateral.json`
2. Test policy in isolation (unit tests)
3. Test policy in scenarios:
   - Scenario 1: Urgent transactions trigger posting
   - Scenario 2: Liquidity restored triggers withdrawal
   - Scenario 3: Emergency deadline triggers posting

**Files Created**:
- `backend/policies/liquidity_aware_with_collateral.json`
- `backend/tests/test_collateral_policy.rs`

**Tests**:
- Policy loads and validates correctly
- Posting logic works (urgent + gap → post)
- Withdrawal logic works (healthy + no gap → withdraw)
- Policy equivalent to liquidity_aware for transactions

**Success Criteria**:
- Policy file valid and loads without errors
- Collateral decisions made correctly based on conditions
- Transaction release decisions unchanged from base policy
- Simulation runs complete episode with policy

---

### Phase 4: End-of-Tick Manager ❌ **NOT STARTED**

**Status**: Future work - implements the automatic/reactive collateral layer

**Tasks**:
1. Implement `CollateralManager` struct
2. Implement cleanup logic (withdrawal rules)
3. Implement emergency logic (posting rules)
4. Integrate into orchestrator tick loop
5. Add configuration for thresholds

**Files Created**:
- `backend/src/orchestrator/collateral_manager.rs`

**Files Modified**:
- `backend/src/orchestrator/engine.rs` (integration)
- `backend/src/orchestrator/mod.rs` (expose module)

**Tests**:
- Cleanup logic tests (withdraw when safe)
- Emergency logic tests (post when deadline imminent)
- Integration tests (manager runs at end of tick)
- No conflict tests (manager doesn't fight policy decisions)

**Success Criteria**:
- Cleanup withdraws collateral when clearly not needed
- Emergency posts collateral when deadline < 2 ticks
- Events logged with correct reasons
- Manager respects capacity limits

---

### Phase 5: Integration Testing & Validation (2-3 days)

**Tasks**:
1. End-to-end scenarios:
   - Scenario A: Agent posts collateral for urgent payment, withdraws after settlement
   - Scenario B: Emergency manager posts collateral for expiring Queue 2 transaction
   - Scenario C: Cleanup manager withdraws collateral at end of successful day
   - Scenario D: Agent with collateral pays less total cost than without
2. Performance testing (no regression)
3. Determinism testing (collateral decisions deterministic)
4. Cost validation (opportunity cost accrues correctly)

**Files Created**:
- `backend/tests/test_collateral_integration.rs`
- `backend/tests/scenarios/collateral_scenarios.yaml` (test configs)

**Tests**:
- End-to-end flow tests (all steps execute correctly)
- Cost comparison tests (collateral vs no collateral)
- Determinism tests (same seed → same collateral decisions)
- Performance benchmarks (no significant slowdown)

**Success Criteria**:
- All scenarios pass
- Cost model works correctly with dynamic collateral
- No performance regression (< 5% overhead)
- Determinism maintained
- All existing tests still pass (backward compatibility)

---

### Phase 6: Documentation & Examples (1 day)

**Tasks**:
1. Update `docs/queue_architecture.md` (add collateral management section)
2. Update `docs/policy_dsl_design.md` (document collateral actions)
3. Create `docs/collateral_management_guide.md` (user guide)
4. Add example configs with collateral
5. Update API documentation

**Files Created/Updated**:
- `docs/collateral_management_guide.md` (new)
- `docs/queue_architecture.md` (updated)
- `docs/policy_dsl_design.md` (updated)
- `config/examples/collateral_example.yaml` (new)

**Success Criteria**:
- Users can understand when to use collateral
- Policy DSL docs cover collateral actions
- Example configs demonstrate usage
- Integration with grand_plan.md

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Agent Tests** (`backend/src/models/agent.rs`):
- `test_max_collateral_capacity()` - returns correct limit
- `test_remaining_capacity()` - calculates correctly
- `test_can_post_collateral()` - validates capacity
- `test_can_withdraw_collateral()` - validates amount
- `test_queue1_liquidity_gap()` - calculates gap correctly

**Policy Tests** (`backend/tests/test_collateral_policy.rs`):
- `test_post_collateral_on_urgent_gap()` - policy posts when needed
- `test_withdraw_collateral_on_healthy_balance()` - policy withdraws when safe
- `test_hold_collateral_by_default()` - no action when conditions not met

**Collateral Manager Tests** (`backend/tests/test_collateral_manager.rs`):
- `test_cleanup_withdraws_when_safe()` - manager withdraws excess
- `test_emergency_posts_on_deadline()` - manager posts for expiring
- `test_no_action_when_uncertain()` - conservative behavior

### 10.2 Integration Tests

**Orchestrator Tests** (`backend/tests/test_orchestrator_integration.rs`):
- `test_collateral_decision_execution()` - decisions executed correctly
- `test_collateral_capacity_enforced()` - can't exceed limits
- `test_collateral_events_logged()` - events recorded
- `test_collateral_affects_liquidity()` - posting increases available liquidity

**End-to-End Scenarios** (`backend/tests/test_collateral_integration.rs`):
- `test_scenario_urgent_posting_and_withdrawal()`
- `test_scenario_emergency_manager_saves_deadline()`
- `test_scenario_cleanup_manager_reduces_costs()`
- `test_scenario_collateral_vs_no_collateral_cost_comparison()`

### 10.3 DSL Tests

**Tree Policy Tests** (`backend/src/policy/tree/executor.rs`):
- `test_post_collateral_action()` - JSON action produces Post decision
- `test_withdraw_collateral_action()` - JSON action produces Withdraw decision
- `test_collateral_field_accessors()` - fields return correct values
- `test_queue2_pressure_fields()` - Queue 2 fields calculated correctly

### 10.4 Property Tests

**Invariants** (`backend/tests/test_collateral_properties.rs`):
- `posted_collateral <= max_capacity` (always)
- `posted_collateral >= 0` (always)
- Balance conservation (collateral doesn't create/destroy money)
- Determinism (same seed → same collateral decisions)

---

## 11. Success Criteria

### 11.1 Functional Requirements

- [ ] Policies can make collateral decisions (post/withdraw)
- [ ] End-of-tick manager runs after LSM, before costs
- [ ] Collateral capacity limits enforced
- [ ] Collateral increases available_liquidity correctly
- [ ] Collateral costs accrue only when posted
- [ ] Events logged for all collateral changes
- [ ] JSON policies can specify collateral actions
- [ ] All collateral field accessors work correctly

### 11.2 Performance Requirements

- [ ] No significant performance regression (< 5% slower)
- [ ] Collateral evaluation adds < 1ms per agent per tick
- [ ] No memory leaks (valgrind clean)

### 11.3 Quality Requirements

- [ ] All existing tests still pass (backward compatibility)
- [ ] New tests cover collateral features (>80% coverage)
- [ ] Determinism maintained (replay tests pass)
- [ ] No clippy warnings
- [ ] Documentation complete and accurate

### 11.4 Business Requirements

- [ ] Agent with collateral can settle more transactions
- [ ] Collateral posting reduces delay costs (trade-off)
- [ ] Collateral withdrawal reduces opportunity costs
- [ ] Emergency manager prevents deadline violations
- [ ] Cleanup manager optimizes costs automatically

---

## 12. Future Enhancements

### 12.1 Phase 8 Extensions (Not in Scope)

**Haircut Modeling**:
- Add `collateral_haircut: f64` to AgentConfig (e.g., 0.9 = 90% value)
- Modify `available_liquidity()` to apply haircut:
  ```rust
  collateralized_credit = (posted_collateral as f64 * haircut) as i64
  ```

**Collateral Types**:
- Differentiate government bonds, cash, securities
- Each type has different haircut and opportunity cost
- `Vec<CollateralHolding>` instead of single `posted_collateral: i64`

**Multi-Currency Collateral**:
- Collateral denominated in different currencies
- FX rate risk in collateral value
- Cross-currency haircuts

### 12.2 Phase 13 Extensions (LLM Learning)

**Policy Learning**:
- LLM learns optimal collateral strategies
- Shadow replay validates collateral decisions
- Guardrails for maximum collateral usage

**Adaptive Thresholds**:
- Learn optimal emergency deadline threshold (currently 2 ticks)
- Learn optimal withdrawal safety margin (currently 1.5x buffer)
- Adjust based on agent risk profile

### 12.3 Phase 10+ Extensions (Advanced Features)

**Collateral Repledging**:
- Central bank accepts collateral, can repledge it
- Model collateral velocity and multiplier effects

**Collateral Auctions**:
- Competitive collateral allocation (scarce capacity)
- Price discovery for collateral cost rates

**Collateral Network**:
- Agents borrow collateral from each other
- Collateral chains (A borrows from B, B from C)
- Contagion risk from collateral fire sales

---

## Appendix A: Configuration Schema

### A.1 Agent Configuration with Collateral

```yaml
agents:
  - id: BANK_A
    balance: 5_000_000      # $50k opening
    credit_limit: 2_000_000  # $20k unsecured credit

    # Collateral configuration (Phase 8)
    max_collateral_capacity: 20_000_000  # Can post up to $200k
    initial_posted_collateral: 0  # Start with none (optional, default 0)
    collateral_haircut: 1.0  # 1:1 value (no haircut)

    # Policy configuration
    policy:
      type: tree
      path: "policies/liquidity_aware_with_collateral.json"
      parameters:
        target_buffer: 1_000_000  # $10k buffer
        urgency_threshold: 5  # Ticks to deadline
```

### A.2 Collateral Manager Configuration

```yaml
simulation:
  collateral_manager:
    enabled: true

    # Emergency posting threshold (ticks to deadline)
    emergency_deadline_threshold: 2

    # Withdrawal safety margin (multiplier on target_buffer)
    withdrawal_safety_margin: 1.5
```

### A.3 Cost Configuration

```yaml
costs:
  # Existing costs
  liquidity_rate: 0.0005  # 5 bps annualized (overdraft)
  delay_cost_per_tick_per_cent: 0.00001  # Delay cost

  # Collateral cost (Phase 8)
  collateral_cost_per_tick_bps: 0.0002  # 2 bps annualized opportunity cost

  # Penalties
  eod_penalty_per_transaction: 500_000  # $5k per unsettled
  deadline_penalty: 100_000  # $1k per violation
  split_friction_cost: 1_000  # $10 per split
```

---

## Appendix B: Example Scenarios

### B.1 Scenario: Urgent Payment with Collateral

**Setup**:
- Agent: BANK_A
- Balance: $50k
- Credit: $20k (total liquidity: $70k)
- Collateral capacity: $100k
- Policy: `liquidity_aware_with_collateral`

**Events**:
1. **Tick 10**: Large payment arrives ($80k, deadline tick 15)
2. **Tick 10**: Policy evaluates
   - Liquidity gap: $80k - $70k = $10k
   - Deadline: 5 ticks (urgent)
   - **Decision**: Post $10k collateral
3. **Tick 11**: RTGS processes payment
   - Available liquidity: $70k + $10k = $80k
   - **Payment settles**
4. **Tick 11**: Incoming payment arrives ($50k)
   - Balance: $50k - $80k + $50k = $20k
5. **Tick 12**: Policy evaluates
   - Balance: $20k (healthy, > buffer $10k)
   - No liquidity gap
   - **Decision**: Withdraw $10k collateral
6. **Tick 12**: End-of-tick manager confirms withdrawal is safe

**Outcome**:
- Payment settled on time (no deadline penalty: $0)
- Collateral cost: $10k × 0.0002 × 2 ticks = $4
- **Total cost**: $4 (vs. $100k deadline penalty without collateral)

### B.2 Scenario: Emergency Manager Saves Deadline

**Setup**:
- Agent: BANK_B
- Balance: $30k
- Credit: $20k (total liquidity: $50k)
- Collateral: $0 (none posted)
- Policy: FIFO (doesn't manage collateral)

**Events**:
1. **Tick 20**: Payment submitted to Queue 2 ($60k, deadline tick 23)
   - Insufficient liquidity ($50k < $60k)
   - **Payment waits in Queue 2**
2. **Tick 21**: Still in Queue 2 (no incoming payments)
3. **Tick 22**: End-of-tick manager evaluates
   - Queue 2 transaction deadline: 1 tick away (< threshold 2)
   - Liquidity gap: $10k
   - Has capacity: Yes
   - **Decision**: Post $10k collateral (emergency)
4. **Tick 23**: RTGS retry
   - Available liquidity: $50k + $10k = $60k
   - **Payment settles**

**Outcome**:
- Deadline met (no penalty: $0)
- Collateral cost: $10k × 0.0002 × 1 tick = $2
- **Emergency manager saved $100k penalty for $2 cost**

---

## Appendix C: Trade-Off Analysis

### Collateral vs. Overdraft

| Strategy | Liquidity Source | Cost Rate (annualized) | When to Use |
|----------|-----------------|------------------------|-------------|
| **Overdraft** | Negative balance | 5 bps | Temporary shortfall, expect quick inflow |
| **Collateral** | Posted securities | 2 bps | Anticipated sustained need, overnight |

### Collateral vs. Delay

| Strategy | Approach | Cost | When to Use |
|----------|----------|------|-------------|
| **Post Collateral** | Settle immediately | Opportunity cost | Urgent deadlines, client expectations |
| **Hold (delay)** | Wait for inflow | Delay cost + possible penalty | Non-urgent, inflow expected soon |

**Break-Even Analysis**:
```
Collateral cost per tick = $100k × 0.0002 = $20
Delay cost per tick = $100k × 0.00001 = $1

Collateral more expensive if delay < 20 ticks
→ Use delay for short waits (<20 ticks), collateral for sustained needs
```

---

## Document Status

**Status**: Planning Phase
**Next Steps**:
1. Review plan with team
2. Get approval on architecture decisions
3. Begin Phase 1 implementation
4. Set up tracking for success criteria

**Estimated Completion**: 2-3 weeks (12-15 days of development)

**Dependencies**:
- Phase 8 Part 1 completion (Agent.available_liquidity fix)
- Phase 9 DSL infrastructure (already complete)

**Risks**:
- Policy complexity (may need iterative tuning)
- End-of-tick manager conflicts with policy decisions (needs careful design)
- Performance impact of additional tick loop steps (needs benchmarking)

---

**Maintainer**: Payment Simulator Team
**Last Updated**: 2025-10-29
**Version**: 1.0 - Initial Planning
