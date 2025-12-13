//! TDD Tests for ScheduledSettlementEvent
//!
//! These tests define the expected behavior of the ScheduledSettlement scenario event.
//! ScheduledSettlement creates a transaction AND immediately settles it via RTGS,
//! unlike DirectTransfer (bypasses RTGS) or CustomTransactionArrival (waits in queue).
//!
//! # RED Phase - Tests written BEFORE implementation
//!
//! # Key invariants tested:
//! - INV-1: Money is i64 (all amounts in cents)
//! - INV-2: Determinism (same seed = same results)
//! - Settlement goes through real RTGS engine
//! - Emits RtgsImmediateSettlement event (not just balance adjustment)

use payment_simulator_core_rs::events::types::{EventSchedule, ScenarioEvent, ScheduledEvent};
use serde_json::json;

// ===========================================================================
// Unit Tests: ScenarioEvent parsing
// ===========================================================================

/// Test that ScheduledSettlement parses correctly from JSON
#[test]
fn test_scheduled_settlement_parses_from_json() {
    let json = json!({
        "type": "scheduled_settlement",
        "from_agent": "SOURCE",
        "to_agent": "BANK_A",
        "amount": 100_000  // $1,000.00 in cents (INV-1)
    });

    let event: ScenarioEvent = serde_json::from_value(json).expect("Should parse");

    match event {
        ScenarioEvent::ScheduledSettlement {
            from_agent,
            to_agent,
            amount,
        } => {
            assert_eq!(from_agent, "SOURCE");
            assert_eq!(to_agent, "BANK_A");
            assert_eq!(amount, 100_000);
        }
        _ => panic!("Expected ScheduledSettlement variant"),
    }
}

/// Test that ScheduledSettlement serializes back to JSON correctly
#[test]
fn test_scheduled_settlement_serializes_to_json() {
    let event = ScenarioEvent::ScheduledSettlement {
        from_agent: "SOURCE".to_string(),
        to_agent: "BANK_A".to_string(),
        amount: 100_000,
    };

    let json = serde_json::to_value(&event).expect("Should serialize");

    assert_eq!(json["type"], "scheduled_settlement");
    assert_eq!(json["from_agent"], "SOURCE");
    assert_eq!(json["to_agent"], "BANK_A");
    assert_eq!(json["amount"], 100_000);
}

/// Test that ScheduledSettlement requires all fields
#[test]
fn test_scheduled_settlement_requires_all_fields() {
    // Missing amount
    let json = json!({
        "type": "scheduled_settlement",
        "from_agent": "SOURCE",
        "to_agent": "BANK_A"
    });

    let result: Result<ScenarioEvent, _> = serde_json::from_value(json);
    assert!(result.is_err(), "Should fail when amount is missing");
}

// ===========================================================================
// Integration Tests: Event execution
// ===========================================================================

#[cfg(feature = "pyo3")]
mod integration_tests {
    use payment_simulator_core_rs::ffi::orchestrator::PyOrchestrator;
    use pyo3::prelude::*;
    use pyo3::types::{PyDict, PyList};

    /// Test that ScheduledSettlement settles at exactly the specified tick
    ///
    /// Unlike CustomTransactionArrival which creates a pending transaction,
    /// ScheduledSettlement must settle immediately when the event fires.
    #[test]
    fn test_scheduled_settlement_settles_at_exact_tick() {
        Python::with_gil(|py| {
            let config = create_base_config(py);

            // Add ScheduledSettlement event at tick 5
            let events = PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "ScheduledSettlement").unwrap();
            event.set_item("from_agent", "SOURCE").unwrap();
            event.set_item("to_agent", "TARGET").unwrap();
            event.set_item("amount", 100_000i64).unwrap();  // $1,000.00
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 5).unwrap();
            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Create orchestrator
            let orch = py.get_type::<PyOrchestrator>()
                .call_method1("new", (config,))
                .expect("Should create orchestrator");

            // Check initial balances
            let source_balance: i64 = orch.call_method1("get_agent_balance", ("SOURCE",))
                .unwrap().extract().unwrap();
            let target_balance: i64 = orch.call_method1("get_agent_balance", ("TARGET",))
                .unwrap().extract().unwrap();

            assert_eq!(source_balance, 10_000_000, "SOURCE starts with $100k");
            assert_eq!(target_balance, 0, "TARGET starts with $0");

            // Run ticks 0-4: nothing should happen yet
            for _ in 0..5 {
                orch.call_method0("tick").unwrap();
            }

            let target_balance: i64 = orch.call_method1("get_agent_balance", ("TARGET",))
                .unwrap().extract().unwrap();
            assert_eq!(target_balance, 0, "TARGET should still be $0 before tick 5");

            // Run tick 5: ScheduledSettlement fires
            orch.call_method0("tick").unwrap();

            let target_balance: i64 = orch.call_method1("get_agent_balance", ("TARGET",))
                .unwrap().extract().unwrap();
            assert_eq!(target_balance, 100_000, "TARGET should have $1,000 after tick 5");

            let source_balance: i64 = orch.call_method1("get_agent_balance", ("SOURCE",))
                .unwrap().extract().unwrap();
            assert_eq!(source_balance, 10_000_000 - 100_000, "SOURCE debited $1,000");
        });
    }

    /// Test that ScheduledSettlement emits RtgsImmediateSettlement event
    ///
    /// This proves the settlement goes through the real RTGS engine,
    /// not just a balance adjustment like DirectTransfer.
    #[test]
    fn test_scheduled_settlement_produces_rtgs_event() {
        Python::with_gil(|py| {
            let config = create_base_config(py);

            // Add ScheduledSettlement event at tick 5
            let events = PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "ScheduledSettlement").unwrap();
            event.set_item("from_agent", "SOURCE").unwrap();
            event.set_item("to_agent", "TARGET").unwrap();
            event.set_item("amount", 100_000i64).unwrap();
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 5).unwrap();
            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Create orchestrator and run to tick 5
            let orch = py.get_type::<PyOrchestrator>()
                .call_method1("new", (config,))
                .expect("Should create orchestrator");

            for _ in 0..6 {
                orch.call_method0("tick").unwrap();
            }

            // Get events from tick 5
            let events: Vec<pyo3::Py<PyDict>> = orch
                .call_method1("get_tick_events", (5,))
                .unwrap()
                .extract()
                .unwrap();

            // Find RtgsImmediateSettlement event
            let rtgs_events: Vec<_> = events.iter()
                .filter(|e| {
                    Python::with_gil(|py| {
                        let dict = e.bind(py);
                        dict.get_item("event_type")
                            .ok()
                            .flatten()
                            .and_then(|v| v.extract::<String>().ok())
                            .map(|s| s == "rtgs_immediate_settlement")
                            .unwrap_or(false)
                    })
                })
                .collect();

            assert!(!rtgs_events.is_empty(),
                "Should emit RtgsImmediateSettlement event (proving RTGS engine was used)");

            // Verify the event contains expected data
            Python::with_gil(|py| {
                let event = rtgs_events[0].bind(py);
                let sender: String = event.get_item("sender")
                    .unwrap().unwrap().extract().unwrap();
                let receiver: String = event.get_item("receiver")
                    .unwrap().unwrap().extract().unwrap();
                let amount: i64 = event.get_item("amount")
                    .unwrap().unwrap().extract().unwrap();

                assert_eq!(sender, "SOURCE");
                assert_eq!(receiver, "TARGET");
                assert_eq!(amount, 100_000);
            });
        });
    }

    /// Test that ScheduledSettlement respects sender liquidity constraints
    ///
    /// Unlike DirectTransfer which can go negative, ScheduledSettlement
    /// should fail if sender lacks sufficient liquidity.
    #[test]
    fn test_scheduled_settlement_respects_liquidity() {
        Python::with_gil(|py| {
            let config = create_config_with_low_source_balance(py);

            // Add ScheduledSettlement for more than SOURCE has
            let events = PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "ScheduledSettlement").unwrap();
            event.set_item("from_agent", "SOURCE").unwrap();
            event.set_item("to_agent", "TARGET").unwrap();
            event.set_item("amount", 500_000i64).unwrap();  // $5,000 but SOURCE only has $1,000
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 5).unwrap();
            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            let orch = py.get_type::<PyOrchestrator>()
                .call_method1("new", (config,))
                .expect("Should create orchestrator");

            // Run to tick 5
            for _ in 0..6 {
                orch.call_method0("tick").unwrap();
            }

            // TARGET should NOT receive funds (settlement failed due to insufficient liquidity)
            let target_balance: i64 = orch.call_method1("get_agent_balance", ("TARGET",))
                .unwrap().extract().unwrap();
            assert_eq!(target_balance, 0, "TARGET should not receive funds when SOURCE lacks liquidity");
        });
    }

    /// Test determinism: same seed produces identical results (INV-2)
    #[test]
    fn test_scheduled_settlement_determinism() {
        let run_simulation = || {
            Python::with_gil(|py| {
                let config = create_base_config(py);

                // Add multiple ScheduledSettlement events
                let events = PyList::empty(py);
                for tick in [5, 10, 15] {
                    let event = PyDict::new(py);
                    event.set_item("type", "ScheduledSettlement").unwrap();
                    event.set_item("from_agent", "SOURCE").unwrap();
                    event.set_item("to_agent", "TARGET").unwrap();
                    event.set_item("amount", 10_000i64).unwrap();
                    event.set_item("schedule", "OneTime").unwrap();
                    event.set_item("tick", tick).unwrap();
                    events.append(event).unwrap();
                }
                config.set_item("scenario_events", events).unwrap();

                let orch = py.get_type::<PyOrchestrator>()
                    .call_method1("new", (config,))
                    .expect("Should create orchestrator");

                // Run full simulation
                for _ in 0..20 {
                    orch.call_method0("tick").unwrap();
                }

                // Return final balances
                let source: i64 = orch.call_method1("get_agent_balance", ("SOURCE",))
                    .unwrap().extract().unwrap();
                let target: i64 = orch.call_method1("get_agent_balance", ("TARGET",))
                    .unwrap().extract().unwrap();

                (source, target)
            })
        };

        let run1 = run_simulation();
        let run2 = run_simulation();

        assert_eq!(run1, run2, "Same seed must produce identical results (INV-2)");
    }

    // ===========================================================================
    // Helper functions
    // ===========================================================================

    fn create_base_config(py: Python<'_>) -> pyo3::Bound<'_, PyDict> {
        let config = PyDict::new(py);
        config.set_item("ticks_per_day", 100).unwrap();
        config.set_item("eod_rush_threshold", 0.8).unwrap();
        config.set_item("num_days", 1).unwrap();
        config.set_item("rng_seed", 12345u64).unwrap();  // Fixed seed for determinism

        // Create agents: SOURCE (liquidity provider) and TARGET (receiver)
        let agents = PyList::empty(py);

        // SOURCE: high balance, can send payments
        let source = PyDict::new(py);
        source.set_item("id", "SOURCE").unwrap();
        source.set_item("opening_balance", 10_000_000i64).unwrap();  // $100,000
        source.set_item("credit_limit", 0).unwrap();
        let policy = PyDict::new(py);
        policy.set_item("type", "Fifo").unwrap();
        source.set_item("policy", policy).unwrap();
        agents.append(source).unwrap();

        // TARGET: starts with zero, receives scheduled settlements
        let target = PyDict::new(py);
        target.set_item("id", "TARGET").unwrap();
        target.set_item("opening_balance", 0i64).unwrap();
        target.set_item("credit_limit", 0).unwrap();
        let policy = PyDict::new(py);
        policy.set_item("type", "Fifo").unwrap();
        target.set_item("policy", policy).unwrap();
        agents.append(target).unwrap();

        config.set_item("agent_configs", agents).unwrap();

        config
    }

    fn create_config_with_low_source_balance(py: Python<'_>) -> pyo3::Bound<'_, PyDict> {
        let config = PyDict::new(py);
        config.set_item("ticks_per_day", 100).unwrap();
        config.set_item("eod_rush_threshold", 0.8).unwrap();
        config.set_item("num_days", 1).unwrap();
        config.set_item("rng_seed", 12345u64).unwrap();

        let agents = PyList::empty(py);

        // SOURCE: LOW balance (can't afford large transfers)
        let source = PyDict::new(py);
        source.set_item("id", "SOURCE").unwrap();
        source.set_item("opening_balance", 100_000i64).unwrap();  // Only $1,000
        source.set_item("credit_limit", 0).unwrap();  // No credit
        let policy = PyDict::new(py);
        policy.set_item("type", "Fifo").unwrap();
        source.set_item("policy", policy).unwrap();
        agents.append(source).unwrap();

        let target = PyDict::new(py);
        target.set_item("id", "TARGET").unwrap();
        target.set_item("opening_balance", 0i64).unwrap();
        target.set_item("credit_limit", 0).unwrap();
        let policy = PyDict::new(py);
        policy.set_item("type", "Fifo").unwrap();
        target.set_item("policy", policy).unwrap();
        agents.append(target).unwrap();

        config.set_item("agent_configs", agents).unwrap();

        config
    }
}
