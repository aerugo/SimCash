//! Integration tests for mid-simulation policy update
//!
//! Phase 1 TDD: RED step — these tests define the expected behavior
//! of Orchestrator::update_agent_policy() before implementation.

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
    Transaction,
};

// =============================================================================
// Helpers
// =============================================================================

/// Minimal FIFO policy JSON (releases everything immediately)
const FIFO_JSON: &str = r#"{
    "version": "1.0",
    "policy_id": "fifo_policy",
    "description": "FIFO - release all",
    "payment_tree": {
        "type": "action",
        "node_id": "A1",
        "action": "Release",
        "parameters": {}
    },
    "strategic_collateral_tree": null,
    "end_of_tick_collateral_tree": null,
    "parameters": {
        "initial_liquidity_fraction": 1.0
    }
}"#;

/// Hold policy JSON (holds everything, never releases)
const HOLD_JSON: &str = r#"{
    "version": "1.0",
    "policy_id": "hold_policy",
    "description": "Hold - queue everything",
    "payment_tree": {
        "type": "action",
        "node_id": "A1",
        "action": "Hold",
        "parameters": {}
    },
    "strategic_collateral_tree": null,
    "end_of_tick_collateral_tree": null,
    "parameters": {
        "initial_liquidity_fraction": 1.0
    }
}"#;

/// Create a 2-agent config, both starting with FIFO
fn create_test_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 2,
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

// =============================================================================
// Test 1: Basic policy swap affects behavior
// =============================================================================

#[test]
fn test_update_policy_basic() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    // Add a transaction and queue it for BANK_A
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    let tx_id = tx.id().to_string();
    orch.state_mut().add_transaction(tx);
    orch.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

    // Run a few ticks with FIFO — transaction should be released and settled
    let result = orch.tick().unwrap();
    assert!(result.num_settlements > 0, "FIFO should settle the transaction");

    // Now swap BANK_A to HOLD policy
    orch.update_agent_policy("BANK_A", HOLD_JSON).unwrap();

    // Add another transaction and queue it
    let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 1, 50);
    let tx2_id = tx2.id().to_string();
    orch.state_mut().add_transaction(tx2);
    orch.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx2_id);

    // Run more ticks — new transaction should be held (not released)
    for _ in 0..5 {
        orch.tick().unwrap();
    }

    // BANK_A's queue should still have the held transaction
    // (HOLD policy holds everything, so outgoing queue should be non-empty)
    let queue_after = orch.get_queue1_size("BANK_A").unwrap_or(0);
    assert!(
        queue_after > 0,
        "After switching to HOLD policy, transactions should remain queued. Queue len: {}",
        queue_after
    );
}

// =============================================================================
// Test 2: Unknown agent returns error
// =============================================================================

#[test]
fn test_update_policy_unknown_agent() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    let result = orch.update_agent_policy("NONEXISTENT", FIFO_JSON);
    assert!(result.is_err());
    let err_msg = result.unwrap_err().to_string();
    assert!(
        err_msg.contains("Unknown agent") || err_msg.contains("NONEXISTENT"),
        "Error should mention unknown agent, got: {}",
        err_msg
    );
}

// =============================================================================
// Test 3: Invalid JSON returns error
// =============================================================================

#[test]
fn test_update_policy_invalid_json() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    let result = orch.update_agent_policy("BANK_A", "not valid json at all");
    assert!(result.is_err());

    // Also test valid JSON but invalid policy structure
    let result2 = orch.update_agent_policy("BANK_A", r#"{"not": "a policy"}"#);
    assert!(result2.is_err());
}

// =============================================================================
// Test 4: Determinism — same swaps at same ticks = identical output
// =============================================================================

#[test]
fn test_update_policy_determinism() {
    // Run 1
    let config1 = create_test_config();
    let mut orch1 = Orchestrator::new(config1).unwrap();

    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    let tx1_id = tx1.id().to_string();
    orch1.state_mut().add_transaction(tx1);
    orch1.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx1_id);

    for _ in 0..10 {
        orch1.tick().unwrap();
    }
    orch1.update_agent_policy("BANK_A", HOLD_JSON).unwrap();

    let tx1b = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 50_000, 10, 50);
    let tx1b_id = tx1b.id().to_string();
    orch1.state_mut().add_transaction(tx1b);
    orch1.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx1b_id);
    for _ in 0..10 {
        orch1.tick().unwrap();
    }
    let costs1 = orch1.get_costs("BANK_A").unwrap();

    // Run 2 — identical
    let config2 = create_test_config();
    let mut orch2 = Orchestrator::new(config2).unwrap();

    let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    let tx2_id = tx2.id().to_string();
    orch2.state_mut().add_transaction(tx2);
    orch2.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx2_id);

    for _ in 0..10 {
        orch2.tick().unwrap();
    }
    orch2.update_agent_policy("BANK_A", HOLD_JSON).unwrap();

    let tx2b = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 50_000, 10, 50);
    let tx2b_id = tx2b.id().to_string();
    orch2.state_mut().add_transaction(tx2b);
    orch2.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx2b_id);
    for _ in 0..10 {
        orch2.tick().unwrap();
    }
    let costs2 = orch2.get_costs("BANK_A").unwrap();

    // INV-2: Must be identical
    assert_eq!(costs1.total_liquidity_cost, costs2.total_liquidity_cost, "Liquidity costs must match");
    assert_eq!(costs1.total_delay_cost, costs2.total_delay_cost, "Delay costs must match");
    assert_eq!(costs1.total_penalty_cost, costs2.total_penalty_cost, "Penalty costs must match");
}

// =============================================================================
// Test 5: Cross day-boundary — policy swap between days
// =============================================================================

#[test]
fn test_update_policy_cross_day_boundary() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    // Run full day 1 (100 ticks)
    for _ in 0..100 {
        orch.tick().unwrap();
    }

    // Swap BANK_A to HOLD between days
    orch.update_agent_policy("BANK_A", HOLD_JSON).unwrap();

    // Add transaction at start of day 2 and queue it
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 100, 150);
    let tx_id = tx.id().to_string();
    orch.state_mut().add_transaction(tx);
    orch.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

    // Run some of day 2
    for _ in 0..20 {
        orch.tick().unwrap();
    }

    // With HOLD policy, the transaction should still be queued
    let queue_len = orch.get_queue1_size("BANK_A").unwrap_or(0);
    assert!(
        queue_len > 0,
        "After day-boundary swap to HOLD, transactions should be queued. Queue len: {}",
        queue_len
    );
}

// =============================================================================
// Test 6: get_agent_policies returns updated config after swap
// =============================================================================

#[test]
fn test_update_policy_config_consistency() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    // Before swap: should be Fifo
    let policies_before = orch.get_agent_policies();
    let bank_a_before = policies_before.iter().find(|(id, _)| id == "BANK_A").unwrap();
    assert!(
        matches!(bank_a_before.1, PolicyConfig::Fifo),
        "Before swap, BANK_A should have Fifo policy"
    );

    // Swap to HOLD
    orch.update_agent_policy("BANK_A", HOLD_JSON).unwrap();

    // After swap: should be FromJson with the HOLD JSON
    let policies_after = orch.get_agent_policies();
    let bank_a_after = policies_after.iter().find(|(id, _)| id == "BANK_A").unwrap();
    match &bank_a_after.1 {
        PolicyConfig::FromJson { json } => {
            assert!(
                json.contains("hold_policy"),
                "Updated policy config should contain the new JSON, got: {}",
                json
            );
        }
        other => panic!(
            "After swap, BANK_A should have FromJson policy, got: {:?}",
            other
        ),
    }

    // BANK_B should be unchanged
    let bank_b = policies_after.iter().find(|(id, _)| id == "BANK_B").unwrap();
    assert!(
        matches!(bank_b.1, PolicyConfig::Fifo),
        "BANK_B should still have Fifo policy"
    );
}
