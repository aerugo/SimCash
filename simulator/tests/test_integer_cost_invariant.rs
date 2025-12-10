//! Tests for the critical invariant: Money is always i64, never float
//!
//! These tests verify that cost calculations use integer-only arithmetic
//! to prevent NaN, Inf, and precision errors from f64→i64 casts.
//!
//! Background: Float-to-int casts can produce garbage values when:
//! - Input is NaN (produces undefined value)
//! - Input is Inf (produces undefined value)
//! - Input exceeds i64 range (produces undefined value)
//!
//! All cost calculations must use scaled integer arithmetic to avoid these issues.

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
    Transaction,
};

/// Helper to create basic 2-agent configuration
fn create_test_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
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
                max_collateral_capacity: None,
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
        deadline_cap_at_eod: false,
    }
}

// ============================================================================
// INVARIANT 1: Costs are always non-negative
// ============================================================================

#[test]
fn test_overdraft_cost_always_non_negative() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put agent into overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    // Run 100 ticks
    for _ in 0..100 {
        let result = orchestrator.tick().unwrap();
        assert!(result.total_cost >= 0, "Total cost must never be negative");
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert!(costs.total_liquidity_cost >= 0, "Liquidity cost must never be negative");
    assert!(costs.total() >= 0, "Total accumulated cost must never be negative");
}

#[test]
fn test_delay_cost_always_non_negative() {
    let mut config = create_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.01;
    config.agent_configs[0].opening_balance = 0; // No liquidity to settle
    config.agent_configs[0].unsecured_cap = 0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that will be held in queue
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    // Run 50 ticks
    for _ in 0..50 {
        let result = orchestrator.tick().unwrap();
        assert!(result.total_cost >= 0, "Total cost must never be negative");
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert!(costs.total_delay_cost >= 0, "Delay cost must never be negative");
}

#[test]
fn test_collateral_cost_always_non_negative() {
    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 42.0; // 42 bps (realistic LVTS rate)
    config.agent_configs[0].posted_collateral = Some(10_000_000); // $100k collateral

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run 100 ticks
    for _ in 0..100 {
        let result = orchestrator.tick().unwrap();
        assert!(result.total_cost >= 0, "Total cost must never be negative");
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert!(costs.total_collateral_cost >= 0, "Collateral cost must never be negative");
}

// ============================================================================
// INVARIANT 2: Costs are within reasonable bounds (not overflow/garbage)
// ============================================================================

#[test]
fn test_overdraft_cost_reasonable_magnitude() {
    let mut config = create_test_config();
    // Use realistic rate: 167 bps per tick (as in Castro exp2)
    config.cost_rates.overdraft_bps_per_tick = 167.0;
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 100_000_000; // $1M credit line

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put agent into max overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000_000, 0, 100);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());
    orchestrator.tick().unwrap();

    // Balance should be -100M
    let balance = orchestrator.state().get_agent("BANK_A").unwrap().balance();
    assert_eq!(balance, -100_000_000);

    // Run more ticks
    for _ in 0..11 {
        orchestrator.tick().unwrap();
    }

    // Calculate expected cost:
    // 100,000,000 cents overdraft * 167 bps / 10,000 = 1,670,000 cents per tick
    // Over 12 ticks: 1,670,000 * 12 = 20,040,000 cents = $200,400
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must be within reasonable bounds (not quadrillions!)
    assert!(costs.total_liquidity_cost > 0, "Should have some overdraft cost");
    assert!(costs.total_liquidity_cost < 100_000_000_000, "Cost should not be astronomical");

    // More precise check
    let expected_per_tick = 100_000_000 * 167 / 10_000; // = 1,670,000
    let expected_total = expected_per_tick * 12;

    // Allow small rounding differences
    let diff = (costs.total_liquidity_cost - expected_total).abs();
    assert!(diff <= 12, "Cost should match expected within rounding: got {}, expected {}",
            costs.total_liquidity_cost, expected_total);
}

#[test]
fn test_delay_cost_reasonable_magnitude() {
    let mut config = create_test_config();
    // Use Castro exp2 rate: 0.01 per tick per cent
    config.cost_rates.delay_cost_per_tick_per_cent = 0.01;
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Queue a large transaction that can't settle
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10_000_000, 0, 100);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    // Run 12 ticks
    for _ in 0..12 {
        orchestrator.tick().unwrap();
    }

    // Calculate expected cost:
    // 10,000,000 cents * 0.01 = 100,000 cents per tick
    // Over 12 ticks: 100,000 * 12 = 1,200,000 cents = $12,000
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must be within reasonable bounds
    assert!(costs.total_delay_cost > 0, "Should have some delay cost");
    assert!(costs.total_delay_cost < 100_000_000_000, "Cost should not be astronomical");

    // More precise check
    let expected_per_tick = 10_000_000 * 1 / 100; // 0.01 = 1/100
    let expected_total = expected_per_tick * 12;

    // Allow small rounding differences
    let diff = (costs.total_delay_cost - expected_total).abs();
    assert!(diff <= 12, "Cost should match expected within rounding: got {}, expected {}",
            costs.total_delay_cost, expected_total);
}

#[test]
fn test_collateral_cost_reasonable_magnitude() {
    let mut config = create_test_config();
    // Use Castro exp2 rate: 42 bps per tick
    config.cost_rates.collateral_cost_per_tick_bps = 42.0;
    config.agent_configs[0].posted_collateral = Some(10_000_000); // $100,000

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run 12 ticks
    for _ in 0..12 {
        orchestrator.tick().unwrap();
    }

    // Calculate expected cost:
    // 10,000,000 cents * 42 bps / 10,000 = 42,000 cents per tick
    // Over 12 ticks: 42,000 * 12 = 504,000 cents = $5,040
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must be within reasonable bounds
    assert!(costs.total_collateral_cost > 0, "Should have some collateral cost");
    assert!(costs.total_collateral_cost < 100_000_000_000, "Cost should not be astronomical");

    // More precise check
    let expected_per_tick = 10_000_000 * 42 / 10_000;
    let expected_total = expected_per_tick * 12;

    // Allow small rounding differences
    let diff = (costs.total_collateral_cost - expected_total).abs();
    assert!(diff <= 12, "Cost should match expected within rounding: got {}, expected {}",
            costs.total_collateral_cost, expected_total);
}

// ============================================================================
// INVARIANT 3: Large values don't cause overflow or garbage
// ============================================================================

#[test]
fn test_large_overdraft_no_overflow() {
    let mut config = create_test_config();
    // Use realistic rate: 167 bps per tick (as in Castro exp2)
    config.cost_rates.overdraft_bps_per_tick = 167.0;
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 1_000_000_000_000; // $10 billion credit

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put agent into massive overdraft: $10 billion
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_000_000_000_000, 0, 100);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must not be negative (overflow wraparound) or garbage (NaN cast)
    assert!(costs.total_liquidity_cost >= 0, "Cost must not be negative (overflow)");
    assert!(costs.total_liquidity_cost < i64::MAX / 2, "Cost must not be near max (overflow)");

    // Expected: 1,000,000,000,000 * 167 / 10,000 = 16,700,000,000 cents
    let expected = 1_000_000_000_000_i64 * 167 / 10_000;
    assert_eq!(costs.total_liquidity_cost, expected,
               "Large overdraft cost should be calculated correctly");
}

#[test]
fn test_large_delay_cost_no_overflow() {
    let mut config = create_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.01; // 1% (realistic Castro rate)
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Queue large transaction: $10 billion
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_000_000_000_000, 0, 100);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must not be negative or garbage
    assert!(costs.total_delay_cost >= 0, "Cost must not be negative (overflow)");
    assert!(costs.total_delay_cost < i64::MAX / 2, "Cost must not be near max (overflow)");

    // Expected: 1,000,000,000,000 * 0.01 = 10,000,000,000 cents
    let expected = 10_000_000_000_i64;
    assert_eq!(costs.total_delay_cost, expected,
               "Large delay cost should be calculated correctly");
}

#[test]
fn test_large_collateral_cost_no_overflow() {
    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 42.0; // 42 bps (realistic Castro rate)
    config.agent_configs[0].posted_collateral = Some(1_000_000_000_000); // $10 billion
    config.agent_configs[0].max_collateral_capacity = Some(2_000_000_000_000);

    let mut orchestrator = Orchestrator::new(config).unwrap();

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Must not be negative or garbage
    assert!(costs.total_collateral_cost >= 0, "Cost must not be negative (overflow)");
    assert!(costs.total_collateral_cost < i64::MAX / 2, "Cost must not be near max (overflow)");

    // Expected: 1,000,000,000,000 * 42 / 10,000 = 4,200,000,000 cents
    let expected = 1_000_000_000_000_i64 * 42 / 10_000;
    assert_eq!(costs.total_collateral_cost, expected,
               "Large collateral cost should be calculated correctly");
}

#[test]
fn test_extreme_values_saturate_safely() {
    // Test that very large (but not system-breaking) values don't produce negative or garbage costs
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 10000.0; // 100% per tick (extreme rate)
    config.agent_configs[0].opening_balance = 0;
    // Use large but not system-breaking credit: $100 trillion
    config.agent_configs[0].unsecured_cap = 10_000_000_000_000_000;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Try to create large overdraft: $100 trillion
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10_000_000_000_000_000, 0, 100);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Key invariants: cost is non-negative and not garbage
    assert!(costs.total_liquidity_cost >= 0, "Cost must not be negative (overflow)");
    // Cost should be calculated correctly: 10^16 * 10000 / 10000 = 10^16
    // With u128 arithmetic, this should work correctly
    assert!(costs.total_liquidity_cost > 0, "Should have significant cost");
    assert!(costs.total_liquidity_cost < i64::MAX,
            "Cost should be within i64 range");
}

// ============================================================================
// INVARIANT 4: Zero and small values work correctly
// ============================================================================

#[test]
fn test_zero_rate_produces_zero_cost() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 0.0;
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0;
    config.cost_rates.collateral_cost_per_tick_bps = 0.0;
    config.agent_configs[0].posted_collateral = Some(1_000_000);
    config.agent_configs[0].opening_balance = -500_000; // Start in overdraft

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Queue transaction
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    for _ in 0..10 {
        orchestrator.tick().unwrap();
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    assert_eq!(costs.total_liquidity_cost, 0, "Zero rate should produce zero overdraft cost");
    // Note: delay_cost will be 0 because the rate is 0, but penalties may apply
    assert_eq!(costs.total_collateral_cost, 0, "Zero rate should produce zero collateral cost");
}

#[test]
fn test_small_amounts_produce_small_costs() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // 1 bps
    config.cost_rates.collateral_cost_per_tick_bps = 1.0; // 1 bps
    config.agent_configs[0].posted_collateral = Some(100); // Only $1 collateral
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 100;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Small overdraft of $1
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100, 0, 50);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // 100 cents * 1 bps / 10,000 = 0.01 cents, rounds to 0
    // This is expected behavior for very small amounts
    assert!(costs.total_liquidity_cost >= 0, "Small cost should be non-negative");
    assert!(costs.total_collateral_cost >= 0, "Small cost should be non-negative");

    // Costs should be small, not garbage
    assert!(costs.total_liquidity_cost < 1000, "Small overdraft should have tiny cost");
    assert!(costs.total_collateral_cost < 1000, "Small collateral should have tiny cost");
}

// ============================================================================
// INVARIANT 5: Overdue multiplier applies correctly with integer math
// ============================================================================

#[test]
fn test_overdue_multiplier_integer_math() {
    let mut config = create_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.01; // 1% per cent per tick
    config.cost_rates.overdue_delay_multiplier = 5.0; // 5x for overdue
    config.agent_configs[0].opening_balance = 0;
    config.agent_configs[0].unsecured_cap = 0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Queue transaction with deadline at tick 5
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_000_000, 0, 5);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

    // Run 4 ticks (not overdue yet)
    for _ in 0..4 {
        orchestrator.tick().unwrap();
    }
    let costs_before_overdue = orchestrator.get_costs("BANK_A").unwrap().total_delay_cost;

    // Run 4 more ticks (now overdue, with 5x multiplier)
    for _ in 0..4 {
        orchestrator.tick().unwrap();
    }
    let costs_after_overdue = orchestrator.get_costs("BANK_A").unwrap().total_delay_cost;

    // The cost after overdue should be significantly higher
    let additional_cost = costs_after_overdue - costs_before_overdue;

    // Expected:
    // - Before overdue: 1,000,000 * 0.01 * 4 = 40,000 (4 ticks at base rate)
    // - After overdue: 1,000,000 * 0.01 * 5 * 4 = 200,000 (4 ticks at 5x rate)
    // Total: 40,000 + 200,000 = 240,000

    // Note: tick 5 itself is the deadline tick, tx becomes overdue AFTER deadline passes
    // So we need to account for the exact timing

    assert!(additional_cost > costs_before_overdue,
            "Overdue transactions should incur higher costs");
    assert!(costs_after_overdue > 0, "Should have accumulated delay costs");
    assert!(costs_after_overdue < 1_000_000_000, "Costs should not be astronomical");
}

// ============================================================================
// INVARIANT 6: Deterministic results with same inputs
// ============================================================================

#[test]
fn test_cost_calculation_determinism() {
    fn run_simulation() -> i64 {
        let mut config = create_test_config();
        config.cost_rates.overdraft_bps_per_tick = 167.0;
        config.cost_rates.delay_cost_per_tick_per_cent = 0.01;
        config.cost_rates.collateral_cost_per_tick_bps = 42.0;
        config.agent_configs[0].posted_collateral = Some(1_000_000);
        config.agent_configs[0].opening_balance = 0;
        config.agent_configs[0].unsecured_cap = 2_000_000;

        let mut orchestrator = Orchestrator::new(config).unwrap();

        // Queue transaction
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_500_000, 0, 10);
        orchestrator.state_mut().add_transaction(tx.clone());
        orchestrator.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx.id().to_string());

        // Run 12 ticks
        for _ in 0..12 {
            orchestrator.tick().unwrap();
        }

        orchestrator.get_costs("BANK_A").unwrap().total()
    }

    // Run the same simulation 10 times
    let first_result = run_simulation();
    for i in 0..10 {
        let result = run_simulation();
        assert_eq!(result, first_result,
                   "Run {} produced different cost: {} vs {}", i, result, first_result);
    }
}
