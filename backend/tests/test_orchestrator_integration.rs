//! Integration tests for Orchestrator tick loop
//!
//! These tests validate the complete simulation cycle from policy evaluation
//! through settlement and LSM coordination.

use payment_simulator_core_rs::{
    arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
    Transaction,
};
use std::collections::HashMap;

/// Helper function to create a basic 2-agent configuration
fn create_two_agent_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000, // $10,000
                unsecured_cap: 500_000,      // $5,000
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 2_000_000, // $20,000
                unsecured_cap: 0,
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 500_000, // $5,000 buffer
                    urgency_threshold: 5,   // 5 ticks before deadline
                },
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    }
}

#[test]
fn test_orchestrator_single_tick_no_transactions() {
    // Create orchestrator with no automatic arrivals
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Initial state
    assert_eq!(orchestrator.current_tick(), 0);
    assert_eq!(orchestrator.state().num_transactions(), 0);

    // Execute one tick
    let result = orchestrator.tick().unwrap();

    // Verify tick advanced
    assert_eq!(result.tick, 0); // Result shows tick 0
    assert_eq!(orchestrator.current_tick(), 1); // Now at tick 1
    assert_eq!(result.num_arrivals, 0);
    assert_eq!(result.num_settlements, 0);
    assert_eq!(result.num_lsm_releases, 0);
}

#[test]
fn test_orchestrator_manual_transaction_settlement() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Manually create and add a transaction
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000
        0,       // arrival tick
        10,      // deadline tick 10
    );
    let tx_id = tx.id().to_string();

    // Add transaction to state and to BANK_A's Queue 1
    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id.clone());

    // Verify initial state
    assert_eq!(orchestrator.state().num_transactions(), 1);
    assert_eq!(orchestrator.state().total_internal_queue_size(), 1);

    // Get initial balances
    let bank_a_initial = orchestrator.state().get_agent("BANK_A").unwrap().balance();
    let bank_b_initial = orchestrator.state().get_agent("BANK_B").unwrap().balance();

    // Execute tick - FIFO policy should submit immediately
    let result = orchestrator.tick().unwrap();

    // Verify transaction was processed
    assert_eq!(result.num_settlements, 1);
    assert_eq!(orchestrator.state().total_internal_queue_size(), 0);

    // Verify balances changed
    let bank_a_final = orchestrator.state().get_agent("BANK_A").unwrap().balance();
    let bank_b_final = orchestrator.state().get_agent("BANK_B").unwrap().balance();

    assert_eq!(bank_a_final, bank_a_initial - 100_000);
    assert_eq!(bank_b_final, bank_b_initial + 100_000);

    // Verify transaction is settled
    let tx = orchestrator.state().get_transaction(&tx_id).unwrap();
    assert!(tx.is_fully_settled());
}

#[test]
fn test_orchestrator_insufficient_liquidity_queues_to_rtgs() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Create transaction larger than BANK_A's balance + credit
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        2_000_000, // $20,000 (more than BANK_A's 1M balance + 500k credit)
        0,
        10,
    );
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_id.clone());

    // Execute tick
    let result = orchestrator.tick().unwrap();

    // Transaction should not settle, but should be queued to RTGS queue (Queue 2)
    assert_eq!(result.num_settlements, 0);

    // Transaction should be in RTGS queue
    assert_eq!(orchestrator.state().queue_size(), 1);

    // Transaction still pending
    let tx = orchestrator.state().get_transaction(&tx_id).unwrap();
    assert!(!tx.is_fully_settled());
}

#[test]
fn test_orchestrator_liquidity_aware_policy_holds_transaction() {
    // Create orchestrator with BANK_B using LiquidityAwarePolicy
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // BANK_B has 2M balance, 500k buffer target
    // Create transaction for 1.6M (would leave only 400k < 500k buffer)
    let tx = Transaction::new(
        "BANK_B".to_string(),
        "BANK_A".to_string(),
        1_600_000, // $16,000
        0,
        50, // Far deadline (not urgent)
    );
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx_id.clone());

    // Execute tick - LiquidityAwarePolicy should HOLD (not submit)
    let result = orchestrator.tick().unwrap();

    // No settlement should occur
    assert_eq!(result.num_settlements, 0);

    // Transaction should still be in Queue 1 (internal queue)
    assert_eq!(orchestrator.state().total_internal_queue_size(), 1);

    // Not in RTGS queue
    assert_eq!(orchestrator.state().queue_size(), 0);

    // Transaction still pending
    let tx = orchestrator.state().get_transaction(&tx_id).unwrap();
    assert!(!tx.is_fully_settled());
}

#[test]
fn test_orchestrator_liquidity_aware_policy_urgency_override() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // BANK_B has urgency_threshold = 5
    // Create transaction that would violate buffer, but with urgent deadline
    let tx = Transaction::new(
        "BANK_B".to_string(),
        "BANK_A".to_string(),
        1_600_000, // Would violate buffer
        0,
        4, // Urgent! Only 4 ticks to deadline (< 5 threshold)
    );
    let tx_id = tx.id().to_string();

    orchestrator.state_mut().add_transaction(tx);
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx_id.clone());

    // Execute tick - urgency should override liquidity concern
    let result = orchestrator.tick().unwrap();

    // Transaction should settle (urgency override)
    assert_eq!(result.num_settlements, 1);

    // Verify settlement occurred
    let tx = orchestrator.state().get_transaction(&tx_id).unwrap();
    assert!(tx.is_fully_settled());
}

#[test]
fn test_orchestrator_multi_tick_simulation() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Add several transactions
    for i in 0..5 {
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            50_000, // $500 each
            i,
            i + 20,
        );
        orchestrator.state_mut().add_transaction(tx.clone());
        orchestrator
            .state_mut()
            .get_agent_mut("BANK_A")
            .unwrap()
            .queue_outgoing(tx.id().to_string());
    }

    // Run 10 ticks
    let mut total_settlements = 0;
    for tick in 0..10 {
        let result = orchestrator.tick().unwrap();
        total_settlements += result.num_settlements;

        // Verify tick advances correctly
        assert_eq!(result.tick, tick);
        assert_eq!(orchestrator.current_tick(), tick + 1);
    }

    // All 5 transactions should have settled (FIFO submits immediately)
    assert_eq!(total_settlements, 5);

    // Verify all transactions settled
    for tx in orchestrator.state().transactions().values() {
        assert!(tx.is_fully_settled());
    }
}

#[test]
fn test_orchestrator_balance_conservation() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Get initial total balance
    let initial_total = orchestrator.state().total_balance();

    // Add transactions
    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
    let tx2 = Transaction::new("BANK_B".to_string(), "BANK_A".to_string(), 200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx1.clone());
    orchestrator.state_mut().add_transaction(tx2.clone());

    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1.id().to_string());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx2.id().to_string());

    // Run several ticks
    for _ in 0..5 {
        orchestrator.tick().unwrap();

        // Balance should be conserved after each tick
        let current_total = orchestrator.state().total_balance();
        assert_eq!(
            current_total, initial_total,
            "Balance conservation violated! Initial: {}, Current: {}",
            initial_total, current_total
        );
    }
}

#[test]
fn test_orchestrator_lsm_bilateral_offset() {
    // Create custom config with minimal balances and no credit to force LSM
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 100_000, // Only $1,000
                unsecured_cap: 0,          // No credit
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 100_000,   // Only $1,000
                unsecured_cap: 0,            // No credit
                policy: PolicyConfig::Fifo, // Use FIFO to ensure submission
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create bilateral offsetting transactions
    // A → B: 150k (exceeds A's 100k balance)
    // B → A: 150k (exceeds B's 100k balance)
    // Net effect: Both zero, so LSM can settle via bilateral offset

    let tx_a_to_b = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        150_000, // More than either agent has
        0,
        10,
    );
    let tx_b_to_a = Transaction::new(
        "BANK_B".to_string(),
        "BANK_A".to_string(),
        150_000, // More than either agent has
        0,
        10,
    );

    orchestrator.state_mut().add_transaction(tx_a_to_b.clone());
    orchestrator.state_mut().add_transaction(tx_b_to_a.clone());

    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_a_to_b.id().to_string());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx_b_to_a.id().to_string());

    // Execute tick
    let result = orchestrator.tick().unwrap();

    // Both transactions should fail initial settlement (insufficient liquidity)
    // But LSM should detect bilateral offset and settle both
    assert!(
        result.num_lsm_releases > 0,
        "LSM should have released transactions"
    );

    // Verify both transactions settled
    let tx_a_to_b_status = orchestrator
        .state()
        .get_transaction(tx_a_to_b.id())
        .unwrap();
    let tx_b_to_a_status = orchestrator
        .state()
        .get_transaction(tx_b_to_a.id())
        .unwrap();
    assert!(tx_a_to_b_status.is_fully_settled(), "A→B should be settled");
    assert!(tx_b_to_a_status.is_fully_settled(), "B→A should be settled");

    // Verify balances unchanged (net-zero bilateral offset)
    assert_eq!(
        orchestrator.state().get_agent("BANK_A").unwrap().balance(),
        100_000
    );
    assert_eq!(
        orchestrator.state().get_agent("BANK_B").unwrap().balance(),
        100_000
    );
}

#[test]
fn test_orchestrator_peak_net_debit_tracking() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // BANK_A starts with 1M balance, 500k credit limit
    // Send transaction that uses credit
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        1_200_000, // Uses 200k of credit
        0,
        10,
    );

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute tick
    orchestrator.tick().unwrap();

    // Check peak net debit was tracked
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(
        costs.peak_net_debit, -200_000,
        "Peak net debit should be tracked"
    );
}

#[test]
fn test_orchestrator_event_counting() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Initial event count
    let initial_events = orchestrator.event_count();

    // Add transaction
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute tick
    orchestrator.tick().unwrap();

    // Event count should have increased
    // At minimum: 1 policy decision + 1 settlement
    let final_events = orchestrator.event_count();
    assert!(
        final_events > initial_events,
        "Event count should increase. Initial: {}, Final: {}",
        initial_events,
        final_events
    );
}

#[test]
fn test_orchestrator_multiple_agents_concurrent_transactions() {
    // Create orchestrator
    let mut orchestrator = Orchestrator::new(create_two_agent_config()).unwrap();

    // Both agents send transactions simultaneously
    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
    let tx2 = Transaction::new("BANK_B".to_string(), "BANK_A".to_string(), 200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx1.clone());
    orchestrator.state_mut().add_transaction(tx2.clone());

    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1.id().to_string());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx2.id().to_string());

    // Get initial balances
    let a_initial = orchestrator.state().get_agent("BANK_A").unwrap().balance();
    let b_initial = orchestrator.state().get_agent("BANK_B").unwrap().balance();

    // Execute tick
    let result = orchestrator.tick().unwrap();

    // Both should settle
    assert_eq!(result.num_settlements, 2);

    // Verify net effect on balances
    let a_final = orchestrator.state().get_agent("BANK_A").unwrap().balance();
    let b_final = orchestrator.state().get_agent("BANK_B").unwrap().balance();

    // BANK_A: -100k + 200k = +100k
    assert_eq!(a_final, a_initial + 100_000);
    // BANK_B: +100k - 200k = -100k
    assert_eq!(b_final, b_initial - 100_000);
}

// ============================================================================
// Arrival Generation Tests
// ============================================================================

#[test]
fn test_orchestrator_automatic_arrivals() {
    // Create configuration with automatic arrivals
    let arrival_config = ArrivalConfig {
        rate_per_tick: 2.0, // Expected 2 arrivals per tick
        amount_distribution: AmountDistribution::Uniform {
            min: 50_000,
            max: 150_000,
        },
        counterparty_weights: HashMap::new(), // Uniform selection
        deadline_range: (5, 15),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 10_000_000, // $100k
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config.clone()),
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 10_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Execute one tick
    let result = orchestrator.tick().unwrap();

    // Should have generated arrivals
    assert!(result.num_arrivals > 0, "Expected automatic arrivals");

    // Verify arrivals were processed (some may settle immediately if liquidity permits)
    assert!(
        result.num_arrivals >= result.num_settlements,
        "Arrivals count should be >= settlements count"
    );
}

#[test]
fn test_orchestrator_arrival_determinism() {
    // Same configuration for two orchestrators
    let arrival_config = ArrivalConfig {
        rate_per_tick: 3.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 10_000,
            max: 100_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 20),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 99999, // Same seed
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 5_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config.clone()),
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 5_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None, // No arrivals for BANK_B
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    // Run two simulations with same seed
    let mut orch1 = Orchestrator::new(config.clone()).unwrap();
    let mut orch2 = Orchestrator::new(config).unwrap();

    // Execute 5 ticks on each
    let mut results1 = Vec::new();
    let mut results2 = Vec::new();

    for _ in 0..5 {
        results1.push(orch1.tick().unwrap());
        results2.push(orch2.tick().unwrap());
    }

    // Arrival counts should match
    for (r1, r2) in results1.iter().zip(results2.iter()) {
        assert_eq!(
            r1.num_arrivals, r2.num_arrivals,
            "Arrival counts should be deterministic"
        );
    }
}

#[test]
fn test_orchestrator_weighted_counterparty_arrivals() {
    // Create config with weighted counterparty selection
    let mut weights = HashMap::new();
    weights.insert("BANK_B".to_string(), 10.0); // High weight
    weights.insert("BANK_C".to_string(), 1.0); // Low weight

    let arrival_config = ArrivalConfig {
        rate_per_tick: 20.0, // Many arrivals to test distribution
        amount_distribution: AmountDistribution::Uniform {
            min: 10_000,
            max: 50_000,
        },
        counterparty_weights: weights,
        deadline_range: (5, 15),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 50_000_000, // Large balance to avoid queuing issues
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 50_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_C".to_string(),
                opening_balance: 50_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    let initial_b_balance = 50_000_000;
    let initial_c_balance = 50_000_000;

    // Run multiple ticks to accumulate transactions
    let mut total_arrivals = 0;
    for _ in 0..5 {
        let result = orchestrator.tick().unwrap();
        total_arrivals += result.num_arrivals;
    }

    // Check balance changes (higher balance = more received)
    let agent_b = orchestrator.state().get_agent("BANK_B").unwrap();
    let agent_c = orchestrator.state().get_agent("BANK_C").unwrap();

    let b_received = agent_b.balance() - initial_b_balance;
    let c_received = agent_c.balance() - initial_c_balance;

    // BANK_B should have received significantly more value due to 10:1 weight ratio
    // This is probabilistic but should hold with many arrivals
    assert!(total_arrivals > 0, "Should have generated arrivals");
    assert!(
        b_received > c_received,
        "BANK_B should receive more value than BANK_C. B: {}, C: {}",
        b_received,
        c_received
    );
}

#[test]
fn test_orchestrator_no_arrivals_when_not_configured() {
    // Config without any arrival configurations
    let config = create_two_agent_config(); // Default config has no arrivals

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Execute tick
    let result = orchestrator.tick().unwrap();

    // Should have no arrivals
    assert_eq!(result.num_arrivals, 0, "Should have no automatic arrivals");
}

#[test]
fn test_orchestrator_arrivals_respect_amount_distribution() {
    let arrival_config = ArrivalConfig {
        rate_per_tick: 10.0,
        amount_distribution: AmountDistribution::Uniform {
            min: 100_000,
            max: 200_000,
        },
        counterparty_weights: HashMap::new(),
        deadline_range: (5, 15),
        priority_distribution: PriorityDistribution::Fixed { value: 0 },
        divisible: false,
    };

    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 100_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(arrival_config),
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 100_000_000,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Execute tick
    orchestrator.tick().unwrap();

    // Check all generated transaction amounts are in range
    let queue = orchestrator
        .state()
        .get_agent("BANK_A")
        .unwrap()
        .outgoing_queue();

    for tx_id in queue {
        if let Some(tx) = orchestrator.state().get_transaction(tx_id) {
            assert!(
                tx.amount() >= 100_000 && tx.amount() <= 200_000,
                "Transaction amount {} should be in range [100000, 200000]",
                tx.amount()
            );
        }
    }
}
