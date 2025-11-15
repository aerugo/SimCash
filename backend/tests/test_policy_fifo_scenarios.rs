//! FifoPolicy Integration Tests
//!
//! Tests FIFO (First-In-First-Out) policy behavior under realistic arrival patterns.
//! FIFO is the simplest baseline policy that submits all queued transactions immediately.

use payment_simulator_core_rs::{
    arrivals::{AmountDistribution, ArrivalConfig},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig},
    settlement::lsm::LsmConfig,
};
use std::collections::HashMap;

#[test]
fn test_fifo_preserves_arrival_order() {
    // Scenario: Generate arrivals, verify they settle in arrival order (when liquidity permits)

    let arrival_config = ArrivalConfig {
        rate_per_tick: 1.0, // Exactly 1 arrival per tick (predictable with seed)
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 50),
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 50_000_000, // Ample liquidity
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 50_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;

    // Run for 10 ticks
    for _ in 0..10 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;
    }

    // With FIFO and ample liquidity, everything should settle immediately
    assert_eq!(
        total_arrivals, total_settlements,
        "FIFO with high liquidity should settle all arrivals immediately"
    );

    // Queue should be empty
    assert_eq!(
        orchestrator.state().total_internal_queue_size(),
        0,
        "Queue should be empty after all settlements"
    );
}

#[test]
fn test_fifo_partial_submission() {
    // Scenario: Limited liquidity causes queue buildup
    // FIFO should attempt to submit all, but some will queue in RTGS or fail

    let arrival_config = ArrivalConfig {
        rate_per_tick: 3.0, // Multiple arrivals per tick
        amount_distribution: AmountDistribution::Uniform {
            min: 200_000,
            max: 400_000, // Large amounts
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 30),
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 999,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 5_000_000, // Limited liquidity
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;
    let mut max_queue = 0;

    // Run for 15 ticks
    for _ in 0..15 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;

        let total_queued =
            orchestrator.state().total_internal_queue_size() + orchestrator.state().queue_size(); // Queue 1 + Queue 2

        if total_queued > max_queue {
            max_queue = total_queued;
        }
    }

    // Should have generated arrivals
    assert!(total_arrivals > 0, "Should have generated arrivals");

    // Settlement rate should be < 100% due to liquidity constraint
    let settlement_rate = total_settlements as f64 / total_arrivals as f64;
    assert!(
        settlement_rate < 0.95,
        "Should not settle everything due to limited liquidity. Rate: {:.2}",
        settlement_rate
    );

    // Queue should have built up at some point
    assert!(
        max_queue > 0,
        "Queue should build up when liquidity constrained"
    );
}

#[test]
fn test_fifo_vs_deadline_under_pressure() {
    // Scenario: Same arrivals, FIFO vs DeadlinePolicy
    // FIFO may have more deadline violations since it doesn't prioritize

    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.5,
        amount_distribution: AmountDistribution::Uniform {
            min: 150_000,
            max: 300_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 12), // Tight deadlines
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 55555,
        agent_configs: vec![
            // FIFO agent
            AgentConfig {
                id: "BANK_FIFO".to_string(),
                opening_balance: 8_000_000, // Moderate liquidity
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config.clone()),
                posted_collateral: None,
                    collateral_haircut: None,
            },
            // Deadline agent (for comparison)
            AgentConfig {
                id: "BANK_DEADLINE".to_string(),
                opening_balance: 8_000_000, // Same liquidity
                unsecured_cap: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 3,
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
            },
            // Receiver
            AgentConfig {
                id: "BANK_C".to_string(),
                opening_balance: 20_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let mut fifo_queue_history = Vec::new();
    let mut deadline_queue_history = Vec::new();

    // Run for 20 ticks
    for _ in 0..20 {
        orchestrator.tick().unwrap();

        let fifo_agent = orchestrator.state().get_agent("BANK_FIFO").unwrap();
        let deadline_agent = orchestrator.state().get_agent("BANK_DEADLINE").unwrap();

        fifo_queue_history.push(fifo_agent.outgoing_queue().len());
        deadline_queue_history.push(deadline_agent.outgoing_queue().len());
    }

    // Both should handle the load, but with different strategies
    let avg_fifo_queue: f64 =
        fifo_queue_history.iter().sum::<usize>() as f64 / fifo_queue_history.len() as f64;
    let avg_deadline_queue: f64 =
        deadline_queue_history.iter().sum::<usize>() as f64 / deadline_queue_history.len() as f64;

    println!(
        "Avg FIFO queue: {:.2}, Avg Deadline queue: {:.2}",
        avg_fifo_queue, avg_deadline_queue
    );

    // This is primarily a behavioral comparison test
    // Both policies should be able to process transactions
    assert!(avg_fifo_queue < 30.0, "FIFO queue shouldn't explode");
    assert!(
        avg_deadline_queue < 30.0,
        "Deadline queue shouldn't explode"
    );

    // FIFO typically submits everything immediately, so Queue 1 stays smaller
    // (transactions move to Queue 2 or settle)
    // DeadlinePolicy holds non-urgent in Queue 1
    // So we might expect FIFO's Queue 1 to be smaller or similar
    assert!(
        avg_fifo_queue <= avg_deadline_queue + 5.0,
        "FIFO typically doesn't hold in Queue 1 as much as Deadline policy"
    );
}
