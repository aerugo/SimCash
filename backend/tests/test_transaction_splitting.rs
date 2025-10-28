//! Integration tests for transaction splitting (Phase 5).
//!
//! Following TDD principles: these tests are written BEFORE implementation.
//! They define the expected behavior of transaction splitting at the policy layer.
//!
//! ## Test Coverage
//!
//! 1. **Parent-Child Relationships**: Tracking split transactions
//! 2. **SubmitPartial Handling**: Orchestrator creates child transactions
//! 3. **Split Friction Costs**: Cost formula f_s × (N-1)
//! 4. **LiquiditySplittingPolicy**: Intelligent splitting decisions
//! 5. **Integration**: Full tick loop with splitting scenarios

use payment_simulator_core_rs::models::{Event, Transaction};
use payment_simulator_core_rs::orchestrator::{
    AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig,
};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;

// ============================================================================
// Test 1: Transaction Model - Parent-Child Tracking
// ============================================================================

#[test]
fn test_transaction_parent_child_tracking() {
    // Test that split transactions correctly track parent-child relationships

    // Create parent transaction
    let parent = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000.00
        0,       // arrival_tick
        10,      // deadline
    );

    let parent_id = parent.id().to_string();

    // Create child transactions (3-way split)
    let child1 = Transaction::new_split(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        33_333, // ~$333.33
        0,
        10,
        parent_id.clone(), // Link to parent
    );

    let child2 = Transaction::new_split(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        33_333,
        0,
        10,
        parent_id.clone(),
    );

    let child3 = Transaction::new_split(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        33_334, // Remaining amount to sum to 100k
        0,
        10,
        parent_id.clone(),
    );

    // Verify parent has no parent
    assert_eq!(parent.parent_id(), None);
    assert!(!parent.is_split());

    // Verify children link to parent
    assert_eq!(child1.parent_id(), Some(parent_id.as_str()));
    assert_eq!(child2.parent_id(), Some(parent_id.as_str()));
    assert_eq!(child3.parent_id(), Some(parent_id.as_str()));
    assert!(child1.is_split());
    assert!(child2.is_split());
    assert!(child3.is_split());

    // Verify amounts sum correctly
    let total_child_amount = child1.amount() + child2.amount() + child3.amount();
    assert_eq!(total_child_amount, parent.amount());
}

// ============================================================================
// Test 2: Orchestrator - SubmitPartial Decision Handling
// ============================================================================

#[test]
fn test_orchestrator_handles_submit_partial() {
    // Test that orchestrator correctly creates child transactions when policy returns SubmitPartial

    let mut config = create_basic_config();

    // Use MockSplittingPolicy that returns SubmitPartial
    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 50_000, // Insufficient for 100k transaction
        credit_limit: 0,
        policy: PolicyConfig::MockSplitting {
            num_splits: 2, // Split into 2 parts
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Inject large transaction that will be split
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000,
        0,
        10,
    );
    let parent_id = tx.id().to_string();
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    // Tick should trigger policy decision → SubmitPartial → create 2 children
    orchestrator.tick().unwrap();

    // Verify 2 child transactions were created and submitted to settlement
    let events = orchestrator.event_log().events();

    // Should have:
    // 1. Arrival event for parent
    // 2. PolicySplit event indicating split decision
    // 3. 2x Settlement events for child transactions (if sufficient liquidity)
    // OR 2x QueuedRtgs events (if still insufficient)

    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    assert_eq!(split_events.len(), 1, "Should have 1 PolicySplit event");

    // Check that split event references parent transaction
    if let Event::PolicySplit {
        tx_id,
        num_splits,
        child_ids,
        ..
    } = split_events[0]
    {
        assert_eq!(tx_id, &parent_id);
        assert_eq!(*num_splits, 2);
        assert_eq!(child_ids.len(), 2);
    } else {
        panic!("Expected PolicySplit event");
    }
}

// ============================================================================
// Test 3: Split Friction Cost Calculation
// ============================================================================

#[test]
fn test_split_friction_cost_formula() {
    // Test cost formula: f_s × (N-1) where N is number of splits

    let split_friction_rate = 1000; // 1000 cents = $10 per split

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = split_friction_rate;

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 500_000,
        credit_limit: 0,
        policy: PolicyConfig::MockSplitting { num_splits: 3 }, // 3-way split
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Inject transaction that will be split into 3 parts
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, 0, 10);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    // Check cost accrual
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // Expected friction cost: f_s × (N-1) = 1000 × (3-1) = 2000 cents = $20
    assert_eq!(
        costs.total_split_friction_cost, 2000,
        "Split friction should be f_s × (N-1)"
    );
}

#[test]
fn test_no_split_friction_for_whole_transaction() {
    // Test that whole (unsplit) transactions incur no friction cost

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 1000;

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 500_000,
        credit_limit: 0,
        policy: PolicyConfig::Fifo, // FIFO submits whole transaction
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // No split → no friction cost
    assert_eq!(costs.total_split_friction_cost, 0);
}

// ============================================================================
// Test 4: LiquiditySplittingPolicy - Intelligent Splitting Decisions
// ============================================================================

#[test]
fn test_liquidity_splitting_policy_splits_when_insufficient_balance() {
    // Test that LiquiditySplittingPolicy splits large payment when balance is insufficient

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 100; // $1 per split

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 50_000, // Only $500, but needs to pay $1000
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 4,
            min_split_amount: 10_000, // Don't create splits < $100
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Large transaction that can't be settled whole
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 20);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    // Policy should decide to split (can send partial payments as balance allows)
    let events = orchestrator.event_log().events();
    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    assert!(
        !split_events.is_empty(),
        "Should split when balance insufficient for whole payment"
    );
}

#[test]
fn test_liquidity_splitting_policy_does_not_split_when_affordable() {
    // Test that policy does NOT split when agent has sufficient balance

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 1000; // High friction cost

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 200_000, // Plenty of balance for $1000 payment
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 4,
            min_split_amount: 10_000,
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 20);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    // Should submit whole transaction (no split)
    let events = orchestrator.event_log().events();
    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    assert_eq!(
        split_events.len(),
        0,
        "Should NOT split when balance is sufficient"
    );

    // Should have SubmitFull event instead
    let submit_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySubmit { .. }))
        .collect();

    assert_eq!(
        submit_events.len(),
        1,
        "Should submit whole transaction when affordable"
    );
}

#[test]
fn test_liquidity_splitting_respects_min_split_amount() {
    // Test that policy doesn't create splits smaller than min_split_amount

    let mut config = create_basic_config();

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 30_000,
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 10,
            min_split_amount: 20_000, // Don't create splits < $200
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Small transaction that would create tiny splits
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 50_000, 0, 20);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    let events = orchestrator.event_log().events();

    // Should either:
    // 1. Submit whole (hold until balance increases), OR
    // 2. Split into max 2 parts (25k each) to respect min_split_amount

    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    if !split_events.is_empty() {
        if let Event::PolicySplit { num_splits, .. } = split_events[0] {
            // If it splits, should be max 2 splits (50k / 2 = 25k > 20k min)
            assert!(
                *num_splits <= 2,
                "Should not create more than 2 splits to respect min_split_amount"
            );
        }
    }
}

#[test]
fn test_liquidity_splitting_respects_max_splits() {
    // Test that policy respects max_splits limit

    let mut config = create_basic_config();

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 10_000,
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 3, // Maximum 3 splits
            min_split_amount: 5_000,
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Very large transaction
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 500_000, 0, 50);
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    let events = orchestrator.event_log().events();
    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    if !split_events.is_empty() {
        if let Event::PolicySplit { num_splits, .. } = split_events[0] {
            assert!(
                *num_splits <= 3,
                "Should not exceed max_splits configuration"
            );
        }
    }
}

#[test]
fn test_liquidity_splitting_urgency_factor() {
    // Test that policy is more aggressive with splitting when deadline is near

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 100;

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 80_000, // $800
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 4,
            min_split_amount: 10_000,
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Transaction with URGENT deadline (only 2 ticks away)
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000,
        0,
        2, // Very tight deadline
    );
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    orchestrator.tick().unwrap();

    // Policy should be more willing to split despite friction cost when deadline is urgent
    let events = orchestrator.event_log().events();
    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    // Should attempt to make progress by splitting
    assert!(
        !split_events.is_empty() || events.iter().any(|e| matches!(e, Event::PolicySubmit { .. })),
        "Should take action (split or submit) when deadline is urgent"
    );
}

// ============================================================================
// Test 5: Integration - Full Tick Loop with Splitting
// ============================================================================

#[test]
fn test_full_splitting_workflow() {
    // End-to-end test: arrival → policy decides to split → children settle → costs accrue

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 500; // $5 per split

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 100_000, // Exactly enough for first child
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 3,
            min_split_amount: 30_000,
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Inject 200k transaction (will need to split)
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 10);
    let parent_id = tx.id().to_string();
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id);

    // Tick 0: Policy decides to split into 2 parts (100k each)
    orchestrator.tick().unwrap();

    let events_tick0 = orchestrator.event_log().events();

    // Verify split occurred
    let split_events: Vec<_> = events_tick0
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();
    assert_eq!(split_events.len(), 1);

    // Verify friction cost was charged
    let cost_events: Vec<_> = events_tick0
        .iter()
        .filter(|e| {
            matches!(e, Event::CostAccrual { agent_id, costs, .. }
                if agent_id == "BANK_A" && costs.split_friction_cost > 0)
        })
        .collect();
    assert_eq!(cost_events.len(), 1);

    if let Event::CostAccrual { costs, .. } = cost_events[0] {
        // 2 splits → (N-1) = 1 → cost = 500 × 1 = 500 cents
        assert_eq!(costs.split_friction_cost, 500);
    }

    // First child should settle (balance available)
    let settlement_events: Vec<_> = events_tick0
        .iter()
        .filter(|e| matches!(e, Event::Settlement { .. }))
        .collect();

    // At least one child should settle
    assert!(
        settlement_events.len() >= 1,
        "At least one child transaction should settle"
    );
}

#[test]
fn test_multiple_transactions_with_selective_splitting() {
    // Test that policy can handle multiple transactions, splitting some but not others

    let mut config = create_basic_config();
    config.cost_rates.split_friction_cost = 1000;

    config.agent_configs.push(AgentConfig {
        id: "BANK_A".to_string(),
        opening_balance: 150_000, // $1500
        credit_limit: 0,
        policy: PolicyConfig::LiquiditySplitting {
            max_splits: 4,
            min_split_amount: 20_000,
        },
        arrival_config: None,
                posted_collateral: None,    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Small transaction - should submit whole
    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 50_000, 0, 10);
    let tx1_id = tx1.id().to_string();

    // Large transaction - may need to split after first settles
    let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 200_000, 0, 15);
    let tx2_id = tx2.id().to_string();

    orchestrator.state_mut().add_transaction(tx1);
    orchestrator.state_mut().add_transaction(tx2);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1_id);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx2_id);

    orchestrator.tick().unwrap();

    let events = orchestrator.event_log().events();

    // Should have submitted small transaction whole
    let submit_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySubmit { .. }))
        .collect();

    let split_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, Event::PolicySplit { .. }))
        .collect();

    // Policy should make intelligent decisions based on available liquidity
    assert!(
        submit_events.len() + split_events.len() > 0,
        "Policy should process at least one transaction"
    );
}

// ============================================================================
// Helper Functions
// ============================================================================

fn create_basic_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            // BANK_B receives payments (always has enough balance)
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000, // $10,000
                credit_limit: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,            },
        ],
        cost_rates: CostRates {
            overdraft_bps_per_tick: 0.0001, // 1 bps per tick
            delay_cost_per_tick_per_cent: 0.00001,
            collateral_cost_per_tick_bps: 0.0002,
            eod_penalty_per_transaction: 10000, // $100
            deadline_penalty: 5000,              // $50 per missed deadline
            split_friction_cost: 0,              // Default to 0, tests override
        },
        lsm_config: LsmConfig {
            enable_bilateral: false, // Disable LSM for simpler tests
            enable_cycles: false,
            max_cycle_length: 4,
            max_cycles_per_tick: 10,
        },
    }
}
