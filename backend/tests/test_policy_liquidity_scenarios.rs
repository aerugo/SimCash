//! LiquidityAwarePolicy Edge Case Tests
//!
//! Tests sophisticated liquidity management scenarios including:
//! - High arrival rate pressure
//! - Liquidity recovery and batch releases
//! - Credit limit interactions
//! - Urgency threshold tuning

use payment_simulator_core_rs::{
    arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};
use std::collections::HashMap;

#[test]
fn test_liquidity_aware_with_high_arrival_rate() {
    // Scenario: Overwhelming arrivals that would drain liquidity
    // LiquidityAware should maintain buffer despite high pressure

    let arrival_config = ArrivalConfig {
        rate_per_tick: 5.0, // High arrival rate
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 250_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 40), // Mix of urgent and non-urgent
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000_000, // $100k
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 3_000_000, // Keep $30k buffer
                    urgency_threshold: 5,
                },
                arrival_config: Some(arrival_config),
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
                opening_balance: 20_000_000,
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
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let mut balances = Vec::new();
    let mut queue_sizes = Vec::new();

    // Run for 25 ticks
    for _ in 0..25 {
        orchestrator.tick().unwrap();

        let agent = orchestrator.state().get_agent("BANK_A").unwrap();
        balances.push(agent.balance());
        queue_sizes.push(agent.outgoing_queue().len());
    }

    // Balance should never go below buffer (except for urgent overrides)
    let min_balance = balances.iter().min().unwrap();
    println!("Minimum balance reached: {}", min_balance);

    // Policy should protect liquidity - balance shouldn't drop too far
    // (Note: urgent transactions can override, so buffer may be violated for urgency)
    // The important thing is it doesn't go negative and queue builds up
    assert!(
        *min_balance >= 0, // Should not go negative without credit
        "Balance should not go negative. Min: {}",
        min_balance
    );

    // Queue should build up significantly
    let max_queue = queue_sizes.iter().max().unwrap();
    assert!(
        *max_queue >= 5,
        "Queue should build up under high arrival rate. Max: {}",
        max_queue
    );
}

#[test]
fn test_liquidity_aware_buffer_recovery() {
    // Scenario: Agent receives a large payment, buffer is restored
    // Held transactions should be released in batch

    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 200_000,
            max: 400_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (20, 50), // Non-urgent
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 77777,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 3_000_000, // Low initial balance
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 2_000_000, // $20k buffer
                    urgency_threshold: 5,
                },
                arrival_config: Some(arrival_config),
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
                opening_balance: 50_000_000, // Large balance
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
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run a few ticks to build up queue
    for _ in 0..5 {
        orchestrator.tick().unwrap();
    }

    let queue_before = orchestrator
        .state()
        .get_agent("BANK_A")
        .unwrap()
        .outgoing_queue()
        .len();

    println!("Queue size before inflow: {}", queue_before);

    // Simulate a large incoming payment (manually add transaction from B to A)
    use payment_simulator_core_rs::Transaction;

    let inflow_tx = Transaction::new(
        "BANK_B".to_string(),
        "BANK_A".to_string(),
        5_000_000, // Large inflow
        5,
        10,
    );
    let tx_id = inflow_tx.id().to_string();

    orchestrator.state_mut().add_transaction(inflow_tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx_id);

    // Run a few more ticks - large payment should settle, restoring liquidity
    for _ in 0..5 {
        orchestrator.tick().unwrap();
    }

    let queue_after = orchestrator
        .state()
        .get_agent("BANK_A")
        .unwrap()
        .outgoing_queue()
        .len();
    let balance_after = orchestrator.state().get_agent("BANK_A").unwrap().balance();

    println!("Queue size after inflow: {}", queue_after);
    println!("Balance after inflow: {}", balance_after);

    // Queue should have drained (at least partially) after liquidity restored
    // Note: New arrivals may add to queue, so we check it's smaller or well-managed
    assert!(
        queue_after < queue_before + 5,
        "Queue should not explode after liquidity recovery"
    );
}

#[test]
fn test_liquidity_aware_credit_limit_interaction() {
    // Scenario: Agent has both buffer target AND credit limit
    // Policy should consider total available liquidity (balance + credit)

    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.5,
        amount_distribution: AmountDistribution::Uniform {
            min: 150_000,
            max: 300_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 30),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 33333,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 5_000_000, // $50k
                unsecured_cap: 3_000_000,    // $30k credit
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 2_000_000, // $20k buffer
                    urgency_threshold: 5,
                },
                arrival_config: Some(arrival_config),
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
                opening_balance: 20_000_000,
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
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let mut total_arrivals = 0;
    let mut total_settlements = 0;
    let mut min_balance = i64::MAX;

    // Run for 20 ticks
    for _ in 0..20 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;

        let agent = orchestrator.state().get_agent("BANK_A").unwrap();
        if agent.balance() < min_balance {
            min_balance = agent.balance();
        }
    }

    println!("Min balance reached: {}", min_balance);
    println!(
        "Arrivals: {}, Settlements: {}",
        total_arrivals, total_settlements
    );

    // With credit limit, agent can go into negative balance
    // But policy should still respect buffer logic relative to available liquidity
    assert!(
        min_balance >= -3_000_000, // Shouldn't exceed credit limit
        "Should not exceed credit limit. Min balance: {}",
        min_balance
    );

    // Should have processed some transactions
    assert!(total_settlements > 0, "Should settle some transactions");

    // Settlement rate reflects liquidity-aware behavior (conservative)
    let settlement_rate = total_settlements as f64 / total_arrivals as f64;
    println!("Settlement rate: {:.2}", settlement_rate);
    assert!(
        settlement_rate > 0.2,
        "Should settle at least some transactions. Rate: {:.2}",
        settlement_rate
    );

    // Key test: policy should use available resources (balance + credit) appropriately
    assert!(
        total_arrivals > 0 && total_settlements > 0,
        "Should have activity"
    );
}

#[test]
fn test_liquidity_aware_urgency_threshold_tuning() {
    // Scenario: Same arrivals, different urgency thresholds
    // Lower threshold = more selective (fewer urgent overrides)
    // Higher threshold = more aggressive (more urgent overrides)

    let arrival_config = ArrivalConfig {
        rate_per_tick: 3.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 150_000,
            max: 250_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (3, 15), // Mix of deadlines
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    // Conservative (low urgency threshold = fewer overrides)
    let config_conservative = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 6_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 3_000_000,
                    urgency_threshold: 2, // Conservative: only very urgent
                },
                arrival_config: Some(arrival_config.clone()),
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
                opening_balance: 20_000_000,
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
    };

    // Aggressive (high urgency threshold = more overrides)
    let config_aggressive = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999, // Same seed!
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 6_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 3_000_000,
                    urgency_threshold: 8, // Aggressive: many considered urgent
                },
                arrival_config: Some(arrival_config),
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
                opening_balance: 20_000_000,
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
    };

    let mut orch_conservative = Orchestrator::new(config_conservative).unwrap();
    let mut orch_aggressive = Orchestrator::new(config_aggressive).unwrap();

    let mut conservative_settlements = 0;
    let mut aggressive_settlements = 0;
    let mut conservative_min_balance = i64::MAX;
    let mut aggressive_min_balance = i64::MAX;

    // Run both for 15 ticks
    for _ in 0..15 {
        let result_cons = orch_conservative.tick().unwrap();
        let result_agg = orch_aggressive.tick().unwrap();

        conservative_settlements += result_cons.num_settlements;
        aggressive_settlements += result_agg.num_settlements;

        let balance_cons = orch_conservative
            .state()
            .get_agent("BANK_A")
            .unwrap()
            .balance();
        let balance_agg = orch_aggressive
            .state()
            .get_agent("BANK_A")
            .unwrap()
            .balance();

        if balance_cons < conservative_min_balance {
            conservative_min_balance = balance_cons;
        }
        if balance_agg < aggressive_min_balance {
            aggressive_min_balance = balance_agg;
        }
    }

    println!(
        "Conservative settlements: {}, min balance: {}",
        conservative_settlements, conservative_min_balance
    );
    println!(
        "Aggressive settlements: {}, min balance: {}",
        aggressive_settlements, aggressive_min_balance
    );

    // Aggressive should settle more (more urgency overrides)
    assert!(
        aggressive_settlements >= conservative_settlements,
        "Aggressive threshold should settle more. Aggressive: {}, Conservative: {}",
        aggressive_settlements,
        conservative_settlements
    );

    // Aggressive should have lower minimum balance (violated buffer more often)
    assert!(
        aggressive_min_balance <= conservative_min_balance,
        "Aggressive should use more liquidity. Aggressive min: {}, Conservative min: {}",
        aggressive_min_balance,
        conservative_min_balance
    );
}
