//! FFI Integration Tests for Scenario Events
//!
//! Tests the Python interface for configuring and using scenario events.
//! Following TDD: these tests define the expected FFI behavior.

#[cfg(feature = "pyo3")]
mod ffi_tests {
    use payment_simulator_core_rs::ffi::orchestrator::PyOrchestrator;
    use pyo3::prelude::*;
    use pyo3::types::PyDict;

    /// Test that scenario_events can be passed from Python config
    #[test]
    fn test_ffi_scenario_events_direct_transfer() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            // Create agent configs
            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            agents.append(agent_a).unwrap();

            let agent_b = PyDict::new(py);
            agent_b.set_item("id", "BANK_B").unwrap();
            agent_b.set_item("opening_balance", 1_000_000).unwrap();
            agent_b.set_item("credit_limit", 500_000).unwrap();

            let policy_b = PyDict::new(py);
            policy_b.set_item("type", "Fifo").unwrap();
            agent_b.set_item("policy", policy_b).unwrap();

            agents.append(agent_b).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // Create scenario_events array
            let events = pyo3::types::PyList::empty(py);

            // Event 1: DirectTransfer at tick 10
            let event1 = PyDict::new(py);
            event1.set_item("type", "DirectTransfer").unwrap();
            event1.set_item("from_agent", "BANK_A").unwrap();
            event1.set_item("to_agent", "BANK_B").unwrap();
            event1.set_item("amount", 100_000).unwrap();
            event1.set_item("schedule", "OneTime").unwrap();
            event1.set_item("tick", 10).unwrap();

            events.append(event1).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Create orchestrator with scenario events (call via Python, not direct Rust call)
            let orch_class = py.get_type::<PyOrchestrator>();
            let orch = orch_class.call_method1("new", (config,)).expect("Failed to create orchestrator");

            // Get initial balances
            let balance_a: i64 = orch.call_method1("get_agent_balance", ("BANK_A",)).unwrap().extract().unwrap();
            let balance_b: i64 = orch.call_method1("get_agent_balance", ("BANK_B",)).unwrap().extract().unwrap();

            assert_eq!(balance_a, 1_000_000);
            assert_eq!(balance_b, 1_000_000);
        });
    }

    /// Test repeating scenario events via FFI
    #[test]
    fn test_ffi_scenario_events_repeating() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            // Create agent configs (minimal)
            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            agents.append(agent_a).unwrap();

            let agent_b = PyDict::new(py);
            agent_b.set_item("id", "BANK_B").unwrap();
            agent_b.set_item("opening_balance", 1_000_000).unwrap();
            agent_b.set_item("credit_limit", 500_000).unwrap();

            let policy_b = PyDict::new(py);
            policy_b.set_item("type", "Fifo").unwrap();
            agent_b.set_item("policy", policy_b).unwrap();

            agents.append(agent_b).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // Create repeating event
            let events = pyo3::types::PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "DirectTransfer").unwrap();
            event.set_item("from_agent", "BANK_A").unwrap();
            event.set_item("to_agent", "BANK_B").unwrap();
            event.set_item("amount", 50_000).unwrap();
            event.set_item("schedule", "Repeating").unwrap();
            event.set_item("start_tick", 10).unwrap();
            event.set_item("interval", 10).unwrap();

            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // This should not panic - events should be parsed correctly
            let _orch = py.get_type::<PyOrchestrator>().call_method1("new", (config,)).expect("Failed to create orchestrator");
        });
    }

    /// Test collateral adjustment via FFI
    #[test]
    fn test_ffi_scenario_events_collateral_adjustment() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            // Create agent configs
            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            agents.append(agent_a).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // Create collateral adjustment event
            let events = pyo3::types::PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "CollateralAdjustment").unwrap();
            event.set_item("agent", "BANK_A").unwrap();
            event.set_item("delta", 200_000).unwrap();
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 10).unwrap();

            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Should parse correctly
            let _orch = py.get_type::<PyOrchestrator>().call_method1("new", (config,)).expect("Failed to create orchestrator");
        });
    }

    /// Test global arrival rate change via FFI
    #[test]
    fn test_ffi_scenario_events_global_arrival_rate() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            // Create agent with arrival config
            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            // Add arrival config
            let arrival = PyDict::new(py);
            arrival.set_item("rate_per_tick", 0.5).unwrap();
            arrival.set_item("amount_distribution", PyDict::new(py)).unwrap();
            agent_a.set_item("arrival_config", arrival).unwrap();

            agents.append(agent_a).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // Create global arrival rate change event
            let events = pyo3::types::PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "GlobalArrivalRateChange").unwrap();
            event.set_item("multiplier", 2.0).unwrap();
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 10).unwrap();

            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Should parse correctly
            let _orch = py.get_type::<PyOrchestrator>().call_method1("new", (config,)).expect("Failed to create orchestrator");
        });
    }

    /// Test error handling: invalid event type
    #[test]
    fn test_ffi_scenario_events_invalid_type() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            agents.append(agent_a).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // Invalid event type
            let events = pyo3::types::PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "InvalidEventType").unwrap();
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 10).unwrap();

            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Should fail with error
            let result = py.get_type::<PyOrchestrator>().call_method1("new", (config,));
            assert!(result.is_err(), "Should reject invalid event type");
        });
    }

    /// Test error handling: missing required field
    #[test]
    fn test_ffi_scenario_events_missing_field() {
        Python::with_gil(|py| {
            let config = PyDict::new(py);
            config.set_item("ticks_per_day", 100).unwrap();
            config.set_item("eod_rush_threshold", 0.8).unwrap();
            config.set_item("num_days", 1).unwrap();
            config.set_item("rng_seed", 12345u64).unwrap();

            let agents = pyo3::types::PyList::empty(py);
            let agent_a = PyDict::new(py);
            agent_a.set_item("id", "BANK_A").unwrap();
            agent_a.set_item("opening_balance", 1_000_000).unwrap();
            agent_a.set_item("credit_limit", 500_000).unwrap();

            let policy = PyDict::new(py);
            policy.set_item("type", "Fifo").unwrap();
            agent_a.set_item("policy", policy).unwrap();

            agents.append(agent_a).unwrap();
            config.set_item("agent_configs", agents).unwrap();

            // DirectTransfer missing amount field
            let events = pyo3::types::PyList::empty(py);
            let event = PyDict::new(py);
            event.set_item("type", "DirectTransfer").unwrap();
            event.set_item("from_agent", "BANK_A").unwrap();
            event.set_item("to_agent", "BANK_B").unwrap();
            // Missing: amount
            event.set_item("schedule", "OneTime").unwrap();
            event.set_item("tick", 10).unwrap();

            events.append(event).unwrap();
            config.set_item("scenario_events", events).unwrap();

            // Should fail with error
            let result = py.get_type::<PyOrchestrator>().call_method1("new", (config,));
            assert!(result.is_err(), "Should reject event missing required field");
        });
    }
}

// When pyo3 feature is not enabled, provide empty module
#[cfg(not(feature = "pyo3"))]
mod ffi_tests {}
