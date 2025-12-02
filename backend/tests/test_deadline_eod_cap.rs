//! TDD Tests for Deadline EOD Cap Feature
//!
//! Tests for the `deadline_cap_at_eod` configuration option that caps all
//! transaction deadlines at the end of the current day (Castro-compatible mode).
//!
//! Feature Request: experiments/castro/docs/feature_request_deadline_eod_cap.md

use payment_simulator_core_rs::arrivals::{
    AmountDistribution, ArrivalBandConfig, ArrivalBandsConfig, ArrivalConfig, ArrivalGenerator,
    PriorityDistribution,
};
use payment_simulator_core_rs::rng::RngManager;
use std::collections::HashMap;

// ============================================================================
// Helper Functions
// ============================================================================

/// Create a basic arrival config for testing
fn create_test_arrival_config() -> ArrivalConfig {
    ArrivalConfig {
        rate_per_tick: 5.0, // Generate several transactions per tick
        amount_distribution: AmountDistribution::Uniform {
            min: 10_000,
            max: 50_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 15), // Range that may extend past day boundary
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    }
}

/// Create arrival config with specific deadline range
fn create_arrival_config_with_range(min_offset: usize, max_offset: usize) -> ArrivalConfig {
    ArrivalConfig {
        rate_per_tick: 10.0, // Generate many to have statistical sample
        amount_distribution: AmountDistribution::Uniform {
            min: 10_000,
            max: 50_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (min_offset, max_offset),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    }
}

// ============================================================================
// Test 1: Core Capping Logic - Mid-Day Arrival
// ============================================================================

#[test]
fn test_deadline_capped_at_eod_mid_day_arrival() {
    // THIS IS THE DEFINING TEST
    // ticks_per_day=12, num_days=2, episode_end=24
    // Transaction arrives at tick 10 with deadline_range=[3,8]
    // Raw deadline = 10 + [3,8] = 13-18
    // With EOD cap: deadline capped at 12 (end of day 1)

    let config = create_arrival_config_with_range(3, 8);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 2;
    let episode_end = ticks_per_day * num_days; // 24

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true, // deadline_cap_at_eod = true
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 10; // Late in day 1
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    // All deadlines should be capped at day 1 end (tick 12)
    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= 12,
            "Deadline {} should be capped at day 1 end (tick 12), arrival_tick={}",
            tx.deadline_tick(),
            arrival_tick
        );
        // Also verify deadline is at least the minimum offset (if possible)
        assert!(
            tx.deadline_tick() >= 12 || tx.deadline_tick() >= arrival_tick + 3,
            "Deadline should be at least arrival + min_offset (or day end)"
        );
    }
}

// ============================================================================
// Test 2: EOD Cap Disabled (Backward Compatibility)
// ============================================================================

#[test]
fn test_deadline_not_capped_when_eod_cap_disabled() {
    // Same scenario but deadline_cap_at_eod=false
    // Deadlines should extend into day 2 (up to episode end)

    let config = create_arrival_config_with_range(3, 8);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 2;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        false, // deadline_cap_at_eod = false
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 10;
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    // With EOD cap disabled, some transactions should have deadline > 12
    // Raw deadline range is 13-18, all within episode_end=24
    let mut found_deadline_past_day1 = false;
    for tx in &arrivals {
        if tx.deadline_tick() > 12 {
            found_deadline_past_day1 = true;
        }
        // All should be capped at episode end
        assert!(
            tx.deadline_tick() <= episode_end,
            "Deadline {} should be capped at episode end {}",
            tx.deadline_tick(),
            episode_end
        );
    }

    // With offset [3,8] from tick 10, deadlines are 13-18, all > 12
    assert!(
        found_deadline_past_day1,
        "Without EOD cap, some deadlines should extend past day 1"
    );
}

// ============================================================================
// Test 3: Multi-Day Simulation - Day 2 Transactions
// ============================================================================

#[test]
fn test_deadline_capped_at_each_days_end() {
    // Day 1: ticks 0-11, day_end=12
    // Day 2: ticks 12-23, day_end=24
    // Transaction at tick 20 (day 2)
    // deadline_range=[5,10] -> raw=25-30
    // With EOD cap: capped at 24 (day 2 end)

    let config = create_arrival_config_with_range(5, 10);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 3;
    let episode_end = ticks_per_day * num_days; // 36

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true, // deadline_cap_at_eod = true
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 20; // Day 2 (ticks 12-23)
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    // All deadlines should be capped at day 2 end (tick 24)
    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= 24,
            "Deadline {} should be capped at day 2 end (tick 24)",
            tx.deadline_tick()
        );
    }
}

// ============================================================================
// Test 4: Last Tick of Day Arrival
// ============================================================================

#[test]
fn test_last_tick_of_day_arrival() {
    // Transaction at tick 11 (last tick of day 1, day spans 0-11)
    // deadline_range=[1,5] -> raw=12-16
    // With EOD cap: deadline capped at 12 (exactly at day boundary)

    let config = create_arrival_config_with_range(1, 5);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 2;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true,
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 11; // Last tick of day 1
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    // All deadlines should be exactly 12 (day 1 end)
    for tx in &arrivals {
        assert_eq!(
            tx.deadline_tick(),
            12,
            "Deadline should be exactly at day 1 end (tick 12)"
        );
    }
}

// ============================================================================
// Test 5: First Tick of Day Arrival - No Cap Needed
// ============================================================================

#[test]
fn test_first_tick_of_day_arrival_no_cap_needed() {
    // Transaction at tick 0 (first tick of day 1)
    // deadline_range=[3,8] -> raw=3-8
    // All within day 1 (ends at tick 12), no cap applied

    let config = create_arrival_config_with_range(3, 8);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 1;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true,
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 0;
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    // Deadlines should be in original range [3, 8]
    for tx in &arrivals {
        assert!(
            tx.deadline_tick() >= 3 && tx.deadline_tick() <= 8,
            "Deadline {} should be in range [3, 8] (no cap applied)",
            tx.deadline_tick()
        );
    }
}

// ============================================================================
// Test 6: Episode End Takes Precedence When Earlier
// ============================================================================

#[test]
fn test_episode_end_takes_precedence_when_earlier() {
    // Single day simulation: episode_end = day_end = 12
    // Both caps are the same, should work correctly

    let config = create_arrival_config_with_range(5, 15);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 1;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true,
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 10;
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= 12,
            "Deadline should be capped at 12 (both episode and day end)"
        );
    }
}

// ============================================================================
// Test 7: Per-Band Configuration with EOD Cap
// ============================================================================

#[test]
fn test_band_arrivals_respect_eod_cap() {
    // Test that per-band arrivals also respect the EOD cap
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 2.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 50_000,
                max: 100_000,
            },
            deadline_offset_min: 2,
            deadline_offset_max: 5, // Tight deadlines
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 10_000,
                max: 50_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 20, // Would extend past day with late arrival
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 2;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new_with_bands(
        band_configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true, // deadline_cap_at_eod
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 10; // Late in day 1
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    assert!(
        arrivals.len() > 0,
        "Should generate at least one transaction"
    );

    // All deadlines should be capped at day 1 end (tick 12)
    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= 12,
            "Band arrival deadline {} should be capped at day 1 end (tick 12)",
            tx.deadline_tick()
        );
    }
}

// ============================================================================
// Test 8: Mixed Mode (bands + legacy) with EOD Cap
// ============================================================================

#[test]
fn test_mixed_mode_respects_eod_cap() {
    // Some agents use bands, others use legacy config
    let bands = ArrivalBandsConfig {
        urgent: None,
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 10_000,
                max: 50_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let legacy_config = create_arrival_config_with_range(5, 15);
    let mut legacy_configs = HashMap::new();
    legacy_configs.insert("BANK_B".to_string(), legacy_config);

    let all_agents = vec![
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        "BANK_C".to_string(),
    ];
    let ticks_per_day = 12;
    let num_days = 2;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new_mixed(
        band_configs,
        legacy_configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true, // deadline_cap_at_eod
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 10;

    // Test BANK_A (uses bands)
    let arrivals_a = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);
    for tx in &arrivals_a {
        assert!(
            tx.deadline_tick() <= 12,
            "BANK_A (bands) deadline {} should be capped at 12",
            tx.deadline_tick()
        );
    }

    // Test BANK_B (uses legacy)
    let arrivals_b = generator.generate_for_agent("BANK_B", arrival_tick, &mut rng);
    for tx in &arrivals_b {
        assert!(
            tx.deadline_tick() <= 12,
            "BANK_B (legacy) deadline {} should be capped at 12",
            tx.deadline_tick()
        );
    }
}

// ============================================================================
// Test 9: Determinism with EOD Cap
// ============================================================================

#[test]
fn test_determinism_with_eod_cap() {
    let config = create_arrival_config_with_range(5, 15);

    // Run 1
    let mut configs1 = HashMap::new();
    configs1.insert("BANK_A".to_string(), config.clone());
    let all_agents1 = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator1 = ArrivalGenerator::new(configs1, all_agents1, 24, 12, true);
    let mut rng1 = RngManager::new(42);
    let arrivals1 = generator1.generate_for_agent("BANK_A", 10, &mut rng1);

    // Run 2 (same seed)
    let mut configs2 = HashMap::new();
    configs2.insert("BANK_A".to_string(), config.clone());
    let all_agents2 = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator2 = ArrivalGenerator::new(configs2, all_agents2, 24, 12, true);
    let mut rng2 = RngManager::new(42);
    let arrivals2 = generator2.generate_for_agent("BANK_A", 10, &mut rng2);

    // Should be identical
    assert_eq!(
        arrivals1.len(),
        arrivals2.len(),
        "Same seed should produce same number of arrivals"
    );

    for (tx1, tx2) in arrivals1.iter().zip(arrivals2.iter()) {
        assert_eq!(
            tx1.deadline_tick(),
            tx2.deadline_tick(),
            "Same seed should produce same deadlines"
        );
        assert_eq!(
            tx1.amount(),
            tx2.amount(),
            "Same seed should produce same amounts"
        );
    }
}

// ============================================================================
// Test 10: Single Tick Per Day Edge Case
// ============================================================================

#[test]
fn test_single_tick_per_day() {
    // Edge case: ticks_per_day = 1
    // Day 0: tick 0, day_end = 1
    // Day 1: tick 1, day_end = 2

    let config = create_arrival_config_with_range(1, 3);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 1;
    let num_days = 5;
    let episode_end = ticks_per_day * num_days;

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true,
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 2; // Day 2 (tick 2)
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    // Day 2 ends at tick 3
    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= 3,
            "With ticks_per_day=1, arrival at tick 2 should have deadline <= 3"
        );
    }
}

// ============================================================================
// Test 11: Very Long Deadline Range
// ============================================================================

#[test]
fn test_very_long_deadline_range_capped() {
    // Deadline range much larger than a day
    let config = create_arrival_config_with_range(50, 100);
    let mut configs = HashMap::new();
    configs.insert("BANK_A".to_string(), config);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let ticks_per_day = 12;
    let num_days = 3;
    let episode_end = ticks_per_day * num_days; // 36

    let mut generator = ArrivalGenerator::new(
        configs,
        all_agents,
        episode_end,
        ticks_per_day,
        true,
    );

    let mut rng = RngManager::new(42);
    let arrival_tick = 5; // Day 1
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    // Despite huge deadline range, should be capped at day 1 end (12)
    for tx in &arrivals {
        assert_eq!(
            tx.deadline_tick(),
            12,
            "Very long deadline should be capped at day end"
        );
    }
}

// ============================================================================
// Test 12: Compare Costs with EOD Cap vs Without
// ============================================================================

#[test]
fn test_deadline_calculation_differs_with_cap() {
    // Show that enabling cap actually changes the deadlines
    let config = create_arrival_config_with_range(3, 8);
    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];

    // With cap
    let mut configs_cap = HashMap::new();
    configs_cap.insert("BANK_A".to_string(), config.clone());
    let mut gen_cap = ArrivalGenerator::new(
        configs_cap,
        all_agents.clone(),
        24,
        12,
        true, // cap enabled
    );
    let mut rng_cap = RngManager::new(42);
    let arrivals_cap = gen_cap.generate_for_agent("BANK_A", 10, &mut rng_cap);

    // Without cap
    let mut configs_nocap = HashMap::new();
    configs_nocap.insert("BANK_A".to_string(), config.clone());
    let mut gen_nocap = ArrivalGenerator::new(
        configs_nocap,
        all_agents.clone(),
        24,
        12,
        false, // cap disabled
    );
    let mut rng_nocap = RngManager::new(42);
    let arrivals_nocap = gen_nocap.generate_for_agent("BANK_A", 10, &mut rng_nocap);

    // Same seed should produce same number of arrivals
    assert_eq!(arrivals_cap.len(), arrivals_nocap.len());

    // But deadlines should differ (capped vs uncapped)
    let mut differ_count = 0;
    for (tx_cap, tx_nocap) in arrivals_cap.iter().zip(arrivals_nocap.iter()) {
        // With cap, deadline <= 12
        // Without cap, deadline can be 13-18
        if tx_cap.deadline_tick() != tx_nocap.deadline_tick() {
            differ_count += 1;
        }
        assert!(tx_cap.deadline_tick() <= 12);
        // Without cap, raw deadline is 10 + [3,8] = 13-18, all > 12
        assert!(tx_nocap.deadline_tick() >= 13 && tx_nocap.deadline_tick() <= 18);
    }

    // All should differ since all raw deadlines exceed day end
    assert_eq!(
        differ_count,
        arrivals_cap.len(),
        "All deadlines should differ between cap and no-cap"
    );
}
