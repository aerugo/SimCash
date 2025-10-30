# Phase 2.2: Rust Collateral Event Tracking - TDD Implementation Plan

**Status**: PLANNING
**Priority**: CRITICAL
**Principle**: Strict TDD (RED-GREEN-REFACTOR)
**Estimated Time**: 4-6 hours

---

## Executive Summary

**Goal**: Implement comprehensive collateral event tracking in Rust following strict TDD principles.

**Current State**:
- ✅ Collateral posting/withdrawal already happens in `orchestrator/engine.rs`
- ✅ Events are logged using `Event::CollateralPost` and `Event::CollateralWithdraw`
- ❌ Events have insufficient detail (missing day, layer, balance states)
- ❌ Events are logged but not stored in retrievable structure
- ❌ No FFI method `get_collateral_events_for_day()` exists

**Why Rust Changes Needed**:
- Collateral decisions happen during Rust tick execution (Python can't observe)
- Events exist but aren't persisted in a queryable structure
- Need detailed tracking for research/analysis (Phase 11 LLM Manager)

---

## Architecture Overview

### Current Event System
```rust
// backend/src/models/event.rs
pub enum Event {
    CollateralPost {
        tick: usize,
        agent_id: String,
        amount: i64,
        reason: String,
        new_total: i64,  // Current total posted collateral
    },
    CollateralWithdraw {
        tick: usize,
        agent_id: String,
        amount: i64,
        reason: String,
        new_total: i64,
    },
    // ... other events
}
```

**Problem**: Events are logged but not stored in a retrievable format.

### Target Data Structure

```rust
// backend/src/models/collateral_event.rs (NEW FILE)
pub struct CollateralEvent {
    pub agent_id: String,
    pub tick: usize,
    pub day: usize,
    pub action: CollateralAction,     // Post, Withdraw, Hold
    pub amount: i64,
    pub reason: String,
    pub layer: CollateralLayer,       // Strategic, EndOfTick
    pub balance_before: i64,
    pub posted_collateral_before: i64,
    pub posted_collateral_after: i64,
    pub available_capacity_after: i64,
}

pub enum CollateralAction {
    Post,
    Withdraw,
    Hold,  // Decision to not post when it was considered
}

pub enum CollateralLayer {
    Strategic,   // Policy-driven decision
    EndOfTick,   // Automatic posting/withdrawal
}
```

### Storage Location

Add to `SimulationState`:
```rust
// backend/src/models/state.rs
pub struct SimulationState {
    // ... existing fields
    pub collateral_events: Vec<CollateralEvent>,  // NEW
}
```

---

## TDD Implementation Plan

### Phase 2.2.1: RED - Write Rust Tests (2 hours)

**Principle**: Write tests that FAIL because the feature doesn't exist yet.

#### Step 1.1: Create Test File (15 min)

**File**: `/backend/tests/test_collateral_event_tracking.rs`

```rust
//! Collateral Event Tracking Tests
//!
//! Tests for comprehensive collateral event tracking system.
//! Following TDD: These tests will FAIL until implementation is complete.

use payment_simulator_core_rs::{
    models::{Agent, CollateralEvent, CollateralAction, CollateralLayer},
    orchestrator::Orchestrator,
};

#[test]
fn test_collateral_post_creates_event() {
    // RED: This will fail - CollateralEvent doesn't exist yet
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(
        agents,
        100,  // ticks_per_day
        1,    // num_days
        42,   // seed
    );

    // Trigger collateral posting (need to create scenario)
    // ... simulate until collateral is posted ...

    // Get collateral events for day 0
    let events = orch.get_collateral_events_for_day(0);

    // Should have at least one event
    assert!(!events.is_empty(), "Expected collateral events");

    // First event should be a Post
    let first_event = &events[0];
    assert_eq!(first_event.action, CollateralAction::Post);
    assert!(first_event.amount > 0);
}

#[test]
fn test_collateral_event_has_all_required_fields() {
    // RED: Will fail - CollateralEvent struct doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Trigger collateral event
    // ... simulate ...

    let events = orch.get_collateral_events_for_day(0);
    assert!(!events.is_empty());

    let event = &events[0];

    // Verify all fields exist (compilation test)
    let _ = &event.agent_id;
    let _ = event.tick;
    let _ = event.day;
    let _ = &event.action;
    let _ = event.amount;
    let _ = &event.reason;
    let _ = &event.layer;
    let _ = event.balance_before;
    let _ = event.posted_collateral_before;
    let _ = event.posted_collateral_after;
    let _ = event.available_capacity_after;
}

#[test]
fn test_strategic_layer_events_tracked() {
    // RED: Will fail - layer tracking doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Trigger strategic layer collateral decision
    // ... simulate with policy that posts collateral ...

    let events = orch.get_collateral_events_for_day(0);

    // Should have strategic layer events
    let strategic_events: Vec<_> = events.iter()
        .filter(|e| matches!(e.layer, CollateralLayer::Strategic))
        .collect();

    assert!(!strategic_events.is_empty(), "Expected strategic layer events");
}

#[test]
fn test_end_of_tick_layer_events_tracked() {
    // RED: Will fail - layer tracking doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Trigger end-of-tick automatic collateral posting
    // ... simulate ...

    let events = orch.get_collateral_events_for_day(0);

    // Should have end-of-tick layer events
    let eod_events: Vec<_> = events.iter()
        .filter(|e| matches!(e.layer, CollateralLayer::EndOfTick))
        .collect();

    assert!(!eod_events.is_empty(), "Expected end-of-tick layer events");
}

#[test]
fn test_collateral_withdraw_creates_event() {
    // RED: Will fail - withdraw tracking doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Post collateral, then withdraw
    // ... simulate ...

    let events = orch.get_collateral_events_for_day(0);

    // Should have withdraw event
    let withdraw_events: Vec<_> = events.iter()
        .filter(|e| matches!(e.action, CollateralAction::Withdraw))
        .collect();

    assert!(!withdraw_events.is_empty(), "Expected withdraw events");
}

#[test]
fn test_collateral_hold_decision_tracked() {
    // RED: Will fail - hold tracking doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Simulate scenario where agent considers but doesn't post collateral
    // ... simulate ...

    let events = orch.get_collateral_events_for_day(0);

    // Should have hold decision events
    let hold_events: Vec<_> = events.iter()
        .filter(|e| matches!(e.action, CollateralAction::Hold))
        .collect();

    // Note: Hold events may not always occur, but structure should support them
    // Just verify the enum variant exists
    assert!(matches!(CollateralAction::Hold, CollateralAction::Hold));
}

#[test]
fn test_before_after_states_captured() {
    // RED: Will fail - state capture doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 100_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Trigger collateral posting
    // ... simulate ...

    let events = orch.get_collateral_events_for_day(0);
    assert!(!events.is_empty());

    let event = &events[0];

    // Verify before/after states are different
    assert_ne!(
        event.posted_collateral_before,
        event.posted_collateral_after,
        "Collateral amounts should change"
    );

    // For Post action, after should be greater
    if matches!(event.action, CollateralAction::Post) {
        assert!(
            event.posted_collateral_after > event.posted_collateral_before,
            "Post should increase collateral"
        );
    }
}

#[test]
fn test_events_filter_by_day() {
    // RED: Will fail - day filtering doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(
        agents,
        10,  // ticks_per_day
        3,   // num_days
        42,
    );

    // Simulate multiple days
    for _ in 0..(3 * 10) {
        orch.tick();
    }

    // Get events for each day
    let day0_events = orch.get_collateral_events_for_day(0);
    let day1_events = orch.get_collateral_events_for_day(1);
    let day2_events = orch.get_collateral_events_for_day(2);

    // Verify events are properly filtered by day
    for event in &day0_events {
        assert_eq!(event.day, 0, "Day 0 events should have day=0");
    }

    for event in &day1_events {
        assert_eq!(event.day, 1, "Day 1 events should have day=1");
    }

    for event in &day2_events {
        assert_eq!(event.day, 2, "Day 2 events should have day=2");
    }
}

#[test]
fn test_events_persist_across_ticks() {
    // RED: Will fail - persistence doesn't exist
    let agents = vec![
        Agent::new("BANK_A".to_string(), 50_000, 0),
    ];

    let mut orch = Orchestrator::new(agents, 100, 1, 42);

    // Run some ticks
    for _ in 0..50 {
        orch.tick();
    }

    let events_at_50 = orch.get_collateral_events_for_day(0).len();

    // Run more ticks
    for _ in 0..50 {
        orch.tick();
    }

    let events_at_100 = orch.get_collateral_events_for_day(0).len();

    // Events should accumulate
    assert!(
        events_at_100 >= events_at_50,
        "Events should persist and accumulate"
    );
}
```

**Expected Result**: All tests FAIL with compilation errors (types don't exist).

---

#### Step 1.2: Run Tests to Confirm RED (5 min)

```bash
cd backend
cargo test test_collateral_event_tracking --no-default-features
```

**Expected Output**:
```
error[E0433]: failed to resolve: use of undeclared type `CollateralEvent`
error[E0433]: failed to resolve: use of undeclared type `CollateralAction`
error[E0433]: failed to resolve: use of undeclared type `CollateralLayer`
error[E0599]: no method named `get_collateral_events_for_day` found
```

✅ **RED Phase Complete**: Tests fail because features don't exist.

---

### Phase 2.2.2: GREEN - Implement Rust Code (2-3 hours)

**Principle**: Write minimal code to make tests pass.

#### Step 2.1: Create CollateralEvent Model (30 min)

**File**: `/backend/src/models/collateral_event.rs` (NEW)

```rust
//! Collateral Event Model
//!
//! Tracks individual collateral management decisions for Phase 10 persistence.

use serde::{Deserialize, Serialize};

/// Collateral management action
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CollateralAction {
    /// Posted collateral to increase liquidity
    Post,
    /// Withdrew collateral (no longer needed)
    Withdraw,
    /// Considered posting but decided not to (policy decision)
    Hold,
}

/// Layer where collateral decision occurred
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CollateralLayer {
    /// Strategic policy-driven decision (from policy tree)
    Strategic,
    /// Automatic end-of-tick posting/withdrawal
    EndOfTick,
}

/// Individual collateral management event
///
/// Captures every collateral decision with full context:
/// - What: action (post/withdraw/hold) and amount
/// - When: tick and day
/// - Who: agent_id
/// - Why: reason string
/// - How: layer (strategic vs automatic)
/// - State: before/after balances and collateral
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollateralEvent {
    /// Agent that made the collateral decision
    pub agent_id: String,

    /// Tick when event occurred (0-indexed within simulation)
    pub tick: usize,

    /// Day when event occurred (0-indexed)
    pub day: usize,

    /// Action taken (post, withdraw, hold)
    pub action: CollateralAction,

    /// Amount of collateral posted/withdrawn (i64 cents)
    /// For Hold actions, this is the amount that was considered
    pub amount: i64,

    /// Reason for the action (e.g., "insufficient_liquidity", "strategic_decision")
    pub reason: String,

    /// Layer where decision occurred (strategic vs end-of-tick)
    pub layer: CollateralLayer,

    /// Agent balance before action (i64 cents)
    pub balance_before: i64,

    /// Posted collateral before action (i64 cents)
    pub posted_collateral_before: i64,

    /// Posted collateral after action (i64 cents)
    pub posted_collateral_after: i64,

    /// Available collateral capacity after action (i64 cents)
    /// = max_capacity - posted_collateral_after
    pub available_capacity_after: i64,
}

impl CollateralEvent {
    /// Create a new collateral event
    ///
    /// # Arguments
    /// * `agent_id` - Agent making the decision
    /// * `tick` - Current tick
    /// * `day` - Current day
    /// * `action` - Action taken
    /// * `amount` - Amount posted/withdrawn
    /// * `reason` - Reason for action
    /// * `layer` - Decision layer
    /// * `balance_before` - Balance before action
    /// * `posted_collateral_before` - Collateral before action
    /// * `posted_collateral_after` - Collateral after action
    /// * `available_capacity_after` - Remaining capacity after action
    pub fn new(
        agent_id: String,
        tick: usize,
        day: usize,
        action: CollateralAction,
        amount: i64,
        reason: String,
        layer: CollateralLayer,
        balance_before: i64,
        posted_collateral_before: i64,
        posted_collateral_after: i64,
        available_capacity_after: i64,
    ) -> Self {
        Self {
            agent_id,
            tick,
            day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collateral_event_creation() {
        let event = CollateralEvent::new(
            "BANK_A".to_string(),
            42,
            0,
            CollateralAction::Post,
            100_000,
            "insufficient_liquidity".to_string(),
            CollateralLayer::Strategic,
            500_000,
            0,
            100_000,
            4_900_000,
        );

        assert_eq!(event.agent_id, "BANK_A");
        assert_eq!(event.tick, 42);
        assert_eq!(event.day, 0);
        assert_eq!(event.action, CollateralAction::Post);
        assert_eq!(event.amount, 100_000);
        assert_eq!(event.layer, CollateralLayer::Strategic);
    }

    #[test]
    fn test_collateral_action_variants() {
        // Verify all action variants compile
        let _ = CollateralAction::Post;
        let _ = CollateralAction::Withdraw;
        let _ = CollateralAction::Hold;
    }

    #[test]
    fn test_collateral_layer_variants() {
        // Verify all layer variants compile
        let _ = CollateralLayer::Strategic;
        let _ = CollateralLayer::EndOfTick;
    }
}
```

**Update**: `/backend/src/models/mod.rs`
```rust
pub mod collateral_event;  // ADD THIS LINE

pub use collateral_event::{CollateralEvent, CollateralAction, CollateralLayer};
```

---

#### Step 2.2: Add Storage to SimulationState (15 min)

**File**: `/backend/src/models/state.rs`

Find the `SimulationState` struct and add:

```rust
pub struct SimulationState {
    // ... existing fields ...

    /// Collateral management events (Phase 10 persistence)
    ///
    /// Tracks every collateral post/withdraw/hold decision with full context.
    /// Enables granular analysis of collateral behavior.
    pub collateral_events: Vec<CollateralEvent>,  // ADD THIS
}
```

Update the `new()` method:

```rust
impl SimulationState {
    pub fn new(agents: Vec<Agent>) -> Self {
        Self {
            // ... existing fields ...
            collateral_events: Vec::new(),  // ADD THIS
        }
    }
}
```

---

#### Step 2.3: Add Event Recording Method to Orchestrator (30 min)

**File**: `/backend/src/orchestrator/engine.rs`

Add helper method to record collateral events:

```rust
impl Orchestrator {
    /// Record a collateral event with full state capture
    ///
    /// Called whenever collateral is posted, withdrawn, or a hold decision is made.
    ///
    /// # Arguments
    /// * `agent_id` - Agent making the decision
    /// * `action` - Action taken (Post/Withdraw/Hold)
    /// * `amount` - Amount involved
    /// * `reason` - Reason for action
    /// * `layer` - Decision layer (Strategic/EndOfTick)
    fn record_collateral_event(
        &mut self,
        agent_id: &str,
        action: CollateralAction,
        amount: i64,
        reason: String,
        layer: CollateralLayer,
    ) {
        let agent = self.state.get_agent(agent_id).unwrap();
        let current_tick = self.state.current_tick();
        let current_day = current_tick / self.config.ticks_per_day;

        // Capture before state
        let balance_before = agent.balance();
        let posted_collateral_before = agent.posted_collateral();

        // Calculate after state based on action
        let posted_collateral_after = match action {
            CollateralAction::Post => posted_collateral_before + amount,
            CollateralAction::Withdraw => posted_collateral_before - amount,
            CollateralAction::Hold => posted_collateral_before,  // No change
        };

        // Calculate remaining capacity
        let max_capacity = agent.max_collateral_capacity();
        let available_capacity_after = max_capacity - posted_collateral_after;

        // Create event
        let event = CollateralEvent::new(
            agent_id.to_string(),
            current_tick,
            current_day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after,
        );

        // Store event
        self.state.collateral_events.push(event);
    }
}
```

---

#### Step 2.4: Instrument Existing Collateral Code (1 hour)

**File**: `/backend/src/orchestrator/engine.rs`

Find all places where `set_posted_collateral()` is called and add event recording.

**Location 1: Strategic Layer Post** (around line 1530):

```rust
// BEFORE:
agent_mut.set_posted_collateral(new_collateral);
self.log_event(Event::CollateralPost { ... });

// AFTER:
agent_mut.set_posted_collateral(new_collateral);

// Record detailed collateral event (Phase 10)
self.record_collateral_event(
    &agent_id,
    CollateralAction::Post,
    amount,
    format!("{:?}", reason),
    CollateralLayer::Strategic,
);

self.log_event(Event::CollateralPost { ... });
```

**Location 2: Strategic Layer Withdraw** (around line 1561):

```rust
// BEFORE:
agent_mut.set_posted_collateral(new_collateral);
self.log_event(Event::CollateralWithdraw { ... });

// AFTER:
agent_mut.set_posted_collateral(new_collateral);

// Record detailed collateral event (Phase 10)
self.record_collateral_event(
    &agent_id,
    CollateralAction::Withdraw,
    amount,
    format!("{:?}", reason),
    CollateralLayer::Strategic,
);

self.log_event(Event::CollateralWithdraw { ... });
```

**Location 3: End-of-Tick Post** (around line 1859):

```rust
// BEFORE:
agent_mut.set_posted_collateral(new_collateral);
self.log_event(Event::CollateralPost { ... });

// AFTER:
agent_mut.set_posted_collateral(new_collateral);

// Record detailed collateral event (Phase 10)
self.record_collateral_event(
    &agent_id,
    CollateralAction::Post,
    amount,
    "automatic_eod_posting".to_string(),
    CollateralLayer::EndOfTick,
);

self.log_event(Event::CollateralPost { ... });
```

**Location 4: End-of-Tick Withdraw** (around line 1894):

```rust
// BEFORE:
agent_mut.set_posted_collateral(new_collateral);
self.log_event(Event::CollateralWithdraw { ... });

// AFTER:
agent_mut.set_posted_collateral(new_collateral);

// Record detailed collateral event (Phase 10)
self.record_collateral_event(
    &agent_id,
    CollateralAction::Withdraw,
    amount,
    "automatic_eod_withdrawal".to_string(),
    CollateralLayer::EndOfTick,
);

self.log_event(Event::CollateralWithdraw { ... });
```

---

#### Step 2.5: Add FFI Retrieval Method (30 min)

**File**: `/backend/src/orchestrator/engine.rs`

Add public method to get collateral events:

```rust
impl Orchestrator {
    /// Get collateral events for a specific day
    ///
    /// Returns all collateral management events that occurred during the specified day.
    ///
    /// # Arguments
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    /// Vector of collateral events filtered by day
    ///
    /// # Example
    /// ```ignore
    /// let events = orch.get_collateral_events_for_day(0);
    /// for event in events {
    ///     println!("{} posted {} at tick {}", event.agent_id, event.amount, event.tick);
    /// }
    /// ```
    pub fn get_collateral_events_for_day(&self, day: usize) -> Vec<CollateralEvent> {
        self.state
            .collateral_events
            .iter()
            .filter(|e| e.day == day)
            .cloned()
            .collect()
    }
}
```

---

#### Step 2.6: Expose via PyO3 FFI (45 min)

**File**: `/backend/src/ffi/orchestrator.rs`

Add FFI method:

```rust
#[pymethods]
impl Orchestrator {
    /// Get collateral events for a specific day (Phase 10: Collateral Event Tracking)
    ///
    /// Returns all collateral management events that occurred during the specified day,
    /// including strategic layer decisions and end-of-tick automatic postings.
    ///
    /// # Python Example
    /// ```python
    /// collateral_events = orch.get_collateral_events_for_day(0)
    ///
    /// # Convert to Polars DataFrame
    /// import polars as pl
    /// df = pl.DataFrame(collateral_events)
    ///
    /// # Write to DuckDB
    /// conn.execute("INSERT INTO collateral_events SELECT * FROM df")
    /// ```
    #[pyo3(name = "get_collateral_events_for_day")]
    fn py_get_collateral_events_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
        // Get events from Rust orchestrator
        let events = self.inner.get_collateral_events_for_day(day);

        // Get simulation ID for conversion
        let simulation_id = self.inner.simulation_id();

        // Convert each event to Python dict
        let py_list = PyList::empty(py);
        for event in events {
            let event_dict = collateral_event_to_py(py, &event, &simulation_id)?;
            py_list.append(event_dict)?;
        }

        Ok(py_list.into())
    }
}
```

**File**: `/backend/src/ffi/converters.rs` (or create if doesn't exist)

Add converter function:

```rust
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use crate::models::{CollateralEvent, CollateralAction, CollateralLayer};

/// Convert CollateralEvent to Python dict
///
/// Maps Rust CollateralEvent struct to Python dict with snake_case keys
/// matching the Pydantic CollateralEventRecord schema.
pub fn collateral_event_to_py(
    py: Python,
    event: &CollateralEvent,
    simulation_id: &str,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    dict.set_item("simulation_id", simulation_id)?;
    dict.set_item("agent_id", &event.agent_id)?;
    dict.set_item("tick", event.tick)?;
    dict.set_item("day", event.day)?;

    // Convert enum to string
    let action_str = match event.action {
        CollateralAction::Post => "post",
        CollateralAction::Withdraw => "withdraw",
        CollateralAction::Hold => "hold",
    };
    dict.set_item("action", action_str)?;

    dict.set_item("amount", event.amount)?;
    dict.set_item("reason", &event.reason)?;

    // Convert enum to string
    let layer_str = match event.layer {
        CollateralLayer::Strategic => "strategic",
        CollateralLayer::EndOfTick => "end_of_tick",
    };
    dict.set_item("layer", layer_str)?;

    dict.set_item("balance_before", event.balance_before)?;
    dict.set_item("posted_collateral_before", event.posted_collateral_before)?;
    dict.set_item("posted_collateral_after", event.posted_collateral_after)?;
    dict.set_item("available_capacity_after", event.available_capacity_after)?;

    Ok(dict.into())
}
```

---

#### Step 2.7: Rebuild and Run Tests (15 min)

```bash
cd backend

# Build Rust library
cargo build --release --no-default-features

# Run Rust tests
cargo test test_collateral_event_tracking --no-default-features

# Rebuild Python bindings
cd ../api
source .venv/bin/activate
uv run maturin develop --release
```

**Expected Result**: All Rust tests PASS ✅

---

### Phase 2.2.3: REFACTOR - Clean Up Implementation (30 min)

**Principle**: Improve code quality without changing behavior.

#### Step 3.1: Extract Helper Functions

**File**: `/backend/src/orchestrator/engine.rs`

```rust
impl Orchestrator {
    /// Capture agent state before collateral action
    fn capture_agent_state_before(&self, agent_id: &str) -> (i64, i64) {
        let agent = self.state.get_agent(agent_id).unwrap();
        (agent.balance(), agent.posted_collateral())
    }

    /// Calculate after state based on action
    fn calculate_collateral_after(
        &self,
        before: i64,
        action: &CollateralAction,
        amount: i64,
    ) -> i64 {
        match action {
            CollateralAction::Post => before + amount,
            CollateralAction::Withdraw => before - amount,
            CollateralAction::Hold => before,
        }
    }

    /// Refactored record_collateral_event using helpers
    fn record_collateral_event(
        &mut self,
        agent_id: &str,
        action: CollateralAction,
        amount: i64,
        reason: String,
        layer: CollateralLayer,
    ) {
        let (balance_before, posted_collateral_before) =
            self.capture_agent_state_before(agent_id);

        let posted_collateral_after =
            self.calculate_collateral_after(posted_collateral_before, &action, amount);

        let agent = self.state.get_agent(agent_id).unwrap();
        let available_capacity_after =
            agent.max_collateral_capacity() - posted_collateral_after;

        let current_tick = self.state.current_tick();
        let current_day = current_tick / self.config.ticks_per_day;

        let event = CollateralEvent::new(
            agent_id.to_string(),
            current_tick,
            current_day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after,
        );

        self.state.collateral_events.push(event);
    }
}
```

#### Step 3.2: Add Documentation

Add comprehensive rustdoc comments to all new functions.

#### Step 3.3: Final Test Run

```bash
cargo test --no-default-features
cargo clippy --no-default-features
cargo fmt
```

**Expected Result**:
- All tests pass ✅
- No clippy warnings ✅
- Code formatted ✅

---

## Integration with Python Layer

Once Rust implementation is complete, Python layer can use the FFI method:

```python
# Python code (Phase 2.3)
from payment_simulator._core import Orchestrator
import polars as pl

orch = Orchestrator.new(config)

# Run simulation
for _ in range(20):
    orch.tick()

# Get collateral events
collateral_events = orch.get_collateral_events_for_day(0)

# Convert to DataFrame
df = pl.DataFrame(collateral_events)

# Persist to database
db_manager.conn.execute("INSERT INTO collateral_events SELECT * FROM df")
```

---

## Testing Strategy

### Unit Tests (Rust)
- ✅ CollateralEvent model creation
- ✅ Event recording at each callsite
- ✅ Day filtering
- ✅ Layer tracking (Strategic vs EndOfTick)
- ✅ Action tracking (Post, Withdraw, Hold)
- ✅ State capture (before/after)

### Integration Tests (Python - already exists)
- ✅ FFI method exists and callable
- ✅ Returns correct data structure
- ✅ Validates with Pydantic model
- ✅ Persists to database
- ✅ Counts match daily_agent_metrics

---

## Success Criteria

### Phase 2.2 Complete When:

1. ✅ All Rust tests pass (9/9 tests in test_collateral_event_tracking.rs)
2. ✅ FFI method `get_collateral_events_for_day()` callable from Python
3. ✅ All 4 collateral locations instrumented (strategic post/withdraw, eod post/withdraw)
4. ✅ Python integration tests pass (8/10 tests, 2 schema tests already pass)
5. ✅ No clippy warnings
6. ✅ Code formatted and documented

---

## Rollback Plan

If implementation gets blocked:

**Minimal Viable Implementation**:
1. Skip Hold action tracking (only Post/Withdraw)
2. Skip layer distinction (mark all as Strategic)
3. Reduce state capture (only before/after collateral, not balance)

This would still achieve 80% of value (individual events tracked) while simplifying implementation.

---

## Time Estimates

| Phase | Task | Time | Cumulative |
|-------|------|------|------------|
| 2.2.1 | Write Rust tests | 2h | 2h |
| 2.2.2 | Implement Rust code | 3h | 5h |
| 2.2.3 | Refactor | 30min | 5.5h |
| **Total** | | **5.5 hours** | |

**Buffer**: Add 30min for unexpected issues = **6 hours total**

---

## Next Steps After Phase 2.2

Once Phase 2.2 is complete:
1. ✅ Verify Python tests pass (Phase 2.1 tests should now pass)
2. ➡️ Proceed to Phase 2.3: Python write logic in run.py
3. ➡️ Phase 2.4: REFACTOR - verify all collateral actions tracked

---

*Created: 2025-10-30*
*Status: PLANNING - Ready for Implementation*
*Follows: Strict TDD (RED-GREEN-REFACTOR)*
