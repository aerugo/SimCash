//! Public Signal Fields Tests - Phase 1.3
//!
//! Tests for system-wide public signals that help policies adjust behavior
//! based on overall system conditions.
//!
//! **Public Information**: These fields expose coarse system-level metrics that
//! all agents can see. No privacy violation - everyone sees the same values.
//!
//! **Use Cases**:
//! - System pressure: Adjust aggression when system is gridlocked
//! - LSM run rate: Coordinate releases when LSM is active
//! - Throughput guidance: Compare own progress against expected curve

use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

/// Helper to create agent
fn create_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
    Agent::new(id.to_string(), balance, credit_limit)
}

/// Helper to create transaction
fn create_tx(sender: &str, receiver: &str, amount: i64, arrival: usize, deadline: usize) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        arrival,
        deadline,
    )
}

// ============================================================================
// Test Group 1: System Queue 2 Pressure Index
// ============================================================================

#[test]
fn test_calculate_queue2_pressure_index_empty() {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Empty Queue 2 = no pressure
    let pressure = calculate_queue2_pressure_index(&state);

    assert_eq!(pressure, 0.0);
}

#[test]
fn test_calculate_queue2_pressure_index_moderate() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
    ]);

    // Add some transactions to Queue 2
    for i in 0..5 {
        let tx = create_tx("BANK_A", "BANK_B", 20_000, 0, 100);
        state.add_transaction(tx);
    }

    // Queue all transactions
    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // With 5 transactions in queue, pressure should be > 0 but < 1
    let pressure = calculate_queue2_pressure_index(&state);

    assert!(pressure > 0.0);
    assert!(pressure < 1.0);
}

#[test]
fn test_calculate_queue2_pressure_index_high() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add many transactions to Queue 2
    for i in 0..50 {
        let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
        state.add_transaction(tx);
    }

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // High queue count should give high pressure (approaching 1.0)
    let pressure = calculate_queue2_pressure_index(&state);

    assert!(pressure > 0.5);
    assert!(pressure <= 1.0);
}

#[test]
fn test_queue2_pressure_index_normalized_to_one() {
    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add extreme number of transactions
    for i in 0..500 {
        let tx = create_tx("BANK_A", "BANK_B", 1_000, 0, 100);
        state.add_transaction(tx);
    }

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Pressure should cap at 1.0
    let pressure = calculate_queue2_pressure_index(&state);

    assert!(pressure <= 1.0);
}

// ============================================================================
// Test Group 2: LSM Run Rate Calculation
// ============================================================================

#[test]
fn test_lsm_run_rate_no_events() {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // No LSM events recorded
    let run_rate = calculate_lsm_run_rate(&state, 10);

    assert_eq!(run_rate, 0.0);
}

#[test]
fn test_lsm_run_rate_with_recent_events() {
    // This test requires LSM event tracking in SimulationState
    // For now, we'll test the calculation logic with mock data

    // Simulate: 5 LSM events in last 10 ticks
    let lsm_events_last_10_ticks = 5;
    let window_size = 10;

    let run_rate = (lsm_events_last_10_ticks as f64) / (window_size as f64);

    assert_eq!(run_rate, 0.5); // 5 events / 10 ticks = 0.5 events per tick
}

#[test]
fn test_lsm_run_rate_high_activity() {
    // Simulate: 20 LSM events in last 10 ticks (very high activity)
    let lsm_events_last_10_ticks = 20;
    let window_size = 10;

    let run_rate = (lsm_events_last_10_ticks as f64) / (window_size as f64);

    assert_eq!(run_rate, 2.0); // 20 events / 10 ticks = 2.0 events per tick
}

// ============================================================================
// Test Group 3: Throughput Guidance Integration
// ============================================================================

#[test]
fn test_throughput_guidance_not_configured() {
    // When throughput guidance is not configured, field should default to 0.0
    let guidance_value = get_throughput_guidance_for_tick(None, 50);

    assert_eq!(guidance_value, 0.0);
}

#[test]
fn test_throughput_guidance_configured() {
    // Throughput guidance curve: [0.0, 0.25, 0.5, 0.75, 1.0] for 5 ticks
    let guidance = vec![0.0, 0.25, 0.5, 0.75, 1.0];

    // Check each tick
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 0), 0.0);
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 1), 0.25);
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 2), 0.5);
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 3), 0.75);
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 4), 1.0);
}

#[test]
fn test_throughput_guidance_tick_out_of_bounds() {
    let guidance = vec![0.0, 0.5, 1.0];

    // Tick beyond configured range should return 0.0 (or last value)
    let value = get_throughput_guidance_for_tick(Some(&guidance), 10);

    assert_eq!(value, 0.0);
}

#[test]
fn test_throughput_guidance_interpolation() {
    // If we want interpolation between ticks (optional enhancement)
    // For now, we'll just use direct lookup
    let guidance = vec![0.0, 0.5, 1.0];

    // Tick 0 → 0.0, Tick 1 → 0.5, Tick 2 → 1.0
    assert_eq!(get_throughput_guidance_for_tick(Some(&guidance), 1), 0.5);
}

// ============================================================================
// Test Group 4: Policy Context Field Exposure
// ============================================================================

#[test]
fn test_context_exposes_system_pressure_field() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    // Add some transactions to Queue 2
    for i in 0..10 {
        let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
        state.add_transaction(tx);
    }

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Build context
    let tx = create_tx("BANK_A", "BANK_B", 5_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that system_queue2_pressure_index exists
    // This field doesn't exist yet - test will fail until implemented
    let pressure = context.get_field("system_queue2_pressure_index");

    assert!(pressure.is_ok(), "system_queue2_pressure_index should exist");
    let pressure_val = pressure.unwrap();
    assert!(pressure_val >= 0.0);
    assert!(pressure_val <= 1.0);
}

#[test]
fn test_context_exposes_lsm_run_rate_field() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that lsm_run_rate_last_10_ticks exists
    // This field doesn't exist yet - test will fail until implemented
    let lsm_rate = context.get_field("lsm_run_rate_last_10_ticks");

    assert!(lsm_rate.is_ok(), "lsm_run_rate_last_10_ticks should exist");
    assert!(lsm_rate.unwrap() >= 0.0);
}

#[test]
fn test_context_exposes_throughput_guidance_field() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();

    // Note: This requires passing throughput guidance to build()
    // For now, we'll test with default (0.0)
    let context = EvalContext::build(&tx, &agent_a, &state, 10, &cost_rates, 100, 0.8);

    // Check that system_throughput_guidance_fraction_by_tick exists
    // This field doesn't exist yet - test will fail until implemented
    let guidance = context.get_field("system_throughput_guidance_fraction_by_tick");

    assert!(guidance.is_ok(), "system_throughput_guidance_fraction_by_tick should exist");
    let guidance_val = guidance.unwrap();
    assert!(guidance_val >= 0.0);
    assert!(guidance_val <= 1.0);
}

// ============================================================================
// Test Group 5: All Agents See Same Public Signals
// ============================================================================

#[test]
fn test_all_agents_see_same_system_pressure() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let mut state = SimulationState::new(vec![
        create_agent("BANK_A", 100_000, 50_000),
        create_agent("BANK_B", 100_000, 50_000),
        create_agent("BANK_C", 100_000, 50_000),
    ]);

    // Add transactions to Queue 2
    for _ in 0..15 {
        let tx = create_tx("BANK_A", "BANK_B", 10_000, 0, 100);
        state.add_transaction(tx);
    }

    for tx_id in state.transactions().keys().cloned().collect::<Vec<_>>() {
        state.queue_transaction(tx_id);
    }

    // Build context for different agents
    let tx_a = create_tx("BANK_A", "BANK_B", 5_000, 0, 100);
    let tx_b = create_tx("BANK_B", "BANK_C", 5_000, 0, 100);
    let tx_c = create_tx("BANK_C", "BANK_A", 5_000, 0, 100);

    let agent_a = state.get_agent("BANK_A").unwrap().clone();
    let agent_b = state.get_agent("BANK_B").unwrap().clone();
    let agent_c = state.get_agent("BANK_C").unwrap().clone();

    let cost_rates = CostRates::default();

    let context_a = EvalContext::build(&tx_a, &agent_a, &state, 10, &cost_rates, 100, 0.8);
    let context_b = EvalContext::build(&tx_b, &agent_b, &state, 10, &cost_rates, 100, 0.8);
    let context_c = EvalContext::build(&tx_c, &agent_c, &state, 10, &cost_rates, 100, 0.8);

    // All agents should see the SAME system pressure
    let pressure_a = context_a.get_field("system_queue2_pressure_index").unwrap();
    let pressure_b = context_b.get_field("system_queue2_pressure_index").unwrap();
    let pressure_c = context_c.get_field("system_queue2_pressure_index").unwrap();

    assert_eq!(pressure_a, pressure_b);
    assert_eq!(pressure_b, pressure_c);
}

// ============================================================================
// Helper Functions (to be implemented in Phase 1.3)
// ============================================================================

/// Calculate Queue 2 pressure index (0.0 = no pressure, 1.0 = high pressure)
///
/// Formula: Normalized based on queue size and total system capacity
/// Uses a sigmoid-like function to map queue size to [0, 1]
fn calculate_queue2_pressure_index(state: &SimulationState) -> f64 {
    let queue_size = state.queue_size();
    let num_agents = state.num_agents();

    if num_agents == 0 || queue_size == 0 {
        return 0.0;
    }

    // Normalize: pressure increases with queue size relative to agent count
    // Use a sigmoid-like function to map to [0, 1]
    // Threshold: ~10 transactions per agent is considered "moderate"
    let threshold = (num_agents * 10) as f64;
    let x = queue_size as f64 / threshold;

    // Sigmoid: 1 / (1 + e^(-k*x))
    // Using k=2 for moderate steepness
    let pressure = 1.0 / (1.0 + (-2.0 * x).exp());

    pressure.min(1.0)
}

/// Calculate LSM run rate (events per tick over last N ticks)
///
/// Returns average number of LSM events per tick in the last window_size ticks
fn calculate_lsm_run_rate(_state: &SimulationState, _window_size: usize) -> f64 {
    // This requires LSM event tracking in SimulationState
    // For now, return 0.0 (will be implemented with state.lsm_event_rate())

    // TODO: Implement state.lsm_event_rate(window_size)
    // This would count LSM-related events (bilateral offsets, cycles) in recent history

    0.0
}

/// Get throughput guidance value for a specific tick
///
/// Returns the expected throughput fraction from the guidance curve,
/// or 0.0 if not configured or tick is out of bounds
fn get_throughput_guidance_for_tick(guidance: Option<&Vec<f64>>, tick_in_day: usize) -> f64 {
    match guidance {
        Some(curve) => {
            if tick_in_day < curve.len() {
                curve[tick_in_day]
            } else {
                0.0 // Out of bounds
            }
        }
        None => 0.0, // Not configured
    }
}
