# Plan: Realistic Dropped Transaction Handling

**Status**: Ready for Implementation
**Created**: 2025-11-04
**Priority**: High (Realism Impact)

## Problem Statement

Currently, when a transaction passes its deadline, it is marked as `Dropped` and never processed again. This is unrealistic:

- In real payment systems, transactions cannot simply be "dropped"
- Banks must eventually settle all obligations
- Delayed transactions incur escalating penalties
- Cash managers need ability to prioritize overdue transactions urgently

## Goals

1. **Persistence**: Dropped transactions remain in queue until successfully settled
2. **Escalating Costs**: Overdue transactions incur:
   - One-time hefty penalty when deadline is first missed
   - Multiplied delay cost per tick while overdue (e.g., 5x normal rate)
3. **Re-prioritization**: Agents can adjust priority of overdue transactions to expedite settlement
4. **Realistic Behavior**: Mirrors real-world payment system behavior where all obligations must eventually clear

## Design Decisions

### 1. Terminology Change

**Old**: `TransactionStatus::Dropped { tick }`
**New**: `TransactionStatus::Overdue { missed_deadline_tick }`

**Rationale**: "Dropped" implies abandonment. "Overdue" is the industry-standard banking term and conveys that the transaction is late but must still be processed.

### 2. Status Lifecycle

```
Pending → (settlement attempt) → Settled
   ↓
(deadline passes - SYSTEM ENFORCED)
   ↓
Overdue → (settlement attempt) → Settled
```

**Critical**: Deadline passing is **system-enforced**, not policy-driven:
- Queue 2 (RTGS) has no policy - system must handle transitions
- Deadline is a system invariant, not policy decision
- Both Queue 1 and Queue 2 transactions become overdue automatically

### 3. Cost Model Changes

#### Current Costs (Per Tick)
- **Delay cost**: `delay_cost_per_tick_per_cent × remaining_amount`
- Applied to all pending transactions in Queue 1

#### New Costs (Per Tick)
- **Delay cost (Pending)**: `delay_cost_per_tick_per_cent × remaining_amount`
- **Delay cost (Overdue)**: `overdue_multiplier × delay_cost_per_tick_per_cent × remaining_amount`
- **One-time penalty**: `deadline_penalty` (charged only on the tick when deadline is first missed)

#### New Configuration Parameter

Add to `CostRates`:
```rust
/// Multiplier for delay cost when transaction is overdue
/// (e.g., 5.0 = 5x normal delay cost)
pub overdue_delay_multiplier: f64,
```

**Default**: `5.0` (5x penalty for overdue transactions)

### 4. Priority Re-prioritization

Agents can re-prioritize overdue transactions via a **dedicated policy action**.

#### New Policy Action: `Reprioritize`

This action allows policies to adjust transaction priority independently of submission decisions.

**Key benefits:**
- Can adjust priority without submitting to RTGS
- Can reprioritize multiple times as conditions change
- Clear separation of concerns (priority change ≠ submission)
- Flexible policy logic

**Example policy flow:**
```yaml
# Step 1: Check if overdue and reprioritize
- if: is_overdue == 1
  then:
    action: reprioritize
    new_priority: 10
    reason: "Urgent: past deadline"

# Step 2: Decide whether to submit (separate decision)
- if: available_liquidity >= amount
  then:
    action: submit_full
  else:
    action: hold
    reason: "Insufficient liquidity"
```

#### New Policy Context Fields

Add to `EvalContext`:
```rust
/// Field: "is_overdue" (bool → 0.0/1.0)
/// True if transaction has passed its deadline
fields.insert("is_overdue", if tx.is_overdue() { 1.0 } else { 0.0 });

/// Field: "overdue_duration" (f64)
/// Number of ticks since deadline was missed
fields.insert("overdue_duration", overdue_duration as f64);
```

#### Implementation: New `ReleaseDecision` Variant

```rust
pub enum ReleaseDecision {
    SubmitFull { tx_id: String },
    SubmitPartial { tx_id: String, num_splits: usize },
    Hold { tx_id: String, reason: HoldReason },

    // NEW: Dedicated re-prioritization action
    Reprioritize {
        tx_id: String,
        new_priority: u8  // Absolute priority (0-10)
    },
}
```

### 5. Settlement Logic Changes (CRITICAL)

#### Current Behavior (backend/src/settlement/rtgs.rs:336-340)
```rust
// Check if past deadline → drop
if transaction.is_past_deadline(tick) {
    transaction.drop_transaction(tick);
    dropped_count += 1;
    continue;  // ← Removed from queue!
}
```

#### New Behavior (System-Enforced)
```rust
// SYSTEM automatically marks overdue (not policy-driven!)
// This is critical for Queue 2 where there is NO policy
if transaction.is_past_deadline(tick) && !transaction.is_overdue() {
    transaction.mark_overdue(tick).ok();
    // One-time penalty charged in cost calculation
}

// Continue with settlement attempt regardless of overdue status
let sender_id = transaction.sender_id().to_string();
// ... rest of settlement logic
```

**Why system-enforced is critical:**
- Queue 2 (RTGS) has no policy engine
- Deadline is a fundamental system constraint
- Prevents policy bugs from breaking invariants

### 6. Queue Management Changes

**No changes needed** to queue data structures. Overdue transactions remain in queues naturally.

## Implementation Plan (TDD)

### Phase 1: Core Model Changes

#### Test 1.1: Transaction Status Transition
**File**: `backend/src/models/transaction.rs` (tests)

```rust
#[test]
fn test_mark_transaction_overdue() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Initially pending
    assert!(tx.is_pending());
    assert!(!tx.is_overdue());

    // Mark overdue at tick 51
    tx.mark_overdue(51).unwrap();

    // Check status
    assert!(tx.is_overdue());
    assert_eq!(tx.overdue_since_tick(), Some(51));
}

#[test]
fn test_mark_overdue_is_idempotent() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Mark overdue twice
    tx.mark_overdue(51).unwrap();
    let result = tx.mark_overdue(52); // Different tick

    // Should succeed (idempotent) but not change tick
    assert!(result.is_ok());
    assert_eq!(tx.overdue_since_tick(), Some(51)); // Original tick preserved
}

#[test]
fn test_overdue_transaction_can_still_settle() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Mark overdue
    tx.mark_overdue(51).unwrap();
    assert!(tx.is_overdue());

    // Should still be able to settle
    let result = tx.settle(100_000, 55);
    assert!(result.is_ok());
    assert!(tx.is_fully_settled());
}

#[test]
fn test_cannot_mark_settled_transaction_overdue() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Settle first
    tx.settle(100_000, 40).unwrap();

    // Attempting to mark overdue should fail
    let result = tx.mark_overdue(51);
    assert!(result.is_err());
    assert_eq!(result.unwrap_err(), TransactionError::AlreadySettled);
}

#[test]
fn test_partially_settled_can_become_overdue() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Partially settle (if system supported this - future proof)
    // For now, just ensure status transition logic handles all cases
    tx.mark_overdue(51).unwrap();
    assert!(tx.is_overdue());
}
```

**Implementation**:
1. Rename `TransactionStatus::Dropped` → `TransactionStatus::Overdue { missed_deadline_tick }`
2. Add `Transaction::mark_overdue(&mut self, tick: usize) -> Result<(), TransactionError>`
   - Returns `Ok(())` if already overdue (idempotent)
   - Returns `Err(AlreadySettled)` if settled
   - Transitions `Pending` → `Overdue`
3. Add `Transaction::is_overdue(&self) -> bool`
4. Add `Transaction::overdue_since_tick(&self) -> Option<usize>`
5. Add `Transaction::set_priority(&mut self, priority: u8)` for reprioritization
6. Update `settle()` to allow settlement of overdue transactions

**Transaction Model Changes**:
```rust
// In backend/src/models/transaction.rs

impl Transaction {
    /// Mark transaction as overdue (idempotent)
    pub fn mark_overdue(&mut self, tick: usize) -> Result<(), TransactionError> {
        match self.status {
            TransactionStatus::Pending | TransactionStatus::PartiallySettled { .. } => {
                self.status = TransactionStatus::Overdue { missed_deadline_tick: tick };
                Ok(())
            }
            TransactionStatus::Overdue { .. } => {
                // Idempotent - already overdue, keep original tick
                Ok(())
            }
            TransactionStatus::Settled { .. } => {
                Err(TransactionError::AlreadySettled)
            }
        }
    }

    /// Check if transaction is overdue
    pub fn is_overdue(&self) -> bool {
        matches!(self.status, TransactionStatus::Overdue { .. })
    }

    /// Get tick when transaction became overdue
    pub fn overdue_since_tick(&self) -> Option<usize> {
        match self.status {
            TransactionStatus::Overdue { missed_deadline_tick } => Some(missed_deadline_tick),
            _ => None,
        }
    }

    /// Set transaction priority (for re-prioritization)
    pub fn set_priority(&mut self, priority: u8) {
        self.priority = priority.min(10); // Cap at 10
    }
}
```

#### Test 1.2: Settlement Error Removal
**File**: `backend/src/models/transaction.rs` (tests)

```rust
#[test]
fn test_settle_no_longer_rejects_overdue() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);
    tx.mark_overdue(51).unwrap();

    // Old behavior: Err(TransactionError::TransactionDropped)
    // New behavior: Ok(())
    let result = tx.settle(100_000, 55);
    assert!(result.is_ok());
}
```

**Implementation**: Remove the check in `Transaction::settle()` at line 499:
```rust
// REMOVE THIS:
if matches!(self.status, TransactionStatus::Dropped { .. }) {
    return Err(TransactionError::TransactionDropped);
}
```

### Phase 2: Settlement Logic Changes

#### Test 2.1: RTGS Queue Processing (CRITICAL)
**File**: `backend/src/settlement/rtgs.rs` (tests)

```rust
#[test]
fn test_overdue_transactions_remain_in_queue() {
    let agents = vec![
        Agent::new("BANK_A".to_string(), 100_000, 0),  // Insufficient
        Agent::new("BANK_B".to_string(), 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 500_000, 0, 50);
    submit_transaction(&mut state, tx, 5).unwrap();

    // Process at tick 51 (past deadline)
    let result = process_queue(&mut state, 51);

    // Old behavior: dropped_count = 1, remaining_queue_size = 0
    // New behavior: transaction marked overdue but stays in queue
    assert_eq!(result.dropped_count, 0);  // No longer "dropping"
    assert_eq!(result.overdue_count, 1);   // New metric
    assert_eq!(result.remaining_queue_size, 1);

    // Transaction should be overdue but still in queue
    let tx = state.transactions().values().next().unwrap();
    assert!(tx.is_overdue());
    assert_eq!(tx.overdue_since_tick(), Some(51));
}

#[test]
fn test_overdue_transaction_settles_when_liquidity_arrives() {
    let agents = vec![
        Agent::new("BANK_A".to_string(), 100_000, 0),
        Agent::new("BANK_B".to_string(), 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 500_000, 0, 50);
    submit_transaction(&mut state, tx, 5).unwrap();

    // Tick 51: Past deadline, becomes overdue
    process_queue(&mut state, 51);

    // Verify overdue but still in queue
    assert_eq!(state.queue_size(), 1);
    let tx = state.transactions().values().next().unwrap();
    assert!(tx.is_overdue());

    // Add liquidity
    state.get_agent_mut("BANK_A").unwrap().credit(500_000);

    // Tick 52: Should settle despite being overdue
    let result = process_queue(&mut state, 52);

    assert_eq!(result.settled_count, 1);
    assert_eq!(result.remaining_queue_size, 0);

    let tx = state.transactions().values().next().unwrap();
    assert!(tx.is_fully_settled());
}

#[test]
fn test_system_enforces_overdue_without_policy() {
    // This test verifies the CRITICAL design decision:
    // The system marks transactions overdue automatically,
    // not relying on policy (which doesn't exist in Queue 2)

    let agents = vec![
        Agent::new("BANK_A".to_string(), 0, 0),  // No liquidity
        Agent::new("BANK_B".to_string(), 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    submit_transaction(&mut state, tx, 5).unwrap();

    // Process through deadline - NO POLICY INVOLVED
    for tick in 6..=55 {
        process_queue(&mut state, tick);
    }

    // Transaction should be overdue (system-enforced)
    let tx = state.transactions().values().next().unwrap();
    assert!(tx.is_overdue());
    assert_eq!(tx.overdue_since_tick(), Some(51));
}
```

**Implementation**: Modify `process_queue()` in `backend/src/settlement/rtgs.rs`:

```rust
/// Result of processing RTGS queue
#[derive(Debug, Clone, PartialEq)]
pub struct QueueProcessingResult {
    pub settled_count: usize,
    pub settled_value: i64,
    pub remaining_queue_size: usize,

    /// Deprecated: Always 0 (transactions no longer "dropped")
    #[deprecated(note = "Transactions are now marked overdue, not dropped")]
    pub dropped_count: usize,

    /// NEW: Number of transactions newly marked overdue this tick
    pub overdue_count: usize,
}

pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut settled_value = 0i64;
    let mut overdue_count = 0;  // NEW: Count newly overdue
    let mut still_pending = Vec::new();

    let queue = state.rtgs_queue_mut();
    let tx_ids: Vec<String> = queue.drain(..).collect();

    for tx_id in tx_ids {
        let transaction = state.get_transaction_mut(&tx_id).unwrap();

        // Skip if already settled
        if transaction.is_fully_settled() {
            continue;
        }

        // CRITICAL: System automatically marks overdue (not policy-driven!)
        // This must happen here because Queue 2 has NO policy
        if transaction.is_past_deadline(tick) && !transaction.is_overdue() {
            transaction.mark_overdue(tick).ok();  // Ignore errors (defensive)
            overdue_count += 1;
            // One-time penalty will be charged in orchestrator cost calculation
        }

        // Attempt settlement (regardless of overdue status)
        let sender_id = transaction.sender_id().to_string();
        let receiver_id = transaction.receiver_id().to_string();
        let amount = transaction.remaining_amount();

        let can_settle = {
            let sender = state.get_agent(&sender_id).unwrap();
            sender.can_pay(amount)
        };

        if can_settle {
            // Perform settlement
            {
                let sender = state.get_agent_mut(&sender_id).unwrap();
                sender.debit(amount).unwrap();
            }
            {
                let receiver = state.get_agent_mut(&receiver_id).unwrap();
                receiver.credit(amount);
            }
            {
                let transaction = state.get_transaction_mut(&tx_id).unwrap();
                transaction.settle(amount, tick).unwrap();
            }

            settled_count += 1;
            settled_value += amount;
        } else {
            // Still can't settle, re-queue
            still_pending.push(tx_id);
        }
    }

    *state.rtgs_queue_mut() = still_pending;

    QueueProcessingResult {
        settled_count,
        settled_value,
        remaining_queue_size: state.queue_size(),
        dropped_count: 0,  // Deprecated - always 0
        overdue_count,
    }
}
```

#### Test 2.2: Settlement Error Handling
**File**: `backend/src/settlement/rtgs.rs` (tests)

```rust
#[test]
fn test_try_settle_accepts_overdue_transactions() {
    let mut sender = Agent::new("A".to_string(), 1_000_000, 0);
    let mut receiver = Agent::new("B".to_string(), 0, 0);
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 500_000, 0, 50);

    // Mark overdue
    tx.mark_overdue(51).unwrap();

    // Should settle successfully
    let result = try_settle(&mut sender, &mut receiver, &mut tx, 55);

    assert!(result.is_ok());
    assert!(tx.is_fully_settled());
    assert_eq!(sender.balance(), 500_000);
    assert_eq!(receiver.balance(), 500_000);
}
```

**Implementation**: Modify `try_settle()` in `backend/src/settlement/rtgs.rs`:

```rust
pub fn try_settle(
    sender: &mut Agent,
    receiver: &mut Agent,
    transaction: &mut Transaction,
    tick: usize,
) -> Result<(), SettlementError> {
    // Validate transaction state
    if transaction.is_fully_settled() {
        return Err(SettlementError::AlreadySettled);
    }

    // REMOVE THIS CHECK - overdue transactions can be settled:
    // if matches!(transaction.status(), TransactionStatus::Dropped { .. }) {
    //     return Err(SettlementError::Dropped);
    // }

    let amount = transaction.remaining_amount();

    // Check liquidity
    if !sender.can_pay(amount) {
        return Err(SettlementError::InsufficientLiquidity {
            required: amount,
            available: sender.available_liquidity(),
        });
    }

    // Execute settlement (atomic operation)
    sender.debit(amount)?;
    receiver.credit(amount);
    transaction.settle(amount, tick)?;

    Ok(())
}
```

### Phase 3: Cost Model Changes

#### Test 3.1: Overdue Penalty Calculation
**File**: `backend/src/orchestrator/engine.rs` (tests)

```rust
#[test]
fn test_overdue_delay_cost_multiplier() {
    let cost_rates = CostRates {
        delay_cost_per_tick_per_cent: 0.0001,  // 1 bp per tick
        overdue_delay_multiplier: 5.0,          // 5x for overdue
        deadline_penalty: 100_000,              // $1000 one-time
        ..Default::default()
    };

    // Pending transaction: 1M cents, 1 tick
    let pending_cost = calculate_delay_cost_for_transaction(
        1_000_000,
        false, // not overdue
        &cost_rates
    );

    // Expected: 1_000_000 * 0.0001 = 100 cents
    assert_eq!(pending_cost, 100);

    // Overdue transaction: same amount, 1 tick
    let overdue_cost = calculate_delay_cost_for_transaction(
        1_000_000,
        true, // overdue
        &cost_rates
    );

    // Expected: 1_000_000 * 0.0001 * 5.0 = 500 cents
    assert_eq!(overdue_cost, 500);
}

#[test]
fn test_one_time_deadline_penalty() {
    let cost_rates = CostRates {
        deadline_penalty: 100_000,  // $1000
        ..Default::default()
    };

    let mut accumulator = CostAccumulator::new();

    // Transaction just became overdue this tick
    let penalty = cost_rates.deadline_penalty;
    accumulator.add_penalty(penalty);

    assert_eq!(accumulator.total_penalty_cost, 100_000);
}

#[test]
fn test_deadline_penalty_only_charged_once() {
    // Simulation scenario:
    // Tick 50: TX deadline
    // Tick 51: TX becomes overdue (penalty charged)
    // Tick 52-60: TX remains overdue (no additional deadline penalty, only delay multiplier)

    let cost_rates = CostRates {
        delay_cost_per_tick_per_cent: 0.0001,
        overdue_delay_multiplier: 5.0,
        deadline_penalty: 100_000,
        ..Default::default()
    };

    let mut accumulator = CostAccumulator::new();
    let tx_amount = 1_000_000;

    // Tick 51: First overdue tick
    // - One-time penalty: 100,000
    // - Delay cost: 1,000,000 * 0.0001 * 5.0 = 500
    accumulator.add_penalty(cost_rates.deadline_penalty);
    accumulator.add_delay(500);

    let tick_51_total = accumulator.total_penalty_cost + accumulator.total_delay_cost;
    assert_eq!(tick_51_total, 100_500);

    // Tick 52: Still overdue
    // - No additional deadline penalty
    // - Delay cost: 500
    accumulator.add_delay(500);

    let tick_52_total = accumulator.total_penalty_cost + accumulator.total_delay_cost;
    assert_eq!(tick_52_total, 101_000);  // 100,000 + 500 + 500
}
```

**Implementation**:

1. Add `overdue_delay_multiplier` to `CostRates`:
```rust
pub struct CostRates {
    pub overdraft_bps_per_tick: f64,
    pub delay_cost_per_tick_per_cent: f64,
    pub collateral_cost_per_tick_bps: f64,
    pub eod_penalty_per_transaction: i64,
    pub deadline_penalty: i64,
    pub split_friction_cost: i64,

    // NEW FIELD
    /// Multiplier for delay cost when transaction is overdue (default: 5.0)
    pub overdue_delay_multiplier: f64,
}

impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,
            delay_cost_per_tick_per_cent: 0.0001,
            collateral_cost_per_tick_bps: 0.0002,
            eod_penalty_per_transaction: 50_000,
            deadline_penalty: 100_000,
            split_friction_cost: 1_000,
            overdue_delay_multiplier: 5.0,  // NEW DEFAULT
        }
    }
}
```

2. Modify delay cost calculation:
```rust
// In backend/src/orchestrator/engine.rs
fn calculate_delay_cost(&self, agent_id: &str) -> i64 {
    let agent = self.state.get_agent(agent_id).unwrap();
    let mut total_weighted_value = 0.0;

    for tx_id in agent.outgoing_queue() {
        if let Some(tx) = self.state.get_transaction(tx_id) {
            let amount = tx.remaining_amount() as f64;

            // Apply multiplier for overdue transactions
            let multiplier = if tx.is_overdue() {
                self.cost_rates.overdue_delay_multiplier
            } else {
                1.0
            };

            total_weighted_value += amount * multiplier;
        }
    }

    let cost = total_weighted_value * self.cost_rates.delay_cost_per_tick_per_cent;
    cost.round() as i64
}
```

3. Charge one-time penalty when transaction first becomes overdue:
```rust
// In tick processing loop (Queue 1 processing)
for tx_id in agent.outgoing_queue() {
    let tx = self.state.get_transaction(tx_id).unwrap();

    // Check if newly overdue this tick
    if tx.is_past_deadline(current_tick) && !tx.is_overdue() {
        // Mark overdue
        let tx_mut = self.state.get_transaction_mut(tx_id).unwrap();
        tx_mut.mark_overdue(current_tick).ok();

        // Charge one-time penalty
        cost_breakdown.penalty_cost += self.cost_rates.deadline_penalty;
    }
}
```

### Phase 4: Policy Integration with Reprioritize Action

#### Test 4.1: Evaluation Context Fields
**File**: `backend/src/policy/tree/context.rs` (tests)

```rust
#[test]
fn test_context_includes_is_overdue_field() {
    let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    let mut tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    // Pending transaction
    let context = EvalContext::build(&tx, &agent, &state, 40, &cost_rates, 100, 0.8);
    assert_eq!(context.get_field("is_overdue").unwrap(), 0.0);

    // Overdue transaction
    tx.mark_overdue(51).unwrap();
    let context = EvalContext::build(&tx, &agent, &state, 55, &cost_rates, 100, 0.8);
    assert_eq!(context.get_field("is_overdue").unwrap(), 1.0);
}

#[test]
fn test_context_includes_overdue_duration() {
    let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    let mut tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    // Mark overdue at tick 51
    tx.mark_overdue(51).unwrap();

    // Current tick 60 → 9 ticks overdue
    let context = EvalContext::build(&tx, &agent, &state, 60, &cost_rates, 100, 0.8);

    assert_eq!(context.get_field("overdue_duration").unwrap(), 9.0);
}
```

**Implementation**: Add to `EvalContext::build()` in `backend/src/policy/tree/context.rs`:

```rust
// Transaction fields (existing)
fields.insert("amount".to_string(), tx.amount() as f64);
// ... other fields ...

// NEW FIELDS: Overdue status
fields.insert(
    "is_overdue".to_string(),
    if tx.is_overdue() { 1.0 } else { 0.0 },
);

if let Some(overdue_since) = tx.overdue_since_tick() {
    let overdue_duration = tick.saturating_sub(overdue_since);
    fields.insert("overdue_duration".to_string(), overdue_duration as f64);
} else {
    fields.insert("overdue_duration".to_string(), 0.0);
}
```

#### Test 4.2: Reprioritize Action
**File**: `backend/src/policy/mod.rs` (tests)

```rust
#[test]
fn test_reprioritize_decision() {
    let decision = ReleaseDecision::Reprioritize {
        tx_id: "tx_123".to_string(),
        new_priority: 10,
    };

    // Verify enum construction
    match decision {
        ReleaseDecision::Reprioritize { tx_id, new_priority } => {
            assert_eq!(tx_id, "tx_123");
            assert_eq!(new_priority, 10);
        }
        _ => panic!("Wrong variant"),
    }
}

#[test]
fn test_reprioritize_changes_transaction_priority() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);
    assert_eq!(tx.priority(), 5); // Default

    // Reprioritize to 10
    tx.set_priority(10);
    assert_eq!(tx.priority(), 10);

    // Reprioritize to 3
    tx.set_priority(3);
    assert_eq!(tx.priority(), 3);
}

#[test]
fn test_reprioritize_caps_at_10() {
    let mut tx = Transaction::new("A".to_string(), "B".to_string(), 100_000, 0, 50);

    // Try to set priority > 10
    tx.set_priority(255);
    assert_eq!(tx.priority(), 10); // Capped
}
```

**Implementation**:

1. **Add `Reprioritize` to `ReleaseDecision` enum** (`backend/src/policy/mod.rs`):
```rust
pub enum ReleaseDecision {
    /// Submit entire transaction to RTGS now
    SubmitFull { tx_id: String },

    /// Split transaction and submit all parts
    SubmitPartial {
        tx_id: String,
        num_splits: usize
    },

    /// Hold transaction in Queue 1
    Hold {
        tx_id: String,
        reason: HoldReason
    },

    /// NEW: Change transaction priority (doesn't submit to RTGS)
    ///
    /// Allows policy to adjust priority of queued transactions
    /// based on changing conditions (e.g., overdue status).
    /// Transaction remains in Queue 1 after reprioritization.
    Reprioritize {
        tx_id: String,
        new_priority: u8  // Absolute priority (0-10, capped)
    },
}
```

2. **Add `Reprioritize` to `ActionType` enum** (`backend/src/policy/tree/types.rs`):
```rust
pub enum ActionType {
    SubmitFull,
    SubmitPartial,
    Hold,
    Reprioritize,  // NEW
}
```

3. **Implement interpreter support** (`backend/src/policy/tree/interpreter.rs`):
```rust
// In build_decision() function
match action {
    ActionType::SubmitFull => { /* existing */ }
    ActionType::SubmitPartial => { /* existing */ }
    ActionType::Hold => { /* existing */ }

    ActionType::Reprioritize => {
        let new_priority = evaluate_action_parameter(
            action_params,
            "new_priority",
            context,
            params
        )?;
        let new_priority_u8 = new_priority.round().max(0.0).min(10.0) as u8;

        Ok(ReleaseDecision::Reprioritize {
            tx_id,
            new_priority: new_priority_u8,
        })
    }
}
```

4. **Handle `Reprioritize` in orchestrator** (`backend/src/orchestrator/engine.rs`):
```rust
// In tick() method's decision handler
match decision {
    ReleaseDecision::SubmitFull { tx_id } => { /* existing */ }
    ReleaseDecision::SubmitPartial { tx_id, num_splits } => { /* existing */ }
    ReleaseDecision::Hold { tx_id, reason } => { /* existing */ }

    ReleaseDecision::Reprioritize { tx_id, new_priority } => {
        if let Some(tx) = self.state.get_transaction_mut(&tx_id) {
            tx.set_priority(new_priority);

            // Optional: Log reprioritization event
            self.log_event(Event::TransactionReprioritized {
                tick: current_tick,
                agent_id: agent_id.clone(),
                tx_id: tx_id.clone(),
                old_priority: tx.priority(),
                new_priority,
            });
        }
    }
}
```

### Phase 5: FFI and API Updates

#### Test 5.1: FFI Serialization
**File**: `backend/src/ffi/types.rs` (tests)

```rust
#[test]
fn test_transaction_status_overdue_serializes() {
    let status = TransactionStatus::Overdue { missed_deadline_tick: 51 };

    // Should serialize to Python-friendly format
    let json = serde_json::to_string(&status).unwrap();
    assert!(json.contains("Overdue"));
    assert!(json.contains("51"));
}

#[test]
fn test_queue_processing_result_serializes() {
    let result = QueueProcessingResult {
        settled_count: 5,
        settled_value: 1_000_000,
        remaining_queue_size: 3,
        dropped_count: 0,  // Always 0 now
        overdue_count: 2,
    };

    let json = serde_json::to_string(&result).unwrap();
    assert!(json.contains("overdue_count"));
}
```

**Implementation**:
- Update FFI type conversions to handle `Overdue` status
- Ensure Python can deserialize new status correctly
- Update `QueueProcessingResult` serialization

#### Test 5.2: API Response Changes
**File**: `api/tests/integration/test_overdue_transactions.py` (new file)

```python
def test_overdue_transaction_remains_in_system():
    """Verify overdue transactions stay in system until settled."""
    config = {
        "agents": [
            {"id": "BANK_A", "balance": 100_000, "credit_limit": 0},
            {"id": "BANK_B", "balance": 0, "credit_limit": 0},
        ],
        "seed": 42,
        "ticks_per_day": 100,
        "cost_rates": {
            "delay_cost_per_tick_per_cent": 0.0001,
            "overdue_delay_multiplier": 5.0,
            "deadline_penalty": 100_000,
        },
    }

    orch = Orchestrator.new(config)

    # Add transaction that will be insufficient
    orch.add_transaction({
        "sender_id": "BANK_A",
        "receiver_id": "BANK_B",
        "amount": 500_000,
        "arrival_tick": 0,
        "deadline_tick": 50,
    })

    # Run to tick 55 (past deadline)
    for _ in range(55):
        orch.tick()

    # Check state
    state = orch.get_state()

    # Should have 1 transaction still in system
    assert len(state["transactions"]) == 1

    tx = state["transactions"][0]
    assert tx["status"]["Overdue"]["missed_deadline_tick"] == 51
    assert not tx["is_fully_settled"]

    # Should still be in queue
    assert state["queue_size"] > 0

def test_overdue_transaction_eventually_settles():
    """Verify overdue transactions settle when liquidity arrives."""
    # ... similar setup ...

    # Run past deadline
    for _ in range(55):
        orch.tick()

    # Add liquidity
    orch.credit_agent("BANK_A", 500_000)

    # Run more ticks
    for _ in range(10):
        orch.tick()

    # Should eventually settle
    state = orch.get_state()
    tx = state["transactions"][0]
    assert tx["is_fully_settled"]
    assert state["queue_size"] == 0

def test_overdue_delay_cost_multiplier():
    """Verify overdue transactions incur multiplied delay costs."""
    # ... setup with overdue transaction ...

    # Get cost breakdown before and after deadline
    costs_before = orch.get_agent_costs("BANK_A")

    # Run past deadline
    for _ in range(55):
        orch.tick()

    costs_after = orch.get_agent_costs("BANK_A")

    # Delay cost should increase by more than 1x per tick
    # (due to overdue_delay_multiplier)

def test_reprioritize_action_via_policy():
    """Verify policies can reprioritize overdue transactions."""
    policy = {
        "release_policy": [
            {
                "if": "is_overdue == 1",
                "then": {
                    "action": "reprioritize",
                    "new_priority": 10,
                }
            }
        ]
    }

    # ... test that overdue transaction gets priority 10
```

**Implementation**:
1. Update Python config schema to include `overdue_delay_multiplier`
2. Update state serialization to handle overdue status
3. Update cost breakdown reporting
4. Add support for `reprioritize` action in policy YAML/JSON

### Phase 6: Documentation and Examples

#### Example Policy: Overdue Handling
**File**: `examples/policies/overdue_handling.yaml` (new file)

```yaml
# Example policy: Aggressive handling of overdue transactions
name: "Overdue Priority Management"
description: "Reprioritize overdue transactions and submit when liquidity available"

release_policy:
  # Step 1: Reprioritize any overdue transaction to maximum priority
  - if: is_overdue == 1
    then:
      action: reprioritize
      new_priority: 10
      reason: "Urgent: transaction past deadline"

  # Step 2: Submit high-priority transactions if liquidity sufficient
  - if: priority >= 8 && available_liquidity >= amount
    then:
      action: submit_full
      reason: "High priority with sufficient liquidity"

  # Step 3: Hold lower-priority transactions if approaching EOD
  - if: is_eod_rush == 1 && priority < 8
    then:
      action: hold
      reason: "Preserving liquidity for high-priority items"

  # Step 4: Default - submit if we can
  - if: available_liquidity >= amount
    then:
      action: submit_full

collateral_policy:
  # Post collateral aggressively if have overdue transactions in Queue 2
  - if: queue2_count_for_agent > 0 && ticks_to_nearest_queue2_deadline < 10
    then:
      action: post
      amount: remaining_collateral_capacity * 0.5
      reason: "Need liquidity for imminent deadline"
```

#### Example Policy: Moderate Approach
**File**: `examples/policies/overdue_moderate.yaml` (new file)

```yaml
# Example policy: Gradual priority escalation for overdue
name: "Gradual Overdue Escalation"
description: "Increase priority based on how long transaction is overdue"

release_policy:
  # Extremely overdue (>20 ticks) → priority 10
  - if: overdue_duration > 20
    then:
      action: reprioritize
      new_priority: 10

  # Very overdue (>10 ticks) → priority 8
  - if: overdue_duration > 10
    then:
      action: reprioritize
      new_priority: 8

  # Recently overdue (>0 ticks) → priority 7
  - if: is_overdue == 1
    then:
      action: reprioritize
      new_priority: 7

  # Submit if liquidity available
  - if: available_liquidity >= amount
    then:
      action: submit_full
```

#### Documentation Updates

**Files to update**:

1. **`CLAUDE.md`**: Update domain model terminology
   - Change "Dropped" → "Overdue"
   - Add reprioritize action to policy examples

2. **`docs/architecture.md`**: Explain overdue transaction lifecycle
   - System-enforced deadline checking
   - Queue 2 behavior without policy

3. **`backend/CLAUDE.md`**: Update settlement logic description
   - Overdue transactions remain in queue
   - Reprioritization mechanism

4. **Add new doc**: `docs/overdue-transactions.md`
   - Rationale for design
   - Cost model explanation
   - Policy examples

## Testing Strategy

### Unit Tests (Per Phase)
- Phase 1: Transaction status transitions, idempotency
- Phase 2: RTGS queue processing, system-enforced transitions
- Phase 3: Cost calculations with multiplier
- Phase 4: Policy context fields, reprioritize action

### Integration Tests
- End-to-end overdue transaction lifecycle
- Multi-agent scenarios with overdue gridlock
- Cost accumulation over time
- Reprioritization via policy

### Property Tests
- **Invariant**: All transactions eventually settle (given sufficient liquidity)
- **Invariant**: Total system balance conserved
- **Invariant**: Overdue delay cost >= regular delay cost
- **Invariant**: Deadline transitions happen at correct tick

### Critical Tests (Queue 2 Without Policy)
```rust
#[test]
fn test_queue2_transitions_without_policy() {
    // Verify system-enforced behavior in Queue 2
    // where NO policy exists
}
```

### Performance Tests
- Large queue with mix of overdue and pending
- Ensure overdue flag doesn't degrade performance
- Benchmark cost calculation with multipliers

## Migration and Backward Compatibility

### Breaking Changes
1. **TransactionStatus enum**: `Dropped` → `Overdue`
2. **QueueProcessingResult struct**: Add `overdue_count`, deprecate `dropped_count`
3. **CostRates struct**: Add `overdue_delay_multiplier` field
4. **ReleaseDecision enum**: Add `Reprioritize` variant
5. **ActionType enum**: Add `Reprioritize` variant

### Migration Path
1. Update Rust code (Phase 1-4)
2. Update FFI layer with new serialization
3. Update Python API with schema changes
4. Provide default value for `overdue_delay_multiplier` (5.0)
5. Update example configs and documentation

### Deprecation Timeline
- **v0.x.0**: Introduce new behavior, mark `dropped_count` as deprecated
- **v0.x+1.0**: Remove references to `dropped_count`
- **v1.0.0**: Finalize API

## Success Criteria

### Functional
- ✅ Overdue transactions remain in queue (both Queue 1 and Queue 2)
- ✅ Overdue transactions settle when liquidity available
- ✅ One-time penalty charged when deadline first missed
- ✅ Multiplied delay cost applied per tick
- ✅ System enforces deadline transitions (not policy-dependent)
- ✅ Policies can reprioritize overdue transactions
- ✅ Reprioritize action works independently of submission

### Performance
- ✅ No degradation in tick processing speed
- ✅ Memory usage reasonable for large overdue queues

### Code Quality
- ✅ All tests pass
- ✅ Code follows existing patterns
- ✅ Documentation updated
- ✅ FFI boundary stable

### Realism
- ✅ Behavior matches real payment systems
- ✅ Banks cannot ignore obligations
- ✅ Delayed payments have escalating costs
- ✅ Cash managers can prioritize urgent items
- ✅ Priority changes are explicit policy decisions

## Open Questions

1. **Default multiplier value**: Is 5.0x appropriate, or should it be higher (10x)?
   - **Recommendation**: Start with 5.0x, make configurable, gather empirical data

2. **Maximum overdue duration**: Should transactions eventually be forcibly settled (e.g., after 1 business day)?
   - **Recommendation**: No forced settlement (let simulation play out), but add warning logs

3. **Priority boost limits**: Should there be a rate limit on reprioritization?
   - **Recommendation**: No limit (policy decides), but could add cooldown if needed

4. **Overdue in Queue 1 vs Queue 2**: Do transactions become overdue in both queues?
   - **Answer**: Yes, deadline is global regardless of queue

5. **Event logging**: Should reprioritization generate a new event type?
   - **Recommendation**: Yes, add `Event::TransactionReprioritized` for observability

## Next Steps

1. **Implement Phase 1** (core model changes) following TDD
2. **Implement Phase 2** (settlement logic) with emphasis on Queue 2
3. **Implement Phase 3** (cost model)
4. **Implement Phase 4** (reprioritize action)
5. **Implement Phase 5** (FFI/API)
6. **Implement Phase 6** (documentation)
7. **Run full test suite** at each phase
8. **Deploy to test environment** for validation
9. **Collect feedback** on realism and performance

---

**Dependencies**: None (standalone feature)
**Estimated Effort**: 2-3 days (including tests and documentation)
**Risk Level**: Medium (touches critical settlement paths, mitigated by TDD)
