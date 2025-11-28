//! TDD Tests for Enhancement 11.3: Per-Band Arrival Functions
//!
//! Tests for configuring different arrival characteristics (rate, amount, deadline)
//! per priority band (urgent, normal, low).

use payment_simulator_core_rs::arrivals::{
    AmountDistribution, ArrivalBandConfig, ArrivalBandsConfig, ArrivalConfig, ArrivalGenerator,
    PriorityDistribution,
};
use payment_simulator_core_rs::rng::RngManager;
use std::collections::HashMap;

// ============================================================================
// Test 1: ArrivalBandConfig struct exists and is constructible
// ============================================================================

#[test]
fn test_arrival_band_config_struct_exists() {
    // A single band configuration with rate, amount distribution, and deadline offset
    let band = ArrivalBandConfig {
        rate_per_tick: 0.5,
        amount_distribution: AmountDistribution::LogNormal {
            mean: 12.0,
            std_dev: 0.5,
        },
        deadline_offset_min: 5,
        deadline_offset_max: 15,
        counterparty_weights: HashMap::new(),
        divisible: false,
    };

    assert_eq!(band.rate_per_tick, 0.5);
    assert_eq!(band.deadline_offset_min, 5);
    assert_eq!(band.deadline_offset_max, 15);
}

// ============================================================================
// Test 2: ArrivalBandsConfig struct with urgent/normal/low bands
// ============================================================================

#[test]
fn test_arrival_bands_config_with_all_bands() {
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 0.1,
            amount_distribution: AmountDistribution::LogNormal {
                mean: 14.0, // ~$10k
                std_dev: 0.5,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 3.0,
            amount_distribution: AmountDistribution::LogNormal {
                mean: 11.0, // ~$500
                std_dev: 0.8,
            },
            deadline_offset_min: 20,
            deadline_offset_max: 50,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: Some(ArrivalBandConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::LogNormal {
                mean: 9.2, // ~$100
                std_dev: 0.6,
            },
            deadline_offset_min: 40,
            deadline_offset_max: 80,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
    };

    assert!(bands.urgent.is_some());
    assert!(bands.normal.is_some());
    assert!(bands.low.is_some());
}

// ============================================================================
// Test 3: ArrivalBandsConfig with only some bands enabled
// ============================================================================

#[test]
fn test_arrival_bands_config_partial_bands() {
    // Only urgent band enabled
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 0.2,
            amount_distribution: AmountDistribution::Uniform {
                min: 500_000,
                max: 1_000_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 10,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: None,
        low: None,
    };

    assert!(bands.urgent.is_some());
    assert!(bands.normal.is_none());
    assert!(bands.low.is_none());
}

// ============================================================================
// Test 4: ArrivalGenerator accepts ArrivalBandsConfig
// ============================================================================

#[test]
fn test_arrival_generator_with_bands_config() {
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 0.5,
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 500_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 2.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 10_000,
                max: 50_000,
            },
            deadline_offset_min: 20,
            deadline_offset_max: 40,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    assert!(generator.has_bands_config("BANK_A"));
}

// ============================================================================
// Test 5: Per-band arrival generation produces transactions with correct priority ranges
// ============================================================================

#[test]
fn test_per_band_arrivals_have_correct_priority_ranges() {
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 5.0, // High rate for testing
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 200_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 10,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 10_000,
                max: 20_000,
            },
            deadline_offset_min: 20,
            deadline_offset_max: 30,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: Some(ArrivalBandConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1_000,
                max: 5_000,
            },
            deadline_offset_min: 40,
            deadline_offset_max: 60,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);
    let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

    // Verify priority ranges:
    // Urgent: 8-10
    // Normal: 4-7
    // Low: 0-3
    for tx in &arrivals {
        let priority = tx.priority();
        let amount = tx.amount();

        if amount >= 100_000 {
            // Urgent band (large amounts)
            assert!(
                priority >= 8 && priority <= 10,
                "Urgent transaction (amount {}) should have priority 8-10, got {}",
                amount,
                priority
            );
        } else if amount >= 10_000 {
            // Normal band (medium amounts)
            assert!(
                priority >= 4 && priority <= 7,
                "Normal transaction (amount {}) should have priority 4-7, got {}",
                amount,
                priority
            );
        } else {
            // Low band (small amounts)
            assert!(
                priority <= 3,
                "Low transaction (amount {}) should have priority 0-3, got {}",
                amount,
                priority
            );
        }
    }

    // Ensure we generated transactions from all bands
    assert!(
        arrivals.len() > 0,
        "Should generate some arrivals with rate 5.0 per band"
    );
}

// ============================================================================
// Test 6: Urgent band arrivals have tight deadlines
// ============================================================================

#[test]
fn test_urgent_band_has_tight_deadlines() {
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 10.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 200_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15, // Tight deadlines
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: None,
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);
    let arrival_tick = 10;
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    for tx in &arrivals {
        let deadline = tx.deadline_tick();
        assert!(
            deadline >= arrival_tick + 5 && deadline <= arrival_tick + 15,
            "Urgent deadline {} should be in range [{}, {}]",
            deadline,
            arrival_tick + 5,
            arrival_tick + 15
        );
    }
}

// ============================================================================
// Test 7: Low band arrivals have relaxed deadlines
// ============================================================================

#[test]
fn test_low_band_has_relaxed_deadlines() {
    let bands = ArrivalBandsConfig {
        urgent: None,
        normal: None,
        low: Some(ArrivalBandConfig {
            rate_per_tick: 10.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1_000,
                max: 5_000,
            },
            deadline_offset_min: 40,
            deadline_offset_max: 80, // Relaxed deadlines
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);
    let arrival_tick = 10;
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    for tx in &arrivals {
        let deadline = tx.deadline_tick();
        assert!(
            deadline >= arrival_tick + 40 && deadline <= arrival_tick + 80,
            "Low priority deadline {} should be in range [{}, {}]",
            deadline,
            arrival_tick + 40,
            arrival_tick + 80
        );
    }
}

// ============================================================================
// Test 8: Determinism - same seed produces identical arrivals from bands
// ============================================================================

#[test]
fn test_per_band_arrivals_deterministic() {
    let make_bands = || ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 2.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 200_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: Some(ArrivalBandConfig {
            rate_per_tick: 3.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 10_000,
                max: 50_000,
            },
            deadline_offset_min: 20,
            deadline_offset_max: 40,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        low: None,
    };

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];

    // First run
    let mut band_configs1 = HashMap::new();
    band_configs1.insert("BANK_A".to_string(), make_bands());
    let mut generator1 = ArrivalGenerator::new_with_bands(band_configs1, all_agents.clone(), 1000);
    let mut rng1 = RngManager::new(12345);
    let arrivals1 = generator1.generate_for_agent("BANK_A", 0, &mut rng1);

    // Second run with same seed
    let mut band_configs2 = HashMap::new();
    band_configs2.insert("BANK_A".to_string(), make_bands());
    let mut generator2 = ArrivalGenerator::new_with_bands(band_configs2, all_agents, 1000);
    let mut rng2 = RngManager::new(12345);
    let arrivals2 = generator2.generate_for_agent("BANK_A", 0, &mut rng2);

    // Should be identical
    assert_eq!(
        arrivals1.len(),
        arrivals2.len(),
        "Same seed should produce same number of arrivals"
    );

    for (tx1, tx2) in arrivals1.iter().zip(arrivals2.iter()) {
        assert_eq!(tx1.amount(), tx2.amount());
        assert_eq!(tx1.priority(), tx2.priority());
        assert_eq!(tx1.deadline_tick(), tx2.deadline_tick());
        assert_eq!(tx1.receiver_id(), tx2.receiver_id());
    }
}

// ============================================================================
// Test 9: Mixed arrival modes - some agents use bands, others use legacy config
// ============================================================================

#[test]
fn test_mixed_arrival_modes() {
    // BANK_A uses per-band arrivals
    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 2.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 200_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
        normal: None,
        low: None,
    };

    // BANK_B uses legacy arrival config
    let legacy_config = ArrivalConfig {
        rate_per_tick: 3.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 5_000,
            max: 20_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (10, 30),
        priority_distribution: PriorityDistribution::Fixed { value: 5 },
        divisible: false,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let mut legacy_configs = HashMap::new();
    legacy_configs.insert("BANK_B".to_string(), legacy_config);

    let all_agents = vec![
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        "BANK_C".to_string(),
    ];
    let mut generator =
        ArrivalGenerator::new_mixed(band_configs, legacy_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);

    // BANK_A should generate urgent priority transactions
    let arrivals_a = generator.generate_for_agent("BANK_A", 0, &mut rng);
    for tx in &arrivals_a {
        assert!(
            tx.priority() >= 8 && tx.priority() <= 10,
            "BANK_A should generate urgent priority only"
        );
    }

    // BANK_B should generate fixed priority 5 transactions
    let arrivals_b = generator.generate_for_agent("BANK_B", 0, &mut rng);
    for tx in &arrivals_b {
        assert_eq!(tx.priority(), 5, "BANK_B should generate priority 5");
    }
}

// ============================================================================
// Test 10: Per-band counterparty weights
// ============================================================================

#[test]
fn test_per_band_counterparty_weights() {
    let mut urgent_weights = HashMap::new();
    urgent_weights.insert("BANK_B".to_string(), 10.0); // Prefer BANK_B for urgent

    let bands = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            rate_per_tick: 20.0, // High rate for testing
            amount_distribution: AmountDistribution::Uniform {
                min: 100_000,
                max: 200_000,
            },
            deadline_offset_min: 5,
            deadline_offset_max: 15,
            counterparty_weights: urgent_weights,
            divisible: false,
        }),
        normal: None,
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec![
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        "BANK_C".to_string(),
    ];
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);
    let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

    // Count receivers
    let bank_b_count = arrivals.iter().filter(|tx| tx.receiver_id() == "BANK_B").count();
    let bank_c_count = arrivals.iter().filter(|tx| tx.receiver_id() == "BANK_C").count();

    // BANK_B should be selected more often due to higher weight
    assert!(
        bank_b_count > bank_c_count,
        "BANK_B should be selected more often: B={}, C={}",
        bank_b_count,
        bank_c_count
    );
}

// ============================================================================
// Test 11: Orchestrator integration with per-band arrivals
// ============================================================================

#[test]
fn test_orchestrator_with_arrival_bands() {
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, Orchestrator, OrchestratorConfig, PolicyConfig,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: Some(ArrivalBandsConfig {
                    urgent: Some(ArrivalBandConfig {
                        rate_per_tick: 0.5,
                        amount_distribution: AmountDistribution::Uniform {
                            min: 50_000,
                            max: 100_000,
                        },
                        deadline_offset_min: 5,
                        deadline_offset_max: 20,
                        counterparty_weights: HashMap::new(),
                        divisible: false,
                    }),
                    normal: Some(ArrivalBandConfig {
                        rate_per_tick: 2.0,
                        amount_distribution: AmountDistribution::Uniform {
                            min: 5_000,
                            max: 20_000,
                        },
                        deadline_offset_min: 20,
                        deadline_offset_max: 50,
                        counterparty_weights: HashMap::new(),
                        divisible: false,
                    }),
                    low: None,
                }),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000,
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
        cost_rates: Default::default(),
        lsm_config: Default::default(),
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
    };

    let mut orchestrator = Orchestrator::new(config).expect("Should create orchestrator");

    // Run a few ticks
    for _ in 0..10 {
        orchestrator.tick().expect("Tick should succeed");
    }

    // Verify transactions were generated - collect arrivals from tick events
    let mut arrival_count = 0;
    for tick in 0..10 {
        let events = orchestrator.get_tick_events(tick);
        for event in events {
            if event.event_type() == "Arrival" {
                arrival_count += 1;
            }
        }
    }

    // Should have some arrivals from the bands (with rate 0.5 + 2.0 = 2.5 per tick)
    // Over 10 ticks, we expect ~25 arrivals on average
    assert!(arrival_count > 0, "Should have generated some arrival events, got {}", arrival_count);
}

// ============================================================================
// Test 12: Validation - arrival_config and arrival_bands are mutually exclusive
// ============================================================================

#[test]
fn test_arrival_config_and_bands_mutually_exclusive() {
    use payment_simulator_core_rs::orchestrator::{
        AgentConfig, Orchestrator, OrchestratorConfig, PolicyConfig,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 1_000_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Fifo,
            arrival_config: Some(ArrivalConfig {
                rate_per_tick: 1.0,
                amount_distribution: AmountDistribution::Uniform {
                    min: 1_000,
                    max: 10_000,
                },
                counterparty_weights: HashMap::new(),
                deadline_range: (10, 30),
                priority_distribution: PriorityDistribution::Fixed { value: 5 },
                divisible: false,
            }),
            arrival_bands: Some(ArrivalBandsConfig {
                urgent: Some(ArrivalBandConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 50_000,
                        max: 100_000,
                    },
                    deadline_offset_min: 5,
                    deadline_offset_max: 20,
                    counterparty_weights: HashMap::new(),
                    divisible: false,
                }),
                normal: None,
                low: None,
            }),
            posted_collateral: None,
            collateral_haircut: None,
            limits: None,
            liquidity_pool: None,
            liquidity_allocation_fraction: None,
        }],
        cost_rates: Default::default(),
        lsm_config: Default::default(),
        scenario_events: None,
        queue1_ordering: Default::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
    };

    let result = Orchestrator::new(config);
    assert!(
        result.is_err(),
        "Should reject config with both arrival_config and arrival_bands"
    );

    let err_msg = result.unwrap_err().to_string();
    assert!(
        err_msg.contains("mutually exclusive") || err_msg.contains("arrival"),
        "Error should mention mutual exclusivity"
    );
}

// ============================================================================
// Test 13: Empty bands config is valid (no arrivals generated)
// ============================================================================

#[test]
fn test_empty_bands_config_valid() {
    let bands = ArrivalBandsConfig {
        urgent: None,
        normal: None,
        low: None,
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, 1000);

    let mut rng = RngManager::new(42);
    let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

    assert_eq!(arrivals.len(), 0, "No bands enabled should produce no arrivals");
}

// ============================================================================
// Test 14: Deadline capping at episode end works for band arrivals
// ============================================================================

#[test]
fn test_band_arrivals_deadline_capped_at_episode_end() {
    let bands = ArrivalBandsConfig {
        urgent: None,
        normal: None,
        low: Some(ArrivalBandConfig {
            rate_per_tick: 10.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1_000,
                max: 5_000,
            },
            deadline_offset_min: 40,
            deadline_offset_max: 80, // Large offset
            counterparty_weights: HashMap::new(),
            divisible: false,
        }),
    };

    let mut band_configs = HashMap::new();
    band_configs.insert("BANK_A".to_string(), bands);

    let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
    let episode_end = 50; // Short episode
    let mut generator = ArrivalGenerator::new_with_bands(band_configs, all_agents, episode_end);

    let mut rng = RngManager::new(42);
    let arrival_tick = 30; // Late in episode
    let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

    // All deadlines should be capped at episode_end
    for tx in &arrivals {
        assert!(
            tx.deadline_tick() <= episode_end,
            "Deadline {} should be capped at episode end {}",
            tx.deadline_tick(),
            episode_end
        );
    }
}
