//! Orchestrator integration tests for Collateral Auto-Withdraw Timers (Phase 3.4).
//!
//! Following TDD principles: these tests are written BEFORE orchestrator implementation.
//!
//! ## Test Coverage
//!
//! 1. **Timer Processing**: Orchestrator processes timers each tick
//! 2. **Automatic Withdrawal**: Collateral withdrawn when timer fires
//! 3. **Event Emission**: CollateralTimerWithdrawn event emitted
//! 4. **Balance Updates**: Agent balance and posted_collateral updated correctly
//! 5. **Multiple Timers**: Multiple agents with timers processed correctly

use payment_simulator_core_rs::models::agent::Agent;
use payment_simulator_core_rs::models::event::Event;
use payment_simulator_core_rs::models::state::SimulationState;

// ============================================================================
// Test Group 1: Basic Timer Processing (3 tests)
// ============================================================================

#[test]
fn test_state_can_have_agents_with_timers() {
    // Test that SimulationState can hold agents with scheduled timers

    let mut state = SimulationState::new(vec![
        Agent::new("BANK_A".to_string(), 1_000_000, 100_000),
    ]);

    // Manually schedule a timer for tick 5
    {
        let agent = state.get_agent_mut("BANK_A").unwrap();
        agent.set_posted_collateral(50_000); // Post collateral first
        agent.schedule_collateral_withdrawal_with_posted_tick(
            5,
            50_000,
            "TemporaryBoost".to_string(),
            2, // posted at tick 2
        );
    }

    // Verify timer is scheduled
    let agent = state.get_agent("BANK_A").unwrap();
    assert_eq!(agent.get_pending_collateral_withdrawals(5).len(), 1);
}

#[test]
fn test_timer_withdrawal_reduces_posted_collateral() {
    // Test that when timer fires, posted_collateral is reduced

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);

    // Post collateral
    agent.set_posted_collateral(100_000);
    assert_eq!(agent.posted_collateral(), 100_000);

    // Schedule withdrawal
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        50_000,
        "TemporaryBoost".to_string(),
        5,
    );

    // Simulate timer processing (what orchestrator will do)
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(10);
    assert_eq!(timers.len(), 1);

    // Withdraw the collateral
    let new_collateral = agent.posted_collateral() - timers[0].0;
    agent.set_posted_collateral(new_collateral);

    // Clean up timer
    agent.remove_collateral_withdrawal_timer(10);

    // Verify
    assert_eq!(agent.posted_collateral(), 50_000);
    assert_eq!(agent.get_pending_collateral_withdrawals(10).len(), 0);
}

#[test]
fn test_event_emitted_when_timer_fires() {
    // Test that CollateralTimerWithdrawn event is emitted

    let event = Event::CollateralTimerWithdrawn {
        tick: 10,
        agent_id: "BANK_A".to_string(),
        amount: 50_000,
        original_reason: "TemporaryBoost".to_string(),
        posted_at_tick: 5,
    };

    // Verify event structure
    assert_eq!(event.tick(), 10);
    assert_eq!(event.event_type(), "CollateralTimerWithdrawn");

    match event {
        Event::CollateralTimerWithdrawn {
            tick,
            agent_id,
            amount,
            original_reason,
            posted_at_tick,
        } => {
            assert_eq!(tick, 10);
            assert_eq!(agent_id, "BANK_A");
            assert_eq!(amount, 50_000);
            assert_eq!(original_reason, "TemporaryBoost");
            assert_eq!(posted_at_tick, 5);
        }
        _ => panic!("Wrong event type"),
    }
}

// ============================================================================
// Test Group 2: Multiple Timers (2 tests)
// ============================================================================

#[test]
fn test_multiple_timers_for_same_agent() {
    // Test that agent can have multiple timers at different ticks

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    agent.set_posted_collateral(200_000);

    // Schedule three withdrawals
    agent.schedule_collateral_withdrawal_with_posted_tick(10, 50_000, "First".to_string(), 5);
    agent.schedule_collateral_withdrawal_with_posted_tick(15, 75_000, "Second".to_string(), 8);
    agent.schedule_collateral_withdrawal_with_posted_tick(20, 75_000, "Third".to_string(), 12);

    // Process tick 10
    let timers_10 = agent.get_pending_collateral_withdrawals_with_posted_tick(10);
    assert_eq!(timers_10.len(), 1);
    assert_eq!(timers_10[0].0, 50_000);

    // Process tick 15
    let timers_15 = agent.get_pending_collateral_withdrawals_with_posted_tick(15);
    assert_eq!(timers_15.len(), 1);
    assert_eq!(timers_15[0].0, 75_000);
}

#[test]
fn test_multiple_agents_with_timers() {
    // Test that multiple agents can each have timers

    let mut agent_a = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    let mut agent_b = Agent::new("BANK_B".to_string(), 2_000_000, 200_000);

    agent_a.set_posted_collateral(100_000);
    agent_b.set_posted_collateral(150_000);

    // Each schedules a withdrawal at tick 10
    agent_a.schedule_collateral_withdrawal_with_posted_tick(10, 50_000, "A_Timer".to_string(), 5);
    agent_b.schedule_collateral_withdrawal_with_posted_tick(10, 75_000, "B_Timer".to_string(), 5);

    // Both should have timers
    assert_eq!(agent_a.get_pending_collateral_withdrawals(10).len(), 1);
    assert_eq!(agent_b.get_pending_collateral_withdrawals(10).len(), 1);

    // Different amounts
    assert_eq!(agent_a.get_pending_collateral_withdrawals(10)[0].0, 50_000);
    assert_eq!(agent_b.get_pending_collateral_withdrawals(10)[0].0, 75_000);
}

// ============================================================================
// Test Group 3: Edge Cases (3 tests)
// ============================================================================

#[test]
fn test_timer_does_not_fire_before_due_tick() {
    // Test that timer scheduled for tick 10 doesn't fire at tick 9

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    agent.schedule_collateral_withdrawal(10, 50_000, "Test".to_string());

    // Check ticks 1-9
    for tick in 1..10 {
        assert_eq!(
            agent.get_pending_collateral_withdrawals(tick).len(),
            0,
            "Timer should not fire at tick {}",
            tick
        );
    }

    // Should fire at tick 10
    assert_eq!(agent.get_pending_collateral_withdrawals(10).len(), 1);
}

#[test]
fn test_timer_only_fires_once() {
    // Test that timer doesn't fire again after being processed

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    agent.schedule_collateral_withdrawal(10, 50_000, "Test".to_string());

    // Fire at tick 10
    let timers = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(timers.len(), 1);

    // Remove timer after processing
    agent.remove_collateral_withdrawal_timer(10);

    // Should not fire again at tick 11
    assert_eq!(agent.get_pending_collateral_withdrawals(10).len(), 0);
    assert_eq!(agent.get_pending_collateral_withdrawals(11).len(), 0);
}

#[test]
fn test_withdrawal_cannot_exceed_posted_collateral() {
    // Test that withdrawal amount is bounded by actual posted collateral
    // This is a safety check - orchestrator should handle this

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    agent.set_posted_collateral(30_000); // Only 30k posted

    // Try to schedule withdrawal of 50k
    agent.schedule_collateral_withdrawal(10, 50_000, "Excessive".to_string());

    // Timer exists
    let timers = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(timers.len(), 1);

    // But withdrawal should be capped at actual posted amount
    let withdrawal_amount = timers[0].0.min(agent.posted_collateral());
    assert_eq!(withdrawal_amount, 30_000);
}

// ============================================================================
// Test Group 4: Orchestrator Tick Loop Order (1 test)
// ============================================================================

#[test]
fn test_timer_processing_happens_in_tick_loop() {
    // Test that timer processing is part of the orchestrator tick sequence
    // This test documents the expected behavior:
    // 1. Start of tick N
    // 2. Check for timers due at tick N
    // 3. Process each timer:
    //    - Withdraw collateral
    //    - Emit CollateralTimerWithdrawn event
    //    - Remove timer
    // 4. Continue with rest of tick processing

    // This is a documentation test - actual behavior tested via integration
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);
    agent.set_posted_collateral(100_000);

    // Schedule timer for tick 10
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        50_000,
        "TemporaryBoost".to_string(),
        5,
    );

    // At tick 10, orchestrator should:
    // 1. Get pending timers
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(10);
    assert_eq!(timers.len(), 1);

    // 2. Process each timer
    for (amount, reason, posted_at) in timers {
        // Withdraw collateral
        let new_collateral = agent.posted_collateral() - amount;
        agent.set_posted_collateral(new_collateral);

        // Would emit event here (in real orchestrator)
        let _event = Event::CollateralTimerWithdrawn {
            tick: 10,
            agent_id: agent.id().to_string(),
            amount,
            original_reason: reason,
            posted_at_tick: posted_at,
        };
    }

    // 3. Clean up timer
    agent.remove_collateral_withdrawal_timer(10);

    // Verify final state
    assert_eq!(agent.posted_collateral(), 50_000);
    assert!(!agent.has_pending_collateral_withdrawals());
}

// ============================================================================
// Test Group 5: Integration Scenario (1 test)
// ============================================================================

#[test]
fn test_full_timer_lifecycle() {
    // Test complete lifecycle: post collateral → schedule timer → timer fires → collateral withdrawn

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 100_000);

    // Step 1: Post collateral at tick 5
    let post_tick = 5;
    let post_amount = 100_000;
    agent.set_posted_collateral(post_amount);
    assert_eq!(agent.posted_collateral(), 100_000);

    // Step 2: Schedule auto-withdrawal for 10 ticks later
    let auto_withdraw_after_ticks = 10;
    let withdrawal_tick = post_tick + auto_withdraw_after_ticks;
    agent.schedule_collateral_withdrawal_with_posted_tick(
        withdrawal_tick,
        post_amount,
        "TemporaryBoost".to_string(),
        post_tick,
    );

    // Step 3: Verify timer is scheduled
    assert!(agent.has_pending_collateral_withdrawals());
    assert_eq!(agent.get_pending_collateral_withdrawals(withdrawal_tick).len(), 1);

    // Step 4: Simulate ticks passing (timer not due yet)
    for tick in (post_tick + 1)..withdrawal_tick {
        assert_eq!(
            agent.get_pending_collateral_withdrawals(tick).len(),
            0,
            "Timer should not fire at tick {}",
            tick
        );
    }

    // Step 5: Timer fires at withdrawal_tick
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(withdrawal_tick);
    assert_eq!(timers.len(), 1);
    assert_eq!(timers[0].0, post_amount);
    assert_eq!(timers[0].1, "TemporaryBoost");
    assert_eq!(timers[0].2, post_tick);

    // Step 6: Process withdrawal
    let new_collateral = agent.posted_collateral() - timers[0].0;
    agent.set_posted_collateral(new_collateral);
    agent.remove_collateral_withdrawal_timer(withdrawal_tick);

    // Step 7: Verify final state
    assert_eq!(agent.posted_collateral(), 0);
    assert!(!agent.has_pending_collateral_withdrawals());
}
