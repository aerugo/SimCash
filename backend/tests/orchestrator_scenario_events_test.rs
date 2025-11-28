//! Integration tests for scenario events with Orchestrator
//!
//! Tests full integration of scenario events into the simulation loop.
//! Following TDD: these tests define the expected behavior.

use payment_simulator_core_rs::{
    events::{EventSchedule, ScenarioEvent, ScheduledEvent},
    orchestrator::{AgentConfig, CostRates, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    Orchestrator,
};
use payment_simulator_core_rs::arrivals::{AmountDistribution, ArrivalConfig, PriorityDistribution};
use payment_simulator_core_rs::settlement::lsm::LsmConfig;
use std::collections::HashMap;

// ============================================================================
// Helper Functions
// ============================================================================

fn create_basic_config_with_events(events: Vec<ScheduledEvent>) -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: None,  // Disable arrivals for scenario event tests
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: None,  // Disable arrivals for scenario event tests
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
        scenario_events: Some(events),
    }
}

fn create_config_with_arrivals_and_events(events: Vec<ScheduledEvent>) -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 12345,
        agent_configs: vec![
            AgentConfig {
                id: "BANK_A".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 50_000,
                    },
                    counterparty_weights: HashMap::new(),
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 0 },
                    divisible: false,
                }),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "BANK_B".to_string(),
                opening_balance: 1_000_000,
                unsecured_cap: 500_000,
                policy: PolicyConfig::Fifo,
                arrival_config: Some(ArrivalConfig {
                    rate_per_tick: 0.5,
                    amount_distribution: AmountDistribution::Uniform {
                        min: 10_000,
                        max: 50_000,
                    },
                    counterparty_weights: HashMap::new(),
                    deadline_range: (10, 50),
                    priority_distribution: PriorityDistribution::Fixed { value: 0 },
                    divisible: false,
                }),
                posted_collateral: None,
                collateral_haircut: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
        scenario_events: Some(events),
    }
}

// ============================================================================
// Direct Transfer Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_direct_transfer_event() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "BANK_A".to_string(),
            to_agent: "BANK_B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_basic_config_with_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Get initial balances
    let initial_a = orch.get_agent_balance("BANK_A").unwrap();
    let initial_b = orch.get_agent_balance("BANK_B").unwrap();

    // Run through tick 10 (need 11 calls: ticks 0-10)
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Check balances changed
    let final_a = orch.get_agent_balance("BANK_A").unwrap();
    let final_b = orch.get_agent_balance("BANK_B").unwrap();

    assert_eq!(final_a, initial_a - 100_000);
    assert_eq!(final_b, initial_b + 100_000);
}

#[test]
fn test_orchestrator_repeating_direct_transfer() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "BANK_A".to_string(),
            to_agent: "BANK_B".to_string(),
            amount: 50_000,
        },
        schedule: EventSchedule::Repeating {
            start_tick: 10,
            interval: 10,
        },
    }];

    let config = create_basic_config_with_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    let initial_a = orch.get_agent_balance("BANK_A").unwrap();
    let initial_b = orch.get_agent_balance("BANK_B").unwrap();

    // Run through tick 30 (need 31 calls) - should trigger at ticks 10, 20, 30
    for _ in 0..31 {
        orch.tick().expect("Tick failed");
    }

    let final_a = orch.get_agent_balance("BANK_A").unwrap();
    let final_b = orch.get_agent_balance("BANK_B").unwrap();

    // Should have transferred 3 times
    assert_eq!(final_a, initial_a - 150_000);
    assert_eq!(final_b, initial_b + 150_000);
}

// ============================================================================
// Collateral Adjustment Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_collateral_adjustment() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::CollateralAdjustment {
            agent: "BANK_A".to_string(),
            delta: 200_000,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_basic_config_with_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    let initial_limit = orch.get_agent_unsecured_cap("BANK_A").unwrap();

    // Run through tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    let final_limit = orch.get_agent_unsecured_cap("BANK_A").unwrap();

    assert_eq!(final_limit, initial_limit + 200_000);
}

// ============================================================================
// Arrival Rate Change Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_global_arrival_rate_change() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::GlobalArrivalRateChange { multiplier: 2.0 },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_config_with_arrivals_and_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Get initial rates
    let initial_rate_a = orch.get_arrival_rate("BANK_A").expect("Rate not found");
    let initial_rate_b = orch.get_arrival_rate("BANK_B").expect("Rate not found");

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Check rates doubled
    let final_rate_a = orch.get_arrival_rate("BANK_A").expect("Rate not found");
    let final_rate_b = orch.get_arrival_rate("BANK_B").expect("Rate not found");

    assert!((final_rate_a - initial_rate_a * 2.0).abs() < 0.001);
    assert!((final_rate_b - initial_rate_b * 2.0).abs() < 0.001);
}

#[test]
fn test_orchestrator_agent_arrival_rate_change() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::AgentArrivalRateChange {
            agent: "BANK_A".to_string(),
            multiplier: 1.5,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_config_with_arrivals_and_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    let initial_rate_a = orch.get_arrival_rate("BANK_A").expect("Rate not found");
    let initial_rate_b = orch.get_arrival_rate("BANK_B").expect("Rate not found");

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    let final_rate_a = orch.get_arrival_rate("BANK_A").expect("Rate not found");
    let final_rate_b = orch.get_arrival_rate("BANK_B").expect("Rate not found");

    // Only BANK_A should change
    assert!((final_rate_a - initial_rate_a * 1.5).abs() < 0.001);
    assert!((final_rate_b - initial_rate_b).abs() < 0.001);
}

// ============================================================================
// Counterparty Weight Change Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_counterparty_weight_change() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::CounterpartyWeightChange {
            agent: "BANK_A".to_string(),
            counterparty: "BANK_B".to_string(),
            new_weight: 0.8,
            auto_balance_others: false,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_config_with_arrivals_and_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Check weight was updated
    let weight = orch
        .get_counterparty_weight("BANK_A", "BANK_B")
        .expect("Weight not found");
    assert!((weight - 0.8).abs() < 0.001);
}

// ============================================================================
// Deadline Window Change Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_deadline_window_change() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DeadlineWindowChange {
            min_ticks_multiplier: Some(0.5),
            max_ticks_multiplier: Some(0.5),
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_config_with_arrivals_and_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Get initial deadline range (should be (10, 50) from config)
    let (_initial_min, _initial_max) = orch.get_deadline_range("BANK_A").expect("Range not found");

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Check deadline range was halved
    let (final_min, final_max) = orch.get_deadline_range("BANK_A").expect("Range not found");

    assert_eq!(final_min, 5); // 10 * 0.5
    assert_eq!(final_max, 25); // 50 * 0.5
}

// ============================================================================
// Multiple Events Integration Tests
// ============================================================================

#[test]
fn test_orchestrator_multiple_events_same_tick() {
    let events = vec![
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "BANK_A".to_string(),
                to_agent: "BANK_B".to_string(),
                amount: 100_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
        ScheduledEvent {
            event: ScenarioEvent::CollateralAdjustment {
                agent: "BANK_A".to_string(),
                delta: 300_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
    ];

    let config = create_basic_config_with_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    let initial_balance_a = orch.get_agent_balance("BANK_A").unwrap();
    let initial_balance_b = orch.get_agent_balance("BANK_B").unwrap();
    let initial_credit_a = orch.get_agent_unsecured_cap("BANK_A").unwrap();

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Both events should have executed
    assert_eq!(
        orch.get_agent_balance("BANK_A").unwrap(),
        initial_balance_a - 100_000
    );
    assert_eq!(
        orch.get_agent_balance("BANK_B").unwrap(),
        initial_balance_b + 100_000
    );
    assert_eq!(
        orch.get_agent_unsecured_cap("BANK_A").unwrap(),
        initial_credit_a + 300_000
    );
}

// ============================================================================
// Event Logging Tests
// ============================================================================

#[test]
fn test_scenario_events_are_logged() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "BANK_A".to_string(),
            to_agent: "BANK_B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let config = create_basic_config_with_events(events);
    let mut orch = Orchestrator::new(config).expect("Failed to create orchestrator");

    // Run to tick 10
    for _ in 0..11 {
        orch.tick().expect("Tick failed");
    }

    // Check that scenario event was logged
    let tick_events = orch.get_tick_events(10);
    let scenario_events: Vec<_> = tick_events
        .iter()
        .filter(|e| e.event_type() == "ScenarioEventExecuted")
        .collect();

    assert!(!scenario_events.is_empty(), "Scenario event should be logged");
}

// ============================================================================
// Determinism Tests
// ============================================================================

#[test]
fn test_scenario_events_are_deterministic() {
    let events = vec![
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "BANK_A".to_string(),
                to_agent: "BANK_B".to_string(),
                amount: 100_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
        ScheduledEvent {
            event: ScenarioEvent::GlobalArrivalRateChange { multiplier: 1.5 },
            schedule: EventSchedule::OneTime { tick: 20 },
        },
    ];

    let config1 = create_config_with_arrivals_and_events(events.clone());
    let config2 = create_config_with_arrivals_and_events(events);

    let mut orch1 = Orchestrator::new(config1).expect("Failed to create orchestrator 1");
    let mut orch2 = Orchestrator::new(config2).expect("Failed to create orchestrator 2");

    // Run both for 30 ticks
    for _ in 0..30 {
        orch1.tick().expect("Tick 1 failed");
        orch2.tick().expect("Tick 2 failed");
    }

    // States should be identical
    assert_eq!(
        orch1.get_agent_balance("BANK_A").unwrap(),
        orch2.get_agent_balance("BANK_A").unwrap()
    );
    assert_eq!(
        orch1.get_agent_balance("BANK_B").unwrap(),
        orch2.get_agent_balance("BANK_B").unwrap()
    );
    assert_eq!(
        orch1.get_arrival_rate("BANK_A").unwrap(),
        orch2.get_arrival_rate("BANK_A").unwrap()
    );
}
