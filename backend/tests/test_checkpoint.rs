//! Checkpoint Tests - Save/Load Simulation State
//!
//! Test suite for serializing and deserializing complete orchestrator state.
//! Following TDD: These tests are written FIRST and should fail initially.
//!
//! Critical invariants tested:
//! - Determinism: Restored simulation produces identical results
//! - Balance conservation: Total balance preserved across save/load
//! - Queue integrity: No orphaned or duplicate transactions
//! - Config matching: Reject state from different config

use payment_simulator_core_rs::arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution};
use payment_simulator_core_rs::orchestrator::{
    AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering,
};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;
use std::collections::HashMap;

// ============================================================================
// Test Helpers
// ============================================================================

/// Create minimal test orchestrator with 2 agents
fn create_test_orchestrator() -> Orchestrator {
    create_test_orchestrator_with_seed(42)
}

/// Create test orchestrator with specific seed
fn create_test_orchestrator_with_seed(seed: u64) -> Orchestrator {
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: seed,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000, // $10,000
                unsecured_cap: 500_000,      // $5,000
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 2_000_000, // $20,000
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                    collateral_haircut: None,
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
    };

    Orchestrator::new(config).expect("Failed to create test orchestrator")
}

/// Create orchestrator with automatic arrivals for determinism testing
fn create_test_orchestrator_with_arrivals() -> Orchestrator {
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000_000, // $100,000
                unsecured_cap: 1_000_000,     // $10,000
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5, // Poisson λ
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,  // $100
                        max: 100_000, // $1,000
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_B".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 1_000_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 100_000,
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_A".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
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
    };

    Orchestrator::new(config).expect("Failed to create orchestrator with arrivals")
}

// ============================================================================
// Unit Tests - Save State
// ============================================================================

#[test]
fn test_save_state_returns_valid_json() {
    let orchestrator = create_test_orchestrator();

    // Should return JSON string
    let state_json = orchestrator
        .save_state()
        .expect("save_state() should succeed");

    // Should be valid JSON
    let parsed: serde_json::Value =
        serde_json::from_str(&state_json).expect("save_state() should return valid JSON");

    assert!(parsed.is_object(), "Root should be JSON object");
}

#[test]
fn test_save_state_includes_all_required_fields() {
    let orchestrator = create_test_orchestrator();
    let state_json = orchestrator.save_state().unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&state_json).unwrap();

    // Required temporal fields
    assert!(parsed["current_tick"].is_number(), "Missing current_tick");
    assert!(parsed["current_day"].is_number(), "Missing current_day");

    // Required determinism field
    assert!(parsed["rng_seed"].is_number(), "Missing rng_seed");

    // Required state arrays
    assert!(parsed["agents"].is_array(), "Missing agents array");
    assert!(
        parsed["transactions"].is_array(),
        "Missing transactions array"
    );
    assert!(parsed["rtgs_queue"].is_array(), "Missing rtgs_queue array");

    // Required config validation
    assert!(parsed["config_hash"].is_string(), "Missing config_hash");
}

#[test]
fn test_save_state_captures_agent_data() {
    let orchestrator = create_test_orchestrator();
    let state_json = orchestrator.save_state().unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&state_json).unwrap();

    let agents = parsed["agents"].as_array().unwrap();
    assert_eq!(agents.len(), 2, "Should have 2 agents");

    // Check first agent has required fields
    let agent = &agents[0];
    assert!(agent["id"].is_string(), "Agent missing id");
    assert!(agent["balance"].is_number(), "Agent missing balance");
    assert!(
        agent["unsecured_cap"].is_number(),
        "Agent missing unsecured_cap"
    );
    assert!(
        agent["outgoing_queue"].is_array(),
        "Agent missing outgoing_queue"
    );
    assert!(
        agent["posted_collateral"].is_number(),
        "Agent missing posted_collateral"
    );
}

// ============================================================================
// Unit Tests - Load State
// ============================================================================

#[test]
fn test_load_state_restores_exact_state() {
    let mut original = create_test_orchestrator();

    // Run a few ticks to create non-trivial state
    for _ in 0..10 {
        original.tick().unwrap();
    }

    // Save state
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
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
    };
    let state_json = original.save_state().unwrap();

    // Load state
    let restored =
        Orchestrator::load_state(config, &state_json).expect("load_state() should succeed");

    // Verify exact match
    assert_eq!(restored.current_tick(), original.current_tick());
    assert_eq!(restored.current_day(), original.current_day());
}

// ============================================================================
// Critical Test: Determinism After Restore
// ============================================================================

#[test]
fn test_determinism_after_restore() {
    let mut sim1 = create_test_orchestrator_with_arrivals();

    // Run 50 ticks to build up state
    for _ in 0..50 {
        sim1.tick().unwrap();
    }

    // Save state at tick 50
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 1_000_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 100_000,
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_B".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 1_000_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 100_000,
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_A".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
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
    };
    let state_json = sim1.save_state().unwrap();

    // Continue sim1 for 50 more ticks
    let mut results1 = Vec::new();
    for _ in 0..50 {
        let result = sim1.tick().unwrap();
        results1.push((result.num_arrivals, result.num_settlements));
    }

    // Restore sim2 from checkpoint at tick 50
    let mut sim2 =
        Orchestrator::load_state(config, &state_json).expect("load_state() should succeed");

    // Run sim2 for 50 ticks (same as continuation)
    let mut results2 = Vec::new();
    for _ in 0..50 {
        let result = sim2.tick().unwrap();
        results2.push((result.num_arrivals, result.num_settlements));
    }

    // Results MUST be IDENTICAL (determinism guarantee)
    assert_eq!(
        results1, results2,
        "Restored simulation must produce identical results (determinism violated!)"
    );
}

// ============================================================================
// Critical Test: Balance Conservation
// ============================================================================

#[test]
fn test_balance_conservation_preserved() {
    let mut orchestrator = create_test_orchestrator_with_arrivals();

    // Initial total balance
    let initial_balance: i64 = 10_000_000 + 10_000_000; // Both agents

    // Run simulation to generate transactions
    for _ in 0..100 {
        orchestrator.tick().unwrap();
    }

    // Save and restore
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 1_000_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 100_000,
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_B".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 1_000_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 100_000,
                    },
                    counterparty_weights: {
                        let mut weights = HashMap::new();
                        weights.insert("BANK_A".to_string(), 1.0);
                        weights
                    },
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 5 },
                    divisible: false,
                }),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
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
    };
    let state_json = orchestrator.save_state().unwrap();
    let restored = Orchestrator::load_state(config, &state_json).unwrap();

    // Get balances from restored state
    let restored_balances = restored.get_all_agent_balances();
    let restored_total: i64 = restored_balances.values().sum();

    // Balance MUST be conserved (fundamental invariant)
    assert_eq!(
        restored_total, initial_balance,
        "Balance conservation violated! Initial: {}, Restored: {}",
        initial_balance, restored_total
    );
}

// ============================================================================
// Test: Config Mismatch Detection
// ============================================================================

#[test]
fn test_config_mismatch_rejected() {
    let mut orchestrator = create_test_orchestrator();
    orchestrator.tick().unwrap();

    let state_json = orchestrator.save_state().unwrap();

    // Create DIFFERENT config (different seed)
    let different_config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999, // DIFFERENT SEED
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
    };

    // Should fail to load with config mismatch error
    let result = Orchestrator::load_state(different_config, &state_json);
    assert!(result.is_err(), "Should reject mismatched config");

    let err_msg = format!("{:?}", result.unwrap_err());
    assert!(
        err_msg.contains("ConfigMismatch") || err_msg.contains("config"),
        "Error should mention config mismatch, got: {}",
        err_msg
    );
}

// ============================================================================
// Test: Corrupted JSON Rejected
// ============================================================================

#[test]
fn test_corrupted_state_json_rejected() {
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 1_000_000,
            unsecured_cap: 500_000,
            policy: PolicyConfig::Fifo,
            arrival_config: None,
                arrival_bands: None,
            posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    };

    // Invalid JSON
    let corrupted_json = r#"{"current_tick": "not_a_number"}"#;

    let result = Orchestrator::load_state(config, corrupted_json);
    assert!(result.is_err(), "Should reject corrupted JSON");
}

// ============================================================================
// Property Tests - Multiple Seeds
// ============================================================================

#[test]
fn test_save_load_roundtrip_preserves_state_multiple_seeds() {
    // Property test: save/load should preserve state for ANY seed
    for seed in [42, 123, 999, 54321] {
        let mut original = create_test_orchestrator_with_seed(seed);

        // Random number of ticks based on seed
        let num_ticks = (seed % 100) + 1;
        for _ in 0..num_ticks {
            original.tick().unwrap();
        }

        // Save and restore
        let config = OrchestratorConfig {
            ticks_per_day: 100,
        eod_rush_threshold: 0.8,            num_days: 1,
            rng_seed: seed,
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
        };
        let state_json = original.save_state().unwrap();
        let mut restored = Orchestrator::load_state(config, &state_json).unwrap();

        // Continue both for same number of ticks
        for _ in 0..10 {
            let r1 = original.tick().unwrap();
            let r2 = restored.tick().unwrap();

            assert_eq!(
                r1.num_arrivals, r2.num_arrivals,
                "Seed {}: arrivals differ after restore",
                seed
            );
            assert_eq!(
                r1.num_settlements, r2.num_settlements,
                "Seed {}: settlements differ after restore",
                seed
            );
        }
    }
}
