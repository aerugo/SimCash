//! Overdraft Regime Tests - Phase 1.1
//!
//! Tests to clarify and enforce credit limit behavior.
//!
//! **Decision**: Option B - Enforce `credit_used ≤ credit_limit` at ALL settlement points
//!
//! **Issue**: LSM currently uses `adjust_balance` which bypasses liquidity checks,
//! allowing agents to exceed their credit limits.
//!
//! **Solution**: Add credit limit verification before all balance adjustments.

use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

/// Helper to create agent
fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
}

/// Helper to create transaction
fn create_tx(sender: &str, receiver: &str, amount: i64, arrival: usize, deadline: usize) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        arrival,
        deadline,
    )
}

// ============================================================================
// Test Group 1: RTGS Settlement Credit Limit Enforcement
// ============================================================================

#[test]
fn test_rtgs_enforces_credit_limit_basic() {
    use payment_simulator_core_rs::settlement::try_settle;

    // Agent has 100k balance, 50k credit → 150k total liquidity
    let mut sender = create_agent("A", 100_000, 50_000);
    let mut receiver = create_agent("B", 0, 0);

    // Try to settle 200k (exceeds available 150k)
    let mut tx = create_tx("A", "B", 200_000, 0, 100);

    let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

    assert!(result.is_err());
    assert_eq!(sender.balance(), 100_000); // Unchanged
    assert_eq!(sender.credit_used(), 0);
}

#[test]
fn test_rtgs_allows_up_to_credit_limit() {
    use payment_simulator_core_rs::settlement::try_settle;

    // Agent has 100k balance, 50k credit → 150k total liquidity
    let mut sender = create_agent("A", 100_000, 50_000);
    let mut receiver = create_agent("B", 0, 0);

    // Settle exactly 150k (should succeed)
    let mut tx = create_tx("A", "B", 150_000, 0, 100);

    let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

    assert!(result.is_ok());
    assert_eq!(sender.balance(), -50_000); // Used all credit
    assert_eq!(sender.credit_used(), 50_000);
    assert_eq!(receiver.balance(), 150_000);
}

#[test]
fn test_rtgs_prevents_exceeding_credit_limit() {
    use payment_simulator_core_rs::settlement::try_settle;

    // Agent already using some credit
    let mut sender = create_agent("A", -30_000, 50_000); // Using 30k of 50k credit
    let mut receiver = create_agent("B", 0, 0);

    // Try to pay 30k more (would use 60k total, exceeding 50k limit)
    let mut tx = create_tx("A", "B", 30_000, 0, 100);

    let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

    assert!(result.is_err());
    assert_eq!(sender.balance(), -30_000); // Unchanged
    assert_eq!(sender.credit_used(), 30_000);
}

#[test]
fn test_rtgs_allows_payment_within_remaining_credit() {
    use payment_simulator_core_rs::settlement::try_settle;

    // Agent already using some credit
    let mut sender = create_agent("A", -30_000, 50_000); // Using 30k of 50k credit
    let mut receiver = create_agent("B", 0, 0);

    // Pay 20k (would use 50k total, exactly at limit)
    let mut tx = create_tx("A", "B", 20_000, 0, 100);

    let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

    assert!(result.is_ok());
    assert_eq!(sender.balance(), -50_000); // At credit limit
    assert_eq!(sender.credit_used(), 50_000);
    assert_eq!(receiver.balance(), 20_000);
}

// ============================================================================
// Test Group 2: Credit Headroom Calculation Tests
// ============================================================================

#[test]
fn test_credit_headroom_field_positive_balance() {
    // Agent with positive balance
    let agent = create_agent("A", 100_000, 50_000);

    // credit_headroom = credit_limit - credit_used = 50k - 0 = 50k
    assert_eq!(agent.credit_used(), 0);
    let credit_headroom = agent.unsecured_cap() - agent.credit_used();
    assert_eq!(credit_headroom, 50_000);
}

#[test]
fn test_credit_headroom_field_negative_balance() {
    // Agent using credit
    let agent = create_agent("A", -30_000, 50_000);

    // credit_headroom = credit_limit - credit_used = 50k - 30k = 20k
    assert_eq!(agent.credit_used(), 30_000);
    let credit_headroom = agent.unsecured_cap() - agent.credit_used();
    assert_eq!(credit_headroom, 20_000);
}

#[test]
fn test_credit_headroom_field_at_limit() {
    // Agent at credit limit
    let agent = create_agent("A", -50_000, 50_000);

    // credit_headroom = credit_limit - credit_used = 50k - 50k = 0
    assert_eq!(agent.credit_used(), 50_000);
    let credit_headroom = agent.unsecured_cap() - agent.credit_used();
    assert_eq!(credit_headroom, 0);
}

#[test]
fn test_credit_headroom_field_beyond_limit() {
    // Agent BEYOND credit limit (this is the bug we're fixing)
    // This state should not be possible after our fix
    let mut agent = create_agent("A", 0, 50_000);

    // Directly manipulate balance to simulate LSM bypass bug
    agent.adjust_balance(-70_000); // Force balance to -70k

    // credit_used = 70k, credit_limit = 50k
    // credit_headroom = 50k - 70k = -20k (should not be negative!)
    assert_eq!(agent.credit_used(), 70_000);
    let credit_headroom = agent.unsecured_cap() - agent.credit_used();
    assert_eq!(credit_headroom, -20_000); // BUG: negative headroom!
}

// ============================================================================
// Test Group 3: Policy Context Field Tests
// ============================================================================

#[test]
fn test_policy_context_includes_credit_headroom() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let agent = create_agent("A", 100_000, 50_000);
    let tx = create_tx("A", "B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

    // Should expose credit_headroom field for policies
    // Note: This field doesn't exist yet - test will fail until implemented
    // credit_headroom = credit_limit - credit_used = 50k - 0 = 50k
    let credit_headroom = context.get_field("credit_headroom");

    // This test will fail until we add the field in Phase 1.1 implementation
    assert!(credit_headroom.is_ok(), "credit_headroom field should exist in policy context");
    assert_eq!(credit_headroom.unwrap(), 50_000.0);
}

#[test]
fn test_policy_context_includes_is_overdraft_capped() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let agent = create_agent("A", 100_000, 50_000);
    let tx = create_tx("A", "B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

    // Should expose is_overdraft_capped field (1.0 for Option B)
    // This field doesn't exist yet - test will fail until implemented
    let is_capped = context.get_field("is_overdraft_capped");

    // This test will fail until we add the field in Phase 1.1 implementation
    assert!(is_capped.is_ok(), "is_overdraft_capped field should exist");
    assert_eq!(is_capped.unwrap(), 1.0); // Option B: always capped
}

// ============================================================================
// Test Group 4: Collateral + Credit Limit Tests
// ============================================================================

#[test]
fn test_credit_limit_with_collateral_enforced() {
    use payment_simulator_core_rs::settlement::try_settle;

    // Agent with collateral posted
    let mut sender = create_agent("A", 100_000, 50_000);
    sender.set_posted_collateral(100_000); // Post 100k collateral (98k after 2% haircut)

    // Available liquidity = 100k (balance) + 50k (credit) + 98k (collateral) = 248k
    assert_eq!(sender.available_liquidity(), 248_000);

    let mut receiver = create_agent("B", 0, 0);

    // Try to settle 250k (exceeds 248k)
    let mut tx = create_tx("A", "B", 250_000, 0, 100);

    let result = try_settle(&mut sender, &mut receiver, &mut tx, 5);

    // Should fail: collateral gives more headroom, but still enforced
    assert!(result.is_err());
}

#[test]
fn test_collateral_increases_available_liquidity() {
    let mut agent = create_agent("A", 100_000, 50_000);

    // Without collateral: 100k + 50k = 150k
    assert_eq!(agent.available_liquidity(), 150_000);

    // Post 100k collateral (98k after 2% haircut)
    agent.set_posted_collateral(100_000);

    // With collateral: 100k + 50k + 98k = 248k
    assert_eq!(agent.available_liquidity(), 248_000);
}

// ============================================================================
// Test Group 5: Effective Liquidity vs Available Liquidity
// ============================================================================

#[test]
fn test_effective_liquidity_equals_available_when_positive_balance() {
    let agent = create_agent("A", 100_000, 50_000);

    // When balance is positive:
    // available_liquidity = balance + credit_limit = 150k
    // effective_liquidity = balance + (credit_limit - credit_used) = 100k + 50k = 150k
    assert_eq!(agent.available_liquidity(), 150_000);

    // Both should be equal
    let credit_headroom = agent.unsecured_cap() - agent.credit_used();
    let effective_liquidity = agent.balance() + credit_headroom;
    assert_eq!(effective_liquidity, 150_000);
}

#[test]
fn test_effective_liquidity_when_using_credit() {
    let agent = create_agent("A", -30_000, 50_000);

    // When using credit (balance = -30k):
    // credit_used = 30k
    // available_liquidity = 0 (balance capped) + (50k - 30k) = 20k
    // effective_liquidity = -30k + (50k - 30k) = -30k + 20k = -10k? No!
    // effective_liquidity = balance + unused_credit = -30k + 20k = -10k

    // Actually, for policies, effective_liquidity should represent "can I do X?"
    // So it should be: balance + unused_credit_capacity
    // If balance = -30k, credit_limit = 50k, credit_used = 30k
    // unused_credit = 50k - 30k = 20k
    // effective_liquidity = -30k + 20k = -10k?

    // Wait, let me check what effective_liquidity means in context.rs...
    // From context.rs:167-172:
    // credit_headroom = credit_limit - credit_used
    // effective_liquidity = balance + credit_headroom

    // So: effective_liquidity = -30k + (50k - 30k) = -30k + 20k = -10k

    // Hmm, that doesn't seem right. Let me recalculate:
    // If balance = -30k and credit_limit = 50k:
    // - credit_used = 30k
    // - credit_headroom = 50k - 30k = 20k
    // - effective_liquidity = -30k + 20k = -10k

    // But available_liquidity = 20k (which is correct - can pay up to 20k more)

    // So effective_liquidity is actually showing net position, not payment capacity!
    // Let me verify this...

    let credit_used = agent.credit_used();
    let credit_headroom = agent.unsecured_cap() - credit_used;
    let effective_liquidity = agent.balance() + credit_headroom;

    assert_eq!(credit_used, 30_000);
    assert_eq!(credit_headroom, 20_000);
    assert_eq!(effective_liquidity, -10_000); // Net position
    assert_eq!(agent.available_liquidity(), 20_000); // Payment capacity
}

// ============================================================================
// Test Group 6: Integration Tests (will add LSM tests here after fix)
// ============================================================================

#[test]
#[ignore] // Will enable after LSM fix is implemented
fn test_lsm_respects_credit_limit_bilateral() {
    // TODO: Test that LSM bilateral offset respects credit limits
    // This test should PASS after we fix LSM to check credit limits
    todo!("Implement after LSM credit limit enforcement is added");
}

#[test]
#[ignore] // Will enable after LSM fix is implemented
fn test_lsm_respects_credit_limit_cycle() {
    // TODO: Test that LSM cycle settlement respects credit limits
    // This test should PASS after we fix LSM to check credit limits
    todo!("Implement after LSM credit limit enforcement is added");
}

// ============================================================================
// Test Group 7: Documentation Tests for New Fields
// ============================================================================

/// Test that demonstrates how policies should use credit_headroom
#[test]
#[ignore] // Will enable after field is added
fn test_policy_usage_credit_headroom() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    // Scenario: Agent considering whether to release a payment
    let agent = create_agent("A", -30_000, 50_000); // Using 30k of 50k credit
    let tx = create_tx("A", "B", 25_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

    // Policy logic: Only release if credit_headroom >= amount
    let credit_headroom = context.get_field("credit_headroom").unwrap();
    let amount = context.get_field("remaining_amount").unwrap();

    // credit_headroom = 50k - 30k = 20k
    // amount = 25k
    // Should hold because headroom < amount
    assert_eq!(credit_headroom, 20_000.0);
    assert_eq!(amount, 25_000.0);
    assert!(credit_headroom < amount, "Policy should HOLD this payment");
}

#[test]
#[ignore] // Will enable after field is added
fn test_policy_usage_is_overdraft_capped() {
    use payment_simulator_core_rs::policy::tree::EvalContext;
    use payment_simulator_core_rs::orchestrator::CostRates;

    let agent = create_agent("A", 100_000, 50_000);
    let tx = create_tx("A", "B", 10_000, 0, 100);
    let state = SimulationState::new(vec![agent.clone()]);
    let cost_rates = CostRates::default();

    let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

    // Policy logic: Different strategies based on whether overdraft is capped
    let is_capped = context.get_field("is_overdraft_capped").unwrap();

    // In Option B: always 1.0 (capped)
    assert_eq!(is_capped, 1.0);

    // Policy might use this to decide:
    // if is_capped == 1.0:
    //     "Must respect hard credit limit"
    // else:
    //     "Can exceed limit but will pay higher cost"
}
