//! Test to reproduce exp3 scenario issue
//!
//! This test replicates the exact configuration from castro exp3
//! to reproduce the "deadline must be after arrival" panic.

use payment_simulator_core_rs::arrivals::{
    AmountDistribution, ArrivalConfig, ArrivalGenerator, PriorityDistribution,
};
use payment_simulator_core_rs::rng::RngManager;
use std::collections::HashMap;

/// Reproduce exp3 scenario with many seeds
#[test]
fn test_exp3_scenario_many_seeds() {
    // Exactly match exp3 config
    let ticks_per_day = 3;
    let num_days = 1;
    let episode_end = ticks_per_day * num_days; // 3
    let deadline_range = (1, 3);

    let mut counterparty_weights_a = HashMap::new();
    counterparty_weights_a.insert("BANK_B".to_string(), 1.0);

    let config_a = ArrivalConfig {
        rate_per_tick: 1.5,
        amount_distribution: AmountDistribution::LogNormal {
            mean: 15000.0,
            std_dev: 7500.0,
        },
        counterparty_weights: counterparty_weights_a,
        deadline_range,
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let mut counterparty_weights_b = HashMap::new();
    counterparty_weights_b.insert("BANK_A".to_string(), 1.0);

    let config_b = ArrivalConfig {
        rate_per_tick: 1.5,
        amount_distribution: AmountDistribution::LogNormal {
            mean: 15000.0,
            std_dev: 7500.0,
        },
        counterparty_weights: counterparty_weights_b,
        deadline_range,
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config_a);
    configs.insert("BANK_B".to_string(), config_b);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];

    // Test with multiple seeds to find the one that causes the issue
    for seed in 0..1000 {
        let mut generator = ArrivalGenerator::new(
            configs.clone(),
            all_agents.clone(),
            episode_end,
            ticks_per_day,
            true, // deadline_cap_at_eod
        );

        let mut rng = RngManager::new(seed);

        // Run through all ticks
        for tick in 0..ticks_per_day {
            for agent_id in &all_agents {
                // This is where the panic happens in the real scenario
                let arrivals = generator.generate_for_agent(agent_id, tick, &mut rng);

                // Verify all arrivals have valid deadlines
                for tx in &arrivals {
                    assert!(
                        tx.deadline_tick() > tx.arrival_tick(),
                        "FAIL with seed={}, tick={}, agent={}: deadline={} <= arrival={}",
                        seed,
                        tick,
                        agent_id,
                        tx.deadline_tick(),
                        tx.arrival_tick()
                    );
                }
            }
        }
    }
}

/// Test critical edge case: arrival at last tick of day
#[test]
fn test_exp3_last_tick_edge_case() {
    let ticks_per_day = 3;
    let num_days = 1;
    let episode_end = ticks_per_day * num_days; // 3

    // Use deadline_range = (1, 3) from exp3
    let config = ArrivalConfig {
        rate_per_tick: 100.0, // High rate to guarantee arrivals
        amount_distribution: AmountDistribution::LogNormal {
            mean: 15000.0,
            std_dev: 7500.0,
        },
        counterparty_weights: {
            let mut m = HashMap::new();
            m.insert("BANK_B".to_string(), 1.0);
            m
        },
        deadline_range: (1, 3),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true, // deadline_cap_at_eod
    );

    let mut rng = RngManager::new(42);

    // Test last tick (tick 2)
    let arrivals = generator.generate_for_agent("BANK_A", 2, &mut rng);

    assert!(!arrivals.is_empty(), "Should have arrivals");

    for tx in &arrivals {
        // With arrival at tick 2 and deadline_range (1, 3):
        // - raw deadline = 2 + [1,2,3] = 3, 4, or 5
        // - episode_end = 3
        // - day_end = 3
        // - capped deadline = min(raw, 3) = 3
        // - 3 > 2, so this should work
        println!(
            "TX: arrival={}, deadline={}",
            tx.arrival_tick(),
            tx.deadline_tick()
        );
        assert!(
            tx.deadline_tick() > tx.arrival_tick(),
            "deadline {} should be > arrival {}",
            tx.deadline_tick(),
            tx.arrival_tick()
        );
    }
}
