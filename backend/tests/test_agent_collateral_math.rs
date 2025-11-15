// Tests for Agent collateral and headroom calculation methods
//
// These tests define the correct behavior for T2/CLM-style collateralized intraday credit.
// They will FAIL initially until the methods are implemented.

use payment_simulator_core_rs::models::Agent;

/// Helper to create test agent with balance and posted collateral
fn create_test_agent(id: &str, balance: i64, posted_collateral: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance); // 0 credit_limit
    agent.set_posted_collateral(posted_collateral);
    agent
}

/// Helper to create agent with full collateral configuration
fn create_test_agent_with_collateral(
    id: &str,
    balance: i64,
    posted_collateral: i64,
    haircut: f64,
    unsecured_cap: i64,
) -> Agent {
    let mut agent = create_test_agent(id, balance, posted_collateral);
    agent.set_collateral_haircut(haircut);
    agent.set_unsecured_cap(unsecured_cap);
    agent
}

// ============================================================================
// Test Suite 1: credit_used() method
// ============================================================================

#[cfg(test)]
mod test_credit_used {
    use super::*;

    #[test]
    fn test_credit_used_positive_balance() {
        let agent = create_test_agent("TEST", 100_000_00, 0);
        assert_eq!(
            agent.credit_used(),
            0,
            "No credit used when balance is positive"
        );
    }

    #[test]
    fn test_credit_used_negative_balance() {
        let agent = create_test_agent("TEST", -50_000_00, 0);
        assert_eq!(
            agent.credit_used(),
            50_000_00,
            "Credit used equals absolute value of overdraft"
        );
    }

    #[test]
    fn test_credit_used_zero_balance() {
        let agent = create_test_agent("TEST", 0, 0);
        assert_eq!(agent.credit_used(), 0, "No credit used at zero balance");
    }

    #[test]
    fn test_credit_used_deep_overdraft() {
        // Simulates the tick 282 REGIONAL_TRUST scenario
        let agent = create_test_agent("TEST", -164_897_33, 0);
        assert_eq!(
            agent.credit_used(),
            164_897_33,
            "Credit used matches deep overdraft"
        );
    }
}

// ============================================================================
// Test Suite 2: allowed_overdraft_limit() method
// ============================================================================

#[cfg(test)]
mod test_allowed_overdraft_limit {
    use super::*;

    #[test]
    fn test_allowed_overdraft_no_collateral() {
        let agent = create_test_agent_with_collateral("TEST", 100_000_00, 0, 0.0, 0);
        assert_eq!(
            agent.allowed_overdraft_limit(),
            0,
            "No overdraft allowed without collateral or unsecured cap"
        );
    }

    #[test]
    fn test_allowed_overdraft_with_collateral_no_haircut() {
        let agent = create_test_agent_with_collateral("TEST", 100_000_00, 100_000_00, 0.0, 0);

        assert_eq!(
            agent.allowed_overdraft_limit(),
            100_000_00,
            "Full collateral value available with 0% haircut"
        );
    }

    #[test]
    fn test_allowed_overdraft_with_2_percent_haircut() {
        // Typical T2 haircut for high-quality government bonds
        let agent = create_test_agent_with_collateral("TEST", 0, 100_000_00, 0.02, 0);

        let expected = (100_000_00.0_f64 * 0.98).floor() as i64; // $98,000
        assert_eq!(
            agent.allowed_overdraft_limit(),
            expected,
            "Overdraft limit = floor(collateral × (1 - 0.02))"
        );
    }

    #[test]
    fn test_allowed_overdraft_with_10_percent_haircut() {
        // Higher haircut for lower-quality collateral
        let agent = create_test_agent_with_collateral("TEST", 0, 100_000_00, 0.10, 0);

        let expected = (100_000_00.0_f64 * 0.90).floor() as i64; // $90,000
        assert_eq!(
            agent.allowed_overdraft_limit(),
            expected,
            "Overdraft limit = floor(collateral × (1 - 0.10))"
        );
    }

    #[test]
    fn test_allowed_overdraft_with_unsecured_cap() {
        let agent = create_test_agent_with_collateral("TEST", 0, 100_000_00, 0.05, 20_000_00);

        let collat_portion = (100_000_00.0_f64 * 0.95).floor() as i64; // $95,000
        let expected = collat_portion + 20_000_00; // $115,000

        assert_eq!(
            agent.allowed_overdraft_limit(),
            expected,
            "Overdraft limit = collateralized + unsecured cap"
        );
    }

    #[test]
    fn test_allowed_overdraft_only_unsecured_cap() {
        // Agent with no collateral but has unsecured daylight cap
        let agent = create_test_agent_with_collateral("TEST", 0, 0, 0.0, 50_000_00);

        assert_eq!(
            agent.allowed_overdraft_limit(),
            50_000_00,
            "Unsecured cap provides overdraft capacity without collateral"
        );
    }

    #[test]
    fn test_allowed_overdraft_100_percent_haircut() {
        // Edge case: worthless collateral
        let agent = create_test_agent_with_collateral("TEST", 0, 100_000_00, 1.0, 0);

        assert_eq!(
            agent.allowed_overdraft_limit(),
            0,
            "100% haircut means no overdraft capacity from collateral"
        );
    }
}

// ============================================================================
// Test Suite 3: headroom() method
// ============================================================================

#[cfg(test)]
mod test_headroom {
    use super::*;

    #[test]
    fn test_headroom_no_usage() {
        let agent = create_test_agent_with_collateral("TEST", 50_000_00, 100_000_00, 0.10, 0);

        // No overdraft, so credit_used = 0
        // allowed_limit = 90,000
        assert_eq!(
            agent.headroom(),
            90_000_00,
            "Full headroom available when no credit used"
        );
    }

    #[test]
    fn test_headroom_partial_usage() {
        let agent = create_test_agent_with_collateral("TEST", -30_000_00, 100_000_00, 0.10, 0);

        // credit_used = 30,000
        // allowed_limit = 90,000
        // headroom = 60,000
        assert_eq!(
            agent.headroom(),
            60_000_00,
            "Headroom = allowed_limit - credit_used"
        );
    }

    #[test]
    fn test_headroom_fully_utilized() {
        let agent = create_test_agent_with_collateral("TEST", -90_000_00, 100_000_00, 0.10, 0);

        // credit_used = 90,000
        // allowed_limit = 90,000
        assert_eq!(agent.headroom(), 0, "Zero headroom at full utilization");
    }

    #[test]
    fn test_headroom_over_limit_violation() {
        // This represents the tick 282 REGIONAL_TRUST bug scenario
        // Balance: -$164,897, Posted: $80,000 (implied), Haircut: 2%
        // This state should NEVER occur after fix, but test captures the math
        let agent = create_test_agent_with_collateral("TEST", -100_000_00, 80_000_00, 0.10, 0);

        // credit_used = 100,000
        // allowed_limit = 72,000 (80k × 0.9)
        // headroom = -28,000 (NEGATIVE!)
        assert!(
            agent.headroom() < 0,
            "Negative headroom indicates invariant violation (should be prevented by withdraw logic)"
        );

        let expected_headroom = 72_000_00 - 100_000_00; // -28,000
        assert_eq!(
            agent.headroom(),
            expected_headroom,
            "Headroom correctly calculates negative value for violation detection"
        );
    }

    #[test]
    fn test_headroom_with_unsecured_cap() {
        let agent = create_test_agent_with_collateral("TEST", -50_000_00, 80_000_00, 0.05, 20_000_00);

        // credit_used = 50,000
        // collateral_portion = 76,000 (80k × 0.95)
        // allowed_limit = 96,000 (76k + 20k)
        // headroom = 46,000
        assert_eq!(
            agent.headroom(),
            46_000_00,
            "Headroom accounts for unsecured cap"
        );
    }
}

// ============================================================================
// Test Suite 4: max_withdrawable_collateral() method
// ============================================================================

#[cfg(test)]
mod test_max_withdrawable_collateral {
    use super::*;

    #[test]
    fn test_max_withdrawable_no_usage_no_buffer() {
        let agent = create_test_agent_with_collateral("TEST", 50_000_00, 100_000_00, 0.10, 0);

        // No usage, no buffer: can withdraw all
        assert_eq!(
            agent.max_withdrawable_collateral(0),
            100_000_00,
            "Can withdraw all collateral when no credit used and no buffer"
        );
    }

    #[test]
    fn test_max_withdrawable_no_usage_with_buffer() {
        let agent = create_test_agent_with_collateral("TEST", 50_000_00, 100_000_00, 0.10, 0);

        // Buffer = $20k
        // Need: allowed_limit ≥ 0 + 20k after withdrawal
        // Need: C_new × 0.9 ≥ 20k → C_new ≥ 22,223 (ceil)
        // Can withdraw: 100k - 22,223 = 77,777

        let max_w = agent.max_withdrawable_collateral(20_000_00);
        assert!(
            max_w >= 77_777_00 && max_w <= 77_778_00,
            "Max withdrawable accounts for safety buffer. Got: {}",
            max_w
        );
    }

    #[test]
    fn test_max_withdrawable_with_active_overdraft() {
        let agent = create_test_agent_with_collateral("TEST", -60_000_00, 100_000_00, 0.10, 0);

        // credit_used = 60,000
        // Need: C_new × 0.9 ≥ 60k → C_new ≥ 66,667 (ceil)
        // Can withdraw: 100k - 66,667 = 33,333

        let max_w = agent.max_withdrawable_collateral(0);
        assert!(
            max_w >= 33_333_00 && max_w <= 33_334_00,
            "Can withdraw excess beyond required collateral. Got: {}",
            max_w
        );
    }

    #[test]
    fn test_max_withdrawable_with_overdraft_and_buffer() {
        let agent = create_test_agent_with_collateral("TEST", -60_000_00, 100_000_00, 0.10, 0);

        // credit_used = 60,000
        // buffer = 10,000
        // Need: C_new × 0.9 ≥ 70k → C_new ≥ 77,778 (ceil)
        // Can withdraw: 100k - 77,778 = 22,222

        let max_w = agent.max_withdrawable_collateral(10_000_00);
        assert!(
            max_w >= 22_222_00 && max_w <= 22_223_00,
            "Max withdrawable accounts for both usage and buffer. Got: {}",
            max_w
        );
    }

    #[test]
    fn test_max_withdrawable_at_limit() {
        let agent = create_test_agent_with_collateral("TEST", -90_000_00, 100_000_00, 0.10, 0);

        // credit_used = 90,000
        // allowed_limit = 90,000 (fully utilized)
        // Cannot withdraw anything

        assert_eq!(
            agent.max_withdrawable_collateral(0),
            0,
            "Cannot withdraw when at utilization limit"
        );
    }

    #[test]
    fn test_max_withdrawable_over_limit_violation() {
        // Reproduces the tick 282 REGIONAL_TRUST violation scenario
        let agent = create_test_agent_with_collateral("TEST", -164_897_33, 120_000_00, 0.02, 0);

        // credit_used = 164,897
        // allowed_limit = 117,600 (120k × 0.98)
        // Already over limit! Max withdrawable = 0

        assert_eq!(
            agent.max_withdrawable_collateral(0),
            0,
            "Cannot withdraw any collateral when over limit (tick 282 bug scenario)"
        );
    }

    #[test]
    fn test_max_withdrawable_with_unsecured_cap() {
        let agent = create_test_agent_with_collateral("TEST", -50_000_00, 80_000_00, 0.10, 20_000_00);

        // credit_used = 50,000
        // Need: C_new × 0.9 + 20k ≥ 50k
        // Need: C_new ≥ (50k - 20k) / 0.9 = 33,334 (ceil)
        // Can withdraw: 80k - 33,334 = 46,666

        let max_w = agent.max_withdrawable_collateral(0);
        assert!(
            max_w >= 46_666_00 && max_w <= 46_667_00,
            "Unsecured cap reduces required collateral. Got: {}",
            max_w
        );
    }

    #[test]
    fn test_max_withdrawable_100_percent_haircut() {
        // Edge case: collateral provides no overdraft capacity
        let agent = create_test_agent_with_collateral("TEST", 50_000_00, 100_000_00, 1.0, 0);

        // No credit used, so can withdraw all
        assert_eq!(
            agent.max_withdrawable_collateral(0),
            100_000_00,
            "With 100% haircut and no usage, can still withdraw (collateral is worthless for credit)"
        );
    }

    #[test]
    fn test_max_withdrawable_100_percent_haircut_with_unsecured() {
        // Collateral provides no capacity, but unsecured cap is being used
        let agent = create_test_agent_with_collateral("TEST", -30_000_00, 100_000_00, 1.0, 50_000_00);

        // credit_used = 30,000
        // Collateral contributes 0 to allowed_limit
        // allowed_limit = 0 + 50,000 = 50,000
        // All usage is against unsecured cap, not collateral
        // Can withdraw all collateral

        assert_eq!(
            agent.max_withdrawable_collateral(0),
            100_000_00,
            "Can withdraw all collateral when it doesn't contribute to credit capacity"
        );
    }

    #[test]
    fn test_max_withdrawable_zero_haircut_edge() {
        // Edge case: 0% haircut means full collateral value
        let agent = create_test_agent_with_collateral("TEST", -80_000_00, 100_000_00, 0.0, 0);

        // credit_used = 80,000
        // Need: C_new × 1.0 ≥ 80k → C_new ≥ 80,000
        // Can withdraw: 100k - 80k = 20,000

        assert_eq!(
            agent.max_withdrawable_collateral(0),
            20_000_00,
            "With 0% haircut, 1:1 relationship between collateral and credit"
        );
    }

    #[test]
    fn test_max_withdrawable_rounding_precision() {
        // Test that rounding is done correctly (ceil for required, floor for allowed)
        let agent = create_test_agent_with_collateral("TEST", -33_333_00, 100_000_00, 0.07, 0);

        // credit_used = 33,333
        // Need: C_new × 0.93 ≥ 33,333
        // Need: C_new ≥ 33,333 / 0.93 = 35,841.935... → ceil to 35,842
        // Can withdraw: 100,000 - 35,842 = 64,158

        let max_w = agent.max_withdrawable_collateral(0);

        // Allow for off-by-one due to rounding
        assert!(
            max_w >= 64_157_00 && max_w <= 64_159_00,
            "Rounding should be done safely (ceil required collateral). Got: {}",
            max_w
        );
    }
}

// ============================================================================
// Test Suite 5: Invariant Integration Tests
// ============================================================================

#[cfg(test)]
mod test_invariants {
    use super::*;

    #[test]
    fn test_invariant_i1_credit_used_never_exceeds_limit_at_initialization() {
        // When properly initialized, credit_used should never exceed allowed_limit
        let agent = create_test_agent_with_collateral("TEST", -80_000_00, 100_000_00, 0.10, 0);

        let credit_used = agent.credit_used();
        let allowed_limit = agent.allowed_overdraft_limit();

        assert!(
            credit_used <= allowed_limit,
            "Invariant I1: credit_used ({}) must be ≤ allowed_limit ({})",
            credit_used,
            allowed_limit
        );
    }

    #[test]
    fn test_invariant_i2_withdrawal_preserves_headroom() {
        let agent = create_test_agent_with_collateral("TEST", -60_000_00, 100_000_00, 0.10, 0);

        let max_w = agent.max_withdrawable_collateral(0);

        // Simulate withdrawal by calculating new state
        let new_collateral = agent.posted_collateral() - max_w;
        let new_allowed_limit = ((new_collateral as f64) * 0.9).floor() as i64;
        let credit_used = agent.credit_used(); // Unchanged by withdrawal

        assert!(
            credit_used <= new_allowed_limit,
            "Invariant I2: After max withdrawal, credit_used ({}) must still be ≤ new allowed_limit ({})",
            credit_used,
            new_allowed_limit
        );
    }

    #[test]
    fn test_invariant_i3_buffer_preserved() {
        let buffer = 10_000_00;
        let agent = create_test_agent_with_collateral("TEST", -60_000_00, 100_000_00, 0.10, 0);

        let max_w = agent.max_withdrawable_collateral(buffer);

        // Simulate withdrawal
        let new_collateral = agent.posted_collateral() - max_w;
        let new_allowed_limit = ((new_collateral as f64) * 0.9).floor() as i64;
        let credit_used = agent.credit_used();
        let new_headroom = new_allowed_limit - credit_used;

        assert!(
            new_headroom >= buffer,
            "Invariant I3: After max withdrawal with buffer, headroom ({}) must be ≥ buffer ({})",
            new_headroom,
            buffer
        );
    }

    #[test]
    fn test_tick_282_violation_state_detected() {
        // This test documents the tick 282 bug: agent is in violation state
        // In reality, this state should NEVER be reached due to withdrawal guards
        let agent = create_test_agent_with_collateral("TEST", -164_897_33, 50_000_00, 0.02, 0);

        let credit_used = agent.credit_used();
        let allowed_limit = agent.allowed_overdraft_limit();
        let headroom = agent.headroom();

        // Document the violation
        assert!(
            credit_used > allowed_limit,
            "Tick 282 bug: credit_used ({}) > allowed_limit ({})",
            credit_used,
            allowed_limit
        );

        assert!(
            headroom < 0,
            "Tick 282 bug: headroom ({}) is negative",
            headroom
        );

        // Verify that max_withdrawable correctly returns 0 in this state
        assert_eq!(
            agent.max_withdrawable_collateral(0),
            0,
            "In violation state, max_withdrawable must be 0"
        );
    }
}
