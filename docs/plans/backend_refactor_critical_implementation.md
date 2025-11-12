# Backend Refactoring: Critical Fixes Implementation Plan

**Date**: 2025-11-12
**Status**: Ready to Implement
**Scope**: FFI Event Serialization + Python Config Validation + State Access Patterns
**Estimated Duration**: 1.5 weeks
**Expected Impact**: ~310 lines saved, significant maintainability improvement

---

## Table of Contents

1. [Overview](#overview)
2. [Fix #1: FFI Event Serialization](#fix-1-ffi-event-serialization)
3. [Fix #2: Python Config Validation](#fix-2-python-config-validation)
4. [Fix #3: State Access Patterns](#fix-3-state-access-patterns)
5. [Testing Strategy](#testing-strategy)
6. [Rollback Plan](#rollback-plan)

---

## Overview

This plan focuses on three high-impact refactorings that will eliminate ~310 lines of duplicated code while improving maintainability and reducing the risk of bugs.

### Success Criteria

- [ ] All existing tests pass (100% pass rate)
- [ ] Replay identity maintained (byte-for-byte identical output)
- [ ] No performance regression (within 5% of baseline)
- [ ] Code review approved
- [ ] Documentation updated

### Prerequisites

Before starting:

```bash
# 1. Create a feature branch
cd /home/user/SimCash
git checkout -b refactor/critical-dry-fixes

# 2. Establish baseline
cd backend
cargo test --no-default-features > test_baseline.txt 2>&1

# 3. Run performance baseline (if available)
cd ../api
uv sync --extra dev
# Run any performance benchmarks and save results

# 4. Create replay baseline
# (Run a test simulation and save output for comparison)
```

---

## Fix #1: FFI Event Serialization

**Priority**: 🔴 P0 (CRITICAL)
**Impact**: 150 lines saved (50% reduction in affected code)
**Risk**: LOW (pure extraction, no logic changes)
**Duration**: 4-6 hours
**Files Modified**: `backend/src/ffi/orchestrator.rs`

### Problem

`backend/src/ffi/orchestrator.rs` contains ~300 lines of duplicated event serialization code:
- Lines 964-1112: `get_tick_events()` with full event match
- Lines 1135-1284: `get_all_events()` with identical match

Every time a new event type is added, it must be added in TWO places, leading to potential divergence.

### Current State Analysis

```rust
// DUPLICATE #1: get_tick_events (lines 964-1112)
fn get_tick_events(&self, py: Python, tick: usize) -> PyResult<Py<PyList>> {
    let events = self.inner.get_tick_events(tick);
    let py_list = PyList::empty(py);
    for event in events {
        let event_dict = PyDict::new(py);
        event_dict.set_item("event_type", event.event_type())?;
        event_dict.set_item("tick", event.tick())?;
        match event {
            Event::Arrival { tx_id, sender_id, ... } => { /* 7 set_item calls */ }
            Event::PolicySubmit { ... } => { /* 2 set_item calls */ }
            // ... 15+ more event types
        }
        py_list.append(event_dict)?;
    }
    Ok(py_list.into())
}

// DUPLICATE #2: get_all_events (lines 1135-1284)
fn get_all_events(&self, py: Python) -> PyResult<Py<PyList>> {
    let events = self.inner.event_log().events();  // ← ONLY DIFFERENCE
    // ... EXACT SAME CODE AS ABOVE (140+ lines)
}
```

### Solution

Extract the event serialization logic into a single helper function.

### Implementation Steps

#### Step 1.1: Create Helper Function (30 minutes)

Add this function to `backend/src/ffi/orchestrator.rs` (around line 960, before `get_tick_events`):

```rust
/// Convert a single Event to Python dictionary.
///
/// This is the single source of truth for event serialization to Python.
/// Used by both `get_tick_events()` and `get_all_events()`.
///
/// # Arguments
/// * `py` - Python interpreter context
/// * `event` - Reference to the event to serialize
///
/// # Returns
/// Python dictionary with event fields
///
/// # Example
/// ```ignore
/// let event = Event::Arrival { tick: 1, tx_id: "tx_001".to_string(), ... };
/// let dict = event_to_py_dict(py, &event)?;
/// assert_eq!(dict.get_item("event_type")?, Some("arrival"));
/// ```
fn event_to_py_dict<'py>(
    py: Python<'py>,
    event: &crate::models::event::Event,
) -> PyResult<&'py PyDict> {
    let dict = PyDict::new(py);

    // Set common fields for all events
    dict.set_item("event_type", event.event_type())?;
    dict.set_item("tick", event.tick())?;

    // Set event-specific fields based on event type
    match event {
        crate::models::event::Event::Arrival {
            tx_id,
            sender_id,
            receiver_id,
            amount,
            deadline,
            priority,
            is_divisible,
            ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("deadline", deadline)?;
            dict.set_item("priority", priority)?;
            dict.set_item("is_divisible", is_divisible)?;
        }
        crate::models::event::Event::PolicySubmit { agent_id, tx_id, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
        }
        crate::models::event::Event::PolicyHold {
            agent_id,
            tx_id,
            reason,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::PolicyDrop {
            agent_id,
            tx_id,
            reason,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::PolicySplit {
            agent_id,
            tx_id,
            num_splits,
            child_ids,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("num_splits", num_splits)?;
            dict.set_item("child_ids", child_ids)?;
        }
        crate::models::event::Event::TransactionReprioritized {
            agent_id,
            tx_id,
            old_priority,
            new_priority,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("old_priority", old_priority)?;
            dict.set_item("new_priority", new_priority)?;
        }
        crate::models::event::Event::CollateralPost {
            agent_id,
            amount,
            reason,
            new_total,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
            dict.set_item("new_total", new_total)?;
        }
        crate::models::event::Event::CollateralRelease {
            agent_id,
            amount,
            reason,
            new_total,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
            dict.set_item("new_total", new_total)?;
        }
        crate::models::event::Event::Queue {
            tx_id,
            sender_id,
            receiver_id,
            amount,
            reason,
            ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::Settlement {
            tx_id,
            sender_id,
            receiver_id,
            amount,
            is_partial,
            ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("is_partial", is_partial)?;
        }
        crate::models::event::Event::LsmBilateralOffset {
            agent_a,
            agent_b,
            amount_a,
            amount_b,
            tx_ids,
            ..
        } => {
            dict.set_item("agent_a", agent_a)?;
            dict.set_item("agent_b", agent_b)?;
            dict.set_item("amount_a", amount_a)?;
            dict.set_item("amount_b", amount_b)?;
            dict.set_item("tx_ids", tx_ids)?;
        }
        crate::models::event::Event::LsmCycleSettlement {
            agents,
            tx_ids,
            tx_amounts,
            net_positions,
            max_net_outflow,
            max_net_outflow_agent,
            total_value,
            ..
        } => {
            dict.set_item("agents", agents)?;
            dict.set_item("tx_ids", tx_ids)?;
            dict.set_item("tx_amounts", tx_amounts)?;
            dict.set_item("net_positions", net_positions)?;
            dict.set_item("max_net_outflow", max_net_outflow)?;
            dict.set_item("max_net_outflow_agent", max_net_outflow_agent)?;
            dict.set_item("total_value", total_value)?;
        }
        crate::models::event::Event::CostAccrual {
            agent_id,
            breakdown,
            total_cost,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("total_cost", total_cost)?;

            // Serialize breakdown as nested dict
            let breakdown_dict = PyDict::new(py);
            breakdown_dict.set_item("liquidity_cost", breakdown.liquidity_cost)?;
            breakdown_dict.set_item("delay_cost", breakdown.delay_cost)?;
            breakdown_dict.set_item("collateral_cost", breakdown.collateral_cost)?;
            breakdown_dict.set_item("split_cost", breakdown.split_cost)?;
            dict.set_item("breakdown", breakdown_dict)?;
        }
        crate::models::event::Event::TransactionOverdue {
            tx_id,
            sender_id,
            receiver_id,
            amount,
            deadline,
            current_tick,
            penalty_applied,
            ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("deadline", deadline)?;
            dict.set_item("current_tick", current_tick)?;
            dict.set_item("penalty_applied", penalty_applied)?;
        }
        crate::models::event::Event::EodPenalty {
            agent_id,
            unsettled_tx_ids,
            penalty_amount,
            ..
        } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("unsettled_tx_ids", unsettled_tx_ids)?;
            dict.set_item("penalty_amount", penalty_amount)?;
        }
        crate::models::event::Event::DayEnd {
            day,
            final_tick,
            ..
        } => {
            dict.set_item("day", day)?;
            dict.set_item("final_tick", final_tick)?;
        }
        crate::models::event::Event::EpisodeEnd {
            final_tick,
            total_days,
            ..
        } => {
            dict.set_item("final_tick", final_tick)?;
            dict.set_item("total_days", total_days)?;
        }
    }

    Ok(dict)
}
```

**Note**: You'll need to review the actual Event enum in `backend/src/models/event.rs` to ensure all event types are covered.

#### Step 1.2: Refactor get_tick_events (15 minutes)

Replace the existing `get_tick_events` method (lines 964-1112) with:

```rust
fn get_tick_events(&self, py: Python, tick: usize) -> PyResult<Py<PyList>> {
    let events = self.inner.get_tick_events(tick);
    let py_list = PyList::empty(py);

    for event in events {
        let event_dict = event_to_py_dict(py, &event)?;
        py_list.append(event_dict)?;
    }

    Ok(py_list.into())
}
```

**From**: ~150 lines → **To**: ~10 lines ✅

#### Step 1.3: Refactor get_all_events (15 minutes)

Replace the existing `get_all_events` method (lines 1135-1284) with:

```rust
fn get_all_events(&self, py: Python) -> PyResult<Py<PyList>> {
    let events = self.inner.event_log().events();
    let py_list = PyList::empty(py);

    for event in events {
        let event_dict = event_to_py_dict(py, &event)?;
        py_list.append(event_dict)?;
    }

    Ok(py_list.into())
}
```

**From**: ~150 lines → **To**: ~10 lines ✅

#### Step 1.4: Verify Compilation (5 minutes)

```bash
cd /home/user/SimCash/backend
cargo build --no-default-features
```

Fix any compilation errors (likely missing event types in the match statement).

#### Step 1.5: Run Tests (15 minutes)

```bash
# Run Rust tests
cargo test --no-default-features

# Rebuild Python module and run Python tests
cd ../api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest tests/ -v
```

Verify:
- [ ] All tests pass
- [ ] No new warnings
- [ ] Event serialization works correctly

#### Step 1.6: Manual Verification (30 minutes)

Test with a real simulation run:

```bash
# Run a test simulation and compare event output
cd /home/user/SimCash/api
.venv/bin/python -c "
from payment_simulator.backends.orchestrator import Orchestrator

config = {
    'ticks_per_day': 10,
    'num_days': 1,
    'rng_seed': 42,
    'agent_configs': [
        {'id': 'BANK_A', 'opening_balance': 1000000, 'credit_limit': 0},
        {'id': 'BANK_B', 'opening_balance': 1000000, 'credit_limit': 0},
    ],
}

orch = Orchestrator.new(config)
orch.tick()
events = orch.get_tick_events(1)

print(f'Found {len(events)} events at tick 1')
for event in events:
    print(f\"  {event['event_type']}: {event}\")
"
```

Verify:
- [ ] Events are returned correctly
- [ ] All expected fields are present
- [ ] No Python exceptions

#### Step 1.7: Test Replay Identity (30 minutes)

```bash
# Run with persistence
payment-sim run --config sim_config_simple_example.yaml --persist test_output.db --verbose > run.txt 2>&1

# Replay
payment-sim replay test_output.db --verbose > replay.txt 2>&1

# Compare (ignore timing lines)
diff <(grep -v "Duration:" run.txt | grep -v "Elapsed:") \
     <(grep -v "Duration:" replay.txt | grep -v "Elapsed:")
```

Verify:
- [ ] No differences found (replay is identical)
- [ ] All events display correctly

### Completion Checklist for Fix #1

- [ ] Helper function `event_to_py_dict` created
- [ ] `get_tick_events` refactored to use helper
- [ ] `get_all_events` refactored to use helper
- [ ] Compilation successful with no warnings
- [ ] All Rust tests pass
- [ ] All Python tests pass
- [ ] Manual verification successful
- [ ] Replay identity verified
- [ ] Code reviewed
- [ ] Commit created with clear message

### Expected Commit Message

```
refactor(ffi): extract event serialization to helper function

Extract duplicated event-to-Python-dict serialization logic into a
single helper function event_to_py_dict(). This eliminates ~300 lines
of duplication between get_tick_events() and get_all_events().

Benefits:
- Single source of truth for event serialization
- Adding new event types requires changes in ONE place
- Reduced risk of divergence between the two methods
- Maintains replay identity (verified)

Files changed:
- backend/src/ffi/orchestrator.rs: Extract event_to_py_dict helper

Tested:
- All Rust tests pass
- All Python integration tests pass
- Replay identity verified (byte-for-byte match)
- No performance regression

Relates to: docs/plans/backend_refactor_dry.md (Fix #1)
```

---

## Fix #2: Python Config Validation

**Priority**: 🔴 P1 (CRITICAL)
**Impact**: 100 lines saved (67% reduction in affected code)
**Risk**: LOW (helper functions, backward compatible)
**Duration**: 3-4 hours
**Files Modified**: `backend/src/ffi/types.rs` or new `backend/src/ffi/py_extract.rs`

### Problem

`backend/src/ffi/types.rs` contains 50+ instances of a verbose 4-line pattern for extracting fields from Python dictionaries:

```rust
let field_name: Type = py_dict
    .get_item("field_name")?
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'field_name'"))?
    .extract()?;
```

This appears in:
- `parse_orchestrator_config`
- `parse_agent_config`
- `parse_policy_config`
- `parse_cost_rates`
- Other config parsing functions

### Solution

Create helper functions for required and optional field extraction.

### Implementation Steps

#### Step 2.1: Review Current Code (15 minutes)

Read through `backend/src/ffi/types.rs` to understand:
- All places where field extraction occurs
- Different patterns (required vs optional fields)
- Default value handling

```bash
cd /home/user/SimCash/backend/src/ffi
grep -n "get_item" types.rs | wc -l  # Count occurrences
```

#### Step 2.2: Create Helper Module (45 minutes)

**Option A**: Add to existing `backend/src/ffi/types.rs`

**Option B** (recommended): Create new file `backend/src/ffi/py_extract.rs`

```rust
//! Helper functions for extracting values from Python dictionaries.
//!
//! These utilities reduce boilerplate when parsing configuration from Python.
//! All functions provide consistent error messages and type conversion.

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Extract required field from Python dict with automatic error handling.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `field` - Field name as string
///
/// # Returns
/// Extracted and converted value, or PyErr if field is missing or conversion fails
///
/// # Example
/// ```ignore
/// let ticks_per_day: usize = extract_required(&py_config, "ticks_per_day")?;
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
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Missing required field '{}'",
                field
            ))
        })?
        .extract()
}

/// Extract optional field from Python dict.
///
/// Returns `None` if field is missing or is Python `None`.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `field` - Field name as string
///
/// # Returns
/// `Some(value)` if field exists and is not None, otherwise `None`
///
/// # Example
/// ```ignore
/// let threshold: Option<f64> = extract_optional(&py_config, "eod_rush_threshold")?;
/// let threshold = threshold.unwrap_or(0.8);  // Apply default
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

/// Extract field with default value if missing.
///
/// Convenience wrapper around `extract_optional` that applies a default.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `field` - Field name as string
/// * `default` - Default value if field is missing
///
/// # Returns
/// Extracted value, or default if field is missing
///
/// # Example
/// ```ignore
/// let threshold: f64 = extract_with_default(&py_config, "eod_rush_threshold", 0.8)?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;

    #[test]
    fn test_extract_required_success() {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);
            dict.set_item("foo", 42).unwrap();

            let value: i32 = extract_required(&dict, "foo").unwrap();
            assert_eq!(value, 42);
        });
    }

    #[test]
    fn test_extract_required_missing() {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);

            let result: PyResult<i32> = extract_required(&dict, "missing");
            assert!(result.is_err());
            assert!(result
                .unwrap_err()
                .to_string()
                .contains("Missing required field"));
        });
    }

    #[test]
    fn test_extract_optional_present() {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);
            dict.set_item("foo", 42).unwrap();

            let value: Option<i32> = extract_optional(&dict, "foo").unwrap();
            assert_eq!(value, Some(42));
        });
    }

    #[test]
    fn test_extract_optional_missing() {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);

            let value: Option<i32> = extract_optional(&dict, "missing").unwrap();
            assert_eq!(value, None);
        });
    }

    #[test]
    fn test_extract_with_default() {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);

            // Missing field uses default
            let value: f64 = extract_with_default(&dict, "threshold", 0.8).unwrap();
            assert_eq!(value, 0.8);

            // Present field uses actual value
            dict.set_item("threshold", 0.5).unwrap();
            let value: f64 = extract_with_default(&dict, "threshold", 0.8).unwrap();
            assert_eq!(value, 0.5);
        });
    }
}
```

#### Step 2.3: Register Module (5 minutes)

If you created a new file, add to `backend/src/ffi/mod.rs`:

```rust
pub mod orchestrator;
pub mod types;
pub mod py_extract;  // Add this line
```

#### Step 2.4: Refactor parse_orchestrator_config (30 minutes)

In `backend/src/ffi/types.rs`, update imports:

```rust
use crate::ffi::py_extract::{extract_required, extract_optional, extract_with_default};
```

Then refactor the function:

```rust
// BEFORE: ~40 lines of boilerplate
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    let ticks_per_day: usize = py_config
        .get_item("ticks_per_day")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'ticks_per_day'"))?
        .extract()?;

    let num_days: usize = py_config
        .get_item("num_days")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'num_days'"))?
        .extract()?;

    // ... 10+ more fields with same pattern
}

// AFTER: ~15 lines, much clearer
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    let ticks_per_day = extract_required::<usize>(py_config, "ticks_per_day")?;
    let num_days = extract_required::<usize>(py_config, "num_days")?;
    let rng_seed = extract_required::<u64>(py_config, "rng_seed")?;

    // Optional fields with defaults
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

#### Step 2.5: Refactor parse_agent_config (20 minutes)

Apply the same pattern to `parse_agent_config`:

```rust
pub fn parse_agent_config(py_agent: &Bound<'_, PyDict>) -> PyResult<AgentConfig> {
    let id = extract_required::<String>(py_agent, "id")?;
    let opening_balance = extract_required::<i64>(py_agent, "opening_balance")?;
    let credit_limit = extract_with_default(py_agent, "credit_limit", 0)?;

    // ... other fields

    Ok(AgentConfig {
        id,
        opening_balance,
        credit_limit,
        // ...
    })
}
```

#### Step 2.6: Refactor Remaining Config Functions (30 minutes)

Apply to:
- `parse_policy_config`
- `parse_cost_rates`
- Any other config parsing functions

#### Step 2.7: Verify Compilation (5 minutes)

```bash
cd /home/user/SimCash/backend
cargo build --no-default-features
cargo test --no-default-features
```

#### Step 2.8: Test Python Integration (30 minutes)

```bash
cd /home/user/SimCash/api
uv sync --extra dev --reinstall-package payment-simulator

# Test with various configs
.venv/bin/python -c "
from payment_simulator.backends.orchestrator import Orchestrator

# Test with minimal config
config = {
    'ticks_per_day': 10,
    'num_days': 1,
    'rng_seed': 42,
    'agent_configs': [
        {'id': 'BANK_A', 'opening_balance': 1000000},
    ],
}

orch = Orchestrator.new(config)
print('✓ Minimal config works')

# Test with full config
config['eod_rush_threshold'] = 0.75
config['lsm_enabled'] = False
config['agent_configs'][0]['credit_limit'] = 500000

orch = Orchestrator.new(config)
print('✓ Full config works')

# Test error handling (missing required field)
try:
    bad_config = {'ticks_per_day': 10}  # Missing required fields
    Orchestrator.new(bad_config)
    print('✗ Should have raised error')
except ValueError as e:
    print(f'✓ Error handling works: {e}')
"

# Run full test suite
.venv/bin/python -m pytest tests/ -v -k config
```

### Completion Checklist for Fix #2

- [ ] Helper module created (`py_extract.rs` or in `types.rs`)
- [ ] Unit tests for helpers pass
- [ ] `parse_orchestrator_config` refactored
- [ ] `parse_agent_config` refactored
- [ ] All other config functions refactored
- [ ] Compilation successful
- [ ] All Rust tests pass
- [ ] All Python tests pass
- [ ] Config validation still works (missing fields caught)
- [ ] Code reviewed
- [ ] Commit created

### Expected Commit Message

```
refactor(ffi): add helpers for Python dict field extraction

Create reusable helper functions for extracting fields from Python
dictionaries, eliminating ~150 lines of boilerplate code.

New helpers:
- extract_required<T>(): Extract required field or error
- extract_optional<T>(): Extract optional field (returns Option)
- extract_with_default<T>(): Extract with default value

Applied to all config parsing functions:
- parse_orchestrator_config
- parse_agent_config
- parse_policy_config
- parse_cost_rates

Benefits:
- 67% reduction in config parsing boilerplate
- Consistent error messages
- Easier to add new config fields
- Improved readability

Files changed:
- backend/src/ffi/py_extract.rs: New helper module
- backend/src/ffi/types.rs: Refactored to use helpers
- backend/src/ffi/mod.rs: Register new module

Tested:
- All Rust tests pass
- Python config parsing still works
- Error handling verified (missing fields caught)

Relates to: docs/plans/backend_refactor_dry.md (Fix #2)
```

---

## Fix #3: State Access Patterns

**Priority**: 🟡 P2 (MEDIUM)
**Impact**: 60 lines saved, improved safety
**Risk**: MEDIUM (touches core settlement logic)
**Duration**: 4-5 hours
**Files Modified**: `backend/src/models/state.rs`, `backend/src/settlement/rtgs.rs`, `backend/src/settlement/lsm.rs`

### Problem

State access patterns for transferring balances and settling transactions are repeated across RTGS, LSM, and orchestrator modules:

```rust
// Pattern repeated 10+ times:
let can_pay = {
    let sender = state.get_agent(&sender_id).unwrap();
    sender.can_pay(amount)
};

if can_pay {
    {
        let sender = state.get_agent_mut(&sender_id).unwrap();
        sender.debit(amount)?;
    }
    {
        let receiver = state.get_agent_mut(&receiver_id).unwrap();
        receiver.credit(amount);
    }

    let tx = state.get_transaction_mut(&tx_id).unwrap();
    tx.settle(amount, tick)?;

    state.event_log_mut().push(Event::Settlement { ... });
}
```

### Solution

Add atomic helper methods to `SimulationState` that encapsulate common state operations.

### Implementation Steps

#### Step 3.1: Review Current Patterns (30 minutes)

Read through these files to identify all state access patterns:

```bash
cd /home/user/SimCash/backend/src
grep -n "get_agent_mut\|get_transaction_mut" settlement/rtgs.rs settlement/lsm.rs orchestrator/engine.rs
```

Document:
- How many times balance transfers occur
- How many times transactions are settled
- Error handling patterns
- Event emission patterns

#### Step 3.2: Add Helper Methods to SimulationState (1 hour)

In `backend/src/models/state.rs`, add these methods:

```rust
// Add to impl SimulationState block

/// Execute atomic balance transfer between two agents.
///
/// This is an atomic operation - either succeeds completely or fails without side effects.
///
/// # Arguments
/// * `sender_id` - ID of agent sending funds
/// * `receiver_id` - ID of agent receiving funds
/// * `amount` - Amount to transfer (in cents)
///
/// # Returns
/// * `Ok(())` if transfer succeeded
/// * `Err(SettlementError)` if sender has insufficient liquidity or agent not found
///
/// # Example
/// ```ignore
/// state.transfer_balance("BANK_A", "BANK_B", 100_000)?;
/// ```
pub fn transfer_balance(
    &mut self,
    sender_id: &str,
    receiver_id: &str,
    amount: i64,
) -> Result<(), String> {
    // Validate sender exists and can pay
    let can_pay = self
        .get_agent(sender_id)
        .ok_or_else(|| format!("Sender agent '{}' not found", sender_id))?
        .can_pay(amount);

    if !can_pay {
        let available = self.get_agent(sender_id).unwrap().available_liquidity();
        return Err(format!(
            "Insufficient liquidity: agent '{}' needs {} but has {}",
            sender_id, amount, available
        ));
    }

    // Validate receiver exists
    if self.get_agent(receiver_id).is_none() {
        return Err(format!("Receiver agent '{}' not found", receiver_id));
    }

    // Execute transfer atomically
    self.get_agent_mut(sender_id)
        .unwrap()
        .debit(amount)
        .map_err(|e| format!("Debit failed: {:?}", e))?;

    self.get_agent_mut(receiver_id)
        .unwrap()
        .credit(amount);

    Ok(())
}

/// Execute complete transaction settlement: transfer + mark settled + emit event.
///
/// This is the highest-level settlement operation that:
/// 1. Transfers balance from sender to receiver
/// 2. Marks transaction as settled
/// 3. Emits Settlement event
///
/// # Arguments
/// * `tx_id` - Transaction ID to settle
/// * `tick` - Current tick number
///
/// # Returns
/// * `Ok(())` if settlement succeeded
/// * `Err(String)` if any step failed
///
/// # Example
/// ```ignore
/// state.settle_transaction("tx_00001", 42)?;
/// ```
pub fn settle_transaction(
    &mut self,
    tx_id: &str,
    tick: usize,
) -> Result<(), String> {
    // Get transaction details (immutable borrow)
    let (sender_id, receiver_id, amount) = {
        let tx = self
            .get_transaction(tx_id)
            .ok_or_else(|| format!("Transaction '{}' not found", tx_id))?;

        if tx.is_fully_settled() {
            return Err(format!("Transaction '{}' already settled", tx_id));
        }

        (
            tx.sender_id().to_string(),
            tx.receiver_id().to_string(),
            tx.remaining_amount(),
        )
    };

    // Execute balance transfer
    self.transfer_balance(&sender_id, &receiver_id, amount)?;

    // Mark transaction as settled
    let is_partial = {
        let tx = self.get_transaction_mut(tx_id).unwrap();
        tx.settle(amount, tick)
            .map_err(|e| format!("Failed to mark transaction settled: {:?}", e))?;
        tx.is_partially_settled()
    };

    // Emit settlement event
    self.event_log_mut().push(crate::models::event::Event::Settlement {
        tick,
        tx_id: tx_id.to_string(),
        sender_id,
        receiver_id,
        amount,
        is_partial,
    });

    Ok(())
}

/// Check if transaction can be settled without modifying state.
///
/// # Arguments
/// * `tx_id` - Transaction ID to check
///
/// # Returns
/// * `Ok(true)` if settlement would succeed
/// * `Ok(false)` if insufficient liquidity
/// * `Err(String)` if transaction or agents not found
pub fn can_settle_transaction(&self, tx_id: &str) -> Result<bool, String> {
    let tx = self
        .get_transaction(tx_id)
        .ok_or_else(|| format!("Transaction '{}' not found", tx_id))?;

    if tx.is_fully_settled() {
        return Ok(false);
    }

    let sender = self
        .get_agent(tx.sender_id())
        .ok_or_else(|| format!("Sender '{}' not found", tx.sender_id()))?;

    Ok(sender.can_pay(tx.remaining_amount()))
}
```

#### Step 3.3: Add Unit Tests (30 minutes)

In `backend/src/models/state.rs`, add test module:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::agent::Agent;
    use crate::models::transaction::Transaction;

    fn create_test_state() -> SimulationState {
        let agents = vec![
            Agent::new("BANK_A".to_string(), 1_000_000, 500_000),
            Agent::new("BANK_B".to_string(), 1_000_000, 0),
        ];
        SimulationState::new(agents)
    }

    #[test]
    fn test_transfer_balance_success() {
        let mut state = create_test_state();

        // Transfer should succeed
        let result = state.transfer_balance("BANK_A", "BANK_B", 500_000);
        assert!(result.is_ok());

        // Verify balances updated
        assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 500_000);
        assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 1_500_000);
    }

    #[test]
    fn test_transfer_balance_insufficient_liquidity() {
        let mut state = create_test_state();

        // Try to transfer more than available
        let result = state.transfer_balance("BANK_A", "BANK_B", 2_000_000);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Insufficient liquidity"));

        // Balances should be unchanged
        assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 1_000_000);
        assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 1_000_000);
    }

    #[test]
    fn test_transfer_balance_agent_not_found() {
        let mut state = create_test_state();

        let result = state.transfer_balance("BANK_A", "BANK_MISSING", 100_000);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not found"));
    }

    #[test]
    fn test_settle_transaction_success() {
        let mut state = create_test_state();

        // Add transaction
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            500_000,
            0,
            100,
            5,
            false,
        );
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);

        // Settle transaction
        let result = state.settle_transaction(&tx_id, 1);
        assert!(result.is_ok());

        // Verify settlement
        let tx = state.get_transaction(&tx_id).unwrap();
        assert!(tx.is_fully_settled());

        // Verify balances
        assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 500_000);
        assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 1_500_000);

        // Verify event emitted
        let events = state.event_log().events();
        assert!(events.iter().any(|e| matches!(
            e,
            crate::models::event::Event::Settlement { tx_id: id, .. } if id == &tx_id
        )));
    }

    #[test]
    fn test_can_settle_transaction() {
        let mut state = create_test_state();

        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            500_000,
            0,
            100,
            5,
            false,
        );
        let tx_id = tx.id().to_string();
        state.add_transaction(tx);

        // Should be able to settle
        assert_eq!(state.can_settle_transaction(&tx_id).unwrap(), true);

        // Create transaction that's too large
        let large_tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            5_000_000,
            0,
            100,
            5,
            false,
        );
        let large_tx_id = large_tx.id().to_string();
        state.add_transaction(large_tx);

        // Should not be able to settle (insufficient liquidity)
        assert_eq!(state.can_settle_transaction(&large_tx_id).unwrap(), false);
    }
}
```

Run tests:

```bash
cd /home/user/SimCash/backend
cargo test --no-default-features models::state::tests
```

#### Step 3.4: Refactor RTGS (45 minutes)

In `backend/src/settlement/rtgs.rs`, update settlement logic:

```rust
// BEFORE: 15+ lines of manual state manipulation
let can_pay = {
    let sender = state.get_agent(&sender_id).unwrap();
    sender.can_pay(amount)
};

if can_pay {
    {
        let sender = state.get_agent_mut(&sender_id).unwrap();
        sender.debit(amount)?;
    }
    {
        let receiver = state.get_agent_mut(&receiver_id).unwrap();
        receiver.credit(amount);
    }

    let tx = state.get_transaction_mut(&tx_id).unwrap();
    tx.settle(amount, tick)?;

    state.event_log_mut().push(Event::Settlement { ... });
}

// AFTER: 3 lines using helper
match state.settle_transaction(&tx_id, tick) {
    Ok(_) => { /* success */ },
    Err(_) => { /* handle error */ },
}
```

Update `process_queue` function:

```rust
pub fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut still_pending = Vec::new();

    let tx_ids: Vec<String> = state.rtgs_queue_mut().drain(..).collect();

    for tx_id in tx_ids {
        // Check if can settle (without modifying state)
        match state.can_settle_transaction(&tx_id) {
            Ok(true) => {
                // Attempt settlement
                match state.settle_transaction(&tx_id, tick) {
                    Ok(_) => settled_count += 1,
                    Err(e) => {
                        eprintln!("Settlement failed for {}: {}", tx_id, e);
                        still_pending.push(tx_id);
                    }
                }
            }
            Ok(false) => {
                // Insufficient liquidity, keep in queue
                still_pending.push(tx_id);
            }
            Err(e) => {
                eprintln!("Can't check settlement for {}: {}", tx_id, e);
                still_pending.push(tx_id);
            }
        }
    }

    *state.rtgs_queue_mut() = still_pending;

    QueueProcessingResult {
        settled_count,
        still_pending: state.rtgs_queue().len(),
    }
}
```

#### Step 3.5: Refactor LSM (45 minutes)

In `backend/src/settlement/lsm.rs`, update bilateral settlement:

```rust
// BEFORE: Manual balance adjustment
for tx_id in &txs_ab {
    if let Some(tx) = state.get_transaction(tx_id) {
        let amount = tx.remaining_amount();
        let sender_id = tx.sender_id().to_string();
        let receiver_id = tx.receiver_id().to_string();

        state.get_agent_mut(&sender_id).unwrap().adjust_balance(-(amount as i64));
        state.get_agent_mut(&receiver_id).unwrap().adjust_balance(amount as i64);
        state.get_transaction_mut(tx_id).unwrap().settle(amount, tick)?;
    }
}

// AFTER: Use helper
for tx_id in &txs_ab {
    if let Err(e) = state.settle_transaction(tx_id, tick) {
        eprintln!("LSM settlement failed for {}: {}", tx_id, e);
    }
}
```

#### Step 3.6: Run Tests (30 minutes)

```bash
# Test Rust
cd /home/user/SimCash/backend
cargo test --no-default-features

# Test Python
cd ../api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest tests/integration/ -v
```

#### Step 3.7: Integration Testing (30 minutes)

Run full simulations to ensure settlement still works:

```bash
cd /home/user/SimCash/api

# Test with simple config
.venv/bin/python -c "
from payment_simulator.backends.orchestrator import Orchestrator

config = {
    'ticks_per_day': 100,
    'num_days': 1,
    'rng_seed': 42,
    'agent_configs': [
        {'id': 'BANK_A', 'opening_balance': 10000000, 'credit_limit': 0},
        {'id': 'BANK_B', 'opening_balance': 10000000, 'credit_limit': 0},
        {'id': 'BANK_C', 'opening_balance': 10000000, 'credit_limit': 0},
    ],
    'arrival_configs': [
        {'agent_id': 'BANK_A', 'rate_per_tick': 0.5},
        {'agent_id': 'BANK_B', 'rate_per_tick': 0.5},
        {'agent_id': 'BANK_C', 'rate_per_tick': 0.5},
    ],
}

orch = Orchestrator.new(config)

for _ in range(100):
    orch.tick()

summary = orch.get_summary()
print(f'Settled: {summary[\"total_settled\"]}')
print(f'Pending: {summary[\"total_pending\"]}')
print('✓ Simulation completed successfully')
"
```

### Completion Checklist for Fix #3

- [ ] Helper methods added to `SimulationState`
- [ ] Unit tests for helpers pass
- [ ] RTGS refactored to use helpers
- [ ] LSM refactored to use helpers
- [ ] All Rust tests pass
- [ ] All Python integration tests pass
- [ ] Full simulation runs successfully
- [ ] No performance regression
- [ ] Code reviewed
- [ ] Commit created

### Expected Commit Message

```
refactor(state): add atomic settlement helpers

Add helper methods to SimulationState for common settlement operations,
eliminating ~60 lines of repetitive state access patterns.

New methods:
- transfer_balance(): Atomic balance transfer between agents
- settle_transaction(): Complete settlement (transfer + mark + event)
- can_settle_transaction(): Check if settlement would succeed

Applied to:
- backend/src/settlement/rtgs.rs: Simplified queue processing
- backend/src/settlement/lsm.rs: Simplified bilateral settlement

Benefits:
- Atomic operations prevent partial state corruption
- Centralized error handling
- Consistent event emission
- Single source of truth for settlement logic
- Easier to add invariant checks
- Better testability

Files changed:
- backend/src/models/state.rs: Add helper methods + tests
- backend/src/settlement/rtgs.rs: Use helpers
- backend/src/settlement/lsm.rs: Use helpers

Tested:
- All Rust tests pass
- All Python integration tests pass
- Full simulation runs successfully
- No performance regression

Relates to: docs/plans/backend_refactor_dry.md (Fix #3)
```

---

## Testing Strategy

### Pre-Implementation Baseline

Before starting any refactoring:

```bash
cd /home/user/SimCash

# 1. Create baseline branch
git checkout -b baseline-before-refactor
git commit --allow-empty -m "Baseline before DRY refactoring"

# 2. Run full test suite
cd backend
cargo test --no-default-features > ../test_baseline.txt 2>&1

cd ../api
uv sync --extra dev
.venv/bin/python -m pytest > ../pytest_baseline.txt 2>&1

# 3. Create replay baseline (if possible)
# Save output from a test simulation for comparison

# 4. Return to feature branch
git checkout refactor/critical-dry-fixes
```

### After Each Fix

After completing each fix:

```bash
# 1. Run Rust tests
cd /home/user/SimCash/backend
cargo test --no-default-features

# 2. Rebuild and run Python tests
cd ../api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest tests/ -v

# 3. Compare test results
diff test_baseline.txt current_tests.txt

# 4. Commit if all tests pass
git add -A
git commit -m "..."
```

### Final Integration Testing

After all three fixes:

```bash
# 1. Full test suite
cd /home/user/SimCash/backend
cargo test --no-default-features --verbose

cd ../api
.venv/bin/python -m pytest tests/ -v --cov

# 2. Replay identity test
payment-sim run --config sim_config_simple_example.yaml \
  --persist test_output.db --verbose > run_output.txt 2>&1

payment-sim replay test_output.db --verbose > replay_output.txt 2>&1

diff <(grep -v "Duration:\|Elapsed:" run_output.txt) \
     <(grep -v "Duration:\|Elapsed:" replay_output.txt)

# 3. Performance test (if benchmarks exist)
# Compare against baseline

# 4. Manual smoke test
# Run a few simulations with different configs
```

### Test Success Criteria

- [ ] All Rust tests pass (100%)
- [ ] All Python tests pass (100%)
- [ ] Replay produces identical output (byte-for-byte)
- [ ] No new compiler warnings
- [ ] Performance within 5% of baseline
- [ ] Manual smoke tests succeed

---

## Rollback Plan

If any issues arise during implementation:

### Individual Fix Rollback

```bash
# If a specific fix causes problems, revert that commit
git log --oneline  # Find the commit hash
git revert <commit-hash>

# Or reset to before the fix
git reset --hard HEAD~1  # Go back one commit (destructive!)
```

### Full Rollback

```bash
# Abort entire refactoring
git checkout main
git branch -D refactor/critical-dry-fixes

# Start fresh if needed
git checkout -b refactor/critical-dry-fixes-v2
```

### Partial Implementation

If time runs out or issues arise:
- Each fix is independent and can be merged separately
- Merge Fix #1 and #2 first (lower risk)
- Defer Fix #3 if needed

---

## Post-Implementation Checklist

After all fixes are complete:

- [ ] All tests pass
- [ ] Replay identity verified
- [ ] No performance regression
- [ ] Code review completed
- [ ] Documentation updated:
  - [ ] Update `backend/CLAUDE.md` if patterns changed
  - [ ] Update relevant docs in `/docs`
- [ ] Create PR with detailed description
- [ ] Get approval from team
- [ ] Merge to main
- [ ] Delete feature branch
- [ ] Update `docs/plans/backend_refactor_dry.md` with "COMPLETED" status

---

## Success Metrics

Upon completion of all three fixes:

| Metric | Target | Actual |
|--------|--------|--------|
| Lines saved | ~310 lines | ___ |
| Test pass rate | 100% | ___ % |
| Replay identity | Perfect match | ___ |
| Performance | Within 5% | ___ % |
| Code review score | Approved | ___ |
| New bugs introduced | 0 | ___ |

---

## Timeline

### Week 1: Critical FFI and Config Fixes

**Monday-Tuesday**: Fix #1 (FFI Event Serialization)
- Monday AM: Create helper function
- Monday PM: Refactor both methods, test
- Tuesday AM: Integration testing, replay verification
- Tuesday PM: Code review, commit

**Wednesday-Thursday**: Fix #2 (Python Config Validation)
- Wednesday AM: Create helper module
- Wednesday PM: Refactor config functions
- Thursday AM: Testing
- Thursday PM: Code review, commit

**Friday**: Buffer day
- Address any issues from fixes #1 and #2
- Extra testing
- Documentation updates

### Week 2: State Access Patterns

**Monday-Tuesday**: Fix #3 (State Access Patterns)
- Monday AM: Add helper methods to SimulationState
- Monday PM: Unit tests for helpers
- Tuesday AM: Refactor RTGS and LSM
- Tuesday PM: Integration testing

**Wednesday**: Testing and Verification
- Full test suite
- Replay identity verification
- Performance testing

**Thursday**: Code Review and Documentation
- Final code review
- Update documentation
- Prepare PR

**Friday**: Merge and Deploy
- Get approvals
- Merge to main
- Monitor for issues

---

## Notes and Tips

### Common Pitfalls

1. **Forgetting to rebuild after Rust changes**
   ```bash
   # Always rebuild Python module after Rust changes
   cd /home/user/SimCash/api
   uv sync --extra dev --reinstall-package payment-simulator
   ```

2. **Not testing replay identity**
   - Replay identity is critical - test after every fix

3. **Changing logic accidentally**
   - This is pure refactoring - no logic changes
   - If behavior changes, something is wrong

4. **Incomplete event serialization**
   - Ensure ALL event types are in `event_to_py_dict`
   - Missing types will cause runtime errors

### Best Practices

- ✅ Commit after each fix (atomic commits)
- ✅ Run tests before committing
- ✅ Write clear commit messages
- ✅ Ask for code review
- ✅ Update documentation as you go
- ✅ Keep feature branch up to date with main

### Getting Help

If you encounter issues:

1. Check test output for specific errors
2. Review the original code carefully
3. Use `git diff` to see what changed
4. Test in isolation (single function at a time)
5. Consult `CLAUDE.md` files for project patterns

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
**Status**: ✅ Ready to Implement
