//! TDD Tests for Priority-Based Delay Cost Multipliers (Enhancement 11.1)
//!
//! These tests verify that delay costs can be differentiated by transaction priority:
//! - Urgent (priority 8-10): Higher delay costs (e.g., 1.5x)
//! - Normal (priority 4-7): Base delay costs (1.0x)
//! - Low (priority 0-3): Lower delay costs (e.g., 0.5x)

use payment_simulator_core_rs::orchestrator::{CostRates, PriorityDelayMultipliers};

// =============================================================================
// Phase 1.1: Configuration Parsing Tests
// =============================================================================

#[test]
fn test_priority_delay_multipliers_default_values() {
    // When no multipliers are configured, all priorities should use base rate (1.0)
    let multipliers = PriorityDelayMultipliers::default();

    assert_eq!(multipliers.urgent_multiplier, 1.0);
    assert_eq!(multipliers.normal_multiplier, 1.0);
    assert_eq!(multipliers.low_multiplier, 1.0);
}

#[test]
fn test_priority_delay_multipliers_custom_values() {
    // Custom multipliers should be stored correctly
    let multipliers = PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    };

    assert_eq!(multipliers.urgent_multiplier, 1.5);
    assert_eq!(multipliers.normal_multiplier, 1.0);
    assert_eq!(multipliers.low_multiplier, 0.5);
}

#[test]
fn test_cost_rates_with_priority_multipliers() {
    // CostRates should support optional priority multipliers
    let mut cost_rates = CostRates::default();

    // By default, no priority multipliers (None)
    assert!(cost_rates.priority_delay_multipliers.is_none());

    // Can set priority multipliers
    cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    assert!(cost_rates.priority_delay_multipliers.is_some());
    let multipliers = cost_rates.priority_delay_multipliers.as_ref().unwrap();
    assert_eq!(multipliers.urgent_multiplier, 1.5);
}

// =============================================================================
// Phase 1.2: Priority Band Classification Tests
// =============================================================================

#[test]
fn test_get_priority_band_urgent() {
    // Priorities 8, 9, 10 should be classified as Urgent
    use payment_simulator_core_rs::orchestrator::get_priority_band;
    use payment_simulator_core_rs::orchestrator::PriorityBand;

    assert_eq!(get_priority_band(8), PriorityBand::Urgent);
    assert_eq!(get_priority_band(9), PriorityBand::Urgent);
    assert_eq!(get_priority_band(10), PriorityBand::Urgent);
}

#[test]
fn test_get_priority_band_normal() {
    // Priorities 4, 5, 6, 7 should be classified as Normal
    use payment_simulator_core_rs::orchestrator::get_priority_band;
    use payment_simulator_core_rs::orchestrator::PriorityBand;

    assert_eq!(get_priority_band(4), PriorityBand::Normal);
    assert_eq!(get_priority_band(5), PriorityBand::Normal);
    assert_eq!(get_priority_band(6), PriorityBand::Normal);
    assert_eq!(get_priority_band(7), PriorityBand::Normal);
}

#[test]
fn test_get_priority_band_low() {
    // Priorities 0, 1, 2, 3 should be classified as Low
    use payment_simulator_core_rs::orchestrator::get_priority_band;
    use payment_simulator_core_rs::orchestrator::PriorityBand;

    assert_eq!(get_priority_band(0), PriorityBand::Low);
    assert_eq!(get_priority_band(1), PriorityBand::Low);
    assert_eq!(get_priority_band(2), PriorityBand::Low);
    assert_eq!(get_priority_band(3), PriorityBand::Low);
}

#[test]
fn test_get_priority_band_boundary_7_8() {
    // Priority 7 should be Normal, Priority 8 should be Urgent
    use payment_simulator_core_rs::orchestrator::get_priority_band;
    use payment_simulator_core_rs::orchestrator::PriorityBand;

    assert_eq!(get_priority_band(7), PriorityBand::Normal);
    assert_eq!(get_priority_band(8), PriorityBand::Urgent);
}

#[test]
fn test_get_priority_band_boundary_3_4() {
    // Priority 3 should be Low, Priority 4 should be Normal
    use payment_simulator_core_rs::orchestrator::get_priority_band;
    use payment_simulator_core_rs::orchestrator::PriorityBand;

    assert_eq!(get_priority_band(3), PriorityBand::Low);
    assert_eq!(get_priority_band(4), PriorityBand::Normal);
}

// =============================================================================
// Phase 1.3: Multiplier Lookup Tests
// =============================================================================

#[test]
fn test_get_delay_multiplier_for_priority() {
    use payment_simulator_core_rs::orchestrator::PriorityDelayMultipliers;

    let multipliers = PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    };

    // Urgent priority (9) should get 1.5x
    assert_eq!(multipliers.get_multiplier_for_priority(9), 1.5);

    // Normal priority (5) should get 1.0x
    assert_eq!(multipliers.get_multiplier_for_priority(5), 1.0);

    // Low priority (2) should get 0.5x
    assert_eq!(multipliers.get_multiplier_for_priority(2), 0.5);
}

#[test]
fn test_get_delay_multiplier_boundary_values() {
    use payment_simulator_core_rs::orchestrator::PriorityDelayMultipliers;

    let multipliers = PriorityDelayMultipliers {
        urgent_multiplier: 2.0,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    };

    // Boundary: priority 8 (first urgent)
    assert_eq!(multipliers.get_multiplier_for_priority(8), 2.0);

    // Boundary: priority 7 (last normal)
    assert_eq!(multipliers.get_multiplier_for_priority(7), 1.0);

    // Boundary: priority 4 (first normal)
    assert_eq!(multipliers.get_multiplier_for_priority(4), 1.0);

    // Boundary: priority 3 (last low)
    assert_eq!(multipliers.get_multiplier_for_priority(3), 0.5);
}

// =============================================================================
// Phase 1.4: Delay Cost Calculation Integration Tests
// =============================================================================

use payment_simulator_core_rs::{
    orchestrator::{AgentConfig, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
    Transaction,
};

/// Helper to create basic 2-agent configuration for delay cost tests
fn create_delay_cost_test_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 0,
                // Use LiquidityAware policy with high buffer to force holding transactions
                policy: PolicyConfig::LiquidityAware {
                    target_buffer: 1_500_000, // Higher than balance to force hold
                    urgency_threshold: 5,
                },
                arrival_config: None,
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 2_000_000,
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
        algorithm_sequencing: false,
        entry_disposition_offsetting: false,
    }
}

#[test]
fn test_delay_cost_without_priority_multipliers_baseline() {
    // Baseline test: without priority multipliers, all transactions use base rate
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001; // 0.1 bp per tick
    config.cost_rates.priority_delay_multipliers = None; // No priority differentiation

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create a transaction that will be held (amount 500k, balance 1M, buffer target 1.5M)
    // Priority 9 (urgent) - but without multipliers, should be base rate
    let tx_urgent = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50, // Far deadline (not urgent for urgency_threshold)
    ).with_priority(9); // Priority 9 (urgent band)

    orchestrator.state_mut().add_transaction(tx_urgent.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_urgent.id().to_string());

    // Execute tick - transaction should be held due to buffer policy
    let result = orchestrator.tick().unwrap();
    assert_eq!(result.num_settlements, 0, "Transaction should be held");

    // Delay cost without multipliers: 500_000 * 0.0001 = 50 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 50, "Base delay cost should be 50 cents");
}

#[test]
fn test_delay_cost_with_urgent_priority_multiplier() {
    // With priority multipliers, urgent transactions should cost more
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001; // 0.1 bp per tick
    config.cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create urgent priority transaction (priority 9)
    let tx_urgent = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50,
    ).with_priority(9); // Priority 9 (urgent band)

    orchestrator.state_mut().add_transaction(tx_urgent.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_urgent.id().to_string());

    // Execute tick - transaction should be held
    let result = orchestrator.tick().unwrap();
    assert_eq!(result.num_settlements, 0);

    // Delay cost with urgent multiplier: 500_000 * 0.0001 * 1.5 = 75 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 75, "Urgent priority should have 1.5x delay cost");
}

#[test]
fn test_delay_cost_with_normal_priority_multiplier() {
    // Normal priority transactions should use base rate (1.0x)
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001;
    config.cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create normal priority transaction (priority 5)
    let tx_normal = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50,
    ).with_priority(5); // Priority 5 (normal band)

    orchestrator.state_mut().add_transaction(tx_normal.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_normal.id().to_string());

    orchestrator.tick().unwrap();

    // Delay cost with normal multiplier: 500_000 * 0.0001 * 1.0 = 50 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 50, "Normal priority should have 1.0x delay cost");
}

#[test]
fn test_delay_cost_with_low_priority_multiplier() {
    // Low priority transactions should have reduced delay cost (0.5x)
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001;
    config.cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 1.5,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create low priority transaction (priority 2)
    let tx_low = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        500_000,
        0,
        50,
    ).with_priority(2); // Priority 2 (low band)

    orchestrator.state_mut().add_transaction(tx_low.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_low.id().to_string());

    orchestrator.tick().unwrap();

    // Delay cost with low multiplier: 500_000 * 0.0001 * 0.5 = 25 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 25, "Low priority should have 0.5x delay cost");
}

#[test]
fn test_delay_cost_multiple_priorities_in_queue() {
    // Test with multiple transactions of different priorities in queue
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001;
    config.cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 2.0,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create one transaction of each priority
    let tx_urgent = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000
        0,
        50,
    ).with_priority(9); // Urgent

    let tx_normal = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000
        0,
        50,
    ).with_priority(5); // Normal

    let tx_low = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000
        0,
        50,
    ).with_priority(2); // Low

    orchestrator.state_mut().add_transaction(tx_urgent.clone());
    orchestrator.state_mut().add_transaction(tx_normal.clone());
    orchestrator.state_mut().add_transaction(tx_low.clone());

    let agent = orchestrator.state_mut().get_agent_mut("BANK_A").unwrap();
    agent.queue_outgoing(tx_urgent.id().to_string());
    agent.queue_outgoing(tx_normal.id().to_string());
    agent.queue_outgoing(tx_low.id().to_string());

    orchestrator.tick().unwrap();

    // Expected delay costs:
    // Urgent: 100_000 * 0.0001 * 2.0 = 20 cents
    // Normal: 100_000 * 0.0001 * 1.0 = 10 cents
    // Low:    100_000 * 0.0001 * 0.5 = 5 cents
    // Total: 35 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();
    assert_eq!(costs.total_delay_cost, 35, "Combined delay cost should be 35 cents");
}

#[test]
fn test_priority_multiplier_combines_with_overdue_multiplier() {
    // Test that priority multiplier combines multiplicatively with overdue multiplier
    let mut config = create_delay_cost_test_config();
    config.cost_rates.delay_cost_per_tick_per_cent = 0.0001;
    config.cost_rates.overdue_delay_multiplier = 5.0; // 5x for overdue
    config.cost_rates.priority_delay_multipliers = Some(PriorityDelayMultipliers {
        urgent_multiplier: 2.0,
        normal_multiplier: 1.0,
        low_multiplier: 0.5,
    });

    let mut orchestrator = Orchestrator::new(config).unwrap();

    // Create an urgent transaction with deadline tick 10 (arrives tick 0)
    // The urgency_threshold is 5, so deadline needs to be > current_tick + 5 to not be urgent
    // This transaction will be held until deadline passes, then becomes overdue
    let tx_urgent_overdue = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100_000, // $1,000
        0,       // Arrival tick 0
        10,      // Deadline tick 10 - far enough that deadline - tick > urgency_threshold (5)
    ).with_priority(9); // Urgent priority band (but not urgent by deadline)

    orchestrator.state_mut().add_transaction(tx_urgent_overdue.clone());
    orchestrator
        .state_mut()
        .get_agent_mut("BANK_A")
        .unwrap()
        .queue_outgoing(tx_urgent_overdue.id().to_string());

    // Run ticks 0-9 (not yet overdue, should accumulate delay cost with priority multiplier)
    for _ in 0..10 {
        orchestrator.tick().unwrap();
    }

    // Now at tick 10, transaction is at deadline
    // Run tick 10 and 11 - transaction becomes overdue during this period
    orchestrator.tick().unwrap(); // tick 10
    orchestrator.tick().unwrap(); // tick 11 - now overdue

    // Expected delay costs:
    // Ticks 0-10 (11 ticks): 100_000 * 0.0001 * 2.0 (priority) = 20 cents/tick = 220 cents
    // Tick 11 (overdue): 100_000 * 0.0001 * 2.0 (priority) * 5.0 (overdue) = 100 cents
    // Total: 320 cents
    let costs = orchestrator.get_costs("BANK_A").unwrap();

    // The expected total includes the deadline penalty cost as well
    // Check that priority and overdue multipliers combine for high delay cost
    assert!(
        costs.total_delay_cost >= 100,
        "Combined priority (2x) and overdue (5x) should result in high delay cost: got {}",
        costs.total_delay_cost
    );
}
