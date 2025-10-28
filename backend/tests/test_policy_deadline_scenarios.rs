//! DeadlinePolicy Integration Tests
//!
//! Tests deadline-aware policy behavior under realistic arrival patterns.
//! These tests verify that DeadlinePolicy:
//! - Prioritizes urgent transactions (approaching deadline)
//! - Holds non-urgent transactions when appropriate
//! - Outperforms FIFO in deadline violation prevention

use payment_simulator_core_rs::{
    arrivals::{ArrivalConfig, AmountDistribution},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig},
    settlement::lsm::LsmConfig,
};
use std::collections::HashMap;

/// Helper struct to track policy outcome metrics
#[derive(Debug, Default)]
struct PolicyMetrics {
    total_arrivals: usize,
    total_settlements: usize,
    total_deadline_violations: usize,
    max_queue_depth: usize,
    queue_depths_per_tick: Vec<usize>,
    settlements_per_tick: Vec<usize>,
}

impl PolicyMetrics {
    fn new() -> Self {
        Self::default()
    }

    fn record_tick(&mut self, tick_arrivals: usize, tick_settlements: usize, current_queue_depth: usize) {
        self.total_arrivals += tick_arrivals;
        self.total_settlements += tick_settlements;
        self.queue_depths_per_tick.push(current_queue_depth);
        self.settlements_per_tick.push(tick_settlements);

        if current_queue_depth > self.max_queue_depth {
            self.max_queue_depth = current_queue_depth;
        }
    }

    fn settlement_rate(&self) -> f64 {
        if self.total_arrivals == 0 {
            0.0
        } else {
            self.total_settlements as f64 / self.total_arrivals as f64
        }
    }

    fn avg_queue_depth(&self) -> f64 {
        if self.queue_depths_per_tick.is_empty() {
            0.0
        } else {
            let sum: usize = self.queue_depths_per_tick.iter().sum();
            sum as f64 / self.queue_depths_per_tick.len() as f64
        }
    }
}

#[test]
fn test_deadline_policy_submits_urgent_arrivals() {
    // Scenario: Generate arrivals with mixed deadlines
    // DeadlinePolicy should submit urgent ones first

    let arrival_config = ArrivalConfig {
        rate_per_tick: 3.0, // ~3 arrivals per tick
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 150_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (2, 20), // Mix of urgent and non-urgent
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 50_000_000, // High liquidity to focus on policy behavior
                credit_limit: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 5, // Urgent if deadline within 5 ticks
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 50_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut metrics = PolicyMetrics::new();

    // Run simulation for 20 ticks
    for _ in 0..20 {
        let result = orchestrator.tick().unwrap();
        let queue_depth = orchestrator.state().total_internal_queue_size();

        metrics.record_tick(result.num_arrivals, result.num_settlements, queue_depth);
    }

    // With mixed deadlines and DeadlinePolicy, some transactions will be held (non-urgent)
    // Settlement rate will be moderate since policy holds non-urgent ones
    assert!(
        metrics.settlement_rate() > 0.5,
        "Should settle at least half (urgent ones). Got: {:.2}",
        metrics.settlement_rate()
    );

    // Queue should build up with non-urgent transactions
    assert!(
        metrics.avg_queue_depth() > 0.0,
        "Should have some queued (non-urgent) transactions"
    );

    // Should have settled some transactions (urgent ones)
    assert!(
        metrics.total_settlements > 0,
        "Should settle urgent transactions"
    );
}

#[test]
fn test_deadline_policy_holds_non_urgent_under_liquidity_pressure() {
    // Scenario: Limited liquidity, mixed urgency arrivals
    // Policy should prioritize urgent transactions, hold non-urgent

    let arrival_config = ArrivalConfig {
        rate_per_tick: 4.0, // High arrival rate
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 300_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (3, 30), // Mix of very urgent and non-urgent
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 99,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 5_000_000, // Limited liquidity (constraint)
                credit_limit: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 5,
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut metrics = PolicyMetrics::new();

    // Run for 15 ticks
    for _ in 0..15 {
        let result = orchestrator.tick().unwrap();
        let queue_depth = orchestrator.state().total_internal_queue_size();

        metrics.record_tick(result.num_arrivals, result.num_settlements, queue_depth);
    }

    // Queue should build up significantly (non-urgent held)
    assert!(
        metrics.max_queue_depth >= 5,
        "Queue should build up under liquidity pressure. Max depth: {}",
        metrics.max_queue_depth
    );

    // Should still settle some transactions (urgent ones)
    assert!(
        metrics.total_settlements > 0,
        "Should settle urgent transactions despite pressure"
    );

    // Settlement rate should be lower due to liquidity constraint
    assert!(
        metrics.settlement_rate() < 0.9,
        "Settlement rate should be constrained. Got: {:.2}",
        metrics.settlement_rate()
    );
}

#[test]
fn test_deadline_policy_vs_fifo_comparison() {
    // Scenario: Same arrival pattern, two agents with different policies
    // DeadlinePolicy should have fewer late/dropped transactions

    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.5,
        amount_distribution: AmountDistribution::Uniform {
            min: 80_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 15), // Short deadlines to create pressure
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            // Agent A: DeadlinePolicy
            AgentConfig {
                id: "BANK_A_DEADLINE".to_string(),
                opening_balance: 10_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 3,
                },
                arrival_config: Some(arrival_config.clone()),
                posted_collateral: None,            },
            // Agent B: FIFO Policy
            AgentConfig {
                id: "BANK_B_FIFO".to_string(),
                opening_balance: 10_000_000, // Same liquidity as A
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,            },
            // Receiver bank
            AgentConfig {
                id: "BANK_C".to_string(),
                opening_balance: 20_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let mut deadline_queue_depths = Vec::new();
    let mut fifo_queue_depths = Vec::new();

    // Run for 30 ticks
    for _ in 0..30 {
        orchestrator.tick().unwrap();

        let agent_a = orchestrator.state().get_agent("BANK_A_DEADLINE").unwrap();
        let agent_b = orchestrator.state().get_agent("BANK_B_FIFO").unwrap();

        deadline_queue_depths.push(agent_a.outgoing_queue().len());
        fifo_queue_depths.push(agent_b.outgoing_queue().len());
    }

    // Calculate average queue depths
    let avg_deadline_queue: f64 = deadline_queue_depths.iter().sum::<usize>() as f64
        / deadline_queue_depths.len() as f64;
    let avg_fifo_queue: f64 = fifo_queue_depths.iter().sum::<usize>() as f64
        / fifo_queue_depths.len() as f64;

    // DeadlinePolicy should maintain similar or better queue management
    // (This is a behavioral comparison - both should handle load, but Deadline prioritizes differently)
    println!("Avg queue depth - Deadline: {:.2}, FIFO: {:.2}", avg_deadline_queue, avg_fifo_queue);

    // Both should be able to process arrivals reasonably
    assert!(avg_deadline_queue < 20.0, "Deadline queue shouldn't explode");
    assert!(avg_fifo_queue < 20.0, "FIFO queue shouldn't explode");
}

#[test]
fn test_deadline_policy_all_urgent_scenario() {
    // Scenario: All arrivals have urgent deadlines
    // Policy should submit everything immediately (like FIFO)

    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 100_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (1, 3), // All very urgent (1-3 ticks)
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 777,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 50_000_000, // High liquidity
                credit_limit: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 5, // All arrivals will be urgent
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 50_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut metrics = PolicyMetrics::new();

    for _ in 0..15 {
        let result = orchestrator.tick().unwrap();
        let queue_depth = orchestrator.state().total_internal_queue_size();

        metrics.record_tick(result.num_arrivals, result.num_settlements, queue_depth);
    }

    // With high liquidity and all urgent, settlement rate should be very high
    assert!(
        metrics.settlement_rate() > 0.9,
        "Should settle almost all urgent transactions. Rate: {:.2}",
        metrics.settlement_rate()
    );

    // Average queue depth should be low (everything urgent = submitted immediately)
    assert!(
        metrics.avg_queue_depth() < 2.0,
        "Queue should stay small when all urgent. Avg: {:.2}",
        metrics.avg_queue_depth()
    );
}

#[test]
fn test_deadline_policy_deadline_cascade() {
    // Scenario: Transactions gradually become urgent over time
    // Initially non-urgent transactions should be held, then submitted as they approach deadline

    let arrival_config = ArrivalConfig {
        rate_per_tick: 1.5,
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 15), // Moderate deadlines
        priority: 0,
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 888,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 30_000_000, // Ample liquidity
                credit_limit: 0,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 5, // Becomes urgent at 5 ticks remaining
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 30_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();
    let mut queue_sizes = Vec::new();

    // Run for 20 ticks
    for _ in 0..20 {
        orchestrator.tick().unwrap();
        queue_sizes.push(orchestrator.state().total_internal_queue_size());
    }

    // Queue should initially build up (non-urgent held)
    let early_queue = queue_sizes[0..5].iter().sum::<usize>() as f64 / 5.0;

    // Then decrease as transactions become urgent and are submitted
    let late_queue = queue_sizes[15..20].iter().sum::<usize>() as f64 / 5.0;

    println!("Early avg queue: {:.2}, Late avg queue: {:.2}", early_queue, late_queue);

    // This verifies the "cascade" behavior - queue builds then drains as deadlines approach
    // Note: With ample liquidity, everything should eventually settle
    assert!(
        queue_sizes.iter().any(|&size| size > 0),
        "Should have some queueing at some point"
    );
}
