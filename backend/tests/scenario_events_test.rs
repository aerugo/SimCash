//! Tests for scenario events feature
//!
//! Tests the event scheduler, event handlers, and integration with simulation.
//!
//! Following TDD principles: tests written BEFORE implementation.

use payment_simulator_core_rs::{
    events::{EventSchedule, ScenarioEvent, ScenarioEventHandler, ScheduledEvent},
    Agent, SimulationState,
};

// ============================================================================
// Event Scheduler Tests
// ============================================================================

#[test]
fn test_event_scheduler_one_time_event() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "A".to_string(),
            to_agent: "B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let handler = ScenarioEventHandler::new(events);

    // Should return event at tick 10
    let events_at_10 = handler.get_events_for_tick(10);
    assert_eq!(events_at_10.len(), 1);

    // Should return nothing at other ticks
    assert_eq!(handler.get_events_for_tick(9).len(), 0);
    assert_eq!(handler.get_events_for_tick(11).len(), 0);
}

#[test]
fn test_event_scheduler_repeating_event() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "A".to_string(),
            to_agent: "B".to_string(),
            amount: 100_000,
        },
        schedule: EventSchedule::Repeating {
            start_tick: 10,
            interval: 5,
        },
    }];

    let handler = ScenarioEventHandler::new(events);

    // Should trigger at start_tick
    assert_eq!(handler.get_events_for_tick(10).len(), 1);
    // And at intervals
    assert_eq!(handler.get_events_for_tick(15).len(), 1);
    assert_eq!(handler.get_events_for_tick(20).len(), 1);
    assert_eq!(handler.get_events_for_tick(25).len(), 1);
    // But not in between
    assert_eq!(handler.get_events_for_tick(12).len(), 0);
    assert_eq!(handler.get_events_for_tick(14).len(), 0);
}

#[test]
fn test_event_scheduler_multiple_events_same_tick() {
    let events = vec![
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "A".to_string(),
                to_agent: "B".to_string(),
                amount: 100_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
        ScheduledEvent {
            event: ScenarioEvent::CollateralAdjustment {
                agent: "A".to_string(),
                delta: 50_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
    ];

    let handler = ScenarioEventHandler::new(events);

    let events_at_10 = handler.get_events_for_tick(10);
    assert_eq!(events_at_10.len(), 2);
}

#[test]
fn test_event_scheduler_mixed_one_time_and_repeating() {
    let events = vec![
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "A".to_string(),
                to_agent: "B".to_string(),
                amount: 100_000,
            },
            schedule: EventSchedule::OneTime { tick: 5 },
        },
        ScheduledEvent {
            event: ScenarioEvent::CollateralAdjustment {
                agent: "A".to_string(),
                delta: 50_000,
            },
            schedule: EventSchedule::Repeating {
                start_tick: 10,
                interval: 10,
            },
        },
    ];

    let handler = ScenarioEventHandler::new(events);

    // tick 5: one-time event
    assert_eq!(handler.get_events_for_tick(5).len(), 1);

    // tick 10: repeating event first occurrence
    assert_eq!(handler.get_events_for_tick(10).len(), 1);

    // tick 20: repeating event second occurrence
    assert_eq!(handler.get_events_for_tick(20).len(), 1);

    // tick 15: nothing
    assert_eq!(handler.get_events_for_tick(15).len(), 0);
}

// ============================================================================
// Direct Transfer Event Tests
// ============================================================================

#[test]
fn test_direct_transfer_execution() {
    let agent_a = Agent::new("A".to_string(), 100_000, 0);
    let agent_b = Agent::new("B".to_string(), 50_000, 0);
    let mut state = SimulationState::new(vec![agent_a, agent_b]);

    let event = ScenarioEvent::DirectTransfer {
        from_agent: "A".to_string(),
        to_agent: "B".to_string(),
        amount: 30_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_ok());

    // Check balances changed
    assert_eq!(state.get_agent("A").unwrap().balance(), 70_000);
    assert_eq!(state.get_agent("B").unwrap().balance(), 80_000);

    // Check event was logged
    let events = state.event_log().events_at_tick(10);
    let scenario_events: Vec<_> = events
        .iter()
        .filter(|e| e.event_type() == "ScenarioEventExecuted")
        .collect();
    assert_eq!(scenario_events.len(), 1);
}

#[test]
fn test_direct_transfer_invalid_sender() {
    let agent_a = Agent::new("A".to_string(), 100_000, 0);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::DirectTransfer {
        from_agent: "X".to_string(), // Non-existent agent
        to_agent: "A".to_string(),
        amount: 30_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("Agent not found: X"));
}

#[test]
fn test_direct_transfer_invalid_receiver() {
    let agent_a = Agent::new("A".to_string(), 100_000, 0);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::DirectTransfer {
        from_agent: "A".to_string(),
        to_agent: "Y".to_string(), // Non-existent agent
        amount: 30_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("Agent not found: Y"));
}

#[test]
fn test_direct_transfer_can_go_negative() {
    // Scenario events should bypass liquidity checks
    // (simulating external liquidity injection/withdrawal)
    let agent_a = Agent::new("A".to_string(), 10_000, 0);
    let agent_b = Agent::new("B".to_string(), 50_000, 0);
    let mut state = SimulationState::new(vec![agent_a, agent_b]);

    let event = ScenarioEvent::DirectTransfer {
        from_agent: "A".to_string(),
        to_agent: "B".to_string(),
        amount: 30_000, // More than A has!
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_ok());

    // A should go negative
    assert_eq!(state.get_agent("A").unwrap().balance(), -20_000);
    assert_eq!(state.get_agent("B").unwrap().balance(), 80_000);
}

// ============================================================================
// Collateral Adjustment Event Tests
// ============================================================================

#[test]
fn test_collateral_adjustment_positive() {
    let agent_a = Agent::new("A".to_string(), 100_000, 0);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::CollateralAdjustment {
        agent: "A".to_string(),
        delta: 50_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_ok());

    assert_eq!(state.get_agent("A").unwrap().credit_limit(), 50_000);
}

#[test]
fn test_collateral_adjustment_negative() {
    let agent_a = Agent::new("A".to_string(), 100_000, 100_000);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::CollateralAdjustment {
        agent: "A".to_string(),
        delta: -30_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_ok());

    assert_eq!(state.get_agent("A").unwrap().credit_limit(), 70_000);
}

#[test]
fn test_collateral_adjustment_cannot_go_negative() {
    let agent_a = Agent::new("A".to_string(), 100_000, 50_000);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::CollateralAdjustment {
        agent: "A".to_string(),
        delta: -80_000, // More than current credit limit
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("Credit limit cannot go negative"));
}

#[test]
fn test_collateral_adjustment_invalid_agent() {
    let agent_a = Agent::new("A".to_string(), 100_000, 0);
    let mut state = SimulationState::new(vec![agent_a]);

    let event = ScenarioEvent::CollateralAdjustment {
        agent: "X".to_string(),
        delta: 50_000,
    };

    let result = event.execute(&mut state, 10);
    assert!(result.is_err());
}

// ============================================================================
// Integration Tests
// ============================================================================

#[test]
fn test_scenario_event_handler_full_integration() {
    // Create a realistic scenario with multiple event types
    let events = vec![
        // Payroll at tick 33
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "CORPORATE_BANK".to_string(),
                to_agent: "CONSUMER_BANK".to_string(),
                amount: 20_000_000,
            },
            schedule: EventSchedule::OneTime { tick: 33 },
        },
        // Collateral expansion at tick 55
        ScheduledEvent {
            event: ScenarioEvent::CollateralAdjustment {
                agent: "BANK_C".to_string(),
                delta: 33_000_000,
            },
            schedule: EventSchedule::OneTime { tick: 55 },
        },
    ];

    let handler = ScenarioEventHandler::new(events);

    // Verify scheduling
    assert_eq!(handler.get_events_for_tick(33).len(), 1);
    assert_eq!(handler.get_events_for_tick(55).len(), 1);
}

#[test]
fn test_scenario_events_are_deterministic() {
    // Same events executed twice should produce identical state
    let events = vec![
        ScheduledEvent {
            event: ScenarioEvent::DirectTransfer {
                from_agent: "A".to_string(),
                to_agent: "B".to_string(),
                amount: 100_000,
            },
            schedule: EventSchedule::OneTime { tick: 10 },
        },
        ScheduledEvent {
            event: ScenarioEvent::CollateralAdjustment {
                agent: "A".to_string(),
                delta: 50_000,
            },
            schedule: EventSchedule::OneTime { tick: 20 },
        },
    ];

    // Run 1
    let agent_a = Agent::new("A".to_string(), 1_000_000, 100_000);
    let agent_b = Agent::new("B".to_string(), 500_000, 0);
    let mut state1 = SimulationState::new(vec![agent_a.clone(), agent_b.clone()]);

    for event in &events {
        if let EventSchedule::OneTime { tick } = event.schedule {
            event.event.execute(&mut state1, tick).unwrap();
        }
    }

    // Run 2
    let mut state2 = SimulationState::new(vec![agent_a, agent_b]);

    for event in &events {
        if let EventSchedule::OneTime { tick } = event.schedule {
            event.event.execute(&mut state2, tick).unwrap();
        }
    }

    // States should be identical
    assert_eq!(
        state1.get_agent("A").unwrap().balance(),
        state2.get_agent("A").unwrap().balance()
    );
    assert_eq!(
        state1.get_agent("B").unwrap().balance(),
        state2.get_agent("B").unwrap().balance()
    );
    assert_eq!(
        state1.get_agent("A").unwrap().credit_limit(),
        state2.get_agent("A").unwrap().credit_limit()
    );
}
