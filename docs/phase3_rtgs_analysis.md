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

## 9. Phase 3b: LSM (Liquidity-Saving Mechanisms) - Detailed Plan

### 9.1 LSM Overview & Motivation

**From game_concept_doc.md Section 4.3, 6, 7:**

> "**LSM/optimisation** tries **offsetting** and **multilateral cycles/batches** to release queued items with minimal net liquidity."

> "RTGS aims for fast real-time settlement **with reduced liquidity**, so systems run **optimisation procedures** continuously to dissolve queues via offsetting and cycles."

> "LSMs alleviate [gridlock] but still need *feed* of releasable items."

**Why LSM Matters**:
1. **Reduces liquidity requirements** - Banks can settle payments with less available balance
2. **Prevents gridlock** - Circular dependencies (A→B→C→A) can be resolved without liquidity injection
3. **Improves efficiency** - T2 studies show LSM "notably reduces delay and liquidity need" (game_concept_doc.md Section 6)
4. **Core T2 feature** - Continuous queue-dissolving via offsetting & cycles (game_concept_doc.md Appendix A)

**Phase 3b Scope**:
- ✅ Bilateral offsetting (A↔B payments cancel partially/fully)
- ✅ Cycle detection and settlement (A→B→C→A, A→B→C→D→A)
- ✅ LSM coordinator (when to invoke, integration with RTGS queue)
- ⚠️ Batch optimization under bank caps (optional/future)

### 9.2 LSM Algorithms Design

#### 9.2.1 Bilateral Offsetting (A↔B)

**Concept** (game_concept_doc.md Section 4.3):
```
If Bank A owes Bank B 500k AND Bank B owes Bank A 300k
→ Net: A owes B 200k (settle only the net)
→ Saves 300k liquidity for both banks
```

**Algorithm**:
```rust
/// Find all bilateral pairs in queue and offset them
pub fn bilateral_offset(
    state: &mut SimulationState,
    tick: usize,
) -> BilateralOffsetResult {
    // 1. Build bilateral payment matrix from queue
    //    Map<(AgentA, AgentB), Vec<TxId>>

    // 2. For each pair (A,B):
    //    - Calculate sum A→B
    //    - Calculate sum B→A
    //    - If both > 0: offset min(sum_AB, sum_BA)

    // 3. Settle offsetting payments:
    //    - If A→B sum > B→A sum:
    //      - Settle B→A payments fully
    //      - Partially settle A→B payments
    //    - Else vice versa

    // 4. Return statistics on offset value
}
```

**Example Test Case** (from test coverage analysis):
```rust
// BANK_A: 100k balance, wants to send 500k to B (queued)
// BANK_B: 100k balance, wants to send 400k to A (queued)
//
// Without LSM: Both stuck (bilateral gridlock)
// With LSM: Offset 400k, A sends net 100k (uses own balance)
//
// Result: Both transactions settled, using only 100k liquidity total
```

**Edge Cases**:
- Exact balance (500k↔500k) → both settle fully, zero net
- Multiple transactions in same direction (3 A→B, 2 B→A)
- Divisible vs indivisible transactions
- Partial offset when liquidity still insufficient for net

#### 9.2.2 Cycle Detection (A→B→C→A)

**Concept** (game_concept_doc.md Section 4.3):
```
If A→B (500k), B→C (500k), C→A (500k) all queued
→ Detect cycle A→B→C→A
→ Settle min(500k, 500k, 500k) = 500k on cycle
→ All 3 transactions settle with ZERO net liquidity!
```

**Algorithm** (Tarjan's SCC or DFS-based):
```rust
/// Detect cycles in queued payment graph
pub fn detect_cycles(
    state: &SimulationState,
    max_cycle_length: usize,
) -> Vec<Cycle> {
    // 1. Build directed graph from queued transactions
    //    Node = Agent, Edge = Transaction (with amount)

    // 2. Run cycle detection (DFS with visited tracking)
    //    - Find simple cycles (no repeated nodes)
    //    - Limit to cycles of length 3-5 (configurable)

    // 3. For each cycle found:
    //    - Calculate min amount on cycle
    //    - Check if all participants have min liquidity
    //    - Store cycle metadata (agents, transactions, min_amount)

    // 4. Return cycles sorted by potential value settled
}

pub struct Cycle {
    agents: Vec<String>,           // [A, B, C, A]
    transactions: Vec<String>,      // [tx_ab, tx_bc, tx_ca]
    min_amount: i64,                // Bottleneck amount
    total_value: i64,               // Sum of all tx amounts
}
```

**Cycle Settlement**:
```rust
/// Settle a detected cycle
pub fn settle_cycle(
    state: &mut SimulationState,
    cycle: &Cycle,
    tick: usize,
) -> Result<CycleSettlementResult, SettlementError> {
    // 1. Validate cycle still valid (txs still queued)

    // 2. For each transaction in cycle:
    //    - If amount == min_amount: settle fully
    //    - If amount > min_amount: partial settle min_amount

    // 3. Update balances in circular fashion:
    //    A: -min + min = 0 (net zero)
    //    B: -min + min = 0
    //    C: -min + min = 0

    // 4. Remove settled/partially-settled txs from queue

    // 5. Return statistics
}
```

**Example Test Case** (game_concept_doc.md Section 11, Test 2):
```rust
// Four-bank ring: A→B→C→D→A, each wants to send 500k
// Each bank has only 100k liquidity
//
// Without LSM: Complete gridlock (all 4 queued)
// With LSM: Detect 4-cycle, settle 500k on cycle
//           Each bank: -500k + 500k = net 0
//
// Result: All 4 transactions settled with ONLY initial 100k each
```

**Edge Cases**:
- Multiple cycles (choose which to settle first?)
- Nested cycles (A→B→C→A, A→C→A)
- Cycles with unequal amounts (settle min, partially settle rest)
- Cycle contains indivisible transactions

#### 9.2.3 LSM Coordinator

**Concept**: When and how to invoke LSM procedures

**Decision Points** (game_concept_doc.md Section 3.1, 7):
```
1. After queue processing (each tick)
   → If queue still has items, run LSM pass

2. Priority:
   → Bilateral offsetting first (cheaper, O(n²))
   → Cycle detection second (more expensive, exponential worst-case)

3. Iteration:
   → Bilateral may create new settlement opportunities
   → Re-run queue processing after LSM
   → Limit iterations to prevent infinite loops
```

**Implementation**:
```rust
/// LSM coordinator - main entry point
pub fn run_lsm_pass(
    state: &mut SimulationState,
    config: &LsmConfig,
    tick: usize,
) -> LsmPassResult {
    let mut total_settled_value = 0i64;
    let mut iterations = 0;
    const MAX_ITERATIONS: usize = 3;

    while iterations < MAX_ITERATIONS && !state.rtgs_queue.is_empty() {
        iterations += 1;

        // 1. Bilateral offsetting
        if config.enable_bilateral {
            let bilateral_result = bilateral_offset(state, tick);
            total_settled_value += bilateral_result.offset_value;

            // If settlements occurred, retry basic queue processing
            if bilateral_result.settlements_count > 0 {
                let queue_result = process_queue(state, tick);
                total_settled_value += queue_result.settled_value;
            }
        }

        // 2. Cycle detection and settlement
        if config.enable_cycles && !state.rtgs_queue.is_empty() {
            let cycles = detect_cycles(state, config.max_cycle_length);

            for cycle in cycles.iter().take(config.max_cycles_per_tick) {
                if let Ok(result) = settle_cycle(state, cycle, tick) {
                    total_settled_value += result.settled_value;
                }
            }

            // Retry queue processing after cycle settlements
            if !cycles.is_empty() {
                let queue_result = process_queue(state, tick);
                total_settled_value += queue_result.settled_value;
            }
        }

        // 3. Check if further iteration would help
        if total_settled_value == 0 {
            break; // No progress, stop iterating
        }
    }

    LsmPassResult {
        iterations_run: iterations,
        total_settled_value,
        final_queue_size: state.queue_size(),
    }
}
```

### 9.3 LSM Test Strategy

**Test Categories**:

1. **Bilateral Offsetting Tests**
   - Exact bilateral match (500k↔500k)
   - Asymmetric bilateral (500k↔300k, net 200k)
   - Multiple transactions same pair (3×100k A→B, 2×100k B→A)
   - Insufficient liquidity for net (offset 400k, but A can't pay net 100k)
   - Mixed divisible/indivisible transactions

2. **Cycle Detection Tests**
   - 3-cycle detection (A→B→C→A)
   - 4-cycle detection (A→B→C→D→A)
   - 5-cycle detection
   - Multiple disjoint cycles
   - Nested cycles (choose correctly)
   - Cycle with unequal amounts (partial settlement)

3. **LSM Coordinator Tests**
   - Bilateral resolves, enables queue processing
   - Cycle settlement resolves, enables more settlements
   - Multi-iteration convergence
   - Max iteration limit prevents infinite loops
   - Config toggles (disable bilateral, disable cycles)

4. **LSM Ablation Tests** (game_concept_doc.md Section 8, 11)
   - Same scenario with/without LSM
   - Measure: queue size, delay, liquidity usage
   - Validate: LSM reduces all three metrics

### 9.4 Implementation Plan

**Day 1-2: Bilateral Offsetting**
- [ ] Design bilateral payment matrix data structure
- [ ] Write bilateral offsetting tests (5 tests)
- [ ] Implement `bilateral_offset()` function
- [ ] Implement partial settlement for offsets
- [ ] Verify tests pass

**Day 3-4: Cycle Detection**
- [ ] Design payment graph representation
- [ ] Write cycle detection tests (6 tests)
- [ ] Implement cycle detection (DFS-based, limit length)
- [ ] Implement `settle_cycle()` function
- [ ] Handle partial cycle settlements
- [ ] Verify tests pass

**Day 5: LSM Coordinator**
- [ ] Design LsmConfig and result types
- [ ] Write coordinator tests (4 tests)
- [ ] Implement `run_lsm_pass()` with iteration
- [ ] Integration with existing `process_queue()`
- [ ] Verify tests pass

**Day 6: LSM Ablation & Optimization**
- [ ] Write ablation study tests (compare LSM on/off)
- [ ] Implement game_concept_doc.md Section 11 Test 2 (four-bank ring)
- [ ] Performance optimization (graph caching, early exit)
- [ ] Documentation
- [ ] Commit Phase 3b

### 9.5 Module Structure

**New Module**: `backend/src/settlement/lsm.rs`

```rust
// Bilateral offsetting
pub fn bilateral_offset(state: &mut SimulationState, tick: usize)
    -> BilateralOffsetResult;

// Cycle detection
pub fn detect_cycles(state: &SimulationState, max_length: usize)
    -> Vec<Cycle>;
pub fn settle_cycle(state: &mut SimulationState, cycle: &Cycle, tick: usize)
    -> Result<CycleSettlementResult, SettlementError>;

// Coordinator
pub fn run_lsm_pass(state: &mut SimulationState, config: &LsmConfig, tick: usize)
    -> LsmPassResult;

// Configuration
pub struct LsmConfig {
    pub enable_bilateral: bool,
    pub enable_cycles: bool,
    pub max_cycle_length: usize,      // Default: 4
    pub max_cycles_per_tick: usize,   // Default: 10
}

// Results
pub struct BilateralOffsetResult {
    pub pairs_found: usize,
    pub offset_value: i64,
    pub settlements_count: usize,
}

pub struct CycleSettlementResult {
    pub cycle_length: usize,
    pub settled_value: i64,
    pub transactions_affected: usize,
}

pub struct LsmPassResult {
    pub iterations_run: usize,
    pub total_settled_value: i64,
    pub final_queue_size: usize,
}
```

### 9.6 Integration with Orchestrator (Future Phase 4)

**Orchestrator tick loop** (extended):
```rust
// Each tick
for new_transaction in arrivals {
    rtgs::submit_transaction(&mut state, new_transaction, current_tick)?;
}

// 1. Basic queue processing (FIFO retry)
let queue_result = rtgs::process_queue(&mut state, current_tick);

// 2. If queue still has items, invoke LSM
if !state.rtgs_queue.is_empty() {
    let lsm_result = lsm::run_lsm_pass(&mut state, &lsm_config, current_tick);

    // Log LSM effectiveness
    metrics.lsm_settled_value += lsm_result.total_settled_value;
    metrics.lsm_iterations += lsm_result.iterations_run;
}

// 3. Accrue costs (liquidity, delays, etc.)
// ...
```

### 9.7 Performance Considerations

**Complexity**:
- Bilateral offsetting: O(n²) worst case (all pairs), but typically O(n×m) where m = avg counterparties
- Cycle detection: Exponential worst case, but limited by max_cycle_length and queue size
- Typical queue size: 10-50 transactions → acceptable performance

**Optimizations**:
1. **Early exit**: If no bilateral pairs found, skip cycle detection
2. **Graph caching**: Build payment graph once, reuse for cycle detection
3. **Incremental updates**: Only rebuild graph when queue changes significantly
4. **Cycle length limits**: Default max_cycle_length=4, configurable
5. **Max cycles per tick**: Limit to top 10 cycles by value

**Benchmarks to add**:
- Bilateral offsetting on 100 queued transactions
- Cycle detection on dense payment graph (all-to-all)
- Full LSM pass on gridlocked scenario (worst case)

### 9.8 Success Criteria

**Functionality**:
- [ ] Bilateral offsetting correctly identifies and settles A↔B pairs
- [ ] Cycle detection finds 3-cycles, 4-cycles, 5-cycles
- [ ] Cycle settlement handles partial settlements correctly
- [ ] LSM coordinator iterates until convergence or max iterations
- [ ] Config toggles work (disable bilateral, disable cycles)

**Testing**:
- [ ] 15+ LSM-specific tests pass
- [ ] Game concept test plan item 2 (four-bank ring) passes
- [ ] LSM ablation study shows measurable improvement
- [ ] All previous tests (128) still pass

**Code Quality**:
- [ ] Clear documentation of algorithms
- [ ] Examples in doc comments
- [ ] Performance benchmarks added
- [ ] Clippy clean, no unsafe code

**Alignment with T2**:
- [ ] Continuous optimization (each tick, if queue non-empty)
- [ ] Bilateral + cycle detection (core LSM features)
- [ ] Minimal liquidity usage (net settlements)
- [ ] Gridlock resolution demonstrated

---

## 10. Phase 4: Orchestrator (After Phase 3b)

### Phase 4 Scope

**Orchestrator Module** (`backend/src/orchestrator/`):
- Tick loop (advance time, process events)
- Arrival generation (deterministic RNG)
- Integration: RTGS + LSM + queue processing
- Cost accrual (liquidity, delay, penalty)
- Metrics collection and reporting

**Prerequisites**:
- Phase 3a complete ✅ (RTGS + queue)
- Phase 3b complete (LSM)

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
