//! Integration tests for Collateral Auto-Withdraw Timers (Phase 3.4: Policy Enhancements V2).
//!
//! Following TDD principles: these tests are written BEFORE implementation.
//!
//! ## Test Coverage
//!
//! 1. **Timer Scheduling**: Agent can schedule auto-withdrawal at future tick
//! 2. **Timer Retrieval**: Get pending withdrawals for specific tick
//! 3. **Timer Removal**: Clear timers after processing
//! 4. **Multiple Timers**: Multiple withdrawals can be scheduled for same tick
//! 5. **Timer Persistence**: Timers persist across ticks until due
//! 6. **Event Structure**: CollateralTimerWithdrawn has correct fields

use payment_simulator_core_rs::models::agent::Agent;
use payment_simulator_core_rs::models::event::Event;

// ============================================================================
// Test Group 1: Timer Scheduling (3 tests)
// ============================================================================

#[test]
fn test_agent_can_schedule_collateral_withdrawal() {
    // Test that Agent can store a timer for auto-withdrawal
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    // Schedule withdrawal for tick 15
    agent.schedule_collateral_withdrawal_with_posted_tick(
        15,
        50_000,
        "TemporaryBoost".to_string(),
        5, // posted_at_tick
    );

    // Verify timer is stored
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(15);
    assert_eq!(timers.len(), 1);
    assert_eq!(timers[0].0, 50_000);
    assert_eq!(timers[0].1, "TemporaryBoost");
    assert_eq!(timers[0].2, 5); // posted_at_tick
}

#[test]
fn test_agent_returns_due_withdrawals_only_for_current_tick() {
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    // Schedule multiple withdrawals at different ticks
    agent.schedule_collateral_withdrawal(10, 10_000, "Early".to_string());
    agent.schedule_collateral_withdrawal(15, 20_000, "Middle".to_string());
    agent.schedule_collateral_withdrawal(20, 30_000, "Late".to_string());

    // At tick 10, only first should be due
    let due_at_10 = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(due_at_10.len(), 1);
    assert_eq!(due_at_10[0].0, 10_000);

    // At tick 14, nothing should be due
    let due_at_14 = agent.get_pending_collateral_withdrawals(14);
    assert_eq!(due_at_14.len(), 0);
}

#[test]
fn test_agent_removes_processed_timers() {
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    agent.schedule_collateral_withdrawal(10, 10_000, "Test".to_string());

    // Get and consume the timer
    let due = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(due.len(), 1);

    // Remove it
    agent.remove_collateral_withdrawal_timer(10);

    // Should no longer be present
    let due_again = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(due_again.len(), 0);
}

// ============================================================================
// Test Group 2: Event Structure (1 test)
// ============================================================================

#[test]
fn test_collateral_timer_withdrawn_event_structure() {
    // Test that CollateralTimerWithdrawn event has correct fields
    let event = Event::CollateralTimerWithdrawn {
        tick: 15,
        agent_id: "BANK_A".to_string(),
        amount: 50_000,
        original_reason: "TemporaryBoost".to_string(),
        posted_at_tick: 5,
    };

    assert_eq!(event.tick(), 15);
    assert_eq!(event.event_type(), "CollateralTimerWithdrawn");
}

// ============================================================================
// Test Group 3: Timer Edge Cases (7 tests)
// ============================================================================

#[test]
fn test_timer_calculates_correct_withdrawal_tick() {
    // Test: If posted at tick 10 with auto_withdraw_after_ticks=5, should withdraw at tick 15
    let current_tick = 10;
    let auto_withdraw_after_ticks = 5;
    let withdrawal_tick = current_tick + auto_withdraw_after_ticks;

    assert_eq!(withdrawal_tick, 15);

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    agent.schedule_collateral_withdrawal(withdrawal_tick, 100_000, "Test".to_string());

    // Should not be due at tick 14
    assert_eq!(agent.get_pending_collateral_withdrawals(14).len(), 0);

    // Should be due at tick 15
    assert_eq!(agent.get_pending_collateral_withdrawals(15).len(), 1);

    // Clean up
    agent.remove_collateral_withdrawal_timer(15);
    assert_eq!(agent.get_pending_collateral_withdrawals(16).len(), 0);
}

#[test]
fn test_multiple_timers_at_same_tick() {
    // Test that multiple withdrawals can be scheduled for the same tick
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    agent.schedule_collateral_withdrawal(10, 10_000, "First".to_string());
    agent.schedule_collateral_withdrawal(10, 20_000, "Second".to_string());
    agent.schedule_collateral_withdrawal(10, 30_000, "Third".to_string());

    let due_at_10 = agent.get_pending_collateral_withdrawals(10);
    assert_eq!(due_at_10.len(), 3);

    // Verify total amount
    let total: i64 = due_at_10.iter().map(|(amt, _)| amt).sum();
    assert_eq!(total, 60_000);
}

#[test]
fn test_zero_tick_timer_withdraws_immediately() {
    // Test auto_withdraw_after_ticks=0 means withdraw same tick as post
    let current_tick = 5;
    let auto_withdraw_after_ticks = 0;
    let withdrawal_tick = current_tick + auto_withdraw_after_ticks;

    assert_eq!(withdrawal_tick, 5);

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    agent.schedule_collateral_withdrawal(withdrawal_tick, 50_000, "Immediate".to_string());

    let due_at_5 = agent.get_pending_collateral_withdrawals(5);
    assert_eq!(due_at_5.len(), 1);
}

#[test]
fn test_agent_tracks_when_collateral_was_posted() {
    // Test that timer includes the tick when collateral was originally posted
    let posted_at_tick = 5;
    let withdraw_at_tick = 15;

    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    // Schedule withdrawal with posted_at_tick information
    agent.schedule_collateral_withdrawal_with_posted_tick(
        withdraw_at_tick,
        50_000,
        "TemporaryBoost".to_string(),
        posted_at_tick,
    );

    // Verify timer includes posted_at_tick
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(withdraw_at_tick);
    assert_eq!(timers.len(), 1);
    assert_eq!(timers[0].0, 50_000);
    assert_eq!(timers[0].1, "TemporaryBoost");
    assert_eq!(timers[0].2, posted_at_tick);
}

#[test]
fn test_timer_persists_across_ticks_until_due() {
    // Test that a timer scheduled for future tick persists correctly
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    agent.schedule_collateral_withdrawal(20, 100_000, "Future".to_string());

    // Check multiple ticks before due date
    for tick in 10..20 {
        assert_eq!(
            agent.get_pending_collateral_withdrawals(tick).len(),
            0,
            "Timer should not be due at tick {}",
            tick
        );
    }

    // Should be due at tick 20
    assert_eq!(agent.get_pending_collateral_withdrawals(20).len(), 1);
}

#[test]
fn test_timer_at_tick_zero() {
    // Test timer scheduled for tick 0
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    agent.schedule_collateral_withdrawal(0, 50_000, "StartOfSim".to_string());

    let due_at_0 = agent.get_pending_collateral_withdrawals(0);
    assert_eq!(due_at_0.len(), 1);
}

#[test]
fn test_clear_all_timers() {
    // Test that agent can clear all pending timers
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    agent.schedule_collateral_withdrawal(10, 10_000, "First".to_string());
    agent.schedule_collateral_withdrawal(15, 20_000, "Second".to_string());
    agent.schedule_collateral_withdrawal(20, 30_000, "Third".to_string());

    // Verify timers exist
    assert!(agent.has_pending_collateral_withdrawals());

    // Clear all
    agent.clear_collateral_withdrawal_timers();

    // Verify all cleared
    assert!(!agent.has_pending_collateral_withdrawals());
    assert_eq!(agent.get_pending_collateral_withdrawals(10).len(), 0);
    assert_eq!(agent.get_pending_collateral_withdrawals(15).len(), 0);
    assert_eq!(agent.get_pending_collateral_withdrawals(20).len(), 0);
}

// ============================================================================
// Test Group 4: Event Serialization (1 test)
// ============================================================================

#[test]
fn test_collateral_timer_event_serialization_fields() {
    // Test that all required fields exist for FFI/database persistence
    let event = Event::CollateralTimerWithdrawn {
        tick: 15,
        agent_id: "BANK_A".to_string(),
        amount: 50_000,
        original_reason: "TemporaryBoost".to_string(),
        posted_at_tick: 5,
    };

    // Verify all fields are accessible
    match event {
        Event::CollateralTimerWithdrawn {
            tick,
            agent_id,
            amount,
            original_reason,
            posted_at_tick,
        } => {
            assert_eq!(tick, 15);
            assert_eq!(agent_id, "BANK_A");
            assert_eq!(amount, 50_000);
            assert_eq!(original_reason, "TemporaryBoost");
            assert_eq!(posted_at_tick, 5);
        }
        _ => panic!("Wrong event type"),
    }
}

// ============================================================================
// Test Group 5: Reasonable Limits (1 test)
// ============================================================================

#[test]
fn test_max_reasonable_timer_duration() {
    // Test that very long timer durations work correctly
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

    // Schedule withdrawal 1000 ticks in future (10 days @ 100 ticks/day)
    agent.schedule_collateral_withdrawal(1000, 100_000, "LongTerm".to_string());

    // Should not be due at tick 999
    assert_eq!(agent.get_pending_collateral_withdrawals(999).len(), 0);

    // Should be due at tick 1000
    assert_eq!(agent.get_pending_collateral_withdrawals(1000).len(), 1);
}
