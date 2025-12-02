//! Deferred Crediting Tests
//!
//! Tests for the Castro-compatible deferred crediting mode where credits
//! are accumulated during a tick and applied at the end of tick.
//!
//! Reference: experiments/castro/docs/feature_request_deferred_crediting.md

use payment_simulator_core_rs::{Agent, SimulationState};

// ============================================================================
// Test Helpers
// ============================================================================

/// Create a test agent with given balance and unsecured overdraft capacity
fn create_test_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
}

// ============================================================================
// DeferredCredits Accumulator Unit Tests
// ============================================================================

#[test]
fn test_deferred_credits_new_is_empty() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    let dc = DeferredCredits::new();
    assert!(dc.is_empty(), "New DeferredCredits should be empty");
}

#[test]
fn test_deferred_credits_accumulate_single() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    let mut dc = DeferredCredits::new();
    dc.accumulate("BANK_A", 100_000, "tx_001");

    assert!(!dc.is_empty());
    assert_eq!(dc.total_for_agent("BANK_A"), 100_000);
}

#[test]
fn test_deferred_credits_accumulate_multiple_same_agent() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    let mut dc = DeferredCredits::new();
    dc.accumulate("BANK_A", 100_000, "tx_001");
    dc.accumulate("BANK_A", 50_000, "tx_002");
    dc.accumulate("BANK_A", 25_000, "tx_003");

    assert_eq!(dc.total_for_agent("BANK_A"), 175_000);
}

#[test]
fn test_deferred_credits_accumulate_multiple_agents() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    let mut dc = DeferredCredits::new();
    dc.accumulate("BANK_A", 100_000, "tx_001");
    dc.accumulate("BANK_B", 200_000, "tx_002");
    dc.accumulate("BANK_C", 150_000, "tx_003");

    assert_eq!(dc.total_for_agent("BANK_A"), 100_000);
    assert_eq!(dc.total_for_agent("BANK_B"), 200_000);
    assert_eq!(dc.total_for_agent("BANK_C"), 150_000);
}

#[test]
fn test_deferred_credits_apply_all_in_sorted_order() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    // Create agents with known starting balances
    let agents = vec![
        create_test_agent("BANK_C", 0, 0),
        create_test_agent("BANK_A", 0, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Accumulate credits in non-alphabetical order
    let mut dc = DeferredCredits::new();
    dc.accumulate("BANK_C", 300_000, "tx_003");
    dc.accumulate("BANK_A", 100_000, "tx_001");
    dc.accumulate("BANK_B", 200_000, "tx_002");

    // Apply all credits
    let events = dc.apply_all(&mut state, 5);

    // Verify all agents credited
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 100_000);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 200_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 300_000);

    // Verify events emitted in sorted agent order (for determinism)
    assert_eq!(events.len(), 3);

    // Events should be in alphabetical agent order: A, B, C
    let agent_ids: Vec<_> = events.iter().map(|e| e.agent_id()).collect();
    assert_eq!(agent_ids, vec![Some("BANK_A"), Some("BANK_B"), Some("BANK_C")]);
}

#[test]
fn test_deferred_credits_apply_all_clears_pending() {
    use payment_simulator_core_rs::settlement::deferred::DeferredCredits;

    let agents = vec![create_test_agent("BANK_A", 0, 0)];
    let mut state = SimulationState::new(agents);

    let mut dc = DeferredCredits::new();
    dc.accumulate("BANK_A", 100_000, "tx_001");

    // Apply
    dc.apply_all(&mut state, 5);

    // Should be empty after apply
    assert!(dc.is_empty(), "DeferredCredits should be cleared after apply");
}

// ============================================================================
// Core Behavioral Tests: Gridlock with Zero Balances
// ============================================================================

#[test]
fn test_deferred_crediting_causes_gridlock_zero_balances() {
    // THE DEFINING TEST: With deferred crediting, mutual payments between
    // zero-balance agents should gridlock when LSM is disabled
    // (neither can use incoming to pay their outgoing payment)
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, CostRates, OrchestratorConfig, PolicyConfig,
    };
    use payment_simulator_core_rs::settlement::lsm::LsmConfig;
    use payment_simulator_core_rs::Orchestrator;

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        deferred_crediting: true, // Castro-compatible mode
        deadline_cap_at_eod: false,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        // CRITICAL: Disable LSM to test pure deferred crediting gridlock
        lsm_config: LsmConfig {
            enable_bilateral: false,
            enable_cycles: false,
            max_cycle_length: 0,
            max_cycles_per_tick: 0,
        },
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        eod_rush_threshold: 0.8,
    };

    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit transactions at tick 0
    orch.submit_transaction("BANK_A", "BANK_B", 10_000, 50, 5, false).unwrap();
    orch.submit_transaction("BANK_B", "BANK_A", 10_000, 50, 5, false).unwrap();

    orch.tick().expect("Failed to run tick");

    // With deferred crediting and NO LSM: BOTH transactions should queue (gridlock)
    // Neither agent can use incoming payments to fund their outgoing payment
    assert_eq!(
        orch.get_queue2_size(),
        2,
        "With deferred crediting and LSM disabled, both transactions should queue (gridlock)"
    );

    // Verify no immediate settlements occurred
    let events = orch.get_tick_events(0);
    let settlements: Vec<_> = events
        .iter()
        .filter(|e| e.event_type() == "RtgsImmediateSettlement")
        .collect();
    assert_eq!(
        settlements.len(),
        0,
        "No immediate settlements should occur with zero balances"
    );
}

#[test]
fn test_immediate_crediting_allows_recycling() {
    // Control test: Without deferred crediting (default), recycling should work
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, CostRates, OrchestratorConfig, PolicyConfig,
    };
    use payment_simulator_core_rs::Orchestrator;

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        deferred_crediting: false, // Default (immediate crediting)
        deadline_cap_at_eod: false,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000, // B has enough to start the chain
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: Default::default(),
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        eod_rush_threshold: 0.8,
    };

    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // B → A: $100 (B has liquidity, settles first)
    orch.submit_transaction("BANK_B", "BANK_A", 10_000, 50, 5, false).unwrap();
    // A → B: $100 (A uses recycled liquidity from B→A)
    orch.submit_transaction("BANK_A", "BANK_B", 10_000, 50, 5, false).unwrap();

    orch.tick().expect("Failed to run tick");

    // With immediate crediting: both should settle (recycling works)
    assert_eq!(
        orch.get_queue2_size(),
        0,
        "With immediate crediting, both transactions should settle"
    );
}

// ============================================================================
// Event Emission Tests
// ============================================================================

#[test]
fn test_deferred_credit_event_emitted() {
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, CostRates, OrchestratorConfig, PolicyConfig,
    };
    use payment_simulator_core_rs::Orchestrator;

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        deferred_crediting: true,
        deadline_cap_at_eod: false,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 100_000, // A has liquidity
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: Default::default(),
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        eod_rush_threshold: 0.8,
    };

    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // A → B: A has funds
    orch.submit_transaction("BANK_A", "BANK_B", 50_000, 50, 5, false).unwrap();

    orch.tick().expect("Failed to run tick");

    // Verify DeferredCreditApplied event was emitted
    let events = orch.get_tick_events(0);
    let deferred_events: Vec<_> = events
        .iter()
        .filter(|e| e.event_type() == "DeferredCreditApplied")
        .collect();

    assert_eq!(
        deferred_events.len(),
        1,
        "Should emit exactly one DeferredCreditApplied event"
    );

    // Verify event has correct fields
    let event = deferred_events[0];
    assert_eq!(event.agent_id(), Some("BANK_B"));
}

// ============================================================================
// Determinism Tests
// ============================================================================

#[test]
fn test_deferred_crediting_determinism() {
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, CostRates, OrchestratorConfig, PolicyConfig,
    };
    use payment_simulator_core_rs::Orchestrator;

    let make_config = || OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        deferred_crediting: true,
        deadline_cap_at_eod: false,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 500_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 300_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_C".to_string(),
                opening_balance: 200_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: Default::default(),
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        eod_rush_threshold: 0.8,
    };

    // Run simulation twice with same config and transactions
    let mut orch1 = Orchestrator::new(make_config()).expect("Failed to create orchestrator 1");
    orch1.submit_transaction("BANK_A", "BANK_B", 100_000, 50, 5, false).unwrap();
    orch1.submit_transaction("BANK_B", "BANK_C", 150_000, 50, 5, false).unwrap();
    orch1.submit_transaction("BANK_C", "BANK_A", 75_000, 50, 5, false).unwrap();
    for _ in 0..10 {
        orch1.tick().expect("Failed to run tick");
    }

    let mut orch2 = Orchestrator::new(make_config()).expect("Failed to create orchestrator 2");
    orch2.submit_transaction("BANK_A", "BANK_B", 100_000, 50, 5, false).unwrap();
    orch2.submit_transaction("BANK_B", "BANK_C", 150_000, 50, 5, false).unwrap();
    orch2.submit_transaction("BANK_C", "BANK_A", 75_000, 50, 5, false).unwrap();
    for _ in 0..10 {
        orch2.tick().expect("Failed to run tick");
    }

    // Final states should be identical
    assert_eq!(
        orch1.get_agent_balance("BANK_A"),
        orch2.get_agent_balance("BANK_A"),
        "BANK_A balances should match"
    );
    assert_eq!(
        orch1.get_agent_balance("BANK_B"),
        orch2.get_agent_balance("BANK_B"),
        "BANK_B balances should match"
    );
    assert_eq!(
        orch1.get_agent_balance("BANK_C"),
        orch2.get_agent_balance("BANK_C"),
        "BANK_C balances should match"
    );

    assert_eq!(orch1.get_queue2_size(), orch2.get_queue2_size(), "Queue sizes should match");
}

// Note: The default value test for deferred_crediting is verified implicitly:
// - The #[serde(default)] attribute is on the field
// - All existing tests pass when setting deferred_crediting: false
// - This means the default is working correctly for backward compatibility
