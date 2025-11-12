# Backend Refactoring: DRY Principle Analysis

**Date**: 2025-11-12
**Status**: Analysis Complete - Ready for Implementation
**Impact**: ~550 lines of code reduction (58% in affected areas)

---

## Executive Summary

This document identifies **7 major categories** of DRY (Don't Repeat Yourself) violations across the Rust backend codebase. The analysis reveals opportunities to reduce code duplication by approximately **58% in affected areas** (~550 lines), with the most critical issues found in FFI event serialization and Python configuration validation.

### Key Findings

| Priority | Category | Severity | Impact | Lines Saved |
|----------|----------|----------|---------|-------------|
| 🔴 P0 | FFI Event Serialization | Critical | 50% reduction | ~150 lines |
| 🟠 P1 | Python Config Validation | High | 67% reduction | ~100 lines |
| 🟡 P2 | State Access Patterns | Medium | 60% reduction | ~60 lines |
| 🟡 P2 | Queue Processing | Medium | 60% reduction | ~120 lines |
| 🟡 P3 | Test Setup Code | Medium | 75% reduction | ~60 lines |
| 🟢 P4 | Cost Calculations | Low | 50% reduction | ~30 lines |
| 🟢 P4 | Policy Evaluation | Low | 60% reduction | ~30 lines |

**Total Potential Savings**: ~550 lines across 7 categories

---

## 1. FFI Event Serialization 🔴 CRITICAL

### Priority: P0 (Immediate)

### Problem Statement

**Location**: `backend/src/ffi/orchestrator.rs`
**Lines**: 964-1112 (`get_tick_events`) and 1135-1284 (`get_all_events`)
**Impact**: ~300 lines of near-identical code duplicated twice

The event serialization code for converting Rust `Event` enums to Python dictionaries is duplicated across two methods. The only difference is the source of events (filtered by tick vs. all events).

### Current Code Pattern

```rust
// In get_tick_events (lines 976-1112) - ~136 lines
match event {
    Event::Arrival { tx_id, sender_id, receiver_id, amount, deadline, priority, is_divisible, .. } => {
        event_dict.set_item("event_type", "arrival")?;
        event_dict.set_item("tick", event.tick())?;
        event_dict.set_item("tx_id", tx_id)?;
        event_dict.set_item("sender_id", sender_id)?;
        event_dict.set_item("receiver_id", receiver_id)?;
        event_dict.set_item("amount", amount)?;
        event_dict.set_item("deadline", deadline)?;
        event_dict.set_item("priority", priority)?;
        event_dict.set_item("is_divisible", is_divisible)?;
    }
    Event::Settlement { tx_id, sender_id, receiver_id, amount, .. } => {
        event_dict.set_item("event_type", "settlement")?;
        event_dict.set_item("tick", event.tick())?;
        event_dict.set_item("tx_id", tx_id)?;
        event_dict.set_item("sender_id", sender_id)?;
        event_dict.set_item("receiver_id", receiver_id)?;
        event_dict.set_item("amount", amount)?;
    }
    // ... 15+ more event types with identical patterns ...
}

// In get_all_events (lines 1147-1284) - ~137 lines
// EXACT SAME CODE REPEATED VERBATIM!
```

**Duplication Count**: 17 event types × 2 methods = 34 duplicated match arms

### Proposed Refactoring

**Step 1**: Extract helper function for event serialization

```rust
/// Convert a single Event to Python dict
///
/// This is the single source of truth for event serialization to Python.
/// Used by both get_tick_events() and get_all_events().
fn event_to_py_dict(py: Python<'_>, event: &Event) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new_bound(py);

    // Common fields for all events
    dict.set_item("event_type", event.event_type_str())?;
    dict.set_item("tick", event.tick())?;

    // Event-specific fields
    match event {
        Event::Arrival { tx_id, sender_id, receiver_id, amount, deadline, priority, is_divisible, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("deadline", deadline)?;
            dict.set_item("priority", priority)?;
            dict.set_item("is_divisible", is_divisible)?;
        }
        Event::Settlement { tx_id, sender_id, receiver_id, amount, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
        }
        // ... all other event types (ONCE, not twice!)
    }

    Ok(dict)
}
```

**Step 2**: Simplify the two methods

```rust
fn get_tick_events(&self, py: Python, tick: usize) -> PyResult<Py<PyList>> {
    let events = self.inner.get_tick_events(tick);
    let py_list = PyList::empty_bound(py);

    for event in events {
        let event_dict = event_to_py_dict(py, &event)?;
        py_list.append(event_dict)?;
    }

    Ok(py_list.into())
}

fn get_all_events(&self, py: Python) -> PyResult<Py<PyList>> {
    let events = self.inner.event_log().events();
    let py_list = PyList::empty_bound(py);

    for event in events {
        let event_dict = event_to_py_dict(py, &event)?;
        py_list.append(event_dict)?;
    }

    Ok(py_list.into())
}
```

**Step 3**: Add helper method to Event enum (optional)

```rust
// In backend/src/models/event.rs
impl Event {
    /// Returns the event type as a string for Python serialization
    pub fn event_type_str(&self) -> &'static str {
        match self {
            Event::Arrival { .. } => "arrival",
            Event::Settlement { .. } => "settlement",
            Event::Queue { .. } => "queue",
            // ... etc
        }
    }
}
```

### Benefits

- ✅ Reduces ~300 lines to ~150 lines (50% reduction)
- ✅ Single source of truth for event serialization
- ✅ Adding new event types requires changes in only ONE place
- ✅ Reduces risk of divergence between `get_tick_events` and `get_all_events`
- ✅ Easier to maintain and debug
- ✅ Aligns with **Replay Identity** principle (single display logic)

### Testing Requirements

- [ ] Verify all existing events serialize correctly
- [ ] Test with real simulation runs
- [ ] Verify replay identity still works
- [ ] Run full integration test suite
- [ ] Performance benchmark (should be negligible impact)

### Estimated Effort

- **Time**: 2-3 hours
- **Risk**: Low (pure refactoring, no logic changes)
- **Files Modified**:
  - `backend/src/ffi/orchestrator.rs` (main changes)
  - `backend/src/models/event.rs` (optional helper method)

---

## 2. Python Config Validation Boilerplate 🟠 HIGH

### Priority: P1 (Week 1)

### Problem Statement

**Location**: `backend/src/ffi/types.rs`
**Lines**: Throughout `parse_orchestrator_config`, `parse_agent_config`, `parse_policy_config`, etc.
**Impact**: ~150 lines of repetitive boilerplate

Every field extraction from Python dictionaries uses an extremely verbose 4-line pattern that is repeated 50+ times.

### Current Code Pattern

```rust
// This pattern appears 50+ times across the file!
let ticks_per_day: usize = py_config
    .get_item("ticks_per_day")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'ticks_per_day'"))?
    .extract()?;

let num_days: usize = py_config
    .get_item("num_days")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'num_days'"))?
    .extract()?;

let rng_seed: u64 = py_config
    .get_item("rng_seed")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'rng_seed'"))?
    .extract()?;

// In parse_agent_config:
let id: String = py_agent
    .get_item("id")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'id'"))?
    .extract()?;

let opening_balance: i64 = py_agent
    .get_item("opening_balance")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'opening_balance'"))?
    .extract()?;
```

**Pattern Count**: 50+ instances of 4-line extraction → 200+ lines of boilerplate

### Proposed Refactoring

**Step 1**: Create helper functions

```rust
// In backend/src/ffi/types.rs or new backend/src/ffi/py_extract.rs

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Extract required field from Python dict with automatic error handling
///
/// # Example
/// ```
/// let ticks_per_day = extract_required::<usize>(&py_config, "ticks_per_day")?;
/// ```
pub fn extract_required<'py, T>(
    dict: &Bound<'py, PyDict>,
    field: &str,
) -> PyResult<T>
where
    T: FromPyObject<'py>,
{
    dict.get_item(field)?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Missing required field '{}'", field)
            )
        })?
        .extract()
}

/// Extract optional field from Python dict
///
/// Returns `None` if field is missing or is Python `None`.
///
/// # Example
/// ```
/// let threshold = extract_optional::<f64>(&py_config, "eod_rush_threshold")?;
/// let threshold = threshold.unwrap_or(0.8);  // Default value
/// ```
pub fn extract_optional<'py, T>(
    dict: &Bound<'py, PyDict>,
    field: &str,
) -> PyResult<Option<T>>
where
    T: FromPyObject<'py>,
{
    match dict.get_item(field)? {
        Some(value) if !value.is_none() => Ok(Some(value.extract()?)),
        _ => Ok(None),
    }
}

/// Extract field with default value
///
/// # Example
/// ```
/// let threshold = extract_with_default(&py_config, "eod_rush_threshold", 0.8)?;
/// ```
pub fn extract_with_default<'py, T>(
    dict: &Bound<'py, PyDict>,
    field: &str,
    default: T,
) -> PyResult<T>
where
    T: FromPyObject<'py>,
{
    Ok(extract_optional(dict, field)?.unwrap_or(default))
}
```

**Step 2**: Refactor config parsing functions

```rust
// BEFORE: 40+ lines of boilerplate
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    let ticks_per_day: usize = py_config
        .get_item("ticks_per_day")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'ticks_per_day'"))?
        .extract()?;

    let num_days: usize = py_config
        .get_item("num_days")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'num_days'"))?
        .extract()?;

    let rng_seed: u64 = py_config
        .get_item("rng_seed")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'rng_seed'"))?
        .extract()?;

    let eod_rush_threshold: f64 = match py_config.get_item("eod_rush_threshold")? {
        Some(v) => v.extract()?,
        None => 0.8,
    };

    // ... 10 more fields ...
}

// AFTER: ~15 lines, much clearer
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    let ticks_per_day = extract_required::<usize>(py_config, "ticks_per_day")?;
    let num_days = extract_required::<usize>(py_config, "num_days")?;
    let rng_seed = extract_required::<u64>(py_config, "rng_seed")?;
    let eod_rush_threshold = extract_with_default(py_config, "eod_rush_threshold", 0.8)?;
    let lsm_enabled = extract_with_default(py_config, "lsm_enabled", true)?;
    let max_bilateral_offsets = extract_with_default(py_config, "max_bilateral_offsets", 100)?;

    Ok(OrchestratorConfig {
        ticks_per_day,
        num_days,
        rng_seed,
        eod_rush_threshold,
        lsm_enabled,
        max_bilateral_offsets,
        // ... other fields
    })
}
```

### Benefits

- ✅ Reduces ~150 lines to ~50 lines (67% reduction)
- ✅ More readable and maintainable
- ✅ Consistent error messages
- ✅ Easy to add validation logic in one place
- ✅ Type-safe with Rust's type inference
- ✅ Self-documenting with clear function names

### Advanced Enhancement (Optional)

For even better ergonomics, consider a builder pattern or macro:

```rust
// Using declarative macro (optional advanced feature)
macro_rules! extract_config {
    ($dict:expr, {
        $($field:ident: $typ:ty $(= $default:expr)?),* $(,)?
    }) => {{
        $(
            let $field = extract_config!(@field $dict, stringify!($field), $typ $(, $default)?);
        )*
    }};

    (@field $dict:expr, $name:expr, $typ:ty, $default:expr) => {
        extract_with_default::<$typ>($dict, $name, $default)?
    };

    (@field $dict:expr, $name:expr, $typ:ty) => {
        extract_required::<$typ>($dict, $name)?
    };
}

// Usage:
extract_config!(py_config, {
    ticks_per_day: usize,
    num_days: usize,
    rng_seed: u64,
    eod_rush_threshold: f64 = 0.8,
    lsm_enabled: bool = true,
});
```

### Testing Requirements

- [ ] Test required field validation (missing field throws error)
- [ ] Test optional field handling (missing returns None)
- [ ] Test default value handling
- [ ] Test type conversion errors
- [ ] Test with all existing config types
- [ ] Ensure Python error messages are helpful

### Estimated Effort

- **Time**: 3-4 hours
- **Risk**: Low (straightforward refactoring)
- **Files Modified**:
  - `backend/src/ffi/types.rs` (main changes)
  - Possibly new file: `backend/src/ffi/py_extract.rs`

---

## 3. State Access Patterns 🟡 MEDIUM

### Priority: P2 (Week 2)

### Problem Statement

**Location**: Multiple files
- `backend/src/settlement/rtgs.rs` (lines 256-297)
- `backend/src/settlement/lsm.rs` (lines 373-490)
- `backend/src/orchestrator/engine.rs` (throughout)

**Impact**: ~100 lines of repetitive state access code

Accessing agents and transactions from `SimulationState` follows repetitive patterns with identical error handling across multiple modules.

### Current Code Patterns

**Pattern 1: Check and Transfer (RTGS)**

```rust
// Lines 256-293 in rtgs.rs
let can_pay = {
    let sender = state.get_agent(&sender_id).unwrap();
    sender.can_pay(amount)
};

if can_pay {
    // Perform settlement
    {
        let sender = state.get_agent_mut(&sender_id).unwrap();
        sender.debit(amount)?;
    }
    {
        let receiver = state.get_agent_mut(&receiver_id).unwrap();
        receiver.credit(amount);
    }

    // Mark transaction settled
    let tx = state.get_transaction_mut(&tx_id).unwrap();
    tx.settle(amount, tick)?;

    // Emit event
    state.event_log_mut().push(Event::Settlement { ... });
}
```

**Pattern 2: Bilateral Settlement (LSM)**

```rust
// Lines 428-456 in lsm.rs
for tx_id in txs_ab {
    if let Some(tx) = state.get_transaction(tx_id) {
        let amount = tx.remaining_amount();
        let sender_id = tx.sender_id().to_string();
        let receiver_id = tx.receiver_id().to_string();

        // Transfer balances
        state
            .get_agent_mut(&sender_id)
            .unwrap()
            .adjust_balance(-(amount as i64));
        state
            .get_agent_mut(&receiver_id)
            .unwrap()
            .adjust_balance(amount as i64);

        // Mark settled
        state
            .get_transaction_mut(tx_id)
            .unwrap()
            .settle(amount, tick)?;
    }
}
```

**Pattern 3: Similar patterns in orchestrator/engine.rs**

### Proposed Refactoring

**Step 1**: Add atomic operations to SimulationState

```rust
// In backend/src/models/state.rs

impl SimulationState {
    /// Execute atomic balance transfer between two agents
    ///
    /// Returns error if sender has insufficient liquidity.
    /// This is an atomic operation - either succeeds completely or fails without side effects.
    pub fn transfer_balance(
        &mut self,
        sender_id: &str,
        receiver_id: &str,
        amount: i64,
    ) -> Result<(), SettlementError> {
        // Validation: check sender exists and can pay
        let can_pay = self
            .get_agent(sender_id)
            .ok_or(SettlementError::AgentNotFound(sender_id.to_string()))?
            .can_pay(amount);

        if !can_pay {
            let available = self.get_agent(sender_id).unwrap().available_liquidity();
            return Err(SettlementError::InsufficientLiquidity {
                agent_id: sender_id.to_string(),
                required: amount,
                available,
            });
        }

        // Validate receiver exists
        if self.get_agent(receiver_id).is_none() {
            return Err(SettlementError::AgentNotFound(receiver_id.to_string()));
        }

        // Execute transfer atomically (both succeed or both fail)
        self.get_agent_mut(sender_id)
            .unwrap()
            .debit(amount)?;
        self.get_agent_mut(receiver_id)
            .unwrap()
            .credit(amount);

        Ok(())
    }

    /// Execute complete transaction settlement: transfer + mark settled + emit event
    ///
    /// This is the highest-level operation that combines all settlement steps.
    /// Used by RTGS and LSM for consistent settlement behavior.
    pub fn settle_transaction(
        &mut self,
        tx_id: &str,
        tick: usize,
    ) -> Result<(), SettlementError> {
        // Get transaction details (immutable borrow)
        let (sender_id, receiver_id, amount, is_partial) = {
            let tx = self
                .get_transaction(tx_id)
                .ok_or(SettlementError::TransactionNotFound(tx_id.to_string()))?;

            (
                tx.sender_id().to_string(),
                tx.receiver_id().to_string(),
                tx.remaining_amount(),
                tx.is_partially_settled(),
            )
        };

        // Execute balance transfer
        self.transfer_balance(&sender_id, &receiver_id, amount)?;

        // Mark transaction as settled
        self.get_transaction_mut(tx_id)
            .unwrap()
            .settle(amount, tick)?;

        // Emit settlement event
        self.event_log_mut().push(Event::Settlement {
            tick,
            tx_id: tx_id.to_string(),
            sender_id,
            receiver_id,
            amount,
            is_partial,
        });

        Ok(())
    }

    /// Settle multiple transactions in a batch (for LSM cycles)
    ///
    /// Returns (success_count, failure_count)
    pub fn settle_transaction_batch(
        &mut self,
        tx_ids: &[String],
        tick: usize,
    ) -> (usize, usize) {
        let mut success = 0;
        let mut failure = 0;

        for tx_id in tx_ids {
            match self.settle_transaction(tx_id, tick) {
                Ok(_) => success += 1,
                Err(_) => failure += 1,
            }
        }

        (success, failure)
    }
}
```

**Step 2**: Update settlement code to use helpers

```rust
// RTGS settlement becomes:
pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut still_pending = Vec::new();

    let tx_ids: Vec<String> = state.rtgs_queue_mut().drain(..).collect();

    for tx_id in tx_ids {
        // Simple one-line settlement!
        match state.settle_transaction(&tx_id, tick) {
            Ok(_) => settled_count += 1,
            Err(SettlementError::InsufficientLiquidity { .. }) => {
                still_pending.push(tx_id);
            }
            Err(e) => {
                eprintln!("Settlement error for {}: {:?}", tx_id, e);
            }
        }
    }

    *state.rtgs_queue_mut() = still_pending;

    QueueProcessingResult {
        settled_count,
        still_pending: state.rtgs_queue().len(),
    }
}

// LSM bilateral offset becomes:
for tx_id in &txs_ab {
    // One-line settlement instead of 10 lines!
    state.settle_transaction(tx_id, tick)?;
}
```

### Benefits

- ✅ Reduces ~100 lines to ~40 lines (60% reduction)
- ✅ Atomic operations prevent partial state corruption
- ✅ Centralized error handling
- ✅ Consistent event emission
- ✅ Single source of truth for settlement logic
- ✅ Easier to add invariant checks
- ✅ Better testability (test state operations in isolation)

### Testing Requirements

- [ ] Unit tests for `transfer_balance` (success and failure cases)
- [ ] Unit tests for `settle_transaction`
- [ ] Test insufficient liquidity handling
- [ ] Test missing agent/transaction errors
- [ ] Verify RTGS still works correctly
- [ ] Verify LSM still works correctly
- [ ] Integration tests for full settlement workflow

### Estimated Effort

- **Time**: 4-5 hours
- **Risk**: Medium (core settlement logic, requires careful testing)
- **Files Modified**:
  - `backend/src/models/state.rs` (add new methods)
  - `backend/src/settlement/rtgs.rs` (simplify)
  - `backend/src/settlement/lsm.rs` (simplify)
  - `backend/src/orchestrator/engine.rs` (possibly simplify)

---

## 4. Queue Processing Patterns 🟡 MEDIUM

### Priority: P2 (Week 2-3)

### Problem Statement

**Location**:
- `backend/src/settlement/rtgs.rs` (lines 353-451)
- `backend/src/settlement/lsm.rs` (lines 275-359, 428-492)

**Impact**: ~200 lines of similar queue iteration/processing logic

Both RTGS and LSM modules process queued transactions with nearly identical patterns:
1. Drain queue into temporary vector
2. Iterate over items
3. Attempt processing
4. Collect items that need requeuing
5. Restore queue with remaining items

### Current Code Patterns

**RTGS Queue Processing:**

```rust
pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut still_pending = Vec::new();

    // Drain queue
    let queue = state.rtgs_queue_mut();
    let tx_ids: Vec<String> = queue.drain(..).collect();

    // Process each item
    for tx_id in tx_ids {
        let transaction = state.get_transaction_mut(&tx_id).unwrap();

        if transaction.is_fully_settled() {
            continue;  // Drop from queue
        }

        // Attempt settlement
        let can_settle = /* check logic */;
        if can_settle {
            // settle logic
            settled_count += 1;
        } else {
            still_pending.push(tx_id.clone());  // Requeue
        }
    }

    // Restore queue
    *state.rtgs_queue_mut() = still_pending;

    QueueProcessingResult { settled_count, still_pending: state.rtgs_queue().len() }
}
```

**LSM Bilateral Processing (similar pattern):**

```rust
pub fn bilateral_offset(state: &mut SimulationState, tick: usize) -> BilateralOffsetResult {
    let mut settlements_count = 0;
    let mut to_remove: BTreeMap<String, ()> = BTreeMap::new();

    // Similar drain-process-restore pattern
    // ...

    // Batch removal
    if !to_remove.is_empty() {
        state.rtgs_queue_mut().retain(|id| !to_remove.contains_key(id));
    }
}
```

### Proposed Refactoring

**Step 1**: Create generic queue processor

```rust
// In backend/src/settlement/queue_processor.rs (new file)

/// Result of processing a single queued item
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcessResult {
    /// Item was successfully processed, remove from queue
    Processed,
    /// Item should remain in queue (same ID)
    RequeueSame,
    /// Item should be replaced with different ID
    RequeueDifferent(String),
    /// Item should be dropped from queue
    Drop,
}

/// Statistics from queue processing
#[derive(Debug, Default)]
pub struct QueueProcessStats {
    pub processed: usize,
    pub requeued: usize,
    pub dropped: usize,
}

/// Process queue with custom logic
///
/// This is a generic queue processing framework that:
/// 1. Drains the queue
/// 2. Applies processor function to each item
/// 3. Handles requeuing based on result
/// 4. Returns statistics
///
/// # Example
/// ```
/// let stats = process_queue_generic(
///     state,
///     tick,
///     |state, tx_id, tick| {
///         match state.settle_transaction(tx_id, tick) {
///             Ok(_) => ProcessResult::Processed,
///             Err(SettlementError::InsufficientLiquidity {..}) => ProcessResult::RequeueSame,
///             Err(_) => ProcessResult::Drop,
///         }
///     }
/// );
/// ```
pub fn process_queue_generic<F>(
    state: &mut SimulationState,
    tick: usize,
    mut process_fn: F,
) -> QueueProcessStats
where
    F: FnMut(&mut SimulationState, &str, usize) -> ProcessResult,
{
    let mut stats = QueueProcessStats::default();
    let mut still_pending = Vec::new();

    // Drain queue (takes ownership of items)
    let tx_ids: Vec<String> = state.rtgs_queue_mut().drain(..).collect();

    // Process each item
    for tx_id in tx_ids {
        match process_fn(state, &tx_id, tick) {
            ProcessResult::Processed => {
                stats.processed += 1;
            }
            ProcessResult::RequeueSame => {
                still_pending.push(tx_id);
                stats.requeued += 1;
            }
            ProcessResult::RequeueDifferent(new_id) => {
                still_pending.push(new_id);
                stats.requeued += 1;
            }
            ProcessResult::Drop => {
                stats.dropped += 1;
            }
        }
    }

    // Restore queue with remaining items
    *state.rtgs_queue_mut() = still_pending;

    stats
}

/// Process queue and filter items based on predicate
///
/// More efficient when you just need to remove items without processing.
pub fn filter_queue<F>(
    state: &mut SimulationState,
    mut keep_predicate: F,
) -> usize
where
    F: FnMut(&SimulationState, &str) -> bool,
{
    let original_size = state.rtgs_queue().len();
    state.rtgs_queue_mut().retain(|tx_id| keep_predicate(state, tx_id));
    original_size - state.rtgs_queue().len()
}
```

**Step 2**: Update RTGS to use generic processor

```rust
// In backend/src/settlement/rtgs.rs

use crate::settlement::queue_processor::{process_queue_generic, ProcessResult};

pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let stats = process_queue_generic(state, tick, |state, tx_id, tick| {
        // Check if already settled (shouldn't happen, but defensive)
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.is_fully_settled() {
                return ProcessResult::Drop;
            }
        }

        // Attempt settlement
        match state.settle_transaction(tx_id, tick) {
            Ok(_) => ProcessResult::Processed,
            Err(SettlementError::InsufficientLiquidity { .. }) => {
                // Not enough liquidity, keep in queue
                ProcessResult::RequeueSame
            }
            Err(e) => {
                eprintln!("Unexpected settlement error for {}: {:?}", tx_id, e);
                ProcessResult::Drop
            }
        }
    });

    QueueProcessingResult {
        settled_count: stats.processed,
        still_pending: state.rtgs_queue().len(),
    }
}
```

**Step 3**: Update LSM to use generic processor

```rust
// In backend/src/settlement/lsm.rs

pub fn bilateral_offset(state: &mut SimulationState, tick: usize) -> BilateralOffsetResult {
    // Find bilateral pairs (existing logic)
    let pairs = find_bilateral_pairs(state);

    let mut total_settled = 0;

    for (agent_a, agent_b, txs_ab, txs_ba) in pairs {
        // Settle all transactions in this bilateral offset
        for tx_id in &txs_ab {
            let stats = process_queue_generic(state, tick, |state, tx_id, tick| {
                match state.settle_transaction(tx_id, tick) {
                    Ok(_) => ProcessResult::Processed,
                    Err(_) => ProcessResult::Drop,
                }
            });
            total_settled += stats.processed;
        }

        // Same for txs_ba...
    }

    BilateralOffsetResult {
        settlements_count: total_settled,
        // ...
    }
}
```

### Benefits

- ✅ Reduces ~200 lines to ~80 lines (60% reduction)
- ✅ Consistent queue processing across all modules
- ✅ Easier to add new queue processing strategies
- ✅ Clear separation of concerns (processing logic vs queue management)
- ✅ Better testability (test queue processor independently)
- ✅ Statistics tracking built-in

### Testing Requirements

- [ ] Unit tests for `process_queue_generic`
- [ ] Test all ProcessResult variants
- [ ] Test empty queue handling
- [ ] Verify RTGS queue processing unchanged behavior
- [ ] Verify LSM queue processing unchanged behavior
- [ ] Performance testing (should be similar or faster)

### Estimated Effort

- **Time**: 4-6 hours
- **Risk**: Medium (requires careful design and testing)
- **Files Modified**:
  - New file: `backend/src/settlement/queue_processor.rs`
  - `backend/src/settlement/mod.rs` (add module)
  - `backend/src/settlement/rtgs.rs` (refactor)
  - `backend/src/settlement/lsm.rs` (refactor)

---

## 5. Test Setup Code 🟡 MEDIUM

### Priority: P3 (Week 3)

### Problem Statement

**Location**: Test modules across the codebase
- `backend/src/settlement/rtgs.rs` (lines 454-622 in `#[cfg(test)]`)
- `backend/src/models/transaction.rs` (lines 668-782 in tests)
- `backend/src/models/agent.rs` (lines 717-908 in tests)

**Impact**: ~80 lines of duplicated test helpers

Test setup functions like `create_agent`, `create_transaction`, `create_test_state` are duplicated across multiple test modules, leading to inconsistent test data and maintenance burden.

### Current Code Pattern

**In rtgs.rs tests:**
```rust
#[cfg(test)]
mod tests {
    use super::*;

    fn create_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
        Agent::new(id.to_string(), balance, credit_limit)
    }

    fn create_transaction(
        sender: &str,
        receiver: &str,
        amount: i64,
        arrival: usize,
        deadline: usize,
    ) -> Transaction {
        Transaction::new(
            sender.to_string(),
            receiver.to_string(),
            amount,
            arrival,
            deadline,
        )
    }

    fn create_test_state() -> SimulationState {
        let agents = vec![
            create_agent("BANK_A", 1_000_000, 500_000),
            create_agent("BANK_B", 1_000_000, 0),
        ];
        let mut state = SimulationState::new(agents);
        // ... more setup
        state
    }

    #[test]
    fn test_something() {
        let state = create_test_state();
        // ...
    }
}
```

**Similar helpers duplicated in:**
- `models/transaction.rs`
- `models/agent.rs`
- `settlement/lsm.rs`
- Possibly others

### Proposed Refactoring

**Step 1**: Create centralized test utilities module

```rust
// backend/src/test_utils.rs (new file)

//! Test utilities and fixtures
//!
//! This module provides common test setup functions used across the codebase.
//! Only compiled when running tests.

#![cfg(test)]

use crate::models::{Agent, Transaction, SimulationState};
use crate::core::CostRates;

/// Builder for creating test agents with sensible defaults
#[derive(Default)]
pub struct AgentBuilder {
    id: String,
    balance: i64,
    credit_limit: i64,
}

impl AgentBuilder {
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            balance: 1_000_000,  // $10,000 default
            credit_limit: 0,
        }
    }

    pub fn balance(mut self, balance: i64) -> Self {
        self.balance = balance;
        self
    }

    pub fn credit_limit(mut self, limit: i64) -> Self {
        self.credit_limit = limit;
        self
    }

    pub fn build(self) -> Agent {
        Agent::new(self.id, self.balance, self.credit_limit)
    }
}

/// Builder for creating test transactions with sensible defaults
#[derive(Default)]
pub struct TransactionBuilder {
    sender: String,
    receiver: String,
    amount: i64,
    arrival_tick: usize,
    deadline_tick: usize,
    priority: u8,
    is_divisible: bool,
}

impl TransactionBuilder {
    pub fn new(sender: impl Into<String>, receiver: impl Into<String>) -> Self {
        Self {
            sender: sender.into(),
            receiver: receiver.into(),
            amount: 100_000,  // $1,000 default
            arrival_tick: 0,
            deadline_tick: 100,
            priority: 5,
            is_divisible: false,
        }
    }

    pub fn amount(mut self, amount: i64) -> Self {
        self.amount = amount;
        self
    }

    pub fn deadline(mut self, deadline: usize) -> Self {
        self.deadline_tick = deadline;
        self
    }

    pub fn arrival(mut self, arrival: usize) -> Self {
        self.arrival_tick = arrival;
        self
    }

    pub fn priority(mut self, priority: u8) -> Self {
        self.priority = priority;
        self
    }

    pub fn divisible(mut self) -> Self {
        self.is_divisible = true;
        self
    }

    pub fn build(self) -> Transaction {
        Transaction::new(
            self.sender,
            self.receiver,
            self.amount,
            self.arrival_tick,
            self.deadline_tick,
            self.priority,
            self.is_divisible,
        )
    }
}

/// Common test fixtures
pub mod fixtures {
    use super::*;

    /// Create a simple two-agent test state
    ///
    /// Agents:
    /// - BANK_A: $10,000 balance, $5,000 credit limit
    /// - BANK_B: $10,000 balance, no credit
    pub fn simple_two_agent_state() -> SimulationState {
        let agents = vec![
            AgentBuilder::new("BANK_A")
                .balance(1_000_000)
                .credit_limit(500_000)
                .build(),
            AgentBuilder::new("BANK_B")
                .balance(1_000_000)
                .build(),
        ];

        SimulationState::new(agents, CostRates::default())
    }

    /// Create a complex multi-agent test state
    ///
    /// Agents: A, B, C, D with varying balances and credit
    pub fn multi_agent_state() -> SimulationState {
        let agents = vec![
            AgentBuilder::new("BANK_A").balance(5_000_000).credit_limit(1_000_000).build(),
            AgentBuilder::new("BANK_B").balance(2_000_000).credit_limit(500_000).build(),
            AgentBuilder::new("BANK_C").balance(1_000_000).build(),
            AgentBuilder::new("BANK_D").balance(500_000).build(),
        ];

        SimulationState::new(agents, CostRates::default())
    }

    /// Create state with one well-funded agent and one under-funded agent
    ///
    /// Useful for testing liquidity constraints
    pub fn liquidity_constrained_state() -> SimulationState {
        let agents = vec![
            AgentBuilder::new("RICH").balance(10_000_000).build(),
            AgentBuilder::new("POOR").balance(100_000).build(),
        ];

        SimulationState::new(agents, CostRates::default())
    }
}

/// Assertion helpers
pub mod assertions {
    use super::*;

    /// Assert agent has expected balance
    pub fn assert_balance(state: &SimulationState, agent_id: &str, expected: i64) {
        let agent = state.get_agent(agent_id).expect("Agent not found");
        assert_eq!(
            agent.balance(),
            expected,
            "Agent {} balance mismatch: expected {}, got {}",
            agent_id,
            expected,
            agent.balance()
        );
    }

    /// Assert transaction is fully settled
    pub fn assert_settled(state: &SimulationState, tx_id: &str) {
        let tx = state.get_transaction(tx_id).expect("Transaction not found");
        assert!(
            tx.is_fully_settled(),
            "Transaction {} should be settled but is not",
            tx_id
        );
    }

    /// Assert transaction is still pending
    pub fn assert_pending(state: &SimulationState, tx_id: &str) {
        let tx = state.get_transaction(tx_id).expect("Transaction not found");
        assert!(
            !tx.is_fully_settled(),
            "Transaction {} should be pending but is settled",
            tx_id
        );
    }
}
```

**Step 2**: Update tests to use centralized utilities

```rust
// In settlement/rtgs.rs tests

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::{AgentBuilder, TransactionBuilder, fixtures, assertions};

    #[test]
    fn test_rtgs_settles_with_sufficient_liquidity() {
        // BEFORE: 20 lines of setup
        // AFTER: 5 lines
        let mut state = fixtures::simple_two_agent_state();

        let tx = TransactionBuilder::new("BANK_A", "BANK_B")
            .amount(500_000)
            .build();

        state.add_transaction(tx);

        // Process
        let result = process_rtgs(&mut state, 0);

        // Verify using helpers
        assert_eq!(result.settled_count, 1);
        assertions::assert_balance(&state, "BANK_A", 500_000);
        assertions::assert_balance(&state, "BANK_B", 1_500_000);
    }

    #[test]
    fn test_rtgs_queues_insufficient_liquidity() {
        let mut state = fixtures::liquidity_constrained_state();

        let tx = TransactionBuilder::new("POOR", "RICH")
            .amount(200_000)  // More than POOR has
            .build();

        // ... test logic
    }
}
```

**Step 3**: Add to lib.rs

```rust
// In backend/src/lib.rs

#[cfg(test)]
pub mod test_utils;
```

### Benefits

- ✅ Eliminates ~80 lines of duplicated test code
- ✅ Consistent test data across all tests
- ✅ Builder pattern makes test intent clearer
- ✅ Easy to add new test fixtures
- ✅ Assertion helpers improve test readability
- ✅ Single source of truth for test setup

### Testing Requirements

- [ ] Verify all existing tests still pass
- [ ] Ensure test utilities are only compiled in test mode
- [ ] Document common test scenarios

### Estimated Effort

- **Time**: 3-4 hours
- **Risk**: Low (test-only changes)
- **Files Modified**:
  - New file: `backend/src/test_utils.rs`
  - `backend/src/lib.rs` (add module declaration)
  - All test modules (update to use new utilities)

---

## 6. Cost Calculation Patterns 🟢 LOW

### Priority: P4 (Future)

### Problem Statement

**Location**: `backend/src/orchestrator/engine.rs`
**Impact**: ~60 lines of similar calculation patterns

Cost calculations for different cost types (liquidity, delay, collateral) follow similar patterns with repeated floating-point arithmetic and rounding logic.

### Current Code Pattern

```rust
// Liquidity cost calculation
let liquidity_cost = if agent.is_using_credit() {
    let credit_used = agent.credit_used() as f64;
    (credit_used * cost_rates.overdraft_bps_per_tick).round() as i64
} else {
    0
};

// Delay cost calculation
let delay_cost = {
    let total_pending = calculate_total_pending(agent);
    let multiplier = if is_overdue { 5.0 } else { 1.0 };
    (total_pending as f64 * cost_rates.delay_cost_per_tick_per_cent * multiplier).round() as i64
};

// Collateral cost calculation
let collateral_cost = {
    let posted = agent.posted_collateral() as f64;
    (posted * cost_rates.collateral_cost_per_tick_bps).round() as i64
};

// Similar patterns repeated...
```

### Proposed Refactoring

```rust
// In backend/src/models/costs.rs (new file or add to existing)

/// Cost calculator with consistent rounding and rate application
pub struct CostCalculator<'a> {
    rates: &'a CostRates,
}

impl<'a> CostCalculator<'a> {
    pub fn new(rates: &'a CostRates) -> Self {
        Self { rates }
    }

    /// Calculate cost as: base_amount * rate (with proper rounding)
    ///
    /// All monetary amounts stay as i64, only intermediate calculation uses f64
    fn apply_rate(&self, base_amount: i64, rate: f64) -> i64 {
        ((base_amount as f64) * rate).round() as i64
    }

    pub fn liquidity_cost(&self, agent: &Agent) -> i64 {
        if agent.is_using_credit() {
            self.apply_rate(agent.credit_used(), self.rates.overdraft_bps_per_tick)
        } else {
            0
        }
    }

    pub fn delay_cost(&self, total_pending: i64, is_overdue: bool) -> i64 {
        let base_cost = self.apply_rate(
            total_pending,
            self.rates.delay_cost_per_tick_per_cent
        );

        if is_overdue {
            self.apply_rate(base_cost, self.rates.overdue_delay_multiplier)
        } else {
            base_cost
        }
    }

    pub fn collateral_cost(&self, agent: &Agent) -> i64 {
        self.apply_rate(
            agent.posted_collateral(),
            self.rates.collateral_cost_per_tick_bps
        )
    }

    /// Calculate all costs for an agent at once
    pub fn total_agent_costs(
        &self,
        agent: &Agent,
        total_pending: i64,
        is_overdue: bool,
    ) -> AgentCosts {
        AgentCosts {
            liquidity: self.liquidity_cost(agent),
            delay: self.delay_cost(total_pending, is_overdue),
            collateral: self.collateral_cost(agent),
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct AgentCosts {
    pub liquidity: i64,
    pub delay: i64,
    pub collateral: i64,
}

impl AgentCosts {
    pub fn total(&self) -> i64 {
        self.liquidity + self.delay + self.collateral
    }
}
```

### Benefits

- ✅ Reduces ~60 lines to ~30 lines (50% reduction)
- ✅ Centralized cost calculation logic
- ✅ Consistent rounding behavior
- ✅ Easier to add new cost types
- ✅ Better testability

### Estimated Effort

- **Time**: 2-3 hours
- **Risk**: Low
- **Priority**: Low (can wait)

---

## 7. Policy Evaluation Patterns 🟢 LOW

### Priority: P4 (Future)

### Problem Statement

**Location**: `backend/src/policy/tree/executor.rs`
**Impact**: ~50 lines of similar iteration patterns

Policy evaluation follows a repetitive pattern of iterating over queues, building context, and making decisions.

### Current Code Pattern

```rust
fn evaluate_queue(&mut self, agent: &Agent, state: &SimulationState, ...) -> Vec<ReleaseDecision> {
    let mut decisions = Vec::new();

    for tx_id in agent.outgoing_queue() {
        let tx = match state.get_transaction(tx_id) {
            Some(tx) => tx,
            None => continue,
        };

        let context = build_context(tx, agent, state, tick);
        let decision = self.evaluate(context);
        decisions.push(decision);
    }

    decisions
}
```

### Proposed Refactoring

```rust
trait QueueEvaluator {
    fn evaluate_transaction(
        &mut self,
        tx: &Transaction,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> ReleaseDecision;

    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Vec<ReleaseDecision> {
        agent.outgoing_queue()
            .iter()
            .filter_map(|tx_id| state.get_transaction(tx_id))
            .map(|tx| self.evaluate_transaction(tx, agent, state, tick))
            .collect()
    }
}
```

### Benefits

- ✅ Reduces boilerplate
- ✅ Consistent evaluation pattern
- ✅ Easier to add new policy types

### Estimated Effort

- **Time**: 2-3 hours
- **Risk**: Low
- **Priority**: Very Low (current code is already fairly clean)

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
**Goal**: Eliminate most severe duplication

1. **Day 1-2**: FFI Event Serialization (#1)
   - Extract `event_to_py_dict` helper
   - Update `get_tick_events` and `get_all_events`
   - Test with real simulations
   - **Expected**: 150 lines saved

2. **Day 3-4**: Python Config Validation (#2)
   - Create `extract_required` and `extract_optional` helpers
   - Refactor all config parsing functions
   - Test with various config files
   - **Expected**: 100 lines saved

3. **Day 5**: Testing and Integration
   - Run full test suite
   - Verify replay identity
   - Performance benchmarks
   - Code review

**Phase 1 Output**: ~250 lines saved, 50% of total goal achieved

### Phase 2: Medium Priority (Week 2-3)
**Goal**: Improve state management and queue processing

4. **Week 2 Day 1-3**: State Access Patterns (#3)
   - Add `transfer_balance` and `settle_transaction` to SimulationState
   - Update RTGS and LSM to use new methods
   - Comprehensive testing
   - **Expected**: 60 lines saved

5. **Week 2 Day 4-5**: Queue Processing (#4)
   - Create `queue_processor.rs` module
   - Implement `process_queue_generic`
   - Refactor RTGS and LSM
   - **Expected**: 120 lines saved

6. **Week 3**: Test Utilities (#5)
   - Create `test_utils.rs`
   - Refactor test modules
   - **Expected**: 60 lines saved

**Phase 2 Output**: Additional ~240 lines saved, 90% of total goal achieved

### Phase 3: Polish (Future)
**Goal**: Address remaining low-priority items

7. **Future**: Cost Calculations (#6)
   - Create `CostCalculator`
   - Refactor cost accrual logic
   - **Expected**: 30 lines saved

8. **Future**: Policy Evaluation (#7)
   - Only if more policy types are added
   - **Expected**: 30 lines saved

**Phase 3 Output**: Final ~60 lines saved, 100% of total goal achieved

---

## Success Metrics

### Code Quality Metrics

- [ ] **Lines of Code**: Reduce affected areas by ~550 lines (58%)
- [ ] **Cyclomatic Complexity**: Reduce complexity in settlement modules
- [ ] **Test Coverage**: Maintain or improve current coverage (>80%)
- [ ] **Build Time**: No significant regression (<5% increase acceptable)

### Functional Metrics

- [ ] **All Tests Pass**: 100% test pass rate after each refactoring
- [ ] **Replay Identity**: Perfect replay identity maintained
- [ ] **Performance**: No performance regression (baseline: 1000+ ticks/sec)
- [ ] **Determinism**: Same seed produces identical results

### Maintainability Metrics

- [ ] **Code Duplication**: Reduce duplication by 50%+
- [ ] **Module Cohesion**: Improve related-code grouping
- [ ] **API Clarity**: Clearer interfaces for state operations
- [ ] **Documentation**: Update relevant docs and comments

---

## Risk Assessment

### Low Risk Refactorings
✅ **#1 FFI Event Serialization**: Pure extraction, no logic changes
✅ **#2 Python Config Validation**: Helper functions, backward compatible
✅ **#5 Test Setup Code**: Test-only changes

### Medium Risk Refactorings
⚠️ **#3 State Access Patterns**: Touches core settlement logic
⚠️ **#4 Queue Processing**: Changes control flow patterns

**Mitigation**:
- Comprehensive testing before and after
- Incremental rollout (one module at a time)
- Performance benchmarks
- Keep original code in comments temporarily

### Low Risk (Low Priority)
🟢 **#6 Cost Calculations**: Can defer
🟢 **#7 Policy Evaluation**: Can defer

---

## Testing Strategy

### Before Refactoring
1. **Baseline Tests**: Run full test suite, record results
2. **Performance Baseline**: Benchmark key operations
3. **Replay Baseline**: Generate reference replay outputs

### During Refactoring
1. **Unit Tests**: Test new helper functions in isolation
2. **Integration Tests**: Test refactored modules
3. **Regression Tests**: Compare against baseline

### After Refactoring
1. **Full Test Suite**: Must achieve 100% pass rate
2. **Replay Identity**: Must match baseline byte-for-byte
3. **Performance**: Must meet performance targets
4. **Code Review**: Manual review of all changes

### Test Commands

```bash
# Rust tests
cd backend
cargo test --no-default-features

# Python tests (after rebuilding)
cd api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest

# Replay identity test
payment-sim run --config test.yaml --persist baseline.db --verbose > baseline.txt
payment-sim replay baseline.db --verbose > replay.txt
diff <(grep -v "Duration:" baseline.txt) <(grep -v "Duration:" replay.txt)

# Performance benchmark
payment-sim run --config benchmark.yaml --ticks 10000 --measure-performance
```

---

## Conclusion

This analysis identifies **7 categories of DRY violations** with a total potential reduction of **~550 lines of code** (58% in affected areas). The highest-impact refactorings are:

1. **FFI Event Serialization** (P0) - 150 lines saved
2. **Python Config Validation** (P1) - 100 lines saved
3. **Queue Processing** (P2) - 120 lines saved

These three alone account for **67% of the total savings** and should be prioritized.

The proposed refactorings align with the project's core principles:
- ✅ Maintain **determinism** (no logic changes)
- ✅ Preserve **replay identity** (single source of truth)
- ✅ Keep **FFI boundary minimal** (simplify serialization)
- ✅ Improve **maintainability** (reduce duplication)

**Recommended Next Steps**:
1. Review and approve this plan
2. Begin Phase 1 (Week 1) with FFI and config refactoring
3. Validate with comprehensive testing
4. Proceed to Phase 2 based on results

---

**Document Status**: ✅ Ready for Implementation
**Last Updated**: 2025-11-12
**Author**: Claude Code Analysis
**Reviewers**: [To be assigned]
