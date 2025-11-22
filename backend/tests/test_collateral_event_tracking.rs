//! Collateral Event Tracking Tests
//!
//! Tests for comprehensive collateral event tracking system.
//! Following TDD: These tests validate the collateral event tracking implementation.

use payment_simulator_core_rs::{
    models::{CollateralAction, CollateralLayer},
    orchestrator::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering},
    settlement::lsm::LsmConfig,
};

/// Helper function to create a basic configuration for testing
fn create_test_config() -> OrchestratorConfig {
    OrchestratorConfig {
        ticks_per_day: 10,
        eod_rush_threshold: 0.8,        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 50_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Fifo,
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    }
}

#[test]
fn test_collateral_event_types_exist() {
    // Verify all types compile and exist
    let _ = CollateralAction::Post;
    let _ = CollateralAction::Withdraw;
    let _ = CollateralAction::Hold;

    let _ = CollateralLayer::Strategic;
    let _ = CollateralLayer::EndOfTick;
}

#[test]
fn test_get_collateral_events_for_day_method_exists() {
    // Verify the method exists and can be called
    let config = create_test_config();
    let orch = Orchestrator::new(config).unwrap();

    // Should return empty vec initially (no collateral events yet)
    let events = orch.get_collateral_events_for_day(0);
    assert_eq!(events.len(), 0, "Should have no events initially");
}

#[test]
fn test_collateral_events_filter_by_day() {
    // Create config with multiple days
    let config = OrchestratorConfig {
        ticks_per_day: 10,
        eod_rush_threshold: 0.8,        num_days: 3,
        rng_seed: 42,
        agent_configs: vec![AgentConfig {
            id: "BANK_A".to_string(),
            opening_balance: 50_000,
            unsecured_cap: 0,
            policy: PolicyConfig::Fifo,
            arrival_config: None,
            posted_collateral: None,
                    collateral_haircut: None,
                limits: None,
        }],
        cost_rates: CostRates::default(),
        lsm_config: LsmConfig::default(),
            scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
    };

    let mut orch = Orchestrator::new(config).unwrap();

    // Run multiple days of simulation
    for _ in 0..30 {
        orch.tick().unwrap();
    }

    // Get events for each day
    let day0_events = orch.get_collateral_events_for_day(0);
    let day1_events = orch.get_collateral_events_for_day(1);
    let day2_events = orch.get_collateral_events_for_day(2);

    // Verify events are properly filtered by day
    for event in &day0_events {
        assert_eq!(event.day, 0, "Day 0 events should have day=0");
    }

    for event in &day1_events {
        assert_eq!(event.day, 1, "Day 1 events should have day=1");
    }

    for event in &day2_events {
        assert_eq!(event.day, 2, "Day 2 events should have day=2");
    }
}

#[test]
fn test_collateral_event_has_all_required_fields() {
    // This test just verifies the struct has all the expected fields
    // We create a config and run it, and if any collateral events are created,
    // we verify they have all fields accessible

    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    // Run some ticks
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    let events = orch.get_collateral_events_for_day(0);

    // If events were created, verify all fields exist
    for event in &events {
        let _ = &event.agent_id;
        let _ = event.tick;
        let _ = event.day;
        let _ = &event.action;
        let _ = event.amount;
        let _ = &event.reason;
        let _ = &event.layer;
        let _ = event.balance_before;
        let _ = event.posted_collateral_before;
        let _ = event.posted_collateral_after;
        let _ = event.available_capacity_after;
    }

    // Test passes if no panic (fields exist)
}

#[test]
fn test_events_persist_across_ticks() {
    let config = create_test_config();
    let mut orch = Orchestrator::new(config).unwrap();

    // Run some ticks
    for _ in 0..5 {
        orch.tick().unwrap();
    }

    let events_at_5 = orch.get_collateral_events_for_day(0).len();

    // Run more ticks
    for _ in 0..5 {
        orch.tick().unwrap();
    }

    let events_at_10 = orch.get_collateral_events_for_day(0).len();

    // Events should persist and potentially accumulate
    // (or stay the same if no new collateral events)
    assert!(
        events_at_10 >= events_at_5,
        "Events should persist and accumulate"
    );
}

#[test]
fn test_collateral_event_action_variants() {
    // Verify all action variants exist and can be compared
    let post = CollateralAction::Post;
    let withdraw = CollateralAction::Withdraw;
    let hold = CollateralAction::Hold;

    assert!(matches!(post, CollateralAction::Post));
    assert!(matches!(withdraw, CollateralAction::Withdraw));
    assert!(matches!(hold, CollateralAction::Hold));
}

#[test]
fn test_collateral_event_layer_variants() {
    // Verify all layer variants exist and can be compared
    let strategic = CollateralLayer::Strategic;
    let end_of_tick = CollateralLayer::EndOfTick;

    assert!(matches!(strategic, CollateralLayer::Strategic));
    assert!(matches!(end_of_tick, CollateralLayer::EndOfTick));
}
