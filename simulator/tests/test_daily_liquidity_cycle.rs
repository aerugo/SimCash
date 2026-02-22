//! Integration tests for daily liquidity reallocation cycle
//!
//! Tests the opt-in feature where allocated liquidity returns to pool at EOD
//! and is reallocated at SOD using the current policy's fraction.

use payment_simulator_core_rs::{
    orchestrator::{
        AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering,
    },
    settlement::lsm::LsmConfig,
    Transaction,
};

// =============================================================================
// Helpers
// =============================================================================

/// FIFO policy JSON with configurable fraction
fn fifo_policy_json(fraction: f64) -> String {
    format!(
        r#"{{
            "version": "1.0",
            "policy_id": "fifo_frac_{frac}",
            "description": "FIFO with fraction {frac}",
            "payment_tree": {{
                "type": "action",
                "node_id": "A1",
                "action": "Release",
                "parameters": {{}}
            }},
            "strategic_collateral_tree": null,
            "end_of_tick_collateral_tree": null,
            "parameters": {{
                "initial_liquidity_fraction": {frac}
            }}
        }}"#,
        frac = fraction
    )
}

/// Create a 2-agent config with liquidity pools, daily reallocation enabled
fn create_pool_config(reallocation_enabled: bool) -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 10,
        eod_rush_threshold: 0.8,
        num_days: 3,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 100_000,    // $1,000 base
                unsecured_cap: 500_000,      // $5,000 overdraft capacity
                policy: PolicyConfig::FromJson {
                    json: fifo_policy_json(0.5),
                },
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: Some(1_000_000),  // $10,000 pool
                liquidity_allocation_fraction: Some(0.5), // 50% → $5,000 allocated
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 100_000,
                unsecured_cap: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,  // No pool — should be unaffected
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
        daily_liquidity_reallocation: reallocation_enabled,
    }
}

// =============================================================================
// Phase 1: Fraction extraction
// =============================================================================

#[test]
fn test_extract_fraction_from_json_policy() {
    // Verified indirectly: create orchestrator with fraction=0.5,
    // initial balance should be opening_balance + floor(pool * 0.5)
    let config = create_pool_config(false);
    let orch = Orchestrator::new(config).unwrap();

    // BANK_A: 100,000 + floor(1,000,000 * 0.5) = 100,000 + 500,000 = 600,000
    let balance = orch.get_agent_balance("BANK_A").unwrap();
    assert_eq!(balance, 600_000, "Initial balance should be opening + allocated");
}

// =============================================================================
// Phase 2: EOD liquidity return
// =============================================================================

#[test]
fn test_eod_returns_liquidity_when_enabled() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // BANK_A starts at 600,000 (100k base + 500k allocated)
    assert_eq!(orch.get_agent_balance("BANK_A").unwrap(), 600_000);

    // Run full day 1 (10 ticks) — no transactions, balance unchanged
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // After EOD: allocated liquidity (500,000) should be returned
    // Balance = 600,000 - 500,000 = 100,000 (back to opening_balance)
    // Then immediately reallocated at SOD of day 2... 
    // Actually, EOD happens at end of tick 9 (last tick of day 1).
    // SOD reallocation happens at tick 10 (first tick of day 2).
    // So between EOD and SOD, the balance briefly goes to 100,000.
    // But since both happen within tick processing, we check after tick 10.
    
    // Run first tick of day 2 (triggers SOD reallocation)
    orch.tick().unwrap();

    // After SOD day 2: reallocated with fraction from policy (0.5)
    // Balance = 100,000 + floor(1,000,000 * 0.5) = 600,000
    let balance = orch.get_agent_balance("BANK_A").unwrap();
    assert_eq!(balance, 600_000, "After EOD return + SOD realloc, balance should reset to initial");
}

#[test]
fn test_eod_no_return_when_disabled() {
    let config = create_pool_config(false);
    let mut orch = Orchestrator::new(config).unwrap();

    assert_eq!(orch.get_agent_balance("BANK_A").unwrap(), 600_000);

    // Run full day 1
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Run first tick of day 2
    orch.tick().unwrap();

    // With reallocation disabled, balance should be unchanged (no return, no realloc)
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        600_000,
        "With reallocation disabled, balance should be unchanged"
    );
}

#[test]
fn test_agent_without_pool_unaffected() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // BANK_B has no pool, starts at 100,000
    assert_eq!(orch.get_agent_balance("BANK_B").unwrap(), 100_000);

    // Run full day + first tick of day 2
    for _ in 0..11 {
        orch.tick().unwrap();
    }

    // BANK_B should be unaffected
    assert_eq!(
        orch.get_agent_balance("BANK_B").unwrap(),
        100_000,
        "Agent without pool should not be affected by reallocation"
    );
}

#[test]
fn test_eod_return_emits_events() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Run full day 1 (10 ticks)
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Check for LiquidityReturn event at last tick of day 1 (tick 9)
    let events = orch.get_tick_events(9);
    let return_events: Vec<_> = events
        .iter()
        .filter(|e| e.event_type() == "LiquidityReturn")
        .collect();
    assert_eq!(
        return_events.len(),
        1,
        "Should emit exactly 1 LiquidityReturn event for BANK_A (BANK_B has no pool)"
    );
}

#[test]
fn test_sod_alloc_emits_events() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Run full day 1 + first tick of day 2
    for _ in 0..11 {
        orch.tick().unwrap();
    }

    // Check for LiquidityAllocation event at first tick of day 2 (tick 10)
    let events = orch.get_tick_events(10);
    let alloc_events: Vec<_> = events
        .iter()
        .filter(|e| e.event_type() == "LiquidityAllocation")
        .collect();
    assert_eq!(
        alloc_events.len(),
        1,
        "Should emit exactly 1 LiquidityAllocation event for BANK_A"
    );
}

// =============================================================================
// Phase 3: SOD allocation reads current policy fraction
// =============================================================================

#[test]
fn test_sod_uses_updated_fraction() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Day 1: fraction=0.5, balance=600,000
    assert_eq!(orch.get_agent_balance("BANK_A").unwrap(), 600_000);

    // Run full day 1
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Update policy to fraction=0.3 between days
    orch.update_agent_policy("BANK_A", &fifo_policy_json(0.3)).unwrap();

    // Run first tick of day 2 (triggers EOD return from day 1 already happened, SOD realloc)
    orch.tick().unwrap();

    // After SOD: 100,000 + floor(1,000,000 * 0.3) = 100,000 + 300,000 = 400,000
    let balance = orch.get_agent_balance("BANK_A").unwrap();
    assert_eq!(
        balance, 400_000,
        "After policy update to fraction=0.3, balance should be 100k + 300k = 400k"
    );
}

#[test]
fn test_sod_zero_fraction() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Run full day 1
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Update to fraction=0.0
    orch.update_agent_policy("BANK_A", &fifo_policy_json(0.0)).unwrap();

    // Run first tick of day 2
    orch.tick().unwrap();

    // Balance = opening_balance + 0 = 100,000
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        100_000,
        "With fraction=0.0, only opening balance should remain"
    );
}

#[test]
fn test_sod_full_fraction() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Run full day 1
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Update to fraction=1.0
    orch.update_agent_policy("BANK_A", &fifo_policy_json(1.0)).unwrap();

    // Run first tick of day 2
    orch.tick().unwrap();

    // Balance = 100,000 + 1,000,000 = 1,100,000
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        1_100_000,
        "With fraction=1.0, full pool should be allocated"
    );
}

// =============================================================================
// Phase 4: Integration — multi-day cycle
// =============================================================================

#[test]
fn test_three_day_cycle_with_policy_changes() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Day 1: fraction=0.5 → balance=600,000
    assert_eq!(orch.get_agent_balance("BANK_A").unwrap(), 600_000);
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Update fraction to 0.8 for day 2
    orch.update_agent_policy("BANK_A", &fifo_policy_json(0.8)).unwrap();
    orch.tick().unwrap(); // SOD day 2
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        900_000, // 100k + 800k
        "Day 2 should use fraction=0.8"
    );
    for _ in 0..9 {
        orch.tick().unwrap();
    }

    // Update fraction to 0.1 for day 3
    orch.update_agent_policy("BANK_A", &fifo_policy_json(0.1)).unwrap();
    orch.tick().unwrap(); // SOD day 3
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        200_000, // 100k + 100k
        "Day 3 should use fraction=0.1"
    );
}

#[test]
fn test_determinism_with_reallocation() {
    // Run 1
    let config1 = create_pool_config(true);
    let mut orch1 = Orchestrator::new(config1).unwrap();
    for _ in 0..10 {
        orch1.tick().unwrap();
    }
    orch1.update_agent_policy("BANK_A", &fifo_policy_json(0.3)).unwrap();
    for _ in 0..10 {
        orch1.tick().unwrap();
    }
    let costs1 = orch1.get_costs("BANK_A").unwrap();

    // Run 2 — identical
    let config2 = create_pool_config(true);
    let mut orch2 = Orchestrator::new(config2).unwrap();
    for _ in 0..10 {
        orch2.tick().unwrap();
    }
    orch2.update_agent_policy("BANK_A", &fifo_policy_json(0.3)).unwrap();
    for _ in 0..10 {
        orch2.tick().unwrap();
    }
    let costs2 = orch2.get_costs("BANK_A").unwrap();

    assert_eq!(costs1.total_liquidity_cost, costs2.total_liquidity_cost, "INV-2: determinism");
    assert_eq!(costs1.total_delay_cost, costs2.total_delay_cost, "INV-2: determinism");
    assert_eq!(costs1.total_penalty_cost, costs2.total_penalty_cost, "INV-2: determinism");
}

#[test]
fn test_balance_conservation_with_transactions() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Add a transaction A→B
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 8);
    let tx_id = tx.id().to_string();
    orch.state_mut().add_transaction(tx);
    orch.state_mut().get_agent_mut("BANK_A").unwrap().queue_outgoing(tx_id);

    // Run day 1 — tx should settle, A loses 200k, B gains 200k
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // After EOD return: A balance = (600k - 200k) - 500k_returned = -100k
    // After SOD realloc (fraction=0.5): -100k + 500k = 400k
    // Run first tick of day 2
    orch.tick().unwrap();

    let a_balance = orch.get_agent_balance("BANK_A").unwrap();
    let b_balance = orch.get_agent_balance("BANK_B").unwrap();

    // BANK_A: opening(100k) + alloc(500k) - sent(200k) = 400k after day 1
    // EOD: 400k - 500k = -100k. SOD: -100k + 500k = 400k
    assert_eq!(a_balance, 400_000, "BANK_A after tx + realloc");

    // BANK_B: 100k + received(200k) = 300k. No pool, no realloc.
    assert_eq!(b_balance, 300_000, "BANK_B after receiving");

    // Conservation: total money in system should be consistent
    // Opening: A=600k + B=100k = 700k
    // Day 2: A=400k + B=300k = 700k ✓ (pool allocation is separate)
}

// =============================================================================
// Phase 1 (additional): get_agent_policies consistency after realloc
// =============================================================================

#[test]
fn test_config_consistency_after_realloc() {
    let config = create_pool_config(true);
    let mut orch = Orchestrator::new(config).unwrap();

    // Run day 1
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Update fraction
    orch.update_agent_policy("BANK_A", &fifo_policy_json(0.7)).unwrap();

    // Run into day 2
    orch.tick().unwrap();

    // get_agent_policies should still reflect the updated policy
    let policies = orch.get_agent_policies();
    let bank_a = policies.iter().find(|(id, _)| id == "BANK_A").unwrap();
    match &bank_a.1 {
        PolicyConfig::FromJson { json } => {
            assert!(json.contains("0.7"), "Policy should contain updated fraction");
        }
        other => panic!("Expected FromJson, got {:?}", other),
    }
}
