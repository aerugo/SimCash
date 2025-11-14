//! Tests for Phase 4.5: State Register Actions (SetState, AddState)
//!
//! Tests policy tree actions that manipulate state registers for micro-memory.
//! Following TDD principles: write tests BEFORE implementation.

use payment_simulator_core_rs::models::agent::Agent;
use payment_simulator_core_rs::models::event::Event;
use payment_simulator_core_rs::models::state::SimulationState;

// ============================================================================
// Test Group 1: SetState Basic Functionality
// ============================================================================

#[test]
fn test_agent_can_store_state_registers() {
    // Verify Agent can hold state registers (already implemented)
    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    agent.set_state_register("bank_state_cooldown".to_string(), 42.0).unwrap();
    assert_eq!(agent.get_state_register("bank_state_cooldown"), 42.0);
}

#[test]
fn test_state_can_emit_state_register_set_event() {
    // Test that we can create StateRegisterSet events
    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 100_000, 50_000),
    ]);

    // Manually create event (as orchestrator will do)
    state.log_event(Event::StateRegisterSet {
        tick: 5,
        agent_id: "BANK_A".to_string(),
        register_key: "bank_state_cooldown".to_string(),
        old_value: 0.0,
        new_value: 42.0,
        reason: "policy_action".to_string(),
        decision_path: None,
    });

    let events = state.event_log().events();
    assert_eq!(events.len(), 1);

    match &events[0] {
        Event::StateRegisterSet {
            agent_id,
            register_key,
            old_value,
            new_value,
            ..
        } => {
            assert_eq!(agent_id, "BANK_A");
            assert_eq!(register_key, "bank_state_cooldown");
            assert_eq!(*old_value, 0.0);
            assert_eq!(*new_value, 42.0);
        }
        _ => panic!("Expected StateRegisterSet event"),
    }
}

#[test]
fn test_set_state_workflow() {
    // Test the full workflow of setting a state register and emitting event
    // This simulates what the policy interpreter will do

    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 100_000, 50_000),
    ]);

    let tick = 10;
    let agent_id = "BANK_A";
    let key = "bank_state_last_action_tick".to_string();
    let value = 10.0;

    // Step 1: Set register (as policy action will do)
    let (old_value, new_value) = {
        let agent = state.get_agent_mut(agent_id).unwrap();
        agent.set_state_register(key.clone(), value).unwrap()
    };

    // Step 2: Emit event (as orchestrator will do)
    state.log_event(Event::StateRegisterSet {
        tick,
        agent_id: agent_id.to_string(),
        register_key: key.clone(),
        old_value,
        new_value,
        reason: "policy_action".to_string(),
        decision_path: None,
    });

    // Verify: Register is set
    let agent = state.get_agent(agent_id).unwrap();
    assert_eq!(agent.get_state_register(&key), 10.0);

    // Verify: Event was logged
    assert_eq!(state.event_log().events().len(), 1);
}

// ============================================================================
// Test Group 2: AddState (Increment) Functionality
// ============================================================================

#[test]
fn test_add_state_workflow() {
    // Test incrementing a state register (AddState action)

    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 100_000, 50_000),
    ]);

    let key = "bank_state_counter".to_string();

    // First increment: 0 + 1 = 1
    {
        let agent = state.get_agent_mut("BANK_A").unwrap();
        let current = agent.get_state_register(&key);
        let new_value = current + 1.0;
        let (old, _new) = agent.set_state_register(key.clone(), new_value).unwrap();

        assert_eq!(old, 0.0);
        assert_eq!(new_value, 1.0);
    }

    // Second increment: 1 + 1 = 2
    {
        let agent = state.get_agent_mut("BANK_A").unwrap();
        let current = agent.get_state_register(&key);
        let new_value = current + 1.0;
        let (old, _new) = agent.set_state_register(key.clone(), new_value).unwrap();

        assert_eq!(old, 1.0);
        assert_eq!(new_value, 2.0);
    }

    // Verify final value
    let agent = state.get_agent("BANK_A").unwrap();
    assert_eq!(agent.get_state_register(&key), 2.0);
}

#[test]
fn test_state_registers_persist_across_multiple_sets() {
    // Test that state registers maintain value across multiple updates

    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    // Set initial value
    agent.set_state_register("bank_state_tick_count".to_string(), 1.0).unwrap();

    // Update multiple times
    for _ in 2..=5 {
        let current = agent.get_state_register("bank_state_tick_count");
        agent.set_state_register("bank_state_tick_count".to_string(), current + 1.0).unwrap();
    }

    // Should be 5 now
    assert_eq!(agent.get_state_register("bank_state_tick_count"), 5.0);
}

// ============================================================================
// Test Group 3: Multiple Registers
// ============================================================================

#[test]
fn test_multiple_registers_can_coexist() {
    // Test that multiple registers work independently

    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    agent.set_state_register("bank_state_cooldown".to_string(), 5.0).unwrap();
    agent.set_state_register("bank_state_counter".to_string(), 10.0).unwrap();
    agent.set_state_register("bank_state_last_tick".to_string(), 42.0).unwrap();

    assert_eq!(agent.get_state_register("bank_state_cooldown"), 5.0);
    assert_eq!(agent.get_state_register("bank_state_counter"), 10.0);
    assert_eq!(agent.get_state_register("bank_state_last_tick"), 42.0);
}

#[test]
fn test_registers_independent_across_agents() {
    // Test that different agents have independent registers

    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 100_000, 50_000),
        Agent::new("BANK_B".to_string(), 200_000, 75_000),
    ]);

    // Set different values for each agent
    {
        let agent_a = state.get_agent_mut("BANK_A").unwrap();
        agent_a.set_state_register("bank_state_value".to_string(), 100.0).unwrap();
    }
    {
        let agent_b = state.get_agent_mut("BANK_B").unwrap();
        agent_b.set_state_register("bank_state_value".to_string(), 200.0).unwrap();
    }

    // Verify independence
    assert_eq!(state.get_agent("BANK_A").unwrap().get_state_register("bank_state_value"), 100.0);
    assert_eq!(state.get_agent("BANK_B").unwrap().get_state_register("bank_state_value"), 200.0);
}

// ============================================================================
// Test Group 4: Event Properties
// ============================================================================

#[test]
fn test_state_register_event_has_correct_tick() {
    // Verify events store the tick number correctly

    let event = Event::StateRegisterSet {
        tick: 25,
        agent_id: "BANK_A".to_string(),
        register_key: "bank_state_foo".to_string(),
        old_value: 1.0,
        new_value: 2.0,
        reason: "test".to_string(),
        decision_path: None,
    };

    assert_eq!(event.tick(), 25);
}

#[test]
fn test_state_register_event_has_correct_type() {
    // Verify event_type() returns correct string

    let event = Event::StateRegisterSet {
        tick: 10,
        agent_id: "BANK_A".to_string(),
        register_key: "bank_state_bar".to_string(),
        old_value: 0.0,
        new_value: 5.0,
        reason: "test".to_string(),
        decision_path: None,
    };

    assert_eq!(event.event_type(), "StateRegisterSet");
}

// ============================================================================
// Test Group 5: Edge Cases
// ============================================================================

#[test]
fn test_state_register_with_zero_value() {
    // Test that zero is a valid value (not confused with default)

    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    // Set to 5, then explicitly set to 0
    agent.set_state_register("bank_state_flag".to_string(), 5.0).unwrap();
    agent.set_state_register("bank_state_flag".to_string(), 0.0).unwrap();

    assert_eq!(agent.get_state_register("bank_state_flag"), 0.0);
}

#[test]
fn test_state_register_with_negative_value() {
    // Test that negative values work (useful for deltas)

    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    agent.set_state_register("bank_state_delta".to_string(), -10.5).unwrap();

    assert_eq!(agent.get_state_register("bank_state_delta"), -10.5);
}

#[test]
fn test_state_register_with_large_value() {
    // Test that large values work

    let mut agent = Agent::new("BANK_A".to_string(), 100_000, 50_000);

    let large_value = 1_000_000_000.123456;
    agent.set_state_register("bank_state_large".to_string(), large_value).unwrap();

    assert_eq!(agent.get_state_register("bank_state_large"), large_value);
}
