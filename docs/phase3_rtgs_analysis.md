# Phase 3: RTGS Architecture Analysis & Implementation Plan

## Executive Summary

This document analyzes the existing Phase 1-2 implementation against T2-style RTGS requirements and provides a detailed plan for Phase 3 (Settlement Engine) implementation.

**Key Finding**: Current implementation is **well-aligned** with central bank intermediary model. No breaking changes needed to Phase 1-2 code.

**Phase 3 Scope**: Implement basic RTGS settlement engine with centralized queue management, preparing foundation for LSM (Phase 4).

---

## 1. Architecture Review: Current vs. T2-Style Requirements

### 1.1 Central Bank Intermediary Model

**T2-Style Requirement** (from game_concept_doc.md):
```
Client A → Bank A (internal debit) → RTGS @ Central Bank (A debited, B credited) → Bank B (internal credit) → Client B
```

**Current Implementation Analysis**:

Our current `Agent` and `Transaction` models **correctly represent** this flow:

1. **Agent = Bank's Settlement Account at Central Bank**
   - `Agent.balance` = Bank's central bank reserve balance (✓ Correct)
   - `Agent.credit_limit` = Intraday overdraft/collateralized credit (✓ Correct)
   - Agents don't directly transfer to each other (✓ Correct)

2. **Transaction = Interbank Payment Order**
   - `Transaction.sender_id` = Sending bank's ID (✓ Correct)
   - `Transaction.receiver_id` = Receiving bank's ID (✓ Correct)
   - `Transaction.amount` = Payment value in central bank money (✓ Correct)

3. **Missing Piece: RTGS Settlement Engine**
   - Currently no code that performs: "Debit Bank A at CB, Credit Bank B at CB"
   - This is precisely what Phase 3 will implement (✓ Expected)

**Verdict**: ✅ **No changes needed to Phase 1-2**. The models correctly represent T2-style settlement accounts and payment orders.

### 1.2 Settlement Flow Verification

**T2 Settlement Logic** (game_concept_doc.md, line 41-48):
```
RTGS settlement attempt:
- If Bank A's central bank balance + intraday credit suffices → immediate finality (A debited, B credited)
- Else → queue
- LSM/optimization may offset cycles to settle with less liquidity
```

**Current Agent Model Support**:
- ✅ `Agent.can_pay(amount)` checks balance + credit_limit
- ✅ `Agent.debit(amount)` decreases balance (sender)
- ✅ `Agent.credit(amount)` increases balance (receiver)
- ✅ `Agent.available_liquidity()` calculates headroom

**Current Transaction Model Support**:
- ✅ `Transaction.settle(amount, tick)` tracks settlement state
- ✅ Supports partial settlement for divisible transactions
- ✅ `TransactionStatus` enum tracks lifecycle (Pending → Settled/Dropped)

**Missing Components** (Phase 3):
- ❌ Centralized RTGS settlement function
- ❌ Central queue for insufficient liquidity transactions
- ❌ Attempt-retry logic for queued transactions
- ❌ Settlement orchestration (process all pending transactions)

**Verdict**: ✅ **Foundation is correct**. Phase 3 builds on top without modifying Phase 1-2.

### 1.3 Queue Location Decision

**Question**: Where should queued transactions live?

**Options**:
1. **Per-agent queues** (`Agent.outgoing_queue`)
2. **Centralized RTGS queue** (in `SimulationState`)
3. **Hybrid** (both)

**T2-Style Guidance** (game_concept_doc.md, line 78):
```
Central RTGS engine:
- Entry disposition: each submitted payment triggers immediate settlement attempt
- If not possible, it goes to **central queue**
- The engine maintains per-bank net debit checks
```

**Decision**: **Centralized RTGS Queue** (Option 2)

**Rationale**:
1. **T2-style systems have central queues**: Payments are submitted to RTGS, which queues them centrally
2. **LSM needs global view**: Bilateral offsetting and cycle detection require seeing all queued payments
3. **Simpler implementation**: Single queue, single retry logic
4. **Agent queues can be added later**: For scheduled/future submissions (separate concern)

**Implementation**:
```rust
pub struct SimulationState {
    agents: HashMap<String, Agent>,
    transactions: HashMap<String, Transaction>,
    rtgs_queue: Vec<String>,  // Transaction IDs awaiting liquidity
    // ... other fields
}
```

### 1.4 Settlement Authority

**Clarification**: Who performs the settlement?

**Answer**: The **RTGS Settlement Engine** (Phase 3 module)

**Not the agents themselves**. Agents submit payment orders, but the central RTGS engine:
1. Receives transaction submission
2. Attempts immediate settlement
3. Queues if insufficient liquidity
4. Retries queued transactions each tick
5. Invokes LSM to clear gridlock (Phase 4)

This matches T2 design where the **central platform** (not individual banks) executes settlement.

---

## 2. Phase 1-2 Review: Required Changes

### 2.1 Transaction Model

**Assessment**: ✅ **No changes needed**

**Rationale**:
- `Transaction` already represents interbank payment order
- `sender_id` and `receiver_id` correctly represent banks (not end clients)
- Settlement tracking (`remaining_amount`, `status`) is correct
- Builder pattern (`with_priority()`, `divisible()`) aligns with T2 options

**Potential Future Enhancement** (not Phase 3):
- Add `priority` field (currently defaults to 5, but T2 has explicit priority levels)
- Add `timed_transaction` flag (T2 feature for scheduled settlement)

### 2.2 Agent Model

**Assessment**: ✅ **No changes needed**

**Rationale**:
- `balance` correctly represents central bank reserve account
- `credit_limit` correctly represents intraday overdraft/collateralized credit
- `debit()` and `credit()` are exactly the operations RTGS will invoke
- `can_pay()` and `available_liquidity()` provide correct pre-checks

**Clarification**:
The Agent model represents **the bank's view of its central bank account**, not the bank's internal customer accounts. This is correct for RTGS simulation.

### 2.3 Data Flow

**Current Understanding**:
```
[External] → Transaction created with (sender_id="BANK_A", receiver_id="BANK_B")
             ↓
[Phase 3]  → RTGS engine receives transaction
             ↓
[Phase 3]  → Check if BANK_A can pay
             ↓
             YES: Debit BANK_A.balance, Credit BANK_B.balance (immediate settlement)
             NO:  Add to central RTGS queue (pending)
             ↓
[Phase 3]  → Each tick: retry queued transactions
             ↓
[Phase 4]  → If still queued: LSM attempts bilateral/cycle offsetting
```

**Verdict**: ✅ **Flow is correct**. Phase 1-2 provides all needed primitives.

---

## 3. Phase 3 Implementation Plan: RTGS Settlement Engine

### 3.1 Scope Definition

**Phase 3a: Basic RTGS + Queue** (This phase)
- Immediate settlement for sufficient liquidity
- Central queue for insufficient liquidity
- Per-tick queue retry (FIFO)
- Balance updates (debit sender, credit receiver)
- Settlement failure tracking

**Phase 3b: LSM Foundation** (Future - Phase 4)
- Bilateral netting (A↔B offsetting)
- 3-cycle detection (A→B→C→A)
- 4-cycle detection
- Batch optimization

**Out of Scope for Phase 3**:
- Bilateral caps enforcement (future)
- Priority-based queue ordering (future)
- Timed transactions (future)
- Collateral management (future)
- Cost accrual (future phase)

### 3.2 Module Structure

**New Module**: `backend/src/settlement/rtgs.rs`

**Public API**:
```rust
// Attempt to settle a transaction immediately
pub fn try_settle(
    sender: &mut Agent,
    receiver: &mut Agent,
    transaction: &mut Transaction,
    tick: usize,
) -> Result<(), SettlementError>

// Process all queued transactions (called each tick)
pub fn process_queue(
    agents: &mut HashMap<String, Agent>,
    transactions: &mut HashMap<String, Transaction>,
    queue: &mut Vec<String>,
    tick: usize,
) -> QueueProcessingResult

// Submit a new transaction for settlement
pub fn submit_transaction(
    state: &mut SimulationState,
    transaction: Transaction,
    tick: usize,
) -> SubmissionResult
```

**Error Types**:
```rust
#[derive(Debug, Error)]
pub enum SettlementError {
    #[error("Insufficient liquidity: required {required}, available {available}")]
    InsufficientLiquidity { required: i64, available: i64 },

    #[error("Transaction already settled")]
    AlreadySettled,

    #[error("Transaction dropped")]
    Dropped,

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("Invalid amount: {0}")]
    InvalidAmount(i64),
}

pub struct QueueProcessingResult {
    pub settled_count: usize,
    pub settled_value: i64,
    pub remaining_queue_size: usize,
}

pub enum SubmissionResult {
    SettledImmediately { tick: usize },
    Queued { position: usize },
}
```

### 3.3 Core Settlement Logic

**Immediate Settlement Function**:
```rust
/// Attempt immediate settlement (RTGS)
///
/// This is the core T2-style settlement operation:
/// 1. Check sender has sufficient liquidity (balance + credit)
/// 2. Debit sender's central bank account
/// 3. Credit receiver's central bank account
/// 4. Mark transaction as settled
///
/// If insufficient liquidity, returns error and no state changes occur.
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

    if matches!(transaction.status(), TransactionStatus::Dropped { .. }) {
        return Err(SettlementError::Dropped);
    }

    let amount = transaction.remaining_amount();

    // Check liquidity (balance + credit headroom)
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

**Queue Processing Function**:
```rust
/// Process RTGS queue (retry pending transactions)
///
/// Called each tick to attempt settlement of queued transactions.
/// Uses FIFO ordering (can be enhanced with priority later).
///
/// Returns statistics on settlements and remaining queue.
pub fn process_queue(
    agents: &mut HashMap<String, Agent>,
    transactions: &mut HashMap<String, Transaction>,
    queue: &mut Vec<String>,
    tick: usize,
) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut settled_value = 0i64;
    let mut still_pending = Vec::new();

    for tx_id in queue.drain(..) {
        let transaction = transactions.get_mut(&tx_id).unwrap();

        // Skip if already settled (shouldn't happen, but defensive)
        if transaction.is_fully_settled() {
            continue;
        }

        // Check if past deadline → drop
        if transaction.is_past_deadline(tick) {
            transaction.drop_transaction(tick);
            continue;
        }

        let sender_id = transaction.sender_id().to_string();
        let receiver_id = transaction.receiver_id().to_string();

        // Attempt settlement
        let sender = agents.get_mut(&sender_id).unwrap();
        let receiver = agents.get_mut(&receiver_id).unwrap();

        match try_settle(sender, receiver, transaction, tick) {
            Ok(()) => {
                settled_count += 1;
                settled_value += transaction.amount();
            }
            Err(SettlementError::InsufficientLiquidity { .. }) => {
                // Still can't settle, re-queue
                still_pending.push(tx_id);
            }
            Err(_) => {
                // Other errors (already settled, dropped) → don't re-queue
            }
        }
    }

    // Replace queue with still-pending transactions
    *queue = still_pending;

    QueueProcessingResult {
        settled_count,
        settled_value,
        remaining_queue_size: queue.len(),
    }
}
```

**Transaction Submission Function**:
```rust
/// Submit transaction to RTGS
///
/// Attempts immediate settlement. If insufficient liquidity, adds to queue.
pub fn submit_transaction(
    state: &mut SimulationState,
    transaction: Transaction,
    tick: usize,
) -> Result<SubmissionResult, SettlementError> {
    let tx_id = transaction.id().to_string();
    let sender_id = transaction.sender_id().to_string();
    let receiver_id = transaction.receiver_id().to_string();

    // Add transaction to state
    state.transactions.insert(tx_id.clone(), transaction);

    // Attempt immediate settlement
    let sender = state.agents.get_mut(&sender_id)
        .ok_or_else(|| SettlementError::AgentNotFound(sender_id.clone()))?;
    let receiver = state.agents.get_mut(&receiver_id)
        .ok_or_else(|| SettlementError::AgentNotFound(receiver_id.clone()))?;
    let transaction = state.transactions.get_mut(&tx_id).unwrap();

    match try_settle(sender, receiver, transaction, tick) {
        Ok(()) => Ok(SubmissionResult::SettledImmediately { tick }),
        Err(SettlementError::InsufficientLiquidity { .. }) => {
            // Add to queue
            state.rtgs_queue.push(tx_id);
            let position = state.rtgs_queue.len();
            Ok(SubmissionResult::Queued { position })
        }
        Err(e) => Err(e),
    }
}
```

### 3.4 SimulationState Extensions

**Add to `backend/src/models/state.rs`**:
```rust
pub struct SimulationState {
    // Existing fields from Phase 1
    pub agents: HashMap<String, Agent>,
    pub transactions: HashMap<String, Transaction>,

    // Phase 3: RTGS queue
    pub rtgs_queue: Vec<String>,  // Transaction IDs awaiting settlement

    // Future phases
    // pub time_manager: TimeManager,
    // pub rng_manager: RngManager,
}

impl SimulationState {
    pub fn new(agents: Vec<Agent>) -> Self {
        let agents_map = agents.into_iter()
            .map(|agent| (agent.id().to_string(), agent))
            .collect();

        Self {
            agents: agents_map,
            transactions: HashMap::new(),
            rtgs_queue: Vec::new(),
        }
    }

    /// Get current queue size
    pub fn queue_size(&self) -> usize {
        self.rtgs_queue.len()
    }

    /// Get total value in queue
    pub fn queue_value(&self) -> i64 {
        self.rtgs_queue.iter()
            .filter_map(|tx_id| self.transactions.get(tx_id))
            .map(|tx| tx.remaining_amount())
            .sum()
    }
}
```

---

## 4. Test-Driven Development Plan

### 4.1 Test File Structure

**New Test File**: `backend/tests/test_rtgs_settlement.rs`

### 4.2 Test Cases (Write These First)

**Basic Settlement Tests**:
```rust
#[test]
fn test_immediate_settlement_with_sufficient_liquidity() {
    // Setup: BANK_A has 1000000 cents, BANK_B has 0
    // Action: BANK_A sends 500000 to BANK_B
    // Assert: BANK_A balance = 500000, BANK_B balance = 500000
    // Assert: Transaction is fully settled
}

#[test]
fn test_queue_on_insufficient_liquidity() {
    // Setup: BANK_A has 300000 cents (no credit)
    // Action: BANK_A tries to send 500000 to BANK_B
    // Assert: Transaction is queued
    // Assert: BANK_A balance unchanged (300000)
    // Assert: Queue size = 1
}

#[test]
fn test_settlement_uses_credit_limit() {
    // Setup: BANK_A has 300000 balance, 500000 credit_limit
    // Action: BANK_A sends 600000 to BANK_B
    // Assert: Settlement succeeds (within balance + credit)
    // Assert: BANK_A balance = -300000 (using 300k credit)
    // Assert: BANK_B balance = 600000
}

#[test]
fn test_settlement_respects_credit_limit() {
    // Setup: BANK_A has 300000 balance, 500000 credit_limit
    // Action: BANK_A tries to send 900000 to BANK_B
    // Assert: Insufficient liquidity error
    // Assert: Transaction queued
}
```

**Queue Processing Tests**:
```rust
#[test]
fn test_queue_retry_on_next_tick() {
    // Setup: Transaction queued due to insufficient liquidity
    // Action: BANK_A receives 500000 (now has enough)
    // Action: process_queue() called
    // Assert: Transaction settles
    // Assert: Queue is empty
}

#[test]
fn test_queue_fifo_ordering() {
    // Setup: 3 transactions queued (tx1, tx2, tx3)
    // Action: Liquidity added to settle only 1 transaction
    // Action: process_queue() called
    // Assert: tx1 settles first (FIFO)
    // Assert: tx2, tx3 still queued
}

#[test]
fn test_drop_transaction_past_deadline() {
    // Setup: Transaction queued at tick 10, deadline at tick 50
    // Action: process_queue() called at tick 51
    // Assert: Transaction dropped
    // Assert: Queue is empty
    // Assert: Transaction status = Dropped
}
```

**Partial Settlement Tests** (divisible transactions):
```rust
#[test]
fn test_partial_settlement_divisible_transaction() {
    // Setup: BANK_A has 300000, transaction for 1000000 (divisible)
    // Action: Try to settle 300000 of the transaction
    // Assert: Partial settlement succeeds
    // Assert: Transaction status = PartiallySettled
    // Assert: Remaining amount = 700000
}

#[test]
fn test_indivisible_transaction_must_settle_fully() {
    // Setup: BANK_A has 300000, transaction for 500000 (indivisible)
    // Action: Try to settle
    // Assert: Queued (can't partially settle)
}
```

**Error Handling Tests**:
```rust
#[test]
fn test_agent_not_found_error() {
    // Setup: Transaction with sender_id="UNKNOWN_BANK"
    // Action: submit_transaction()
    // Assert: AgentNotFound error
}

#[test]
fn test_cannot_settle_already_settled() {
    // Setup: Transaction already fully settled
    // Action: try_settle() again
    // Assert: AlreadySettled error
}

#[test]
fn test_cannot_settle_dropped_transaction() {
    // Setup: Transaction dropped
    // Action: try_settle()
    // Assert: Dropped error
}
```

**Balance Conservation Tests** (Critical invariant):
```rust
#[test]
fn test_balance_conservation_on_settlement() {
    // Setup: Total system balance = BANK_A + BANK_B + BANK_C
    // Action: Multiple settlements between agents
    // Assert: Total system balance unchanged
}

#[test]
fn test_balance_conservation_on_queue_processing() {
    // Setup: Queued transactions
    // Action: process_queue() settles some, leaves others queued
    // Assert: Total system balance unchanged
}
```

### 4.3 Property-Based Tests

**Using `proptest` crate**:
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn prop_balance_conservation(
        initial_balances in prop::collection::vec(0i64..10_000_000, 2..10),
        tx_amounts in prop::collection::vec(1i64..1_000_000, 5..20),
    ) {
        // Generate random agents with random balances
        // Generate random transactions
        // Process all settlements
        // Assert: Sum of all balances unchanged
    }

    #[test]
    fn prop_settlement_is_atomic(
        sender_balance in 0i64..10_000_000,
        tx_amount in 1i64..10_000_000,
    ) {
        // Either settlement fully succeeds (both debit and credit occur)
        // Or settlement fully fails (neither debit nor credit occur)
        // Never partial state (only debit without credit)
    }
}
```

---

## 5. Implementation Timeline

### Phase 3a: Basic RTGS (Estimated: 2-3 days)

**Day 1: Core Settlement Logic**
- [ ] Write test cases for `try_settle()`
- [ ] Implement `try_settle()` in `backend/src/settlement/rtgs.rs`
- [ ] Write test cases for `submit_transaction()`
- [ ] Implement `submit_transaction()`
- [ ] Add `rtgs_queue` to `SimulationState`
- [ ] Run tests, ensure all pass

**Day 2: Queue Processing**
- [ ] Write test cases for `process_queue()`
- [ ] Implement `process_queue()` with FIFO retry
- [ ] Write test cases for deadline expiration
- [ ] Implement deadline-based transaction dropping
- [ ] Write balance conservation tests
- [ ] Run full test suite

**Day 3: Integration & Refinement**
- [ ] Add property-based tests (proptest)
- [ ] Test error handling paths
- [ ] Add documentation comments
- [ ] Integration test: Full simulation flow
- [ ] Commit Phase 3a

**Future (Phase 4): LSM Foundation**
- [ ] Bilateral netting implementation
- [ ] Cycle detection (3-cycles, 4-cycles)
- [ ] LSM coordinator integration

---

## 6. Integration Points

### 6.1 With Phase 1-2 Code

**No modifications needed to**:
- ✅ `backend/src/models/transaction.rs`
- ✅ `backend/src/models/agent.rs`
- ✅ `backend/src/core/time.rs`
- ✅ `backend/src/rng/xorshift.rs`

**New module**:
- ➕ `backend/src/settlement/rtgs.rs` (new)
- ➕ `backend/src/settlement/mod.rs` (new)

**Extend**:
- ✏️ `backend/src/models/state.rs` (add `rtgs_queue` field)
- ✏️ `backend/src/models/mod.rs` (export `SimulationState`)
- ✏️ `backend/src/lib.rs` (export settlement module)

### 6.2 With Future Orchestrator (Phase 4)

**Orchestrator will call**:
```rust
// Each tick
for new_transaction in arrivals {
    rtgs::submit_transaction(&mut state, new_transaction, current_tick)?;
}

// Process queue (retry pending transactions)
let result = rtgs::process_queue(
    &mut state.agents,
    &mut state.transactions,
    &mut state.rtgs_queue,
    current_tick,
);

// (Phase 4) If queue still has items, invoke LSM
if !state.rtgs_queue.is_empty() {
    lsm::attempt_netting(&mut state, current_tick)?;
}
```

---

## 7. Success Criteria

### Phase 3a Completion Checklist

**Functionality**:
- [ ] Immediate settlement works for sufficient liquidity
- [ ] Transactions queue when liquidity insufficient
- [ ] Queue processing retries each tick
- [ ] Transactions drop when past deadline
- [ ] Balance updates are atomic (debit sender, credit receiver together)
- [ ] Partial settlement works for divisible transactions
- [ ] Indivisible transactions settle only when full amount available

**Testing**:
- [ ] All unit tests pass (15+ tests)
- [ ] Property-based tests pass (balance conservation, atomicity)
- [ ] Integration test demonstrates full flow
- [ ] Error cases handled gracefully

**Code Quality**:
- [ ] All functions documented with doc comments
- [ ] Examples in doc comments compile and run
- [ ] Code follows Rust best practices (clippy clean)
- [ ] No unsafe code
- [ ] All public APIs use Result<T, E> for error handling

**Documentation**:
- [ ] This plan document updated with actual implementation notes
- [ ] CLAUDE.md updated with settlement patterns
- [ ] Phase 3 checkpoint summary created

---

## 8. Alignment with T2-Style RTGS

### 8.1 Core Features Match

| T2 Feature | Phase 3 Implementation | Status |
|------------|------------------------|--------|
| Central bank settlement accounts | `Agent.balance` | ✅ Phase 1 |
| Intraday credit | `Agent.credit_limit` | ✅ Phase 1 |
| Immediate settlement (RTGS) | `rtgs::try_settle()` | ✅ Phase 3 |
| Central queue | `SimulationState.rtgs_queue` | ✅ Phase 3 |
| Balance + credit check | `Agent.available_liquidity()` | ✅ Phase 1 |
| Bilateral offsetting (LSM) | `lsm::bilateral()` | ⏳ Phase 4 |
| Cycle detection (LSM) | `lsm::cycles()` | ⏳ Phase 4 |
| Priorities | `Transaction.priority` | ⏳ Future |
| Timed transactions | Not yet | ⏳ Future |

### 8.2 Settlement Flow Alignment

**T2 Flow** (game_concept_doc.md):
1. Payment order submitted to RTGS
2. Immediate settlement attempt (balance + credit check)
3. If insufficient → central queue
4. Queue retry each tick
5. LSM optimisation pass (bilateral, cycles)

**Our Implementation**:
1. `submit_transaction()` ← Payment order
2. `try_settle()` ← Immediate attempt
3. Add to `rtgs_queue` if failed
4. `process_queue()` each tick ← Queue retry
5. (Phase 4) `lsm::process()` ← Optimization

✅ **Perfect alignment**

---

## 9. Next Steps After Phase 3

### Phase 4: LSM (Liquidity-Saving Mechanisms)

**Scope**:
- Bilateral netting (A owes B 100, B owes A 80 → net 20)
- 3-cycle detection (A→B→C→A)
- 4-cycle detection (A→B→C→D→A)
- LSM coordinator (when to invoke, priority handling)

**Prerequisites**:
- Phase 3 complete ✅ (RTGS + queue)
- Graph algorithms ready (cycle detection)

**Estimated Effort**: 4-5 days

### Phase 5: Orchestrator

**Scope**:
- Tick loop (advance time, process events)
- Arrival generation (deterministic RNG)
- Policy evaluation hooks (future)
- Cost accrual (liquidity, delay, penalty)

**Prerequisites**:
- Phase 3 complete ✅
- Phase 4 complete (LSM)

**Estimated Effort**: 3-4 days

---

## 10. Appendix: Code Patterns

### Pattern 1: Atomic Settlement

```rust
// ✅ CORRECT: Debit and credit together, or neither
fn try_settle(...) -> Result<(), SettlementError> {
    // Pre-check (no state change yet)
    if !sender.can_pay(amount) {
        return Err(InsufficientLiquidity);
    }

    // Atomic state change (both or neither)
    sender.debit(amount)?;  // If this fails, nothing changed yet
    receiver.credit(amount); // Now both happen together
    transaction.settle(amount, tick)?;

    Ok(())
}
```

### Pattern 2: Queue Iteration with Filtering

```rust
// ✅ CORRECT: Drain queue, filter settled/dropped, re-add pending
let mut still_pending = Vec::new();

for tx_id in queue.drain(..) {
    match attempt_settlement(...) {
        Ok(()) => {}, // Settled, don't re-add
        Err(InsufficientLiquidity) => still_pending.push(tx_id), // Re-add
        Err(_) => {}, // Dropped or error, don't re-add
    }
}

*queue = still_pending; // Replace queue
```

### Pattern 3: Balance Conservation Invariant

```rust
#[test]
fn test_balance_conservation() {
    let total_before: i64 = state.agents.values()
        .map(|agent| agent.balance())
        .sum();

    // ... perform settlements ...

    let total_after: i64 = state.agents.values()
        .map(|agent| agent.balance())
        .sum();

    assert_eq!(total_before, total_after);
}
```

---

## Conclusion

**Phase 1-2 Assessment**: ✅ **Well-designed, no changes needed**

The current `Agent` and `Transaction` models correctly represent T2-style central bank settlement. The architecture properly separates:
- **Settlement accounts** (Agent.balance at central bank)
- **Payment orders** (Transaction between banks)
- **Settlement engine** (Phase 3, to be implemented)

**Phase 3 Plan**: ✅ **Clear scope, ready to implement**

This plan follows TDD principles with comprehensive test coverage before implementation. The RTGS settlement engine will build on Phase 1-2 primitives without breaking changes.

**Alignment with T2**: ✅ **Excellent**

Our design matches the T2-style flow described in game_concept_doc.md. The central bank intermediary model is correctly represented, and we're implementing the exact settlement logic described in the specification.

---

*Ready to proceed with Phase 3 implementation following this plan.*
