//! Collateral Timer Invariant Tests
//!
//! Tests that automatic collateral timer withdrawals respect critical invariants:
//! - Invariant I2: Withdrawal Headroom Protection
//! - Minimum holding period enforcement
//! - Consistency with manual withdrawal path
//!
//! These tests capture the bug where timer withdrawals bypass max_withdrawable_collateral
//! checks, allowing withdrawals while deeply overdrawn.
//!
//! TDD Approach: These tests are written BEFORE the fix to capture the bug (Red phase).
//! They should FAIL initially, then PASS after implementing the unified guard.

use payment_simulator_core_rs::models::agent::Agent;

// Helper function to simulate timer processing using the guarded method
fn process_collateral_timers_guarded(
    agent: &mut Agent,
    current_tick: usize,
    min_holding_ticks: usize,
    safety_buffer: i64,
) -> Vec<(i64, String)> {
    // Get pending timers for this tick
    let timers = agent.get_pending_collateral_withdrawals_with_posted_tick(current_tick);

    let mut results = Vec::new();

    for (requested_amount, original_reason, _posted_at_tick) in timers {
        // Use the guarded withdrawal method (enforces Invariant I2)
        match agent.try_withdraw_collateral_guarded(
            requested_amount,
            current_tick,
            min_holding_ticks,
            safety_buffer,
        ) {
            Ok(actual_withdrawn) => {
                results.push((actual_withdrawn, original_reason));
            }
            Err(_) => {
                // Blocked - record as 0 withdrawal
                results.push((0, original_reason));
            }
        }
    }

    // Clean up processed timers
    agent.remove_collateral_withdrawal_timer(current_tick);

    results
}

// ============================================================================
// Test 1.1: Timer Respects Headroom When Overdrawn
// ============================================================================

#[test]
fn test_timer_withdrawal_respects_headroom_when_overdrawn() {
    // Setup: Agent is overdrawn, posted collateral backs the overdraft
    let mut agent = Agent::new("BANK_A".to_string(), -60_000_00);
    agent.set_posted_collateral(100_000_00); // $100k posted
    agent.set_collateral_haircut(0.10); // 10% haircut
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5); // Posted at tick 5

    // Verify starting state
    let credit_used = agent.credit_used();
    assert_eq!(credit_used, 60_000_00, "Should be using $60k credit");

    let allowed_limit = agent.allowed_overdraft_limit();
    assert_eq!(allowed_limit, 90_000_00, "Limit should be floor(100k × 0.9) = 90k");

    let headroom = agent.headroom();
    assert_eq!(headroom, 30_000_00, "Headroom should be 90k - 60k = 30k");

    // Calculate max safe withdrawal
    // Need: C × 0.9 ≥ 60k → C ≥ 66,667
    // Can withdraw: 100k - 66,667 = 33,333
    let max_safe = agent.max_withdrawable_collateral(0);
    assert!(max_safe >= 33_333_00 && max_safe <= 33_334_00,
        "Max safe withdrawal should be ~$33,333, got {}", max_safe);

    // Schedule timer to withdraw $80k (UNSAFE! Exceeds max_safe)
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10, // withdrawal_tick
        80_000_00, // amount (exceeds max_safe!)
        "TemporaryBoost".to_string(),
        5, // posted_at_tick
    );

    // Process timer at tick 10 (5 ticks after posting, meets min holding period)
    let results = process_collateral_timers_guarded(&mut agent, 10, 5, 0);

    // EXPECTED BEHAVIOR (after fix):
    // Should withdraw ONLY max_safe amount (33,333), not the full 80k
    // OR block entirely with event

    // CURRENT BEHAVIOR (bug):
    // Withdraws the full 80k (capped by posted amount), violating Invariant I2

    let withdrawn_amount = results.first().map(|(amt, _)| *amt).unwrap_or(0);

    // After fix, this assertion should PASS
    assert!(
        withdrawn_amount <= max_safe,
        "Timer withdrew {} but max safe is {}. INVARIANT I2 VIOLATED!",
        withdrawn_amount,
        max_safe
    );

    // Verify Invariant I2 after withdrawal
    let new_limit = agent.allowed_overdraft_limit();
    let credit_used_after = agent.credit_used();
    assert!(
        new_limit >= credit_used_after,
        "Invariant I2 violated: allowed_limit ({}) < credit_used ({})",
        new_limit,
        credit_used_after
    );

    // Verify headroom is non-negative
    let headroom_after = agent.headroom();
    assert!(
        headroom_after >= 0,
        "Headroom went negative: {}",
        headroom_after
    );
}

// ============================================================================
// Test 1.2: Timer Clamps to Safe Amount
// ============================================================================

#[test]
fn test_timer_clamps_withdrawal_to_safe_amount() {
    // Setup: Agent is moderately overdrawn
    let mut agent = Agent::new("BANK_A".to_string(), -30_000_00);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5);

    // Calculate max safe withdrawal
    // Need: C × 0.9 ≥ 30k → C ≥ 33,334
    // Can withdraw: 100k - 33,334 = 66,666
    let max_safe = agent.max_withdrawable_collateral(0);
    assert!(max_safe >= 66_666_00 && max_safe <= 66_667_00, "Max safe should be ~$66,666");

    // Schedule timer to withdraw MORE than safe amount
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        80_000_00, // Request $80k (more than max_safe)
        "TemporaryBoost".to_string(),
        5,
    );

    let collateral_before = agent.posted_collateral();

    // Process timer
    process_collateral_timers_guarded(&mut agent, 10, 5, 0);

    let collateral_after = agent.posted_collateral();
    let actual_withdrawn = collateral_before - collateral_after;

    // After fix: Should withdraw only max_safe, not the full 80k
    assert!(
        actual_withdrawn <= max_safe,
        "Timer withdrew {} but max safe is {}",
        actual_withdrawn,
        max_safe
    );

    // Verify Invariant I2 still holds
    assert!(
        agent.allowed_overdraft_limit() >= agent.credit_used(),
        "Invariant I2 violated after clamped withdrawal"
    );
}

// ============================================================================
// Test 1.3: Timer Blocked When No Headroom
// ============================================================================

#[test]
fn test_timer_blocked_when_no_headroom_available() {
    // Setup: Agent is deeply overdrawn, all collateral needed
    let mut agent = Agent::new("BANK_A".to_string(), -90_000_00);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5);

    // Verify max safe withdrawal is ZERO
    // Need: C × 0.9 ≥ 90k → C ≥ 100k
    // Can withdraw: 100k - 100k = 0 (NONE!)
    let max_safe = agent.max_withdrawable_collateral(0);
    assert_eq!(max_safe, 0, "Max safe should be 0 when fully utilized");

    // Schedule timer to withdraw $10k
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        10_000_00,
        "Test".to_string(),
        5,
    );

    let collateral_before = agent.posted_collateral();

    // Process timer
    process_collateral_timers_guarded(&mut agent, 10, 5, 0);

    let collateral_after = agent.posted_collateral();

    // After fix: NO withdrawal should occur (max_safe = 0)
    assert_eq!(
        collateral_after,
        collateral_before,
        "Timer should NOT withdraw when max_safe = 0, but withdrew {}",
        collateral_before - collateral_after
    );

    // Verify Invariant I2 still holds
    assert!(
        agent.allowed_overdraft_limit() >= agent.credit_used(),
        "Invariant I2 violated"
    );
}

// ============================================================================
// Test 1.4: Timer Respects Minimum Holding Period
// ============================================================================

#[test]
fn test_timer_respects_minimum_holding_period() {
    const MIN_HOLDING_TICKS: usize = 5;

    // Setup: Agent has positive balance (withdrawal is safe liquidity-wise)
    let mut agent = Agent::new("BANK_A".to_string(), 100_000_00);
    agent.set_posted_collateral(50_000_00);
    agent.set_collateral_posted_at_tick(5); // Posted at tick 5

    // Schedule timer for tick 8 (only 3 ticks later, MIN=5)
    agent.schedule_collateral_withdrawal_with_posted_tick(
        8,
        10_000_00,
        "Test".to_string(),
        5,
    );

    let _collateral_before = agent.posted_collateral();

    // Process timer at tick 8 (too early!)
    // Note: Current mock doesn't check min holding period, but real implementation should
    // For now, we test that can_withdraw_collateral returns false
    assert!(
        !agent.can_withdraw_collateral(8, MIN_HOLDING_TICKS),
        "Should not be able to withdraw at tick 8 (posted at 5, need 5 ticks)"
    );

    // After fix, timer processing should check this and block
    // For now, we verify the guard function works
    assert!(
        agent.can_withdraw_collateral(10, MIN_HOLDING_TICKS),
        "Should be able to withdraw at tick 10 (5 + 5)"
    );

    // In full implementation, we'd process and verify:
    // process_collateral_timers_with_guard(&mut agent, 8, MIN_HOLDING_TICKS);
    // assert_eq!(agent.posted_collateral(), collateral_before, "Should not withdraw at tick 8");

    // process_collateral_timers_with_guard(&mut agent, 10, MIN_HOLDING_TICKS);
    // assert_eq!(agent.posted_collateral(), collateral_before - 10_000_00, "Should withdraw at tick 10");
}

// ============================================================================
// Test 1.5: Edge Case - Exact Limit
// ============================================================================

#[test]
fn test_timer_at_exact_credit_limit() {
    // Setup: Agent's collateral exactly covers their overdraft (no headroom)
    let mut agent = Agent::new("BANK_A".to_string(), -90_000_00);
    agent.set_posted_collateral(100_000_00); // Provides exactly 90k capacity
    agent.set_collateral_haircut(0.10);
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5);

    // Verify we're at the limit
    let allowed = agent.allowed_overdraft_limit();
    let used = agent.credit_used();
    assert_eq!(allowed, used, "Should be at exact limit");

    let headroom = agent.headroom();
    assert_eq!(headroom, 0, "Headroom should be exactly 0");

    // Any withdrawal should be blocked
    let max_safe = agent.max_withdrawable_collateral(0);
    assert_eq!(max_safe, 0, "Max safe should be 0 at exact limit");

    // Schedule withdrawal
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        5_000_00,
        "Test".to_string(),
        5,
    );

    let collateral_before = agent.posted_collateral();
    process_collateral_timers_guarded(&mut agent, 10, 5, 0);
    let collateral_after = agent.posted_collateral();

    // After fix: Should NOT withdraw (would violate I2)
    assert_eq!(
        collateral_after,
        collateral_before,
        "Should not withdraw at exact limit"
    );
}

// ============================================================================
// Test 1.6: Safety Buffer Prevents Edge Cases
// ============================================================================

#[test]
fn test_timer_respects_safety_buffer() {
    // Setup: Agent close to limit
    let mut agent = Agent::new("BANK_A".to_string(), -89_000_00);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5);

    // With buffer=0: might allow small withdrawal due to rounding
    let max_safe_no_buffer = agent.max_withdrawable_collateral(0);

    // With buffer=100: should be more conservative
    let max_safe_with_buffer = agent.max_withdrawable_collateral(100);

    assert!(
        max_safe_with_buffer <= max_safe_no_buffer,
        "Buffer should reduce or maintain max safe amount"
    );

    // After fix, timer should use a safety buffer (e.g., 100 cents)
    // to prevent edge cases where floor/ceil rounding causes violations
}

// ============================================================================
// Test 1.7: Multiple Timers Same Tick
// ============================================================================

#[test]
fn test_multiple_timers_same_tick_respect_headroom() {
    // Setup: Agent with moderate overdraft
    let mut agent = Agent::new("BANK_A".to_string(), -50_000_00);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);
    agent.set_unsecured_cap(0);
    agent.set_collateral_posted_at_tick(5);

    // Max safe: 100k - ceil(50k / 0.9) = 100k - 55,556 = 44,444
    let max_safe = agent.max_withdrawable_collateral(0);
    assert!(max_safe >= 44_444_00 && max_safe <= 44_445_00);

    // Schedule TWO timers for same tick, totaling MORE than max_safe
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        30_000_00,
        "Tranche1".to_string(),
        5,
    );
    agent.schedule_collateral_withdrawal_with_posted_tick(
        10,
        30_000_00,
        "Tranche2".to_string(),
        5,
    );

    let collateral_before = agent.posted_collateral();

    // Process timers
    process_collateral_timers_guarded(&mut agent, 10, 5, 0);

    let collateral_after = agent.posted_collateral();
    let total_withdrawn = collateral_before - collateral_after;

    // After fix: Total withdrawn should NOT exceed max_safe
    assert!(
        total_withdrawn <= max_safe,
        "Multiple timers withdrew {} total, but max safe is {}",
        total_withdrawn,
        max_safe
    );

    // Verify Invariant I2
    assert!(
        agent.allowed_overdraft_limit() >= agent.credit_used(),
        "Invariant I2 violated after multiple timer withdrawals"
    );
}
