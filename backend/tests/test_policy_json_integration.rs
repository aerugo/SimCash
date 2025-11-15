// Integration tests for JSON policy loading in orchestrator
//
// Tests that policies can be loaded from JSON files and used in full simulation runs.
// Uses TDD principles - these tests define what Phase 3 should accomplish.

use payment_simulator_core_rs::orchestrator::{
    AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig,
};
use payment_simulator_core_rs::settlement::LsmConfig;

#[test]
fn test_orchestrator_loads_fifo_policy_from_json() {
    // TDD: Define desired behavior - orchestrator should load FIFO from JSON
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 1_000_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Fifo, // Should load from policies/fifo.json
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
        unsecured_cap: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    // Should successfully create orchestrator with JSON-loaded policy
    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit a transaction
    let tx_id = orchestrator
        .submit_transaction("BANK_A", "BANK_A", 100_000, 50, 5, false)
        .expect("Failed to submit transaction");

    // Tick should process transaction with FIFO policy (always releases)
    let result = orchestrator.tick().expect("Failed to tick");

    // FIFO should have submitted the transaction
    assert_eq!(result.num_settlements, 1, "FIFO should submit transaction");
}

#[test]
fn test_orchestrator_loads_deadline_policy_from_json_with_default_params() {
    // TDD: Deadline policy loaded from JSON with default urgency_threshold=5
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 1_000_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Deadline {
                urgency_threshold: 5, // Should inject this into JSON tree
            },
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
        unsecured_cap: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit an urgent transaction (deadline in 3 ticks, < urgency_threshold=5)
    let _urgent_tx = orchestrator
        .submit_transaction("BANK_A", "BANK_A", 100_000, 3, 5, false)
        .expect("Failed to submit urgent transaction");

    // Tick 0 → Tick 1 (deadline in 2 ticks now, still urgent)
    let result = orchestrator.tick().expect("Failed to tick");

    // Urgent transaction should be submitted on first tick
    // (ticks_to_deadline = 2, which is <= urgency_threshold = 5)
    assert!(
        result.num_settlements > 0,
        "Deadline policy should submit urgent transaction"
    );
}

#[test]
fn test_orchestrator_loads_deadline_policy_with_custom_threshold() {
    // TDD: Deadline policy with custom threshold parameter
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 1_000_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Deadline {
                urgency_threshold: 10, // Custom threshold, should override JSON default
            },
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
        unsecured_cap: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit transaction with deadline in 8 ticks
    // With threshold=10, this should be urgent (8 <= 10)
    let _tx = orchestrator
        .submit_transaction("BANK_A", "BANK_A", 100_000, 8, 5, false)
        .expect("Failed to submit transaction");

    // Tick should process with urgency_threshold=10
    let result = orchestrator.tick().expect("Failed to tick");

    // Should submit (8 ticks remaining <= 10 threshold)
    assert!(
        result.num_settlements > 0,
        "Transaction should be urgent with threshold=10"
    );
}

#[test]
fn test_orchestrator_loads_liquidity_aware_policy_from_json() {
    // TDD: LiquidityAware policy with parameter injection
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 300_000, // $3,000
            unsecured_cap: 0,
            policy: PolicyConfig::LiquidityAware {
                target_buffer: 100_000, // Keep at least $1,000
                urgency_threshold: 5,
            },
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
        unsecured_cap: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit transaction that would violate buffer (300k - 250k = 50k < 100k buffer)
    let _tx1 = orchestrator
        .submit_transaction("BANK_A", "BANK_A", 250_000, 100, 5, false)
        .expect("Failed to submit transaction");

    // Tick should hold transaction (violates buffer)
    let result1 = orchestrator.tick().expect("Failed to tick");
    assert_eq!(
        result1.num_settlements, 0,
        "Should hold transaction that violates buffer"
    );

    // Verify transaction still in Queue 1
    assert_eq!(
        orchestrator.get_queue1_size("BANK_A"),
        Some(1),
        "Transaction should still be in Queue 1"
    );

    // Submit safe transaction (300k - 150k = 150k > 100k buffer)
    let _tx2 = orchestrator
        .submit_transaction("BANK_A", "BANK_A", 150_000, 100, 5, false)
        .expect("Failed to submit safe transaction");

    // Tick should submit safe transaction
    let result2 = orchestrator.tick().expect("Failed to tick");
    assert!(
        result2.num_settlements > 0,
        "Should submit transaction that preserves buffer"
    );
}

#[test]
fn test_multi_agent_different_json_policies() {
    // TDD: Multiple agents with different JSON policies
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo, // FIFO from JSON
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            unsecured_cap: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 5,
                }, // Deadline from JSON
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            unsecured_cap: None,
            },
            AgentConfig {
                id: "BANK_C".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 500_000,
                    urgency_threshold: 5,
                }, // LiquidityAware from JSON
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            unsecured_cap: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    // Should successfully create orchestrator with all three JSON policies
    let orchestrator =
        Orchestrator::new(config).expect("Failed to create multi-agent orchestrator");

    // Verify all agents exist
    assert_eq!(orchestrator.get_agent_ids().len(), 3);
    assert!(orchestrator.get_agent_balance("BANK_A").is_some());
    assert!(orchestrator.get_agent_balance("BANK_B").is_some());
    assert!(orchestrator.get_agent_balance("BANK_C").is_some());
}

#[test]
fn test_determinism_with_json_policies() {
    // TDD: JSON policies should produce deterministic results (same seed = same output)
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999, // Fixed seed
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 500_000,
            unsecured_cap: 200_000,
            policy: PolicyConfig::LiquidityAware {
                target_buffer: 100_000,
                urgency_threshold: 5,
            },
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
        unsecured_cap: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    // Run simulation 1
    let mut orch1 = Orchestrator::new(config.clone()).expect("Failed to create orchestrator 1");
    orch1
        .submit_transaction("BANK_A", "BANK_A", 100_000, 50, 5, false)
        .expect("Failed to submit tx 1");
    orch1
        .submit_transaction("BANK_A", "BANK_A", 150_000, 60, 5, false)
        .expect("Failed to submit tx 2");

    let result1_tick1 = orch1.tick().expect("Failed to tick 1");
    let result1_tick2 = orch1.tick().expect("Failed to tick 2");
    let balance1 = orch1.get_agent_balance("BANK_A");

    // Run simulation 2 with same config and actions
    let mut orch2 = Orchestrator::new(config).expect("Failed to create orchestrator 2");
    orch2
        .submit_transaction("BANK_A", "BANK_A", 100_000, 50, 5, false)
        .expect("Failed to submit tx 1");
    orch2
        .submit_transaction("BANK_A", "BANK_A", 150_000, 60, 5, false)
        .expect("Failed to submit tx 2");

    let result2_tick1 = orch2.tick().expect("Failed to tick 1");
    let result2_tick2 = orch2.tick().expect("Failed to tick 2");
    let balance2 = orch2.get_agent_balance("BANK_A");

    // Results should be identical (determinism)
    assert_eq!(
        result1_tick1.num_settlements, result2_tick1.num_settlements,
        "Tick 1 settlements should match"
    );
    assert_eq!(
        result1_tick2.num_settlements, result2_tick2.num_settlements,
        "Tick 2 settlements should match"
    );
    assert_eq!(balance1, balance2, "Final balances should match");
}
