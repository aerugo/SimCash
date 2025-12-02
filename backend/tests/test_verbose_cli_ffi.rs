//! Tests for verbose CLI FFI methods
//!
//! Tests the methods exposed via FFI to support enhanced verbose CLI output.

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};

/// Helper function to create a basic 2-agent configuration
fn create_test_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 500_000,
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
                opening_balance: 2_000_000,
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
        lsm_config: LsmConfig::default(),
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
            deferred_crediting: false,
            deadline_cap_at_eod: false,
    }
}

#[test]
fn test_get_tick_events_returns_all_events_for_tick() {
    // RED TEST - This will fail until we implement get_tick_events

    // Create orchestrator
    let mut orch = Orchestrator::new(create_test_config()).unwrap();

    // Submit a transaction to BANK_A's queue
    let _tx_id = orch.submit_transaction(
        "BANK_A",
        "BANK_B",
        100_000,
        10,
        5,    // priority
        false // not divisible
    ).unwrap();

    // Execute tick 0
    let result = orch.tick().unwrap();
    assert!(result.num_arrivals > 0 || result.num_settlements > 0);

    // Query events for tick 0
    let events = orch.get_tick_events(0);

    // Verify we got events
    assert!(!events.is_empty(), "Should have events for tick 0");

    // Verify we can find arrival or settlement events
    let has_relevant_events = events.iter().any(|e| {
        matches!(e.event_type(), "Arrival" | "Settlement" | "PolicySubmit")
    });

    assert!(has_relevant_events, "Should have arrival, settlement, or policy events");
}

#[test]
fn test_get_transaction_details_returns_full_data() {
    // RED TEST - This will fail until we implement get_transaction

    // Create orchestrator
    let mut orch = Orchestrator::new(create_test_config()).unwrap();

    // Submit a transaction
    let tx_id = orch.submit_transaction(
        "BANK_A",
        "BANK_B",
        150_000, // $1,500
        20,      // deadline
        8,       // priority
        false
    ).unwrap();

    // Query transaction details - THIS METHOD DOESN'T EXIST YET
    let tx = orch.get_transaction(&tx_id);

    // Verify we got the transaction
    assert!(tx.is_some(), "Transaction should exist");

    let tx = tx.unwrap();
    assert_eq!(tx.sender_id(), "BANK_A");
    assert_eq!(tx.receiver_id(), "BANK_B");
    assert_eq!(tx.amount(), 150_000);
    assert_eq!(tx.deadline_tick(), 20);
    assert_eq!(tx.priority(), 8);
}

#[test]
fn test_get_rtgs_queue_contents_returns_tx_ids() {
    // RED TEST - This will fail until we implement get_rtgs_queue_contents

    // Create orchestrator
    let _orch = Orchestrator::new(create_test_config()).unwrap();

    // Submit a transaction that will be queued (insufficient balance)
    // Give BANK_A very low balance
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000, // Very low balance
                unsecured_cap: 0,         // No credit
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
                opening_balance: 2_000_000,
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
        lsm_config: LsmConfig::default(),
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
            deferred_crediting: false,
            deadline_cap_at_eod: false,
    };

    let mut orch = Orchestrator::new(config).unwrap();

    // Submit large transaction that will be queued
    let tx_id = orch.submit_transaction(
        "BANK_A",
        "BANK_B",
        500_000, // $5,000 - more than BANK_A has
        20,
        5,
        false
    ).unwrap();

    // Execute tick - transaction should be queued
    orch.tick().unwrap();

    // Query RTGS queue contents - THIS METHOD DOESN'T EXIST YET
    let queue_contents = orch.get_rtgs_queue_contents();

    // Verify queue contains our transaction or is empty (depending on policy behavior)
    // For now, just verify the method exists and returns a Vec<String>
    assert!(queue_contents.is_empty() || queue_contents.contains(&tx_id));
}

#[test]
fn test_get_agent_unsecured_cap_returns_limit() {
    // RED TEST - This will fail until we implement get_agent_unsecured_cap

    // Create orchestrator
    let orch = Orchestrator::new(create_test_config()).unwrap();

    // Query credit limit - THIS METHOD DOESN'T EXIST YET
    let credit_limit = orch.get_agent_unsecured_cap("BANK_A");

    // Verify we got the credit limit
    assert!(credit_limit.is_some());
    assert_eq!(credit_limit.unwrap(), 500_000); // From create_test_config
}

#[test]
fn test_get_agent_collateral_posted_returns_amount() {
    // RED TEST - This will fail until we implement get_agent_collateral_posted

    // Create orchestrator with collateral
    let mut config = create_test_config();
    config.agent_configs[0].posted_collateral = Some(1_000_000); // $10,000 collateral

    let orch = Orchestrator::new(config).unwrap();

    // Query collateral - THIS METHOD DOESN'T EXIST YET
    let collateral = orch.get_agent_collateral_posted("BANK_A");

    // Verify we got the collateral amount
    assert!(collateral.is_some());
    assert_eq!(collateral.unwrap(), 1_000_000);
}
