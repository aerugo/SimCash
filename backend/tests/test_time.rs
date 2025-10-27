//! Tests for TimeManager
//!
//! Following TDD: These tests are written BEFORE implementation.

use payment_simulator_core_rs::TimeManager;

#[test]
fn test_time_manager_new() {
    let time = TimeManager::new(100);
    assert_eq!(time.current_tick(), 0);
    assert_eq!(time.current_day(), 0);
}

#[test]
fn test_advance_tick() {
    let mut time = TimeManager::new(100);

    time.advance_tick();
    assert_eq!(time.current_tick(), 1);
    assert_eq!(time.current_day(), 0);

    time.advance_tick();
    assert_eq!(time.current_tick(), 2);
    assert_eq!(time.current_day(), 0);
}

#[test]
fn test_day_boundary() {
    let mut time = TimeManager::new(100); // 100 ticks per day

    // Advance to end of day 0
    for _ in 0..99 {
        time.advance_tick();
    }

    assert_eq!(time.current_tick(), 99);
    assert_eq!(time.current_day(), 0);

    // Cross into day 1
    time.advance_tick();
    assert_eq!(time.current_tick(), 100);
    assert_eq!(time.current_day(), 1);
}

#[test]
fn test_tick_within_day() {
    let mut time = TimeManager::new(100);

    // Tick 0 → tick_within_day = 0
    assert_eq!(time.tick_within_day(), 0);

    // Advance to tick 50
    for _ in 0..50 {
        time.advance_tick();
    }
    assert_eq!(time.tick_within_day(), 50);

    // Advance to tick 100 (day 1, tick 0 within day)
    for _ in 0..50 {
        time.advance_tick();
    }
    assert_eq!(time.tick_within_day(), 0);
    assert_eq!(time.current_day(), 1);
}

#[test]
fn test_multiple_days() {
    let mut time = TimeManager::new(10); // 10 ticks per day for faster test

    // Advance 25 ticks (2 full days + 5 ticks into day 3)
    for _ in 0..25 {
        time.advance_tick();
    }

    assert_eq!(time.current_tick(), 25);
    assert_eq!(time.current_day(), 2);
    assert_eq!(time.tick_within_day(), 5);
}

#[test]
fn test_is_end_of_day() {
    let mut time = TimeManager::new(100);

    // Not end of day
    assert!(!time.is_end_of_day());

    // Advance to tick 99 (last tick of day)
    for _ in 0..99 {
        time.advance_tick();
    }

    assert!(time.is_end_of_day());

    // Cross into next day
    time.advance_tick();
    assert!(!time.is_end_of_day());
}
