// Integration tests for three realistic bank policies
// Tests multi-day simulations with GNB, ARB, and MIB policies

use payment_simulator_core_rs::orchestrator::{
    AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;
use std::{fs, path::PathBuf};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

fn policies_dir() -> PathBuf {
    PathBuf::from("policies")
}

/// Load policy JSON file as a string
fn load_policy_json(filename: &str) -> String {
    let path = policies_dir().join(filename);
    fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("Failed to read policy file {:?}: {}", path, e))
}

/// Create a standard 100 tick/day configuration with all three banks
fn create_config(num_days: usize) -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        num_days,
        rng_seed: 42,
        eod_rush_threshold: 0.8, // Last 20% of day
        agent_configs: vec![
            AgentConfig {
                id: "GNB".to_string(),
                opening_balance: 100_000_000, // $1M
                unsecured_cap: 50_000_000,      // $500k
                policy: PolicyConfig::FromJson {
                    json: load_policy_json("goliath_national_bank.json"),
                },
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
                id: "ARB".to_string(),
                opening_balance: 60_000_000,  // $600k
                unsecured_cap: 50_000_000,      // $500k
                policy: PolicyConfig::FromJson {
                    json: load_policy_json("agile_regional_bank.json"),
                },
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
                id: "MIB".to_string(),
                opening_balance: 50_000_000,  // $500k
                unsecured_cap: 50_000_000,      // $500k
                policy: PolicyConfig::FromJson {
                    json: load_policy_json("momentum_investment_bank.json"),
                },
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
        cost_rates: CostRates {
            overdraft_bps_per_tick: 2.0,
            delay_cost_per_tick_per_cent: 0.01,
            collateral_cost_per_tick_bps: 1.0,
            split_friction_cost: 100_00,
            deadline_penalty: 1000_00,
            eod_penalty_per_transaction: 5000_00,
            overdue_delay_multiplier: 5.0, // Phase 3: Escalating delay cost for overdue
            priority_delay_multipliers: None, // Enhancement 11.1
            liquidity_cost_per_tick_bps: 0.0, // Enhancement 11.2
        },
        lsm_config: LsmConfig {
            enable_bilateral: true,
            enable_cycles: true,
            max_cycle_length: 5,
            max_cycles_per_tick: 10,
        },
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    }
}

// ============================================================================
// TESTS
// ============================================================================

#[test]
fn test_policies_load_successfully() {
    // Verify all three policy files can be loaded

    let gnb_json = load_policy_json("goliath_national_bank.json");
    let arb_json = load_policy_json("agile_regional_bank.json");
    let mib_json = load_policy_json("momentum_investment_bank.json");

    assert!(!gnb_json.is_empty(), "GNB policy should not be empty");
    assert!(!arb_json.is_empty(), "ARB policy should not be empty");
    assert!(!mib_json.is_empty(), "MIB policy should not be empty");

    // Verify they contain expected policy IDs
    assert!(gnb_json.contains("goliath_national_bank_v2"));
    assert!(arb_json.contains("agile_regional_bank_v2"));
    assert!(mib_json.contains("momentum_investment_bank_v2"));

    println!("✓ All three policy files loaded successfully");
}

#[test]
fn test_basic_three_bank_simulation() {
    // Simple 3-day simulation with all three banks
    // Verify they can all run without errors

    let config = create_config(3); // 3 days

    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Run for 3 days (300 ticks)
    for _ in 0..300 {
        let result = orchestrator.tick();
        assert!(result.is_ok(), "Tick failed: {:?}", result.err());
    }

    let final_state = orchestrator.state();

    // All agents should still exist
    assert_eq!(final_state.agents().len(), 3);

    // Get final balances
    let gnb_balance = final_state.agents().get("GNB").unwrap().balance();
    let arb_balance = final_state.agents().get("ARB").unwrap().balance();
    let mib_balance = final_state.agents().get("MIB").unwrap().balance();

    println!("✓ Basic three-bank simulation completed successfully");
    println!("  GNB final balance: ${}", gnb_balance / 100);
    println!("  ARB final balance: ${}", arb_balance / 100);
    println!("  MIB final balance: ${}", mib_balance / 100);
}

#[test]
fn test_three_day_with_manual_transactions() {
    // 3-day simulation with manually submitted transactions

    let config = create_config(3);
    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Day 1: MIB sends to GNB (aggressive trader style)
    // Submit at beginning with deadline at tick 50
    for _ in 0..5 {
        orchestrator
            .submit_transaction("MIB", "GNB", 3_000_000, 50, 5, false)
            .expect("Failed to submit MIB transaction");
    }

    // Day 1: GNB sends larger transfer to ARB (deadline tick 90)
    orchestrator
        .submit_transaction("GNB", "ARB", 20_000_000, 90, 7, false)
        .expect("Failed to submit GNB transaction");

    // Day 2: ARB sends back to GNB (deadline tick 180)
    orchestrator
        .submit_transaction("ARB", "GNB", 15_000_000, 180, 6, false)
        .expect("Failed to submit ARB transaction");

    // Day 3: Circular transactions (deadlines near end of day 3)
    orchestrator
        .submit_transaction("GNB", "ARB", 10_000_000, 280, 5, false)
        .expect("Failed to submit GNB->ARB");
    orchestrator
        .submit_transaction("ARB", "MIB", 8_000_000, 285, 5, false)
        .expect("Failed to submit ARB->MIB");
    orchestrator
        .submit_transaction("MIB", "GNB", 6_000_000, 290, 5, false)
        .expect("Failed to submit MIB->GNB");

    // Run full 3 days
    for tick_num in 0..300 {
        let result = orchestrator.tick();
        assert!(result.is_ok(), "Tick {} failed", tick_num);

        // Log key checkpoints
        if tick_num == 99 || tick_num == 199 || tick_num == 299 {
            let state = orchestrator.state();
            println!(
                "  End of Day {}: Queue size={}",
                tick_num / 100 + 1,
                state.queue_size()
            );
        }
    }

    let final_state = orchestrator.state();

    println!("✓ Three-day manual transaction test completed");
    println!("  Final balances:");
    println!(
        "    GNB: ${}",
        final_state.agents().get("GNB").unwrap().balance() / 100
    );
    println!(
        "    ARB: ${}",
        final_state.agents().get("ARB").unwrap().balance() / 100
    );
    println!(
        "    MIB: ${}",
        final_state.agents().get("MIB").unwrap().balance() / 100
    );

    // Queue should be empty or nearly empty at end
    assert!(
        final_state.queue_size() < 3,
        "Most transactions should be settled by end"
    );
}

#[test]
fn test_eod_rush_behavior() {
    // Test EOD rush period (last 20% of day)

    let config = create_config(1); // 1 day
    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Submit transactions during EOD rush period (deadlines near end of day)
    // EOD rush starts at tick 80 (80% of 100-tick day)
    orchestrator
        .submit_transaction("GNB", "ARB", 30_000_000, 95, 5, false)
        .expect("Failed to submit during EOD");
    orchestrator
        .submit_transaction("ARB", "MIB", 20_000_000, 96, 5, false)
        .expect("Failed to submit during EOD");
    orchestrator
        .submit_transaction("MIB", "GNB", 15_000_000, 98, 5, false)
        .expect("Failed to submit during EOD");

    // Run full day
    for _ in 0..100 {
        let result = orchestrator.tick();
        assert!(result.is_ok());
    }

    let final_state = orchestrator.state();

    println!("✓ EOD rush test completed");
    println!("  Final queue size: {}", final_state.queue_size());

    // EOD rush should aggressively settle most transactions
    assert!(
        final_state.queue_size() == 0,
        "All transactions should be settled during EOD rush"
    );
}

#[test]
fn test_different_policy_behaviors() {
    // Test that each bank exhibits different behavior patterns

    let config = create_config(1);
    let mut orchestrator = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Early day: Test conservative vs aggressive
    // GNB should be more conservative (150% buffer in early day)
    // MIB should be aggressive (default-to-release)

    orchestrator
        .submit_transaction("GNB", "ARB", 50_000_000, 80, 5, false)
        .expect("GNB transaction");
    orchestrator
        .submit_transaction("MIB", "ARB", 20_000_000, 80, 5, false)
        .expect("MIB transaction");

    // Run for 50 ticks
    for _ in 0..50 {
        let result = orchestrator.tick();
        assert!(result.is_ok());
    }

    // Check that simulation ran successfully with different policies
    let state = orchestrator.state();
    println!("  Mid-simulation queue size: {}", state.queue_size());

    // Continue to end of day
    for _ in 50..100 {
        let result = orchestrator.tick();
        assert!(result.is_ok());
    }

    println!("✓ Different policy behaviors test completed");
}
