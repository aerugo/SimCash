//! TDD Tests for Liquidity Pool and Allocation (Enhancement 11.2)
//!
//! These tests verify the liquidity pool feature that enables agents to allocate
//! liquidity from an external pool into the payment system. This models the BIS
//! Period 0 decision where agents choose how much actual cash to bring into settlement.
//!
//! Key concepts:
//! - liquidity_pool: Total available external liquidity (i64 cents)
//! - liquidity_allocation_fraction: Fraction of pool to allocate (0.0 to 1.0)
//! - Opening balance + allocated liquidity determines starting balance

use payment_simulator_core_rs::orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;

/// Helper to create basic config for liquidity pool tests
fn create_base_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 10,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![],
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

// =============================================================================
// Phase 2.1: Configuration Parsing Tests
// =============================================================================

#[test]
fn test_agent_config_with_liquidity_pool_basic() {
    // Agent should be able to specify a liquidity pool amount
    let agent_config = AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000), // New field
        liquidity_allocation_fraction: None, // Defaults to 1.0
    };

    assert_eq!(agent_config.liquidity_pool, Some(2_000_000));
}

#[test]
fn test_agent_config_with_allocation_fraction() {
    // Agent should be able to specify an allocation fraction
    let agent_config = AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: Some(0.5), // 50% of pool
    };

    assert_eq!(agent_config.liquidity_allocation_fraction, Some(0.5));
}

#[test]
fn test_agent_config_backwards_compatible() {
    // Existing configs without liquidity_pool should still work
    let agent_config = AgentConfig {
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
        liquidity_pool: None, // Not specified
        liquidity_allocation_fraction: None,
    };

    assert_eq!(agent_config.liquidity_pool, None);
    assert_eq!(agent_config.liquidity_allocation_fraction, None);
}

// =============================================================================
// Phase 2.2: Basic Allocation Mechanics Tests
// =============================================================================

#[test]
fn test_full_pool_allocation_default() {
    // When liquidity_pool specified without fraction, should allocate 100% (default)
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: None, // Should default to 1.0
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    // Balance should be entire pool
    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 2_000_000);
}

#[test]
fn test_half_pool_allocation() {
    // Allocating 50% of pool should set balance to half
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: Some(0.5),
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 1_000_000);
}

#[test]
fn test_zero_allocation() {
    // Allocating 0% should leave balance at zero
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: Some(0.0),
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 0);
}

#[test]
fn test_opening_balance_plus_allocated_liquidity() {
    // Opening balance and allocated liquidity should be additive
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 500_000, // Base balance
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(1_000_000), // Additional pool
        liquidity_allocation_fraction: Some(0.5), // Allocate 50%
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    // balance = opening_balance + (pool * fraction)
    // balance = 500,000 + (1,000,000 * 0.5) = 1,000,000
    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 1_000_000);
}

// =============================================================================
// Phase 2.3: Validation Tests
// =============================================================================

#[test]
#[should_panic(expected = "allocation_fraction")]
fn test_reject_allocation_fraction_above_one() {
    // Allocation fraction > 1.0 should be rejected
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: Some(1.5), // Invalid: > 1.0
    });

    let _ = Orchestrator::new(config).unwrap(); // Should panic
}

#[test]
#[should_panic(expected = "allocation_fraction")]
fn test_reject_allocation_fraction_below_zero() {
    // Allocation fraction < 0 should be rejected
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(2_000_000),
        liquidity_allocation_fraction: Some(-0.1), // Invalid: < 0
    });

    let _ = Orchestrator::new(config).unwrap(); // Should panic
}

#[test]
#[should_panic(expected = "liquidity_pool")]
fn test_reject_negative_liquidity_pool() {
    // Negative liquidity pool should be rejected
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(-1_000_000), // Invalid: negative
        liquidity_allocation_fraction: None,
    });

    let _ = Orchestrator::new(config).unwrap(); // Should panic
}

// =============================================================================
// Phase 2.4: Rounding and Edge Cases
// =============================================================================

#[test]
fn test_fractional_allocation_rounds_down() {
    // Fractional cents should round down to maintain i64 integrity
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(1_000_001), // Odd number
        liquidity_allocation_fraction: Some(0.5),
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    // 1,000,001 * 0.5 = 500,000.5 → should floor to 500,000
    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 500_000);
}

#[test]
fn test_zero_pool_is_valid() {
    // Liquidity pool of 0 should be valid (no external liquidity)
    let mut config = create_base_config();
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 100_000,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(0),
        liquidity_allocation_fraction: Some(0.5),
    });

    let orchestrator = Orchestrator::new(config).unwrap();

    // Balance should just be opening_balance (0 from pool)
    let agent = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(agent.balance(), 100_000);
}

// =============================================================================
// Phase 2.5: Liquidity Cost Tracking Tests
// =============================================================================

#[test]
fn test_allocated_liquidity_has_opportunity_cost() {
    // Allocated liquidity should accrue opportunity cost per tick
    let mut config = create_base_config();
    config.cost_rates.liquidity_cost_per_tick_bps = 15.0; // 15 bps opportunity cost
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 0,
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: Some(1_000_000),
        liquidity_allocation_fraction: Some(1.0),
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run one tick
    orchestrator.tick().unwrap();

    // Check liquidity opportunity cost was accrued
    // Cost = 1,000,000 * (15 / 10,000) = 1,500 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_liquidity_opportunity_cost, 1_500);
}

#[test]
fn test_opening_balance_no_liquidity_cost() {
    // Opening balance without liquidity_pool should NOT have liquidity cost
    // (Only liquidity cost applies when explicitly using pool)
    let mut config = create_base_config();
    config.cost_rates.liquidity_cost_per_tick_bps = 15.0;
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 1_000_000, // Regular opening balance
        unsecured_cap: 0,
        policy: PolicyConfig::Fifo,
        arrival_config: None,
                arrival_bands: None,
        posted_collateral: None,
        collateral_haircut: None,
                max_collateral_capacity: None,
        limits: None,
        liquidity_pool: None, // No liquidity pool
        liquidity_allocation_fraction: None,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    orchestrator.tick().unwrap();

    // No liquidity opportunity cost (opening_balance is assumed already at central bank)
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_liquidity_opportunity_cost, 0);
}
