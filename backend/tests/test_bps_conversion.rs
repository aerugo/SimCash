//! Unit tests for basis points (bps) to rate conversion
//!
//! This test file demonstrates the BUG in cost calculations where
//! bps values are used directly as fractions instead of being
//! converted properly (1 bps = 0.0001 = 1/10,000).
//!
//! TDD Process:
//! 1. Write failing tests (RED) ← WE ARE HERE
//! 2. Implement minimal fix (GREEN)
//! 3. Refactor if needed (REFACTOR)

use payment_simulator_core_rs::orchestrator::{
    AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig,
};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;
use payment_simulator_core_rs::Transaction;

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
                credit_limit: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            unsecured_cap: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 2_000_000,
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
            unsecured_cap: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
        scenario_events: None,
    }
}

// ============================================================================
// TDD: Basis Points Conversion Tests (These SHOULD FAIL initially)
// ============================================================================

#[test]
fn test_overdraft_cost_1_bps() {
    // SETUP: 1 basis point (bps) should equal 0.01% = 0.0001 as a fraction
    // Balance: -$100,000 (negative = overdraft)
    // Rate: 1 bps per tick
    // Expected cost per tick: $100,000 × 0.0001 = $10.00 = 1,000 cents

    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // 1 bp
    // Increase credit limit to allow this level of overdraft
    config.agent_configs[0].credit_limit = 15_000_000; // $150k credit limit

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into $100k overdraft
    // Opening balance: 1,000,000 cents ($10,000)
    // To get to -10,000,000 cents (-$100,000), need to send 11,000,000 cents
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 11_000_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute tick - transaction settles, balance goes to -100k
    orchestrator.tick().unwrap();

    // Check balance
    let bank_a = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(bank_a.balance(), -10_000_000, "Balance should be -$100,000 (-10,000,000 cents)");

    // Check cost (tick 0 already accrued cost)
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // After fix: 10,000,000 cents × 0.0001 = 1,000 cents
    assert_eq!(
        costs.total_liquidity_cost, 1_000,
        "1 bps on $100k overdraft = $10/tick = 1,000 cents"
    );
}

#[test]
fn test_overdraft_cost_0_8_bps() {
    // Real config value from three_day_realistic_crisis.yaml
    // Rate: 0.8 bps per tick
    // Balance: -$117,679.26
    // Expected: $117,679.26 × 0.00008 = $9.41 = 941 cents

    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 0.8; // 0.8 bp (from real config)
    // Increase credit limit to allow this level of overdraft
    config.agent_configs[0].credit_limit = 15_000_000; // $150k credit limit

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into $117,679.26 overdraft (11,767,926 cents)
    // Opening balance: 1,000,000 cents ($10,000)
    // To get to -11,767,926 cents, need to send 12,767,926 cents
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        12_767_926, // Sends $127,679.26, ends at -$117,679.26
        0,
        10,
    );

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // After fix: 11,767,926 cents × 0.00008 = 941 cents
    assert_eq!(
        costs.total_liquidity_cost, 941,
        "0.8 bps on $117,679.26 overdraft = $9.41/tick = 941 cents"
    );
}

#[test]
fn test_collateral_cost_0_0005_bps() {
    // Real config value from three_day_realistic_crisis.yaml
    // Rate: 0.0005 bps per tick
    // Collateral: $64,944.24
    // Expected: $64,944.24 × 0.00000005 = $0.0032 ≈ 0 cents (rounds to 0)

    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 0.0005; // 0.0005 bp
    config.agent_configs[0].posted_collateral = Some(6_494_424); // $64,944.24

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run one tick to accrue cost
    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // ❌ THIS WILL FAIL with current code!
    // Current code: 6,494,424 × 0.0005 = 3,247 cents (wrong!)
    // Expected:     6,494,424 × 0.00000005 = 0.32 cents ≈ 0 cents (rounds to 0)
    assert_eq!(
        costs.total_collateral_cost, 0,
        "0.0005 bps on $64,944.24 collateral = $0.0032/tick ≈ 0 cents (rounds to 0)"
    );
}

#[test]
fn test_collateral_cost_2_bps() {
    // Larger collateral cost to avoid rounding to zero
    // Rate: 2 bps per tick
    // Collateral: $1,000,000
    // Expected: $1,000,000 × 0.0002 = $200 = 20,000 cents

    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 2.0; // 2 bp
    config.agent_configs[0].posted_collateral = Some(100_000_000); // $1,000,000

    let mut orchestrator = Orchestrator::new(config).unwrap();

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // ❌ THIS WILL FAIL with current code!
    // Current code: 100,000,000 × 2.0 = 200,000,000 cents (wrong!)
    // Expected:     100,000,000 × 0.0002 = 20,000 cents (correct!)
    assert_eq!(
        costs.total_collateral_cost, 20_000,
        "2 bps on $1M collateral = $200/tick = 20,000 cents"
    );
}

#[test]
fn test_delay_cost_0_0001_already_correct() {
    // This test verifies that delay_cost_per_tick_per_cent is already
    // treated as a raw fraction (not bps), so it doesn't need conversion.
    // Rate: 0.0001 (already a fraction, equivalent to 1 bp if it were bps)
    // Queued amount: $500,000
    // Expected: $500,000 × 0.0001 = $50 = 5,000 cents

    let mut config = create_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001; // Already a fraction
    config.agent_configs[0].policy = PolicyConfig::LiquidityAware {
        target_buffer: 1_500_000, // High buffer to force holding
        urgency_threshold: 5,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that will be held
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        50_000_000, // $500,000
        0,
        50,
    );

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap(); // Tx held in queue

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // ✅ This should PASS (delay cost is already correct)
    assert_eq!(
        costs.total_delay_cost, 5_000,
        "0.0001 fraction on $500k queued = $50/tick = 5,000 cents"
    );
}

// ============================================================================
// Edge Cases
// ============================================================================

#[test]
fn test_zero_bps_gives_zero_cost() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 0.0;

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_100_000, 0, 10);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_liquidity_cost, 0, "0 bps = $0 cost");
}

#[test]
fn test_very_small_bps_rounds_to_zero() {
    // 0.001 bps on $1,000 should round to 0
    // $1,000 × 0.0000001 = $0.0001 = 0.01 cents → rounds to 0

    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 0.001; // Very small

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Small overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_010_000, 0, 10);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    // 10_000 × 0.0000001 = 0.001 cents → rounds to 0
    assert_eq!(costs.total_liquidity_cost, 0);
}
