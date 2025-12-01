// TDD Cycle 7: Orchestrator Collateral Integration Tests
//
// Tests the full tick loop with both strategic and end-of-tick collateral management.
// These tests verify that:
// 1. STEP 2.5 evaluates strategic_collateral_tree (before RTGS)
// 2. NEW STEP evaluates end_of_tick_collateral_tree (after LSM, before costs)
// 3. Both layers can act independently in the same tick
// 4. Collateral decisions are executed correctly
// 5. Events are logged with correct reasons

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};

/// Create base test configuration
fn create_test_config(agent_id: &str, balance: i64, policy_json: &str) -> OrchestratorConfig {
    // Simple FIFO policy for BANK_B (receiver)
    let fifo_policy = r#"{
        "version": "1.0",
        "policy_id": "fifo",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },
        "strategic_collateral_tree": null,
        "end_of_tick_collateral_tree": null
    }"#;

    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: agent_id.to_string(),
                opening_balance: balance,
                unsecured_cap: 10_000, // Provides collateral capacity (10k × 10 = 100k)
                policy: PolicyConfig::FromJson {
                    json: policy_json.to_string(),
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
            // Add BANK_B as receiver with simple FIFO policy
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 100_000,
                policy: PolicyConfig::FromJson {
                    json: fifo_policy.to_string(),
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
            overdraft_bps_per_tick: 0.0001,
            delay_cost_per_tick_per_cent: 0.00001,
            collateral_cost_per_tick_bps: 0.0002,
            eod_penalty_per_transaction: 10000,
            deadline_penalty: 5000,
            split_friction_cost: 1000,
            overdue_delay_multiplier: 5.0, // Phase 3: Escalating delay cost for overdue
            priority_delay_multipliers: None, // Enhancement 11.1
            liquidity_cost_per_tick_bps: 0.0, // Enhancement 11.2
        },
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    }
}

/// Create test configuration with initial posted collateral
fn create_test_config_with_collateral(
    agent_id: &str,
    balance: i64,
    posted_collateral: i64,
    policy_json: &str,
) -> OrchestratorConfig {
    let mut config = create_test_config(agent_id, balance, policy_json);
    config.agent_configs[0].posted_collateral = Some(posted_collateral);
    config
}

#[test]
fn test_strategic_collateral_layer_runs_at_step_2_5() {
    // Create policy with strategic_collateral_tree that posts 50k when queue1_liquidity_gap > 0
    let policy_json = r#"{
        "version": "1.0",
        "policy_id": "test_strategic",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },
        "strategic_collateral_tree": {
            "node_id": "S1",
            "type": "condition",
            "description": "Check if liquidity gap exists",
            "condition": {
                "op": ">",
                "left": {"field": "queue1_liquidity_gap"},
                "right": {"value": 0}
            },
            "on_true": {
                "node_id": "S2",
                "type": "action",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"value": 50000},
                    "reason": {"value": "UrgentLiquidityNeed"}
                }
            },
            "on_false": {
                "node_id": "S3",
                "type": "action",
                "action": "HoldCollateral"
            }
        },
        "end_of_tick_collateral_tree": null
    }"#;

    // Create orchestrator with custom policy
    let config = create_test_config("BANK_A", 40_000, policy_json);
    let mut orch = Orchestrator::new(config).unwrap();

    // Submit a transaction that exceeds balance
    // This will create the transaction and add it to BANK_A's queue
    orch.submit_transaction(
        "BANK_A", "BANK_B", 60_000, // Needs 60k, has 40k → gap of 20k
        100,    // deadline
        1,      // priority
        false,  // not divisible
    )
    .expect("Failed to submit transaction");

    // Debug: Check queue before tick
    let state_before = orch.state();
    let agent_before = state_before.get_agent("BANK_A").unwrap();
    println!(
        "Before tick: balance={}, queue_size={}, posted_collateral={}",
        agent_before.balance(),
        agent_before.outgoing_queue().len(),
        agent_before.posted_collateral()
    );
    println!(
        "Queue1 liquidity gap: {}",
        agent_before.queue1_liquidity_gap(state_before)
    );

    // Tick once - should trigger strategic collateral posting at STEP 2.5
    let result = orch.tick();
    if let Err(e) = &result {
        panic!("Tick failed: {:?}", e);
    }

    // Debug: Check events
    let events = orch.event_log().events();
    println!("Total events logged: {}", events.len());
    for event in events {
        println!("  Event: {:?}", event);
    }

    // Verify collateral was posted
    let final_state = orch.state();
    let agent = final_state.get_agent("BANK_A").unwrap();
    println!(
        "After tick: posted_collateral={}",
        agent.posted_collateral()
    );
    assert_eq!(
        agent.posted_collateral(),
        50_000,
        "Strategic layer should have posted 50k collateral at STEP 2.5"
    );

    // Verify CollateralPost event was logged
    let collateral_events = orch.event_log().events_of_type("CollateralPost");
    assert_eq!(
        collateral_events.len(),
        1,
        "Should have 1 CollateralPost event"
    );
}

#[test]
fn test_end_of_tick_layer_runs_after_lsm() {
    // Create policy with end_of_tick_collateral_tree that withdraws when queue2_size == 0
    let policy_json = r#"{
        "version": "1.0",
        "policy_id": "test_eot",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },
        "strategic_collateral_tree": null,
        "end_of_tick_collateral_tree": {
            "node_id": "E1",
            "type": "condition",
            "description": "Check if RTGS queue empty",
            "condition": {
                "op": "==",
                "left": {"field": "queue2_size"},
                "right": {"value": 0}
            },
            "on_true": {
                "node_id": "E2",
                "type": "condition",
                "description": "Check if collateral posted",
                "condition": {
                    "op": ">",
                    "left": {"field": "posted_collateral"},
                    "right": {"value": 0}
                },
                "on_true": {
                    "node_id": "E3",
                    "type": "action",
                    "action": "WithdrawCollateral",
                    "parameters": {
                        "amount": {"field": "posted_collateral"},
                        "reason": {"value": "EndOfDayCleanup"}
                    }
                },
                "on_false": {
                    "node_id": "E4",
                    "type": "action",
                    "action": "HoldCollateral"
                }
            },
            "on_false": {
                "node_id": "E5",
                "type": "action",
                "action": "HoldCollateral"
            }
        }
    }"#;

    // Create orchestrator with custom policy and posted collateral
    let config = create_test_config_with_collateral("BANK_A", 100_000, 30_000, policy_json);
    let mut orch = Orchestrator::new(config).unwrap();

    // Tick once - no transactions, queue2 should be empty, should trigger withdrawal
    let result = orch.tick();
    if let Err(e) = &result {
        panic!("Tick failed: {:?}", e);
    }

    // Verify collateral was withdrawn
    let final_state = orch.state();
    let agent = final_state.get_agent("BANK_A").unwrap();
    assert_eq!(
        agent.posted_collateral(),
        0,
        "End-of-tick layer should have withdrawn all collateral after LSM"
    );

    // Verify CollateralWithdraw event was logged
    let withdraw_events = orch.event_log().events_of_type("CollateralWithdraw");
    assert_eq!(
        withdraw_events.len(),
        1,
        "Should have 1 CollateralWithdraw event"
    );
}

#[test]
fn test_both_layers_can_act_in_same_tick() {
    // Create policy with both strategic and end-of-tick trees
    let policy_json = r#"{
        "version": "1.0",
        "policy_id": "test_both_layers",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },
        "strategic_collateral_tree": {
            "node_id": "S1",
            "type": "action",
            "action": "PostCollateral",
            "parameters": {
                "amount": {"value": 20000},
                "reason": {"value": "PreemptivePosting"}
            }
        },
        "end_of_tick_collateral_tree": {
            "node_id": "E1",
            "type": "action",
            "action": "PostCollateral",
            "parameters": {
                "amount": {"value": 10000},
                "reason": {"value": "EndOfDayCleanup"}
            }
        }
    }"#;

    // Create orchestrator with custom policy
    let config = create_test_config("BANK_A", 100_000, policy_json);
    let mut orch = Orchestrator::new(config).unwrap();

    // Tick once - both layers should post collateral
    let result = orch.tick();
    assert!(result.is_ok(), "Tick should succeed");

    // Verify both collateral posts happened
    let final_state = orch.state();
    let agent = final_state.get_agent("BANK_A").unwrap();
    assert_eq!(
        agent.posted_collateral(),
        30_000,
        "Both layers should have posted: 20k (strategic) + 10k (end-of-tick)"
    );

    // Verify both CollateralPost events were logged (one from each layer)
    let post_events = orch.event_log().events_of_type("CollateralPost");
    assert_eq!(
        post_events.len(),
        2,
        "Should have 2 CollateralPost events (one from each layer)"
    );
}

#[test]
fn test_layers_are_independent() {
    // Strategic posts, end-of-tick withdraws - both should execute
    let policy_json = r#"{
        "version": "1.0",
        "policy_id": "test_independent",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },
        "strategic_collateral_tree": {
            "node_id": "S1",
            "type": "action",
            "action": "PostCollateral",
            "parameters": {
                "amount": {"value": 50000},
                "reason": {"value": "UrgentLiquidityNeed"}
            }
        },
        "end_of_tick_collateral_tree": {
            "node_id": "E1",
            "type": "action",
            "action": "WithdrawCollateral",
            "parameters": {
                "amount": {"value": 20000},
                "reason": {"value": "CostOptimization"}
            }
        }
    }"#;

    // Create orchestrator with custom policy and initial collateral
    let config = create_test_config_with_collateral("BANK_A", 100_000, 20_000, policy_json);
    let mut orch = Orchestrator::new(config).unwrap();

    // Tick once
    let result = orch.tick();
    assert!(result.is_ok(), "Tick should succeed");

    // Strategic posts 50k, end-of-tick withdraws 20k → net: 20k + 50k - 20k = 50k
    let final_state = orch.state();
    let agent = final_state.get_agent("BANK_A").unwrap();
    assert_eq!(
        agent.posted_collateral(),
        50_000,
        "Strategic posts 50k, end-of-tick withdraws 20k: 20k + 50k - 20k = 50k"
    );

    // Verify both event types logged
    let post_events = orch.event_log().events_of_type("CollateralPost");
    let withdraw_events = orch.event_log().events_of_type("CollateralWithdraw");

    assert_eq!(post_events.len(), 1, "Should have 1 Post event");
    assert_eq!(withdraw_events.len(), 1, "Should have 1 Withdraw event");
}

#[test]
fn test_end_of_tick_sees_final_settlement_state() {
    // End-of-tick tree should see Queue 2 state AFTER LSM has run
    // This test verifies timing: end-of-tick runs AFTER LSM completion

    let policy_json = r#"{
        "version": "1.0",
        "policy_id": "test_timing",
        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Hold"
        },
        "strategic_collateral_tree": null,
        "end_of_tick_collateral_tree": {
            "node_id": "E1",
            "type": "condition",
            "description": "Withdraw only if Queue 2 empty (after LSM)",
            "condition": {
                "op": "==",
                "left": {"field": "queue2_size"},
                "right": {"value": 0}
            },
            "on_true": {
                "node_id": "E2",
                "type": "action",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"value": 5000},
                    "reason": {"value": "EndOfDayCleanup"}
                }
            },
            "on_false": {
                "node_id": "E3",
                "type": "action",
                "action": "HoldCollateral"
            }
        }
    }"#;

    // Create orchestrator with custom policy
    let config = create_test_config("BANK_A", 200_000, policy_json);
    let mut orch = Orchestrator::new(config).unwrap();

    // Tick once - no transactions in Queue 2, so end-of-tick should post
    let result = orch.tick();
    if let Err(e) = &result {
        panic!("Tick failed: {:?}", e);
    }

    // Verify collateral was posted (Queue 2 was empty after LSM)
    let final_state = orch.state();
    let agent = final_state.get_agent("BANK_A").unwrap();
    assert_eq!(
        agent.posted_collateral(),
        5_000,
        "End-of-tick should have posted because queue2_size == 0 after LSM"
    );
}
