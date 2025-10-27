# Policy DSL Design: Decision Tree Framework for Cash Manager Policies

> **Document Status**: Phase 4a complete (Rust traits), Phase 6 DSL layer designed but not yet implemented
>
> **Last Updated**: 2025-10-27
>
> **Purpose**: Complete specification for LLM-editable decision tree policies

---

## Table of Contents

1. [Introduction & Architecture](#1-introduction--architecture)
2. [Phase 4a: Current Implementation (Rust Traits)](#2-phase-4a-current-implementation-rust-traits)
3. [Phase 6: DSL Specification (JSON Decision Trees)](#3-phase-6-dsl-specification-json-decision-trees)
4. [LLM Integration & Validation](#4-llm-integration--validation)
5. [Migration Path](#5-migration-path)
6. [Examples & Reference](#6-examples--reference)

---

# 1. Introduction & Architecture

## 1.1 Executive Summary

This document specifies the **hybrid policy framework** for cash manager decision-making in the payment simulator. The framework supports two execution modes:

1. **Phase 4a (Current)**: Rust trait-based policies for fast iteration and validation
2. **Phase 6 (Future)**: JSON DSL interpreter for LLM-driven policy evolution

**Key Design Decisions**:
- Start with Rust traits to validate the abstraction
- Design DSL spec now, implement interpreter later (Phase 6)
- Support both execution modes via `PolicyExecutor` enum
- No breaking changes when adding DSL layer

## 1.2 Two-Phase Approach Rationale

### Why Start with Rust Traits (Phase 4a)?

**Advantages**:
- ✅ Fast compilation and iteration
- ✅ Compile-time type checking catches errors early
- ✅ Debugger support for policy logic
- ✅ No interpreter overhead (performance)
- ✅ Proves abstraction works before building DSL infrastructure

**What We Learn**:
- Which decision factors are actually needed
- What edge cases arise in practice
- Performance characteristics of policy evaluation
- Test patterns and invariants

### Why Add DSL Layer Later (Phase 6)?

**When DSL Becomes Necessary**:
- LLM Manager service needs to edit policies at runtime
- Shadow replay validation requires policy versioning
- Monte Carlo opponent sampling needs policy swapping
- A/B testing requires hot-reload without recompilation

**Cost-Benefit Analysis**:
- DSL adds ~2,000 lines of infrastructure
- Needed only when starting RL/LLM optimization
- Can design schema now, implement when needed
- Incremental migration: port policies one-by-one

## 1.3 Architecture Overview

### Two-Queue Model

```
Client Transaction Arrives
         ↓
    [Queue 1: Internal Bank Queue]  ← Cash Manager Policy (strategic)
         ↓
    Submit to RTGS
         ↓
    [Queue 2: Central RTGS Queue]   ← Settlement Engine (mechanical)
         ↓
    Settlement Complete
```

**Queue 1 (Policy-Driven)**:
- Location: `Agent.outgoing_queue: Vec<String>`
- Authority: Cash manager policy (Rust trait or DSL)
- Decision: **When** to submit to RTGS
- Re-evaluated: **Every tick** as conditions change

**Queue 2 (Mechanical)**:
- Location: `SimulationState.rtgs_queue: Vec<String>`
- Authority: RTGS settlement engine (deterministic)
- Purpose: Retry transactions awaiting **liquidity**
- Processing: FIFO with deadline expiration

### Policy Evaluation Flow

```rust
// Every tick, for each agent:
let decisions = policy.evaluate_queue(agent, &state, tick);

for decision in decisions {
    match decision {
        ReleaseDecision::SubmitFull { tx_id } => {
            // Move from Queue 1 to Queue 2
            submit_to_rtgs(&state, &tx_id);
        }
        ReleaseDecision::Hold { tx_id, reason } => {
            // Remain in Queue 1, re-evaluate next tick
        }
        ReleaseDecision::Drop { tx_id } => {
            // Remove from Queue 1 without submitting
        }
        ReleaseDecision::SubmitPartial { tx_id, amount } => {
            // Phase 5: Split transaction
        }
    }
}
```

### Hybrid Execution Architecture (Phase 6)

```rust
pub enum PolicyExecutor {
    /// Hand-coded Rust policy (fast, compile-time checked)
    Trait(Box<dyn CashManagerPolicy>),

    /// JSON decision tree (LLM-editable, hot-reloadable)
    Tree(TreeInterpreter),
}

impl PolicyExecutor {
    pub fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        match self {
            PolicyExecutor::Trait(policy) => {
                policy.evaluate_queue(agent, state, tick)
            }
            PolicyExecutor::Tree(interpreter) => {
                interpreter.evaluate(agent, state, tick)
            }
        }
    }
}
```

## 1.4 Design Goals

### For Phase 4a (Rust Traits)

1. **Validate Abstraction**: Prove that `CashManagerPolicy` trait can express sophisticated logic
2. **Enumerate Decision Factors**: Document all data policies need to access
3. **Establish Test Patterns**: Create reusable test infrastructure
4. **Baseline Policies**: Implement 3+ policies to stress-test interface

### For Phase 6 (DSL Layer)

1. **LLM-Safe**: No code execution, sandboxed interpreter
2. **Expressive**: Can represent complex decision trees with nested conditions
3. **Validatable**: JSON schema + runtime safety checks catch errors
4. **Debuggable**: Clear node IDs, execution traces
5. **Version-Controlled**: Git tracks policy evolution
6. **Hot-Reloadable**: Update policies without restarting simulation

---

# 2. Phase 4a: Current Implementation (Rust Traits)

## 2.1 CashManagerPolicy Trait

### Trait Definition

```rust
/// Cash manager policy trait
///
/// Implement this trait to define custom decision logic for when to submit
/// transactions from internal queue (Queue 1) to RTGS (Queue 2).
pub trait CashManagerPolicy {
    /// Evaluate internal queue and decide what to submit to RTGS
    ///
    /// Called once per tick for each agent. Returns a vector of decisions
    /// for transactions in the agent's Queue 1 (internal outgoing queue).
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent whose queue is being evaluated
    /// * `state` - Full simulation state (for querying transactions, other agents)
    /// * `tick` - Current simulation tick
    ///
    /// # Returns
    ///
    /// Vector of decisions (Submit/Hold/Drop) for transactions in agent's queue
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision>;
}
```

### Evaluation Semantics

**Every-Tick Re-Evaluation**:
- Policies are called **every tick** for each agent
- Allows policies to change their mind as conditions evolve
- Transactions can be held in Queue 1 indefinitely (until deadline)
- Different from "fire-and-forget" semantics in original grand plan

**Why Every-Tick**:
- Liquidity changes as incoming payments settle
- Deadlines approach (urgency increases)
- System-wide queue pressure fluctuates
- Expected inflows materialize or fail to arrive

**Example Scenario**:
```
Tick 50: Transaction A (1000, deadline 100) arrives
         Policy: HOLD (balance 800, buffer 1000, not urgent)

Tick 60: Incoming payment B (500) settles → balance now 1300
         Policy: SUBMIT FULL (balance 1300 > 1000 + buffer)

Tick 70: Transaction A submitted to RTGS Queue 2
```

## 2.2 ReleaseDecision Types

### Decision Enum

```rust
/// Decision about what to do with a transaction in Queue 1
#[derive(Debug, Clone, PartialEq)]
pub enum ReleaseDecision {
    /// Submit entire transaction to RTGS now
    SubmitFull { tx_id: String },

    /// Submit partial amount (Phase 5 - splitting not yet implemented)
    SubmitPartial { tx_id: String, amount: i64 },

    /// Hold transaction in Queue 1 for later re-evaluation
    Hold { tx_id: String, reason: HoldReason },

    /// Drop transaction (expired or unviable)
    Drop { tx_id: String },
}

/// Reason for holding a transaction in Queue 1
#[derive(Debug, Clone, PartialEq)]
pub enum HoldReason {
    /// Insufficient liquidity to send without violating buffer
    InsufficientLiquidity,

    /// Waiting for expected incoming payments
    AwaitingInflows,

    /// Transaction has low priority, others more urgent
    LowPriority,

    /// Approaching deadline but not yet urgent
    NearDeadline { ticks_remaining: usize },

    /// Custom policy-specific reason
    Custom(String),
}
```

### Decision Semantics

**SubmitFull**:
- Transaction moves from Queue 1 to Queue 2 (RTGS)
- RTGS attempts immediate settlement
- If insufficient liquidity, transaction queues in RTGS (Queue 2)
- Transaction ID removed from `agent.outgoing_queue`

**SubmitPartial** (Phase 5):
- Split transaction into parts
- Submit specified amount now
- Remainder stays in Queue 1 or creates new child transaction
- Useful for large transactions that would exhaust liquidity

**Hold**:
- Transaction remains in `agent.outgoing_queue`
- Will be re-evaluated at next tick
- Reason logged for metrics/debugging
- No state change

**Drop**:
- Transaction removed from Queue 1
- Marked as dropped in transaction state
- Deadline penalty applied
- Useful for expired transactions or unviable payments

## 2.3 Decision Context

### Agent State (via `agent: &Agent`)

Policies have access to complete agent state:

```rust
// Liquidity
agent.balance()             // Current central bank balance (i64 cents)
agent.credit()              // Available credit headroom (i64 cents)
agent.credit_limit()        // Total credit limit (i64 cents)
agent.can_pay(amount)       // Can send amount? (balance + credit >= amount)
agent.available_liquidity() // balance + credit

// Queue 1 Analysis
agent.outgoing_queue()              // Vec<String> - transaction IDs
agent.outgoing_queue_size()         // usize - number of queued transactions
agent.outgoing_queue_value()        // i64 - total value queued
agent.incoming_expected()           // Vec<String> - expected inflow IDs

// Liquidity Management
agent.liquidity_buffer()    // Target minimum balance (i64 cents)
agent.liquidity_pressure()  // Stress level: 0.0 (low) to 1.0 (high)
agent.can_afford_to_send(amount) // Sending maintains buffer?

// Metadata
agent.id()                  // Agent ID string
agent.last_decision_tick()  // Option<usize> - last policy evaluation
```

### Transaction Details (via `state.get_transaction(tx_id)`)

```rust
let tx = state.get_transaction(tx_id).unwrap();

// Amount
tx.amount()             // Original amount (i64 cents)
tx.remaining_amount()   // Unsettled amount (i64 cents)
tx.settled_amount()     // Already settled (i64 cents)

// Timing
tx.arrival_tick()       // When transaction entered system
tx.deadline_tick()      // Hard deadline (usize tick)
tx.is_past_deadline(tick) // bool

// Parties
tx.sender_id()          // Sending agent ID
tx.receiver_id()        // Receiving agent ID

// Properties
tx.priority()           // 0-10 priority level
tx.is_divisible()       // Can be split?
tx.status()             // TransactionStatus enum

// Lifecycle
tx.is_pending()         // Not yet settled
tx.is_fully_settled()   // Completely settled
tx.is_partially_settled() // Partial settlement occurred
```

### System State (via `state: &SimulationState`)

```rust
// Queue 1 Analytics (All Agents)
state.total_internal_queue_size()    // Total transactions in all Queue 1s
state.total_internal_queue_value()   // Total value across all Queue 1s
state.agents_with_queued_transactions() // Vec<String> - agent IDs

// Per-Agent Queue Analysis
state.agent_queue_value(agent_id)    // Queue 1 value for specific agent

// Urgent Transactions (System-Wide)
state.get_urgent_transactions(tick, threshold)
    // Vec<(String, String)> - (agent_id, tx_id) pairs
    // Returns transactions with deadline <= tick + threshold

// Queue 2 (RTGS Central Queue)
state.rtgs_queue_size()              // Transactions awaiting liquidity

// Other Agents (for coordination signals)
state.get_agent(agent_id)            // Option<&Agent>
state.agents()                       // Iterator<&Agent>
```

### Time Context (via `tick: usize`)

```rust
let current_tick = tick;
let deadline = tx.deadline_tick();
let ticks_to_deadline = deadline.saturating_sub(current_tick);
let queue_age = current_tick - tx.arrival_tick();

// Derive additional time information
let ticks_to_eod = 100 - current_tick; // Assuming 100 ticks/day
let is_morning = current_tick < 30;
let is_eod_window = ticks_to_eod <= 10;
```

## 2.4 Baseline Policies

### 2.4.1 FifoPolicy - Immediate Submission

**Purpose**: Simplest possible baseline for comparison

**Logic**: Submit all transactions immediately, no strategic holding

**Implementation**:
```rust
pub struct FifoPolicy;

impl CashManagerPolicy for FifoPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        _state: &SimulationState,
        _tick: usize,
    ) -> Vec<ReleaseDecision> {
        agent.outgoing_queue()
            .iter()
            .map(|tx_id| ReleaseDecision::SubmitFull {
                tx_id: tx_id.clone(),
            })
            .collect()
    }
}
```

**Use Case**: Baseline for measuring policy performance impact

**Characteristics**:
- No liquidity management
- No deadline awareness
- Maximizes RTGS queue pressure
- May exhaust credit quickly

### 2.4.2 DeadlinePolicy - Urgency-Based

**Purpose**: Prioritize transactions approaching deadlines

**Parameters**:
- `urgency_threshold: usize` - Ticks before deadline to consider urgent (default: 5)

**Logic**:
1. If past deadline → **Drop**
2. If deadline within threshold → **Submit**
3. Otherwise → **Hold**

**Implementation**:
```rust
pub struct DeadlinePolicy {
    urgency_threshold: usize,
}

impl DeadlinePolicy {
    pub fn new(urgency_threshold: usize) -> Self {
        Self { urgency_threshold }
    }
}

impl CashManagerPolicy for DeadlinePolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        let mut decisions = Vec::new();

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let deadline = tx.deadline_tick();

                // Drop if expired
                if deadline <= tick {
                    decisions.push(ReleaseDecision::Drop {
                        tx_id: tx_id.clone(),
                    });
                    continue;
                }

                let ticks_remaining = deadline - tick;

                // Submit if urgent
                if ticks_remaining <= self.urgency_threshold {
                    decisions.push(ReleaseDecision::SubmitFull {
                        tx_id: tx_id.clone(),
                    });
                } else {
                    // Hold if not urgent
                    decisions.push(ReleaseDecision::Hold {
                        tx_id: tx_id.clone(),
                        reason: HoldReason::NearDeadline { ticks_remaining },
                    });
                }
            }
        }

        decisions
    }
}
```

**Use Case**: Minimize deadline penalties while holding non-urgent transactions

**Trade-offs**:
- ✅ Avoids deadline penalties for urgent transactions
- ✅ Holds non-urgent transactions (reduces RTGS queue pressure)
- ❌ No liquidity awareness (may exhaust credit on urgent transactions)
- ❌ Drops expired transactions without attempting submission

### 2.4.3 LiquidityAwarePolicy - Buffer Preservation

**Purpose**: Preserve liquidity buffer while meeting deadlines

**Parameters**:
- `target_buffer: i64` - Minimum balance to maintain (cents)
- `urgency_threshold: usize` - Ticks before deadline to override liquidity check

**Logic**:
1. If past deadline → **Drop**
2. If urgent (≤ threshold ticks) → **Submit** (override liquidity check if physically possible)
3. If sending maintains buffer → **Submit**
4. Otherwise → **Hold** (insufficient liquidity)

**Implementation**:
```rust
pub struct LiquidityAwarePolicy {
    target_buffer: i64,
    urgency_threshold: usize,
}

impl LiquidityAwarePolicy {
    pub fn new(target_buffer: i64) -> Self {
        Self {
            target_buffer,
            urgency_threshold: 5,
        }
    }

    pub fn with_urgency_threshold(target_buffer: i64, urgency_threshold: usize) -> Self {
        Self {
            target_buffer,
            urgency_threshold,
        }
    }
}

impl CashManagerPolicy for LiquidityAwarePolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        let mut decisions = Vec::new();
        let current_balance = agent.balance();

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let amount = tx.remaining_amount();
                let deadline = tx.deadline_tick();

                // Check if expired
                if deadline <= tick {
                    decisions.push(ReleaseDecision::Drop {
                        tx_id: tx_id.clone(),
                    });
                    continue;
                }

                let ticks_remaining = deadline - tick;
                let is_urgent = ticks_remaining <= self.urgency_threshold;

                // Calculate if sending would violate buffer
                let can_send = if self.target_buffer == 0 {
                    agent.can_pay(amount)
                } else {
                    current_balance - amount >= self.target_buffer
                };

                if is_urgent {
                    // Urgent: submit regardless of liquidity (if physically possible)
                    if agent.can_pay(amount) {
                        decisions.push(ReleaseDecision::SubmitFull {
                            tx_id: tx_id.clone(),
                        });
                    } else {
                        // Can't pay even with all liquidity: hold (will likely expire)
                        decisions.push(ReleaseDecision::Hold {
                            tx_id: tx_id.clone(),
                            reason: HoldReason::InsufficientLiquidity,
                        });
                    }
                } else if can_send {
                    // Safe to send: either no buffer requirement or buffer will be maintained
                    decisions.push(ReleaseDecision::SubmitFull {
                        tx_id: tx_id.clone(),
                    });
                } else {
                    // Would violate buffer and not urgent: hold
                    decisions.push(ReleaseDecision::Hold {
                        tx_id: tx_id.clone(),
                        reason: HoldReason::InsufficientLiquidity,
                    });
                }
            }
        }

        decisions
    }
}
```

**Use Case**: Minimize credit usage while avoiding deadline penalties

**Trade-offs**:
- ✅ Preserves liquidity (reduces overdraft costs)
- ✅ Overrides liquidity check for urgent transactions
- ✅ Configurable buffer threshold
- ❌ May hold transactions longer than necessary
- ❌ Doesn't consider expected inflows

## 2.5 Testing Patterns

### Test Structure

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Agent, SimulationState, Transaction};

    #[test]
    fn test_policy_decision() {
        // 1. Create test state
        let agent = Agent::new("BANK_A".to_string(), 200_000, 0);
        let mut state = SimulationState::new(vec![agent.clone()]);

        // 2. Create transaction
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            150_000,
            0,
            100
        );
        let tx_id = tx.id().to_string();

        // 3. CRITICAL: Add to state BEFORE queuing
        state.add_transaction(tx);
        state.get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

        // 4. Create policy
        let mut policy = LiquidityAwarePolicy::new(100_000);

        // 5. Get fresh agent reference
        let agent = state.get_agent("BANK_A").unwrap();

        // 6. Evaluate policy
        let decisions = policy.evaluate_queue(agent, &state, 5);

        // 7. Assert expected behavior
        assert_eq!(decisions.len(), 1);
        assert!(matches!(decisions[0], ReleaseDecision::Hold { .. }));
    }
}
```

### Critical Test Pattern

**MUST add transaction to state before queuing in agent**:

```rust
// ✅ CORRECT ORDER
let tx = Transaction::new(...);
let tx_id = tx.id().to_string();
state.add_transaction(tx);           // Add to state FIRST
state.get_agent_mut("A").unwrap().queue_outgoing(tx_id);  // Then queue

// ❌ WRONG - will fail
agent.queue_outgoing(tx_id);         // Can't queue before adding to state
state.add_transaction(tx);
```

**Why**: Policy evaluation needs `state.get_transaction(tx_id)` to work

### Test Coverage Checklist

For each policy, test:
- ✅ Submits when conditions met
- ✅ Holds when conditions not met
- ✅ Drops expired transactions
- ✅ Multiple transactions with mixed conditions
- ✅ Edge case: empty queue
- ✅ Edge case: zero balance
- ✅ Edge case: deadline at current tick
- ✅ Edge case: large transactions vs. small balance

## 2.6 Integration Points (Phase 4b)

### Orchestrator Tick Loop

```rust
// 🎯 PHASE 4b TARGET PATTERN (not yet implemented)

pub fn tick(state: &mut SimulationState) -> TickEvents {
    let mut events = TickEvents::new(state.time.tick());

    // 1. Generate arrivals (new transactions)
    let arrivals = generate_arrivals(state);
    events.arrivals = arrivals;

    // 2. Evaluate policies for Queue 1
    for agent_id in state.agents_with_queued_transactions() {
        let agent = state.get_agent(agent_id).unwrap();

        // Get policy (will be configurable per agent in Phase 4b)
        let policy = get_policy_for_agent(agent_id);

        let decisions = policy.evaluate_queue(agent, state, state.time.tick());

        // Execute decisions
        for decision in decisions {
            match decision {
                ReleaseDecision::SubmitFull { tx_id } => {
                    // Move from Queue 1 to Queue 2
                    state.get_agent_mut(agent_id).unwrap().remove_from_queue(&tx_id);
                    submit_to_rtgs(state, &tx_id);
                    events.submitted.push(tx_id);
                }
                ReleaseDecision::Hold { tx_id, reason } => {
                    // Log hold reason for metrics
                    events.held.push((tx_id, reason));
                }
                ReleaseDecision::Drop { tx_id } => {
                    // Remove from queue and mark as dropped
                    state.get_agent_mut(agent_id).unwrap().remove_from_queue(&tx_id);
                    drop_transaction(state, &tx_id);
                    events.dropped.push(tx_id);
                }
                ReleaseDecision::SubmitPartial { .. } => {
                    // Phase 5: Handle splitting
                }
            }
        }
    }

    // 3. Process RTGS queue (Queue 2)
    let rtgs_result = process_rtgs_queue(state);
    events.settlements = rtgs_result.settled;

    // 4. Run LSM pass
    let lsm_result = run_lsm_pass(state, &default_lsm_config());
    events.lsm_offsets = lsm_result.bilateral_count;
    events.lsm_cycles = lsm_result.cycle_count;

    // 5. Update costs
    update_costs(state);

    events
}
```

### Policy Configuration (Phase 4b)

```yaml
# sim_config.yaml
agents:
  - id: "BANK_A"
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: "LiquidityAware"
      parameters:
        target_buffer: 100000
        urgency_threshold: 5

  - id: "BANK_B"
    opening_balance: 800000
    credit_limit: 300000
    policy:
      type: "Deadline"
      parameters:
        urgency_threshold: 10
```

---

# 3. Phase 6: DSL Specification (JSON Decision Trees)

## 3.1 JSON Schema

### Complete Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DecisionTree",
  "description": "LLM-editable decision tree for cash manager policies",
  "type": "object",
  "required": ["version", "tree_id", "root"],
  "properties": {
    "version": {
      "type": "string",
      "enum": ["1.0"],
      "description": "Schema version"
    },
    "tree_id": {
      "type": "string",
      "description": "Unique identifier for this tree"
    },
    "root": {
      "$ref": "#/definitions/TreeNode",
      "description": "Root node of decision tree"
    },
    "parameters": {
      "type": "object",
      "additionalProperties": {"type": "number"},
      "description": "Named parameters (e.g., thresholds, constants)"
    }
  },
  "definitions": {
    "TreeNode": {
      "oneOf": [
        {"$ref": "#/definitions/ConditionNode"},
        {"$ref": "#/definitions/ActionNode"}
      ]
    },
    "ConditionNode": {
      "type": "object",
      "required": ["type", "node_id", "condition", "on_true", "on_false"],
      "properties": {
        "type": {"const": "condition"},
        "node_id": {"type": "string"},
        "description": {"type": "string"},
        "condition": {"$ref": "#/definitions/Expression"},
        "on_true": {"$ref": "#/definitions/TreeNode"},
        "on_false": {"$ref": "#/definitions/TreeNode"}
      }
    },
    "ActionNode": {
      "type": "object",
      "required": ["type", "node_id", "action"],
      "properties": {
        "type": {"const": "action"},
        "node_id": {"type": "string"},
        "action": {
          "enum": ["Release", "ReleaseWithCredit", "PaceAndRelease", "Hold", "Drop"]
        },
        "parameters": {"type": "object"}
      }
    },
    "Expression": {
      "type": "object",
      "required": ["op"],
      "oneOf": [
        {
          "properties": {
            "op": {"enum": ["==", "!=", "<", "<=", ">", ">="]},
            "left": {"$ref": "#/definitions/Value"},
            "right": {"$ref": "#/definitions/Value"}
          },
          "required": ["op", "left", "right"]
        },
        {
          "properties": {
            "op": {"enum": ["and", "or"]},
            "conditions": {
              "type": "array",
              "items": {"$ref": "#/definitions/Expression"},
              "minItems": 2
            }
          },
          "required": ["op", "conditions"]
        },
        {
          "properties": {
            "op": {"const": "not"},
            "condition": {"$ref": "#/definitions/Expression"}
          },
          "required": ["op", "condition"]
        }
      ]
    },
    "Value": {
      "oneOf": [
        {
          "type": "object",
          "required": ["field"],
          "properties": {
            "field": {"type": "string"}
          }
        },
        {
          "type": "object",
          "required": ["param"],
          "properties": {
            "param": {"type": "string"}
          }
        },
        {
          "type": "object",
          "required": ["value"],
          "properties": {
            "value": {"type": ["number", "string", "boolean"]}
          }
        },
        {
          "type": "object",
          "required": ["compute"],
          "properties": {
            "compute": {"$ref": "#/definitions/Computation"}
          }
        }
      ]
    },
    "Computation": {
      "type": "object",
      "required": ["op"],
      "oneOf": [
        {
          "properties": {
            "op": {"enum": ["+", "-", "*", "/"]},
            "left": {"$ref": "#/definitions/Value"},
            "right": {"$ref": "#/definitions/Value"}
          },
          "required": ["left", "right"]
        },
        {
          "properties": {
            "op": {"enum": ["max", "min"]},
            "values": {
              "type": "array",
              "items": {"$ref": "#/definitions/Value"},
              "minItems": 2
            }
          },
          "required": ["values"]
        }
      ]
    }
  }
}
```

## 3.2 Field Enumeration

### Available Fields

All fields accessible to policies in JSON trees:

#### Agent State Fields

```json
{
  "field": "balance"           // i64 - Current central bank balance (cents)
}
{
  "field": "credit"            // i64 - Available credit headroom (cents)
}
{
  "field": "credit_limit"      // i64 - Total credit limit (cents)
}
{
  "field": "effective_liquidity"  // i64 - balance + credit
}
{
  "field": "liquidity_buffer"  // i64 - Target minimum balance (cents)
}
{
  "field": "liquidity_pressure" // f64 - Stress level (0.0-1.0)
}
{
  "field": "outgoing_queue_size"  // usize - Number of queued transactions
}
{
  "field": "outgoing_queue_value" // i64 - Total value queued (cents)
}
```

#### Transaction Fields (Current Transaction Being Evaluated)

```json
{
  "field": "amount"            // i64 - Original transaction amount (cents)
}
{
  "field": "remaining_amount"  // i64 - Unsettled amount (cents)
}
{
  "field": "arrival_tick"      // usize - When transaction arrived
}
{
  "field": "deadline_tick"     // usize - Hard deadline
}
{
  "field": "priority"          // u8 - Priority level (0-10)
}
{
  "field": "is_divisible"      // bool - Can be split?
}
```

#### Derived Time Fields

```json
{
  "field": "tick_current"      // usize - Current simulation tick
}
{
  "field": "ticks_to_deadline" // usize - deadline - current
}
{
  "field": "queue_age"         // usize - current - arrival
}
{
  "field": "ticks_to_eod"      // usize - Ticks to end-of-day
}
```

#### System State Fields

```json
{
  "field": "system_throughput"      // f64 - Settlement rate (0.0-1.0)
}
{
  "field": "queue_pressure"         // f64 - System congestion (0.0-1.0)
}
{
  "field": "total_queue_size"       // usize - All Queue 1s combined
}
{
  "field": "total_queue_value"      // i64 - Total value in all Queue 1s
}
{
  "field": "rtgs_queue_size"        // usize - Queue 2 size
}
```

#### Expected Inflows (Forecasting)

```json
{
  "field": "expected_inflows_total" // i64 - Sum of expected incoming payments
}
{
  "field": "expected_inflows_5"     // i64 - Expected in next 5 ticks
}
{
  "field": "expected_inflows_10"    // i64 - Expected in next 10 ticks
}
```

## 3.3 Rust Interpreter Architecture

### Type Definitions

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use anyhow::{Result, bail};

// ============================================================================
// TREE DEFINITION (DESERIALIZED FROM JSON)
// ============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionTreeDef {
    pub version: String,
    pub tree_id: String,
    pub root: TreeNode,
    #[serde(default)]
    pub parameters: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum TreeNode {
    Condition {
        node_id: String,
        #[serde(default)]
        description: String,
        condition: Expression,
        on_true: Box<TreeNode>,
        on_false: Box<TreeNode>,
    },
    Action {
        node_id: String,
        action: ActionType,
        #[serde(default)]
        parameters: HashMap<String, ValueOrCompute>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "lowercase")]
pub enum Expression {
    #[serde(rename = "==")]
    Equal { left: Value, right: Value },

    #[serde(rename = "!=")]
    NotEqual { left: Value, right: Value },

    #[serde(rename = "<")]
    LessThan { left: Value, right: Value },

    #[serde(rename = "<=")]
    LessOrEqual { left: Value, right: Value },

    #[serde(rename = ">")]
    GreaterThan { left: Value, right: Value },

    #[serde(rename = ">=")]
    GreaterOrEqual { left: Value, right: Value },

    And { conditions: Vec<Expression> },
    Or { conditions: Vec<Expression> },
    Not { condition: Box<Expression> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Value {
    Field { field: String },
    Param { param: String },
    Literal { value: serde_json::Value },
    Compute { compute: Box<Computation> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op")]
pub enum Computation {
    #[serde(rename = "+")]
    Add { left: Value, right: Value },

    #[serde(rename = "-")]
    Subtract { left: Value, right: Value },

    #[serde(rename = "*")]
    Multiply { left: Value, right: Value },

    #[serde(rename = "/")]
    Divide { left: Value, right: Value },

    #[serde(rename = "max")]
    Max { values: Vec<Value> },

    #[serde(rename = "min")]
    Min { values: Vec<Value> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ValueOrCompute {
    Direct { value: serde_json::Value },
    Field { field: String },
    Param { param: String },
    Compute { compute: Computation },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum ActionType {
    Release,
    ReleaseWithCredit,
    PaceAndRelease,
    Hold,
    Drop,
}
```

### Evaluation Context

```rust
pub struct EvalContext {
    pub fields: HashMap<String, f64>,
    pub string_fields: HashMap<String, String>,
    pub parameters: HashMap<String, f64>,
}

impl EvalContext {
    pub fn new(
        tx: &Transaction,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        params: &HashMap<String, f64>,
    ) -> Self {
        let mut fields = HashMap::new();
        let mut string_fields = HashMap::new();

        // Transaction fields
        fields.insert("amount".to_string(), tx.amount() as f64);
        fields.insert("remaining_amount".to_string(), tx.remaining_amount() as f64);
        fields.insert("deadline_tick".to_string(), tx.deadline_tick() as f64);
        fields.insert("arrival_tick".to_string(), tx.arrival_tick() as f64);
        fields.insert("priority".to_string(), tx.priority() as f64);

        // Agent state fields
        fields.insert("balance".to_string(), agent.balance() as f64);
        fields.insert("credit".to_string(), agent.credit() as f64);
        fields.insert("credit_limit".to_string(), agent.credit_limit() as f64);
        fields.insert("liquidity_buffer".to_string(), agent.liquidity_buffer() as f64);
        fields.insert("liquidity_pressure".to_string(), agent.liquidity_pressure());

        // Derived fields
        let ticks_to_deadline = tx.deadline_tick().saturating_sub(tick);
        let queue_age = tick.saturating_sub(tx.arrival_tick());
        fields.insert("tick_current".to_string(), tick as f64);
        fields.insert("ticks_to_deadline".to_string(), ticks_to_deadline as f64);
        fields.insert("queue_age".to_string(), queue_age as f64);

        // System state fields
        fields.insert("total_queue_size".to_string(), state.total_internal_queue_size() as f64);
        fields.insert("total_queue_value".to_string(), state.total_internal_queue_value() as f64);

        Self {
            fields,
            string_fields,
            parameters: params.clone(),
        }
    }
}
```

### Interpreter Implementation

```rust
pub struct TreeInterpreter {
    tree: DecisionTreeDef,
    max_depth: usize,
}

impl TreeInterpreter {
    pub fn new(tree_json: &str) -> Result<Self> {
        let tree: DecisionTreeDef = serde_json::from_str(tree_json)?;
        Self::validate_tree(&tree)?;
        Ok(Self {
            tree,
            max_depth: 100,
        })
    }

    /// Validate tree before allowing execution (CRITICAL FOR SAFETY)
    fn validate_tree(tree: &DecisionTreeDef) -> Result<()> {
        if tree.version != "1.0" {
            bail!("Unsupported tree version: {}", tree.version);
        }

        // Validate all node IDs are unique
        let mut seen_ids = std::collections::HashSet::new();
        Self::validate_node_ids(&tree.root, &mut seen_ids)?;

        // Validate parameter references
        Self::validate_params(&tree.root, &tree.parameters)?;

        Ok(())
    }

    /// Main evaluation entry point
    pub fn evaluate(
        &self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Result<Vec<ReleaseDecision>> {
        let mut decisions = Vec::new();

        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let context = EvalContext::new(tx, agent, state, tick, &self.tree.parameters);
                let decision = self.eval_node(&self.tree.root, &context, 0)?;
                decisions.push(decision);
            }
        }

        Ok(decisions)
    }

    fn eval_node(
        &self,
        node: &TreeNode,
        context: &EvalContext,
        depth: usize,
    ) -> Result<ReleaseDecision> {
        if depth > self.max_depth {
            bail!("Max tree depth exceeded (possible cycle)");
        }

        match node {
            TreeNode::Condition { condition, on_true, on_false, .. } => {
                let result = self.eval_expression(condition, context)?;
                let next_node = if result { on_true } else { on_false };
                self.eval_node(next_node, context, depth + 1)
            }
            TreeNode::Action { action, parameters, .. } => {
                self.build_decision(action, parameters, context)
            }
        }
    }

    fn eval_expression(&self, expr: &Expression, context: &EvalContext) -> Result<bool> {
        match expr {
            Expression::LessThan { left, right } => {
                Ok(self.eval_value(left, context)? < self.eval_value(right, context)?)
            }
            Expression::LessOrEqual { left, right } => {
                Ok(self.eval_value(left, context)? <= self.eval_value(right, context)?)
            }
            Expression::GreaterThan { left, right } => {
                Ok(self.eval_value(left, context)? > self.eval_value(right, context)?)
            }
            Expression::GreaterOrEqual { left, right } => {
                Ok(self.eval_value(left, context)? >= self.eval_value(right, context)?)
            }
            Expression::Equal { left, right } => {
                let l = self.eval_value(left, context)?;
                let r = self.eval_value(right, context)?;
                Ok((l - r).abs() < 1e-9)
            }
            Expression::NotEqual { left, right } => {
                let l = self.eval_value(left, context)?;
                let r = self.eval_value(right, context)?;
                Ok((l - r).abs() >= 1e-9)
            }
            Expression::And { conditions } => {
                for cond in conditions {
                    if !self.eval_expression(cond, context)? {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            Expression::Or { conditions } => {
                for cond in conditions {
                    if self.eval_expression(cond, context)? {
                        return Ok(true);
                    }
                }
                Ok(false)
            }
            Expression::Not { condition } => {
                Ok(!self.eval_expression(condition, context)?)
            }
        }
    }

    fn eval_value(&self, value: &Value, context: &EvalContext) -> Result<f64> {
        match value {
            Value::Field { field } => {
                context.fields.get(field)
                    .copied()
                    .ok_or_else(|| anyhow::anyhow!("Field not found: {}", field))
            }
            Value::Param { param } => {
                context.parameters.get(param)
                    .copied()
                    .ok_or_else(|| anyhow::anyhow!("Parameter not found: {}", param))
            }
            Value::Literal { value } => {
                value.as_f64()
                    .ok_or_else(|| anyhow::anyhow!("Unsupported literal type"))
            }
            Value::Compute { compute } => {
                self.eval_computation(compute, context)
            }
        }
    }

    fn eval_computation(&self, comp: &Computation, context: &EvalContext) -> Result<f64> {
        match comp {
            Computation::Add { left, right } => {
                Ok(self.eval_value(left, context)? + self.eval_value(right, context)?)
            }
            Computation::Subtract { left, right } => {
                Ok(self.eval_value(left, context)? - self.eval_value(right, context)?)
            }
            Computation::Multiply { left, right } => {
                Ok(self.eval_value(left, context)? * self.eval_value(right, context)?)
            }
            Computation::Divide { left, right } => {
                let r = self.eval_value(right, context)?;
                if r.abs() < 1e-9 {
                    bail!("Division by zero");
                }
                Ok(self.eval_value(left, context)? / r)
            }
            Computation::Max { values } => {
                values.iter()
                    .map(|v| self.eval_value(v, context))
                    .collect::<Result<Vec<_>>>()?
                    .into_iter()
                    .fold(f64::NEG_INFINITY, f64::max)
                    .pipe(Ok)
            }
            Computation::Min { values } => {
                values.iter()
                    .map(|v| self.eval_value(v, context))
                    .collect::<Result<Vec<_>>>()?
                    .into_iter()
                    .fold(f64::INFINITY, f64::min)
                    .pipe(Ok)
            }
        }
    }

    fn build_decision(
        &self,
        action_type: &ActionType,
        _parameters: &HashMap<String, ValueOrCompute>,
        _context: &EvalContext,
    ) -> Result<ReleaseDecision> {
        // Extract tx_id from context (simplified)
        let tx_id = "tx_id".to_string(); // Would come from context

        Ok(match action_type {
            ActionType::Release => ReleaseDecision::SubmitFull { tx_id },
            ActionType::Hold => ReleaseDecision::Hold {
                tx_id,
                reason: HoldReason::Custom("policy decision".to_string()),
            },
            ActionType::Drop => ReleaseDecision::Drop { tx_id },
            ActionType::ReleaseWithCredit => ReleaseDecision::SubmitFull { tx_id },
            ActionType::PaceAndRelease => ReleaseDecision::SubmitFull { tx_id },
        })
    }

    /// Allow hot-reload of tree
    pub fn reload(&mut self, tree_json: &str) -> Result<()> {
        let new_tree: DecisionTreeDef = serde_json::from_str(tree_json)?;
        Self::validate_tree(&new_tree)?;
        self.tree = new_tree;
        Ok(())
    }
}

// Helper trait for functional style
trait Pipe: Sized {
    fn pipe<F, R>(self, f: F) -> R
    where
        F: FnOnce(Self) -> R,
    {
        f(self)
    }
}

impl<T> Pipe for T {}
```

## 3.4 Safety Validation

### Validation Pipeline

```rust
impl TreeInterpreter {
    pub fn validate_tree(tree: &DecisionTreeDef) -> Result<()> {
        // 1. Schema version check
        if tree.version != "1.0" {
            bail!("Unsupported tree version: {}", tree.version);
        }

        // 2. Unique node IDs
        let mut seen_ids = std::collections::HashSet::new();
        Self::validate_node_ids(&tree.root, &mut seen_ids)?;

        // 3. Parameter references exist
        Self::validate_params(&tree.root, &tree.parameters)?;

        // 4. Maximum depth limit
        let max_depth = Self::compute_max_depth(&tree.root);
        if max_depth > 100 {
            bail!("Tree too deep: {} (max 100)", max_depth);
        }

        // 5. No division by literal zero
        Self::check_division_by_zero(&tree.root)?;

        // 6. Field references are valid
        Self::validate_field_references(&tree.root)?;

        Ok(())
    }

    fn validate_node_ids(
        node: &TreeNode,
        seen: &mut std::collections::HashSet<String>,
    ) -> Result<()> {
        let id = match node {
            TreeNode::Condition { node_id, on_true, on_false, .. } => {
                Self::validate_node_ids(on_true, seen)?;
                Self::validate_node_ids(on_false, seen)?;
                node_id
            }
            TreeNode::Action { node_id, .. } => node_id,
        };

        if !seen.insert(id.clone()) {
            bail!("Duplicate node ID: {}", id);
        }

        Ok(())
    }

    fn compute_max_depth(node: &TreeNode) -> usize {
        match node {
            TreeNode::Condition { on_true, on_false, .. } => {
                let left_depth = Self::compute_max_depth(on_true);
                let right_depth = Self::compute_max_depth(on_false);
                1 + left_depth.max(right_depth)
            }
            TreeNode::Action { .. } => 1,
        }
    }

    fn check_division_by_zero(node: &TreeNode) -> Result<()> {
        match node {
            TreeNode::Condition { condition, on_true, on_false, .. } => {
                Self::check_expression_division(condition)?;
                Self::check_division_by_zero(on_true)?;
                Self::check_division_by_zero(on_false)?;
            }
            TreeNode::Action { .. } => {}
        }
        Ok(())
    }

    fn check_expression_division(expr: &Expression) -> Result<()> {
        // Check all Value::Compute for division by literal zero
        // Implementation omitted for brevity
        Ok(())
    }

    fn validate_field_references(node: &TreeNode) -> Result<()> {
        let valid_fields = vec![
            "balance", "credit", "amount", "ticks_to_deadline",
            "queue_age", "liquidity_pressure", // ... full list
        ];

        // Check all field references are in valid_fields
        // Implementation omitted for brevity
        Ok(())
    }
}
```

---

# 4. LLM Integration & Validation

## 4.1 LLM Manager Service Architecture

### Service Overview

```
┌─────────────────────────────────────────────────┐
│  LLM Manager Service (Async Python)             │
│                                                  │
│  ┌──────────────┐         ┌──────────────┐     │
│  │ Policy       │         │ Shadow       │     │
│  │ Mutator      │────────>│ Validator    │     │
│  └──────────────┘         └──────────────┘     │
│         │                         │             │
│         │                         │             │
│         ▼                         ▼             │
│  ┌──────────────┐         ┌──────────────┐     │
│  │ Git Version  │         │ Monte Carlo  │     │
│  │ Control      │         │ Sampler      │     │
│  └──────────────┘         └──────────────┘     │
└─────────────────────────────────────────────────┘
         │                         │
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────┐
│  Rust Simulation Engine                         │
│  - TreeInterpreter                               │
│  - Episode Replay                                │
│  - Policy Execution                              │
└─────────────────────────────────────────────────┘
```

### Policy Mutation Workflow

```python
class LLMManager:
    def __init__(self, llm_client, git_repo, validator):
        self.llm = llm_client
        self.repo = git_repo
        self.validator = validator

    async def improve_policy(
        self,
        current_policy_path: str,
        recent_episodes: List[Episode],
        performance_target: dict,
    ) -> PolicyUpdateResult:
        """
        Main workflow for LLM-driven policy improvement.

        1. Analyze recent performance
        2. Prompt LLM for policy modification
        3. Validate new policy (shadow replay)
        4. Git commit if approved
        5. Deploy or rollback
        """
        # 1. Analyze performance
        perf = analyze_performance(recent_episodes)

        # 2. Generate improvement prompt
        prompt = self.generate_improvement_prompt(
            current_policy=load_policy(current_policy_path),
            performance=perf,
            target=performance_target,
        )

        # 3. Get LLM response
        llm_response = await self.llm.generate(prompt)
        new_policy_json = extract_json(llm_response)

        # 4. Validate new policy
        validation_result = await self.validator.validate(
            old_policy=load_policy(current_policy_path),
            new_policy=new_policy_json,
            episode_history=recent_episodes,
            n_samples=100,
        )

        # 5. Check guardbands
        if validation_result.mean_cost_delta > 0:
            return PolicyUpdateResult(
                status="rejected",
                reason="New policy performs worse on average",
                cost_delta=validation_result.mean_cost_delta,
            )

        if validation_result.pareto_dominated:
            return PolicyUpdateResult(
                status="rejected",
                reason="New policy strictly worse on all samples",
            )

        # 6. Git commit
        commit_hash = self.repo.commit_policy(
            policy=new_policy_json,
            path=current_policy_path,
            message=f"LLM improvement: {validation_result.summary()}",
        )

        # 7. Deploy
        return PolicyUpdateResult(
            status="deployed",
            commit=commit_hash,
            improvement=abs(validation_result.mean_cost_delta),
        )
```

## 4.2 LLM Prompting Patterns

### Policy Mutation Prompt

```python
def generate_improvement_prompt(
    current_policy: DecisionTree,
    performance: PerformanceMetrics,
    target: dict,
) -> str:
    return f"""
You are an AI assistant optimizing cash manager policies for an RTGS payment system.

# Current Policy

```json
{json.dumps(current_policy, indent=2)}
```

# Performance Metrics (Recent 100 Episodes)

- **Mean Total Cost**: ${performance.mean_cost:.2f}
  - Overdraft cost: ${performance.overdraft_cost:.2f}
  - Delay penalty: ${performance.delay_penalty:.2f}
  - EoD penalty: ${performance.eod_penalty:.2f}

- **Settlement Rate**: {performance.settlement_rate:.1%}
- **Credit Usage (Peak)**: {performance.peak_credit_usage:.1%}
- **Queue Pressure (Avg)**: {performance.avg_queue_pressure:.2f}

# Target Performance

- Reduce overdraft cost by {target['overdraft_reduction']:.1%}
- Maintain settlement rate > {target['min_settlement_rate']:.1%}
- Keep peak credit usage < {target['max_credit_usage']:.1%}

# Task

Modify the decision tree to achieve the performance target. Focus on:

1. **If overdraft costs are high**: Increase liquidity buffering, wait for inflows
2. **If deadline penalties are high**: Reduce urgency threshold, submit earlier
3. **If queue pressure is high**: Prioritize urgent transactions, drop low-priority

Output ONLY valid JSON matching the schema. Do NOT include explanation.

# Modified Policy
"""
```

### Scenario-Specific Prompts

```python
# Liquidity Crisis Scenario
def liquidity_crisis_prompt(current_policy):
    return f"""
SCENARIO: Banks are experiencing liquidity shortage (50% reduction in opening balances).

Modify the policy to prioritize liquidity preservation:
- Increase weight on checking expected_inflows before releasing
- Only use credit for truly critical deadlines (≤ 3 ticks instead of 5)
- Add condition to check if expected_inflows > amount * 1.2 (was 1.0)

Current policy:
```json
{json.dumps(current_policy, indent=2)}
```

Output modified policy JSON:
"""

# End-of-Day Rush Scenario
def eod_rush_prompt(current_policy):
    return f"""
SCENARIO: High queue congestion in last 10 ticks of day.

Modify the policy to handle EoD rush:
- Detect EoD window (ticks_to_eod <= 10)
- Release everything in EoD window (backstop penalty >> any other cost)
- Use max available credit if needed
- Drop transactions that can't be settled even with full credit

Current policy:
```json
{json.dumps(current_policy, indent=2)}
```

Output modified policy JSON:
"""
```

## 4.3 Shadow Replay Validation

### Shadow Replay Algorithm

```python
class ShadowValidator:
    def __init__(self, orchestrator_factory):
        self.orchestrator_factory = orchestrator_factory

    async def validate(
        self,
        old_policy: DecisionTree,
        new_policy: DecisionTree,
        episode_history: List[Episode],
        n_samples: int = 100,
    ) -> ValidationResult:
        """
        Replay historical episodes with new policy.

        Monte Carlo approach:
        - Sample opponent behaviors from historical data
        - Run replay with new policy vs. sampled opponents
        - Compare cost distributions
        """
        cost_deltas = []

        for episode in sample(episode_history, n_samples):
            # Replay with old policy
            old_cost = await self.replay_episode(
                episode=episode,
                agent_policy=old_policy,
                opponent_policies=sample_opponent_behaviors(episode),
            )

            # Replay with new policy
            new_cost = await self.replay_episode(
                episode=episode,
                agent_policy=new_policy,
                opponent_policies=sample_opponent_behaviors(episode),
            )

            cost_deltas.append(new_cost - old_cost)

        return ValidationResult(
            mean_cost_delta=np.mean(cost_deltas),
            std_cost_delta=np.std(cost_deltas),
            pareto_dominated=all(d >= 0 for d in cost_deltas),
            cost_deltas=cost_deltas,
        )

    async def replay_episode(
        self,
        episode: Episode,
        agent_policy: DecisionTree,
        opponent_policies: Dict[str, DecisionTree],
    ) -> float:
        """
        Replay single episode with specified policies.

        Returns: Total cost for agent using agent_policy
        """
        # Create orchestrator with same seed as original episode
        orch = self.orchestrator_factory.create(seed=episode.seed)

        # Install policies
        orch.set_policy("BANK_A", TreeInterpreter.new(agent_policy))
        for agent_id, policy in opponent_policies.items():
            orch.set_policy(agent_id, TreeInterpreter.new(policy))

        # Replay ticks
        total_cost = 0.0
        for tick in range(episode.num_ticks):
            result = orch.tick()
            total_cost += result.costs.get("BANK_A", 0.0)

        return total_cost
```

### Monte Carlo Opponent Sampling

```python
def sample_opponent_behaviors(episode: Episode) -> Dict[str, DecisionTree]:
    """
    Sample plausible opponent policies from historical data.

    Approach:
    1. Analyze opponent decision patterns in episode
    2. Sample from distribution of historical opponent policies
    3. Add noise to avoid overfitting
    """
    opponents = {}

    for agent_id in episode.opponent_ids:
        # Get historical policy distribution for this agent
        historical_policies = get_agent_policy_history(agent_id)

        # Sample policy (weighted by recency and success)
        sampled_policy = sample_weighted(historical_policies)

        # Add noise (mutate parameters slightly)
        noisy_policy = add_policy_noise(sampled_policy, noise_level=0.1)

        opponents[agent_id] = noisy_policy

    return opponents
```

## 4.4 Guardband Checking

### Live Deployment Safeguards

```python
class GuardbandChecker:
    def __init__(self, baseline_metrics: dict, thresholds: dict):
        self.baseline = baseline_metrics
        self.thresholds = thresholds
        self.alert_triggered = False

    def check_deployment(self, current_metrics: dict) -> GuardbandResult:
        """
        Check if new policy is performing within acceptable bounds.

        Guardbands (example):
        - Total cost < baseline * 1.2 (20% degradation threshold)
        - Settlement rate > baseline * 0.95 (5% degradation threshold)
        - Credit usage < baseline * 1.5 (50% increase threshold)
        """
        violations = []

        # Cost guardband
        if current_metrics['total_cost'] > self.baseline['total_cost'] * 1.2:
            violations.append(GuardbandViolation(
                metric="total_cost",
                baseline=self.baseline['total_cost'],
                current=current_metrics['total_cost'],
                threshold_factor=1.2,
            ))

        # Settlement rate guardband
        if current_metrics['settlement_rate'] < self.baseline['settlement_rate'] * 0.95:
            violations.append(GuardbandViolation(
                metric="settlement_rate",
                baseline=self.baseline['settlement_rate'],
                current=current_metrics['settlement_rate'],
                threshold_factor=0.95,
            ))

        # Credit usage guardband
        if current_metrics['peak_credit'] > self.baseline['peak_credit'] * 1.5:
            violations.append(GuardbandViolation(
                metric="peak_credit",
                baseline=self.baseline['peak_credit'],
                current=current_metrics['peak_credit'],
                threshold_factor=1.5,
            ))

        if violations:
            self.alert_triggered = True
            return GuardbandResult(
                status="violated",
                violations=violations,
                recommendation="ROLLBACK",
            )

        return GuardbandResult(
            status="ok",
            violations=[],
        )
```

### Automatic Rollback

```python
class PolicyDeploymentManager:
    def __init__(self, repo, guardband_checker):
        self.repo = repo
        self.guardband = guardband_checker
        self.deployment_history = []

    async def deploy_with_monitoring(
        self,
        new_policy: DecisionTree,
        monitoring_duration: int = 1000,  # ticks
    ) -> DeploymentResult:
        """
        Deploy policy with automatic rollback if guardbands violated.

        1. Save current policy as backup
        2. Deploy new policy
        3. Monitor performance for duration
        4. Check guardbands every 100 ticks
        5. Rollback if violations detected
        """
        # Backup current policy
        backup_commit = self.repo.get_current_commit()

        # Deploy new policy
        self.repo.commit_policy(new_policy, message="Deployment: new policy")

        # Monitor
        for tick in range(0, monitoring_duration, 100):
            await asyncio.sleep(0.1)  # Simulate time passing

            current_metrics = collect_metrics(window=100)
            guardband_result = self.guardband.check_deployment(current_metrics)

            if guardband_result.status == "violated":
                # ROLLBACK
                self.repo.checkout(backup_commit)
                return DeploymentResult(
                    status="rolled_back",
                    reason=f"Guardband violation: {guardband_result.violations}",
                    duration_before_rollback=tick,
                )

        # Success
        return DeploymentResult(
            status="deployed",
            commit=self.repo.get_current_commit(),
        )
```

---

# 5. Migration Path

## 5.1 Porting Rust Policies to JSON

### Example: LiquidityAwarePolicy → JSON

**Rust Implementation**:
```rust
impl CashManagerPolicy for LiquidityAwarePolicy {
    fn evaluate_queue(&mut self, agent: &Agent, state: &SimulationState, tick: usize)
        -> Vec<ReleaseDecision>
    {
        for tx_id in agent.outgoing_queue() {
            let tx = state.get_transaction(tx_id).unwrap();
            let amount = tx.remaining_amount();
            let deadline = tx.deadline_tick();
            let ticks_remaining = deadline - tick;
            let is_urgent = ticks_remaining <= self.urgency_threshold;

            if deadline <= tick {
                // Drop if expired
                decisions.push(ReleaseDecision::Drop { tx_id: tx_id.clone() });
            } else if is_urgent && agent.can_pay(amount) {
                // Urgent: submit
                decisions.push(ReleaseDecision::SubmitFull { tx_id: tx_id.clone() });
            } else if agent.balance() - amount >= self.target_buffer {
                // Safe: maintains buffer
                decisions.push(ReleaseDecision::SubmitFull { tx_id: tx_id.clone() });
            } else {
                // Hold
                decisions.push(ReleaseDecision::Hold {
                    tx_id: tx_id.clone(),
                    reason: HoldReason::InsufficientLiquidity,
                });
            }
        }
        decisions
    }
}
```

**JSON Tree Equivalent**:
```json
{
  "version": "1.0",
  "tree_id": "liquidity_aware_policy",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "description": "Check if expired",
    "condition": {
      "op": "<=",
      "left": {"field": "deadline_tick"},
      "right": {"field": "tick_current"}
    },
    "on_true": {
      "node_id": "A_DROP",
      "type": "action",
      "action": "Drop",
      "parameters": {}
    },
    "on_false": {
      "node_id": "N2",
      "type": "condition",
      "description": "Check if urgent",
      "condition": {
        "op": "<=",
        "left": {"field": "ticks_to_deadline"},
        "right": {"param": "urgency_threshold"}
      },
      "on_true": {
        "node_id": "N3",
        "type": "condition",
        "description": "Check if can pay",
        "condition": {
          "op": ">=",
          "left": {
            "compute": {
              "op": "+",
              "left": {"field": "balance"},
              "right": {"field": "credit"}
            }
          },
          "right": {"field": "amount"}
        },
        "on_true": {
          "node_id": "A_SUBMIT_URGENT",
          "type": "action",
          "action": "Release",
          "parameters": {}
        },
        "on_false": {
          "node_id": "A_HOLD_URGENT",
          "type": "action",
          "action": "Hold",
          "parameters": {}
        }
      },
      "on_false": {
        "node_id": "N4",
        "type": "condition",
        "description": "Check if maintains buffer",
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
          "node_id": "A_SUBMIT_SAFE",
          "type": "action",
          "action": "Release",
          "parameters": {}
        },
        "on_false": {
          "node_id": "A_HOLD_LIQUIDITY",
          "type": "action",
          "action": "Hold",
          "parameters": {}
        }
      }
    }
  },
  "parameters": {
    "target_buffer": 100000,
    "urgency_threshold": 5
  }
}
```

### Porting Checklist

- [ ] Identify all conditional branches in Rust code
- [ ] Map each Rust condition to JSON `Expression`
- [ ] Map each Rust action to JSON `ActionNode`
- [ ] Extract parameters (thresholds, constants) to `parameters` object
- [ ] Validate JSON against schema
- [ ] Test equivalence: Rust policy vs. JSON policy on same inputs
- [ ] Document any semantic differences

## 5.2 Dual Execution Mode

### PolicyExecutor Enum

```rust
pub enum PolicyExecutor {
    /// Hand-coded Rust policy (fast, compile-time checked)
    Trait(Box<dyn CashManagerPolicy>),

    /// JSON decision tree (LLM-editable, hot-reloadable)
    Tree(TreeInterpreter),
}

impl PolicyExecutor {
    /// Evaluate queue using whichever execution mode is active
    pub fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        match self {
            PolicyExecutor::Trait(policy) => {
                policy.evaluate_queue(agent, state, tick)
            }
            PolicyExecutor::Tree(interpreter) => {
                interpreter.evaluate(agent, state, tick)
                    .unwrap_or_else(|e| {
                        eprintln!("Tree evaluation error: {}", e);
                        vec![]
                    })
            }
        }
    }

    /// Hot-reload tree (only works for Tree variant)
    pub fn reload_tree(&mut self, tree_json: &str) -> Result<()> {
        match self {
            PolicyExecutor::Tree(interpreter) => {
                interpreter.reload(tree_json)
            }
            PolicyExecutor::Trait(_) => {
                Err(anyhow::anyhow!("Cannot reload Rust trait policy"))
            }
        }
    }
}
```

### Configuration

```yaml
# sim_config.yaml
agents:
  - id: "BANK_A"
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: "Trait"
      class: "LiquidityAware"
      parameters:
        target_buffer: 100000
        urgency_threshold: 5

  - id: "BANK_B"
    opening_balance: 800000
    credit_limit: 300000
    policy:
      type: "Tree"
      path: "policies/bank_b_policy.json"
```

### Loading Logic

```rust
pub fn load_policy_from_config(config: &PolicyConfig) -> Result<PolicyExecutor> {
    match config.policy_type.as_str() {
        "Trait" => {
            let policy: Box<dyn CashManagerPolicy> = match config.class.as_str() {
                "FIFO" => Box::new(FifoPolicy::default()),
                "Deadline" => Box::new(DeadlinePolicy::new(
                    config.parameters.get("urgency_threshold").copied().unwrap_or(5.0) as usize
                )),
                "LiquidityAware" => Box::new(LiquidityAwarePolicy::new(
                    config.parameters.get("target_buffer").copied().unwrap_or(0.0) as i64
                )),
                _ => bail!("Unknown policy class: {}", config.class),
            };
            Ok(PolicyExecutor::Trait(policy))
        }
        "Tree" => {
            let tree_json = std::fs::read_to_string(&config.path)?;
            let interpreter = TreeInterpreter::new(&tree_json)?;
            Ok(PolicyExecutor::Tree(interpreter))
        }
        _ => bail!("Unknown policy type: {}", config.policy_type),
    }
}
```

---

# 6. Examples & Reference

## 6.1 Complete JSON Tree Examples

### Example 1: Deadline-Only Policy

```json
{
  "version": "1.0",
  "tree_id": "deadline_simple",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "description": "Check if urgent (deadline within 5 ticks)",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "node_id": "A1",
      "type": "action",
      "action": "Release",
      "parameters": {}
    },
    "on_false": {
      "node_id": "A2",
      "type": "action",
      "action": "Hold",
      "parameters": {}
    }
  },
  "parameters": {
    "urgency_threshold": 5.0
  }
}
```

### Example 2: Cost-Optimizing Policy

```json
{
  "version": "1.0",
  "tree_id": "cost_optimizer",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "description": "Calculate if credit cost < delay penalty",
    "condition": {
      "op": "<",
      "left": {
        "compute": {
          "op": "*",
          "left": {
            "compute": {
              "op": "-",
              "left": {"field": "amount"},
              "right": {"field": "balance"}
            }
          },
          "right": {"param": "credit_rate_per_tick"}
        }
      },
      "right": {"param": "delay_penalty_per_tick"}
    },
    "on_true": {
      "node_id": "A_USE_CREDIT",
      "type": "action",
      "action": "ReleaseWithCredit",
      "parameters": {}
    },
    "on_false": {
      "node_id": "A_WAIT",
      "type": "action",
      "action": "Hold",
      "parameters": {}
    }
  },
  "parameters": {
    "credit_rate_per_tick": 0.0001,
    "delay_penalty_per_tick": 0.5
  }
}
```

### Example 3: Multi-Factor Decision Tree

```json
{
  "version": "1.0",
  "tree_id": "multi_factor",
  "root": {
    "node_id": "N1",
    "type": "condition",
    "description": "Check if expired",
    "condition": {
      "op": "<=",
      "left": {"field": "deadline_tick"},
      "right": {"field": "tick_current"}
    },
    "on_true": {
      "node_id": "A_DROP",
      "type": "action",
      "action": "Drop",
      "parameters": {}
    },
    "on_false": {
      "node_id": "N2",
      "type": "condition",
      "description": "Check if critical deadline (≤3 ticks)",
      "condition": {
        "op": "<=",
        "left": {"field": "ticks_to_deadline"},
        "right": {"value": 3}
      },
      "on_true": {
        "node_id": "A_SUBMIT_CRITICAL",
        "type": "action",
        "action": "Release",
        "parameters": {}
      },
      "on_false": {
        "node_id": "N3",
        "type": "condition",
        "description": "Check if sufficient balance without credit",
        "condition": {
          "op": ">=",
          "left": {"field": "balance"},
          "right": {"field": "amount"}
        },
        "on_true": {
          "node_id": "N4",
          "type": "condition",
          "description": "Check queue age (hold if just arrived)",
          "condition": {
            "op": ">",
            "left": {"field": "queue_age"},
            "right": {"param": "min_hold_ticks"}
          },
          "on_true": {
            "node_id": "A_SUBMIT_AGED",
            "type": "action",
            "action": "Release",
            "parameters": {}
          },
          "on_false": {
            "node_id": "A_HOLD_NEW",
            "type": "action",
            "action": "Hold",
            "parameters": {}
          }
        },
        "on_false": {
          "node_id": "N5",
          "type": "condition",
          "description": "Check if expected inflows cover amount",
          "condition": {
            "op": ">",
            "left": {"field": "expected_inflows_total"},
            "right": {
              "compute": {
                "op": "*",
                "left": {"field": "amount"},
                "right": {"param": "inflow_multiplier"}
              }
            }
          },
          "on_true": {
            "node_id": "A_WAIT_INFLOWS",
            "type": "action",
            "action": "Hold",
            "parameters": {}
          },
          "on_false": {
            "node_id": "N6",
            "type": "condition",
            "description": "Check if EoD window (emergency backstop)",
            "condition": {
              "op": "<=",
              "left": {"field": "ticks_to_eod"},
              "right": {"param": "eod_window"}
            },
            "on_true": {
              "node_id": "A_SUBMIT_EOD",
              "type": "action",
              "action": "Release",
              "parameters": {}
            },
            "on_false": {
              "node_id": "A_HOLD_DEFAULT",
              "type": "action",
              "action": "Hold",
              "parameters": {}
            }
          }
        }
      }
    }
  },
  "parameters": {
    "min_hold_ticks": 3.0,
    "inflow_multiplier": 1.2,
    "eod_window": 10.0
  }
}
```

## 6.2 Common Patterns Library

### Pattern: Urgency Override

```json
{
  "node_id": "urgency_check",
  "type": "condition",
  "description": "Override all other logic if urgent",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"param": "urgency_threshold"}
  },
  "on_true": {
    "type": "action",
    "action": "Release"
  },
  "on_false": {
    "comment": "Continue with normal logic"
  }
}
```

### Pattern: Liquidity Buffer Check

```json
{
  "node_id": "buffer_check",
  "type": "condition",
  "description": "Check if sending maintains liquidity buffer",
  "condition": {
    "op": ">=",
    "left": {
      "compute": {
        "op": "-",
        "left": {"field": "balance"},
        "right": {"field": "amount"}
      }
    },
    "right": {"param": "liquidity_buffer"}
  },
  "on_true": {
    "type": "action",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "action": "Hold"
  }
}
```

### Pattern: Expected Inflows Wait

```json
{
  "node_id": "inflow_wait",
  "type": "condition",
  "description": "Hold if expected inflows will cover shortfall",
  "condition": {
    "op": "and",
    "conditions": [
      {
        "op": "<",
        "left": {"field": "balance"},
        "right": {"field": "amount"}
      },
      {
        "op": ">",
        "left": {"field": "expected_inflows_total"},
        "right": {
          "compute": {
            "op": "-",
            "left": {"field": "amount"},
            "right": {"field": "balance"}
          }
        }
      }
    ]
  },
  "on_true": {
    "type": "action",
    "action": "Hold"
  },
  "on_false": {
    "type": "action",
    "action": "Release"
  }
}
```

### Pattern: EoD Backstop

```json
{
  "node_id": "eod_backstop",
  "type": "condition",
  "description": "Emergency: release everything in EoD window",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_eod"},
    "right": {"param": "eod_window"}
  },
  "on_true": {
    "type": "action",
    "action": "Release",
    "parameters": {
      "comment": "EoD penalty >> any other cost"
    }
  },
  "on_false": {
    "comment": "Normal logic"
  }
}
```

## 6.3 Anti-Patterns

### Anti-Pattern: Division by Zero

```json
{
  "comment": "❌ BAD: Can divide by zero",
  "condition": {
    "op": "/",
    "left": {"field": "amount"},
    "right": {"field": "balance"}  // balance could be 0!
  }
}

{
  "comment": "✅ GOOD: Add safety check",
  "condition": {
    "op": "and",
    "conditions": [
      {
        "op": ">",
        "left": {"field": "balance"},
        "right": {"value": 0}
      },
      {
        "op": "<",
        "left": {
          "compute": {
            "op": "/",
            "left": {"field": "amount"},
            "right": {"field": "balance"}
          }
        },
        "right": {"param": "threshold"}
      }
    ]
  }
}
```

### Anti-Pattern: Infinite Loops

```json
{
  "comment": "❌ BAD: Circular reference (N1 → N2 → N1)",
  "node_id": "N1",
  "type": "condition",
  "on_true": {"node_id": "N2", ...},
  "on_false": {"node_id": "N1", ...}  // Points back to self!
}
```

**Prevention**: Validator checks for cycles, max depth limit

### Anti-Pattern: Unreachable Actions

```json
{
  "comment": "❌ BAD: Second condition unreachable",
  "node_id": "N1",
  "type": "condition",
  "condition": {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
  "on_true": {
    "type": "condition",
    "condition": {"op": "<=", "left": {"field": "balance"}, "right": {"value": 0}},
    "on_true": {"type": "action", "action": "Release"}  // Never reached!
  }
}
```

**Detection**: Static analysis can identify contradictory conditions

---

## 6.4 Performance Considerations

### Tree Depth vs. Evaluation Time

- **Shallow Trees** (depth ≤ 5): ~1-5 μs per evaluation
- **Medium Trees** (depth 6-10): ~5-20 μs per evaluation
- **Deep Trees** (depth 11-20): ~20-100 μs per evaluation
- **Maximum Allowed** (depth 100): Safety limit, not recommended

**Recommendation**: Keep decision trees under depth 10 for best performance

### Computation Complexity

```json
{
  "comment": "Simple field comparison: ~1 μs",
  "condition": {
    "op": ">",
    "left": {"field": "balance"},
    "right": {"field": "amount"}
  }
}

{
  "comment": "Computation: ~2-3 μs",
  "condition": {
    "op": ">",
    "left": {
      "compute": {
        "op": "+",
        "left": {"field": "balance"},
        "right": {"field": "credit"}
      }
    },
    "right": {"field": "amount"}
  }
}

{
  "comment": "Nested computation: ~5-10 μs",
  "condition": {
    "op": ">",
    "left": {
      "compute": {
        "op": "/",
        "left": {
          "compute": {
            "op": "-",
            "left": {"field": "balance"},
            "right": {"field": "amount"}
          }
        },
        "right": {"field": "credit_limit"}
      }
    },
    "right": {"value": 0.5}
  }
}
```

**Recommendation**: Minimize nested computations, precompute complex values in evaluation context

### Caching Strategies (Phase 6 Optimization)

```rust
pub struct CachedTreeInterpreter {
    tree: TreeInterpreter,
    expression_cache: HashMap<String, bool>,  // Memoize expensive expressions
}

impl CachedTreeInterpreter {
    pub fn evaluate_with_cache(&mut self, context: &EvalContext) -> Result<ReleaseDecision> {
        // Check if we've evaluated this exact context before
        let cache_key = self.compute_cache_key(context);

        if let Some(cached_result) = self.expression_cache.get(&cache_key) {
            return self.build_decision_from_cache(cached_result);
        }

        // Evaluate fresh, cache result
        let result = self.tree.evaluate(context)?;
        self.expression_cache.insert(cache_key, result);
        Ok(result)
    }
}
```

---

## Appendix: JSON Schema (Complete)

See Section 3.1 for complete JSON schema definition.

---

## Glossary

- **Queue 1**: Internal bank queue where cash managers make strategic decisions about when to submit transactions
- **Queue 2**: Central RTGS queue where transactions await sufficient liquidity for settlement
- **DSL**: Domain-Specific Language - JSON decision tree format for policies
- **LLM Manager**: Service that uses LLMs to improve policies by editing JSON trees
- **Shadow Replay**: Validation technique that replays historical episodes with new policy
- **Monte Carlo Sampling**: Statistical technique to sample opponent behaviors
- **Guardband**: Safety threshold to detect performance degradation
- **Hot-Reload**: Updating policy without restarting simulation
- **Tree Interpreter**: Rust module that executes JSON decision trees

---

*This document specifies the complete policy DSL design for Phase 6 implementation. Phase 4a (Rust traits) is already complete and operational.*
