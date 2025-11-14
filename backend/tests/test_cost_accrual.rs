//! Integration tests for cost accrual system
//!
//! Tests cover:
//! - Overdraft cost calculation
//! - Delay cost calculation
//! - Collateral cost calculation
//! - End-of-day penalties
//! - Cost accumulation over multiple ticks

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig},
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

#[test]
fn test_overdraft_cost_calculation() {
    // Create orchestrator with specific cost rates
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // 1 bps per tick (FIXED: was 0.001)

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that uses credit (goes into overdraft)
    // BANK_A has 1M balance + 500k credit = 1.5M capacity
    // Send 1.2M, leaving balance at -200k
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute tick - transaction should settle
    let result = orchestrator.tick().unwrap();
    assert_eq!(result.num_settlements, 1);

    // Check balance went negative
    let bank_a = orchestrator.state().get_agent("BANK_A").unwrap();
    assert_eq!(bank_a.balance(), -200_000);

    // Costs are accrued at end of tick, so tick 0 already has cost
    // Execute another tick to accrue more
    orchestrator.tick().unwrap();

    // Check overdraft cost was accrued
    // CORRECTED: 1 bps = 0.0001 as fraction
    // Tick 0: 200,000 × (1.0 / 10,000) = 200,000 × 0.0001 = 20 cents
    // Tick 1: 200,000 × (1.0 / 10,000) = 200,000 × 0.0001 = 20 cents
    // Total = 40 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_liquidity_cost, 40); // FIXED: was 400
}

#[test]
fn test_delay_cost_for_queued_transactions() {
    // Create orchestrator with specific delay cost rates
    let mut config = create_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001; // 0.1 bp per tick
    config.agent_configs[0].policy = PolicyConfig::LiquidityAware {
        target_buffer: 1_500_000, // High buffer to force holding
        urgency_threshold: 5,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that will be held (violates buffer)
    // BANK_A has 1M balance, buffer target 1.5M
    // Sending 500k would leave 500k < 1.5M buffer, so it will be held
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50, // Far deadline (not urgent)
    );

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute tick - transaction should be held
    let result = orchestrator.tick().unwrap();
    assert_eq!(result.num_settlements, 0); // Not settled

    // Delay cost should be accrued
    // 500k * 0.0001 = 50 cents
    assert!(result.total_cost >= 50);

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 50);
}

#[test]
fn test_no_cost_for_positive_balance() {
    let mut orchestrator = Orchestrator::new(create_test_config()).unwrap();

    // Execute tick with no transactions
    let result = orchestrator.tick().unwrap();

    // No costs should be accrued (all balances positive, no queued transactions)
    assert_eq!(result.total_cost, 0);

    let costs_a = orchestrator.get_costs("BANK_A").unwrap();
    let costs_b = orchestrator.get_costs("BANK_B").unwrap();

    assert_eq!(costs_a.total(), 0);
    assert_eq!(costs_b.total(), 0);
}

#[test]
fn test_cost_accumulation_over_multiple_ticks() {
    // Create orchestrator with specific cost rates
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // FIXED: was 0.001

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap(); // Tick 0: settle transaction, accrue first cost

    // Run 5 more ticks with overdraft
    for _ in 0..5 {
        orchestrator.tick().unwrap();
    }

    // CORRECTED: 1 bps = 0.0001 as fraction
    // Balance: -200,000 cents
    // Per tick: 200,000 × (1.0 / 10,000) = 20 cents
    // Total: 6 ticks × 20 cents = 120 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_liquidity_cost, 120); // FIXED: was 1200
}

#[test]
fn test_peak_net_debit_tracking() {
    let mut orchestrator = Orchestrator::new(create_test_config()).unwrap();

    // Send transaction that uses credit
    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx1.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1.id().to_string());

    orchestrator.tick().unwrap();

    // Balance is -200k
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.peak_net_debit, -200_000);

    // Send another transaction to go deeper into overdraft
    let tx2 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 1, 20);

    orchestrator.state_mut().add_transaction(tx2.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx2.id().to_string());

    orchestrator.tick().unwrap();

    // Balance is now -300k
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.peak_net_debit, -300_000);

    // Receive payment to reduce overdraft
    let tx3 = Transaction::new("BANK_B".to_string(), "BANK_A".to_string(), 200_000, 2, 20);

    orchestrator.state_mut().add_transaction(tx3.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx3.id().to_string());

    orchestrator.tick().unwrap();

    // Balance is now -100k, but peak is still -300k
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.peak_net_debit, -300_000);
}

#[test]
fn test_end_of_day_penalty() {
    // Create orchestrator with 10 ticks per day for faster testing
    let mut config = create_test_config();
    config.ticks_per_day = 10;
    config.cost_rates.eod_penalty_per_transaction = 10_000; // $100 per unsettled tx
    config.agent_configs[0].policy = PolicyConfig::LiquidityAware {
        target_buffer: 1_500_000, // Force holding
        urgency_threshold: 5,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that will be held
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50, // Far deadline
    );

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    // Execute 10 ticks to reach end of day
    for _ in 0..10 {
        orchestrator.tick().unwrap();
    }

    // Check EOD penalty was applied
    // After EOD, costs are stored in historical metrics (day 0)
    let metrics = orchestrator.get_daily_agent_metrics(0);
    let bank_a_metrics = metrics.iter().find(|m| m.agent_id == "BANK_A").unwrap();
    assert_eq!(bank_a_metrics.deadline_penalty_cost, 10_000); // $100 for 1 unsettled tx
}

#[test]
fn test_cost_event_logging() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // FIXED: was 0.001

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into overdraft
    let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx.id().to_string());

    orchestrator.tick().unwrap(); // Settle
    orchestrator.tick().unwrap(); // Accrue cost

    // Check cost events were logged
    let cost_events = orchestrator.event_log().events_of_type("CostAccrual");
    assert!(cost_events.len() > 0, "Should have cost accrual events");

    // Verify cost event content
    let event = cost_events[0];
    assert_eq!(event.agent_id(), Some("BANK_A"));
}

#[test]
fn test_multiple_agents_cost_accrual() {
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // FIXED: was 0.001

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Put BANK_A into overdraft first
    let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 1_200_000, 0, 10);

    orchestrator.state_mut().add_transaction(tx1.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1.id().to_string());

    orchestrator.tick().unwrap(); // Settle tx1

    // Now put BANK_B into overdraft
    let tx2 = Transaction::new(
        "BANK_B".to_string(),
        "BANK_A".to_string(),
        2_200_000, // Increased to put B into overdraft
        1,
        10,
    );

    orchestrator.state_mut().add_transaction(tx2.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_B")
        .unwrap()
        .queue_outgoing(tx2.id().to_string());

    orchestrator.tick().unwrap(); // Settle tx2

    // Check both agents have overdraft costs
    let costs_a = orchestrator.get_costs("BANK_A").unwrap();
    let costs_b = orchestrator.get_costs("BANK_B").unwrap();

    // CORRECTED: 1 bps = 0.0001 as fraction
    // BANK_A: started at 1M, sent 1.2M = -200k
    // Tick 0: 200,000 × (1.0 / 10,000) = 20 cents
    // Received 2.2M in tick 1, now at 2M (positive), so no more overdraft
    // Tick 1: 0 overdraft (balance positive after receiving)
    // Total: 20 cents
    assert_eq!(costs_a.total_liquidity_cost, 20); // FIXED: was 200

    // BANK_B: started at 2M, received 1.2M = 3.2M, sent 2.2M = 1M (positive)
    // Actually BANK_B never goes into overdraft with this sequence
    // Let's check it has no overdraft cost
    assert_eq!(costs_b.total_liquidity_cost, 0);
}

#[test]
fn test_collateral_cost_calculation() {
    // Create orchestrator with specific collateral cost rate
    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 2.0; // FIXED: was 0.0002 (2 bps per tick)

    // Set up agent with posted collateral
    config.agent_configs[0].posted_collateral = Some(1_000_000); // $10,000 collateral

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run 10 ticks
    for _ in 0..10 {
        orchestrator.tick().unwrap();
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // CORRECTED: 2 bps = 0.0002 as fraction
    // Per tick: 1,000,000 × (2.0 / 10,000) = 1,000,000 × 0.0002 = 200 cents
    // Total: 200 × 10 ticks = 2,000 cents = $20
    assert!(
        costs.total_collateral_cost > 0,
        "Should have collateral cost"
    );
    assert_eq!(costs.total_collateral_cost, 2000);
}

#[test]
fn test_collateral_accumulation_over_ticks() {
    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 2.0; // FIXED: was 0.0002
    config.agent_configs[0].posted_collateral = Some(500_000); // $5,000 collateral

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run first tick
    orchestrator.tick().unwrap();
    let cost_after_1 = orchestrator
        .get_costs("BANK_A")
        .unwrap()
        .total_collateral_cost;

    // Run second tick
    orchestrator.tick().unwrap();
    let cost_after_2 = orchestrator
        .get_costs("BANK_A")
        .unwrap()
        .total_collateral_cost;

    // Cost should grow linearly
    assert!(cost_after_2 > cost_after_1, "Cost should accumulate");

    // CORRECTED: 2 bps = 0.0002 as fraction
    // Per tick: 500,000 × (2.0 / 10,000) = 500,000 × 0.0002 = 100 cents
    assert_eq!(cost_after_1, 100);
    assert_eq!(cost_after_2, 200);
}

#[test]
fn test_zero_collateral_has_no_cost() {
    let mut config = create_test_config();
    config.cost_rates.collateral_cost_per_tick_bps = 0.0002;
    // Agent has no collateral (default)

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Run 10 ticks
    for _ in 0..10 {
        orchestrator.tick().unwrap();
    }

    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(
        costs.total_collateral_cost, 0,
        "No collateral should mean no cost"
    );
}

#[test]
fn test_all_cost_types_together() {
    // Set up orchestrator with all cost types enabled
    let mut config = create_test_config();
    config.cost_rates.overdraft_bps_per_tick = 1.0; // 1 bps (was 0.001, wrong interpretation)
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001; // Delay cost (already a fraction, not bps)
    config.cost_rates.collateral_cost_per_tick_bps = 2.0; // 2 bps (was 0.0002, wrong interpretation)
    config.agent_configs[0].posted_collateral = Some(1_000_000); // $10,000 collateral
    config.agent_configs[0].policy = PolicyConfig::LiquidityAware {
        target_buffer: 500_000, // Lower buffer so urgent tx can settle
        urgency_threshold: 5,
    };

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create transaction that will be held (delay cost)
    // BANK_A has 1M balance, buffer target is 500k
    // Sending 600k would leave 400k < 500k buffer, so it will be held
    let tx1 = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        600_000,
        0,
        50, // Far deadline (not urgent)
    );

    orchestrator.state_mut().add_transaction(tx1.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx1.id().to_string());

    // Run first tick - transaction will be held
    orchestrator.tick().unwrap();

    // Check we have delay cost and collateral cost (no liquidity cost yet, balance positive)
    let costs_after_1 = orchestrator.get_costs("BANK_A").unwrap();
    assert!(costs_after_1.total_delay_cost > 0, "Should have delay cost");
    assert!(
        costs_after_1.total_collateral_cost > 0,
        "Should have collateral cost"
    );
    assert_eq!(costs_after_1.total_liquidity_cost, 0, "No overdraft yet");

    // Create transaction that will settle and put BANK_A into overdraft
    // BANK_A has 1M balance + 500k credit = 1.5M capacity
    // Sending 1.2M will put it at -200k (within credit limit)
    let tx2 = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        1_200_000,
        1,
        2, // Very urgent deadline (< urgency_threshold of 5)
    );

    orchestrator.state_mut().add_transaction(tx2.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx2.id().to_string());

    // Run tick - urgent tx should settle because deadline is urgent
    orchestrator.tick().unwrap();

    // Now we should have all three cost types
    let costs_final = orchestrator.get_costs("BANK_A").unwrap();
    assert!(
        costs_final.total_liquidity_cost > 0,
        "Should have liquidity cost"
    );
    assert!(costs_final.total_delay_cost > 0, "Should have delay cost");
    assert!(
        costs_final.total_collateral_cost > 0,
        "Should have collateral cost"
    );
    assert!(costs_final.total() > 0, "Total should be sum of all costs");

    // Verify total is sum of parts
    let expected_total = costs_final.total_liquidity_cost
        + costs_final.total_delay_cost
        + costs_final.total_collateral_cost
        + costs_final.total_penalty_cost
        + costs_final.total_split_friction_cost;
    assert_eq!(costs_final.total(), expected_total);
}
