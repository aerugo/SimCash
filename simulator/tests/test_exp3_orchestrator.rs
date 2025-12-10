//! Test to reproduce exp3 scenario with full orchestrator
//!
//! This test replicates the Castro exp3 configuration to find the
//! "deadline must be after arrival" panic.

use payment_simulator_core_rs::{
    arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};
use std::collections::HashMap;

/// Helper to create exp3-like config
fn create_exp3_config(seed: u64) -> OrchestratorConfig {
    let mut counterparty_a = HashMap::new();
    counterparty_a.insert("BANK_B".to_string(), 1.0);

    let mut counterparty_b = HashMap::new();
    counterparty_b.insert("BANK_A".to_string(), 1.0);

    let arrival_a = ArrivalConfig {
        rate_per_tick: 1.5,
        amount_distribution: AmountDistribution::LogNormal {
            mean: 15000.0,
            std_dev: 7500.0,
        },
        counterparty_weights: counterparty_a,
        deadline_range: (1, 3),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let arrival_b = ArrivalConfig {
        rate_per_tick: 1.5,
        amount_distribution: AmountDistribution::LogNormal {
            mean: 15000.0,
            std_dev: 7500.0,
        },
        counterparty_weights: counterparty_b,
        deadline_range: (1, 3),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    OrchestratorConfig {
        ticks_per_day: 3,
        num_days: 1,
        rng_seed: seed,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 0,
                unsecured_cap: 75000,
                policy: PolicyConfig::Fifo, // Simple policy for testing
                arrival_config: Some(arrival_a),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: Some(10_000_000),
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 0,
                unsecured_cap: 75000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_b),
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: Some(10_000_000),
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
        eod_rush_threshold: 0.8,
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        deferred_crediting: true,
        deadline_cap_at_eod: true,
        priority_escalation: Default::default(),
    }
}

/// Test with many seeds
#[test]
fn test_exp3_full_orchestrator_many_seeds() {
    for seed in 0..1000 {
        let config = create_exp3_config(seed);
        let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

        // Run all ticks
        for tick in 0..3 {
            match orch.tick() {
                Ok(_) => {}
                Err(e) => {
                    panic!("Failed at seed={}, tick={}: {:?}", seed, tick, e);
                }
            }
        }
    }
}

/// Test specific edge case with arrivals at last tick
#[test]
fn test_exp3_high_rate_last_tick() {
    // Use a config with very high arrival rate to guarantee arrivals
    let mut counterparty_a = HashMap::new();
    counterparty_a.insert("BANK_B".to_string(), 1.0);

    let arrival_a = ArrivalConfig {
        rate_per_tick: 100.0, // Very high to guarantee arrivals
        amount_distribution: AmountDistribution::Uniform { min: 1000, max: 10000 },
        counterparty_weights: counterparty_a,
        deadline_range: (1, 3),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 3,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 100_000_000, // High balance
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_a),
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
                opening_balance: 100_000_000,
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
        eod_rush_threshold: 0.8,
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
        deferred_crediting: true,
        deadline_cap_at_eod: true,
        priority_escalation: Default::default(),
    };

    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    for tick in 0..3 {
        let result = orch.tick().expect(&format!("Failed at tick {}", tick));
        println!("Tick {}: {} arrivals", tick, result.num_arrivals);
    }
}
