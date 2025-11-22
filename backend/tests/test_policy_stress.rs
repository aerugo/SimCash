//! Policy Stress Tests
//!
//! Tests system behavior under extreme load:
//! - High-frequency arrivals (rate > 10)
//! - Sustained high loads
//! - Large-scale simulations (many agents)
//!
//! These tests verify performance, stability, and reasonable completion times.

use payment_simulator_core_rs::{
    arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};
use std::collections::HashMap;
use std::time::Instant;

#[test]
fn test_high_frequency_arrivals_single_agent() {
    // Stress test: Very high arrival rate (10 transactions per tick)
    // System should handle load without panicking

    let arrival_config = ArrivalConfig {
        rate_per_tick: 10.0, // High frequency
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 20),
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
                opening_balance: 100_000_000, // Large balance to handle volume
                unsecured_cap: 50_000_000,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 20_000_000,
                    urgency_threshold: 5,
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 100_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let start = Instant::now();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;
    let mut max_queue = 0;

    // Run for 50 ticks
    for _ in 0..50 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;

        let queue_depth =
            orchestrator.state().total_internal_queue_size() + orchestrator.state().queue_size();

        if queue_depth > max_queue {
            max_queue = queue_depth;
        }
    }

    let elapsed = start.elapsed();

    println!("High-frequency test completed in {:?}", elapsed);
    println!(
        "Total arrivals: {}, settlements: {}",
        total_arrivals, total_settlements
    );
    println!("Max queue depth: {}", max_queue);
    println!(
        "Settlement rate: {:.2}%",
        (total_settlements as f64 / total_arrivals as f64) * 100.0
    );

    // Verify system handled the load
    assert!(
        total_arrivals > 400,
        "Should generate many arrivals at rate=10.0"
    );
    assert!(total_settlements > 0, "Should settle some transactions");
    assert!(
        elapsed.as_secs() < 5,
        "Should complete in under 5 seconds. Took: {:?}",
        elapsed
    );

    // Queue should build up but not explode
    assert!(
        max_queue < 500,
        "Queue shouldn't explode. Max: {}",
        max_queue
    );
}

#[test]
fn test_sustained_high_load_100_ticks() {
    // Stress test: Sustained high arrival rate over long period
    // Verifies system stability over time

    let arrival_config = ArrivalConfig {
        rate_per_tick: 8.0, // High sustained rate
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 300_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 40),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 150_000_000,
                unsecured_cap: 50_000_000,
                policy: PolicyConfig::Deadline {
                    urgency_threshold: 8,
                },
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 150_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let start = Instant::now();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;
    let mut queue_samples = Vec::new();

    // Run for 100 ticks (full day)
    for tick in 0..100 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;

        // Sample queue depth every 10 ticks
        if tick % 10 == 0 {
            let queue_depth = orchestrator.state().total_internal_queue_size()
                + orchestrator.state().queue_size();
            queue_samples.push(queue_depth);
        }
    }

    let elapsed = start.elapsed();

    println!("Sustained load test (100 ticks) completed in {:?}", elapsed);
    println!(
        "Total arrivals: {}, settlements: {}",
        total_arrivals, total_settlements
    );
    println!("Queue samples: {:?}", queue_samples);

    // Verify reasonable performance
    assert!(
        total_arrivals > 700,
        "Should generate many arrivals over 100 ticks"
    );
    assert!(
        elapsed.as_secs() < 10,
        "Should complete 100 ticks in under 10 seconds. Took: {:?}",
        elapsed
    );

    // Queue should stay bounded (not grow unbounded)
    let avg_queue: f64 = queue_samples.iter().sum::<usize>() as f64 / queue_samples.len() as f64;
    let max_queue = queue_samples.iter().max().unwrap();
    println!("Average queue depth: {:.2}, Max: {}", avg_queue, max_queue);

    // With high sustained load, queue will build up but should stay bounded
    assert!(
        avg_queue < 200.0,
        "Average queue should stay bounded. Got: {:.2}",
        avg_queue
    );
    assert!(
        *max_queue < 300,
        "Max queue should stay reasonable. Got: {}",
        max_queue
    );
}

#[test]
fn test_extreme_high_frequency_arrivals() {
    // Stress test: Extreme arrival rate (rate=20.0)
    // Tests absolute limits of system

    let arrival_config = ArrivalConfig {
        rate_per_tick: 20.0, // Extreme rate
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 150_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 15),
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
                opening_balance: 200_000_000, // Very large balance
                unsecured_cap: 100_000_000,
                policy: PolicyConfig::Fifo, // Simple policy for speed
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 200_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let start = Instant::now();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;

    // Run for 30 ticks (shorter duration for extreme load)
    for _ in 0..30 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;
    }

    let elapsed = start.elapsed();

    println!(
        "Extreme frequency test (rate=20.0) completed in {:?}",
        elapsed
    );
    println!(
        "Total arrivals: {}, settlements: {}",
        total_arrivals, total_settlements
    );
    println!(
        "Throughput: {:.0} arrivals/sec",
        total_arrivals as f64 / elapsed.as_secs_f64()
    );

    // Verify system handled extreme load
    assert!(
        total_arrivals > 500,
        "Should generate many arrivals at rate=20.0"
    );
    assert!(
        elapsed.as_secs() < 10,
        "Should handle extreme load. Took: {:?}",
        elapsed
    );

    // With FIFO and huge liquidity, should settle most
    let settlement_rate = total_settlements as f64 / total_arrivals as f64;
    println!("Settlement rate: {:.2}%", settlement_rate * 100.0);
    assert!(
        settlement_rate > 0.5,
        "Should settle majority with ample liquidity"
    );
}

#[test]
fn test_50_agent_high_frequency_simulation() {
    // Large-scale stress test: 50 agents with high-frequency arrivals
    // Tests scalability and performance with realistic network size

    let arrival_config = ArrivalConfig {
        rate_per_tick: 3.0, // Moderate per-agent rate (150 total/tick)
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(), // Uniform selection across 49 counterparties
        deadline_range: (10, 30),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    // Create 50 agents
    let mut agent_configs = Vec::new();
    for i in 0..50 {
        agent_configs.push(AgentConfig {
            id: format!("BANK_{:02}", i),
            opening_balance: 50_000_000, // $500k each
            unsecured_cap: if i % 3 == 0 { 10_000_000 } else { 0 }, // Some have unsecured overdraft
            policy: match i % 3 {
                0 => PolicyConfig::Fifo,
                1 => PolicyConfig::Deadline {
                    urgency_threshold: 5,
                },
                2 => PolicyConfig::LiquidityAware {
                    target_buffer: 10_000_000,
                    urgency_threshold: 5,
                },
                _ => unreachable!(),
            },
            arrival_config: Some(arrival_config.clone()),
            posted_collateral: None,
            collateral_haircut: None,
                limits: None,
        });
    }

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42424242,
        agent_configs,
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    println!("Initializing 50-agent simulation...");
    let init_start = Instant::now();
    let mut orchestrator = Orchestrator::new(config).unwrap();
    let init_elapsed = init_start.elapsed();
    println!("Initialization took: {:?}", init_elapsed);

    let start = Instant::now();
    let mut total_arrivals = 0;
    let mut total_settlements = 0;
    let mut lsm_releases = 0;
    let mut tick_times = Vec::new();

    // Run for 50 ticks (manageable for large scale)
    for tick in 0..50 {
        let tick_start = Instant::now();
        let result = orchestrator.tick().unwrap();
        let tick_elapsed = tick_start.elapsed();

        total_arrivals += result.num_arrivals;
        total_settlements += result.num_settlements;
        lsm_releases += result.num_lsm_releases;

        tick_times.push(tick_elapsed);

        // Log progress every 10 ticks
        if tick % 10 == 0 {
            println!(
                "Tick {}: {} arrivals, {} settlements, {:?}",
                tick, result.num_arrivals, result.num_settlements, tick_elapsed
            );
        }
    }

    let total_elapsed = start.elapsed();
    let avg_tick_time = tick_times.iter().sum::<std::time::Duration>() / tick_times.len() as u32;
    let max_tick_time = tick_times.iter().max().unwrap();

    println!("\n=== 50-Agent Simulation Results ===");
    println!("Total elapsed: {:?}", total_elapsed);
    println!("Average tick time: {:?}", avg_tick_time);
    println!("Max tick time: {:?}", max_tick_time);
    println!("Total arrivals: {}", total_arrivals);
    println!("Total settlements: {}", total_settlements);
    println!("LSM releases: {}", lsm_releases);
    println!(
        "Settlement rate: {:.2}%",
        (total_settlements as f64 / total_arrivals as f64) * 100.0
    );
    println!(
        "Throughput: {:.0} arrivals/sec",
        total_arrivals as f64 / total_elapsed.as_secs_f64()
    );

    // Performance assertions
    assert!(
        total_elapsed.as_secs() < 30,
        "50-agent simulation should complete in under 30 seconds. Took: {:?}",
        total_elapsed
    );

    assert!(
        avg_tick_time.as_millis() < 500,
        "Average tick should be under 500ms. Got: {:?}",
        avg_tick_time
    );

    // Functional assertions
    assert!(
        total_arrivals > 5000,
        "Should generate many arrivals with 50 agents. Got: {}",
        total_arrivals
    );

    assert!(
        total_settlements > 1000,
        "Should settle significant portion. Got: {}",
        total_settlements
    );

    // LSM may find optimization opportunities, but with uniform counterparty selection
    // across 49 potential receivers, exact bilateral matches are rare
    // This is expected behavior - LSM is most useful with structured payment patterns
    println!(
        "LSM found {} bilateral offsets (expected to be low with uniform selection)",
        lsm_releases
    );

    // Check that queues didn't explode
    let total_queue =
        orchestrator.state().total_internal_queue_size() + orchestrator.state().queue_size();
    println!("Final queue depth: {}", total_queue);
    assert!(
        total_queue < 1000,
        "Queue should stay bounded. Got: {}",
        total_queue
    );
}
