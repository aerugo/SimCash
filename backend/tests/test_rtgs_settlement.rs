//! RTGS Settlement Engine Tests
//!
//! Tests for Phase 3: Basic RTGS settlement with central queue management.
//! Following TDD principles - these tests are written BEFORE implementation.

use payment_simulator_core_rs::{Agent, Transaction, TransactionStatus};

// ============================================================================
// Test Helpers
// ============================================================================

/// Create a test agent with given balance and credit limit
fn create_test_agent(id: &str, balance: i64, credit_limit: i64) -> Agent {
    Agent::new(id.to_string(), balance, credit_limit)
}

/// Create a test transaction
fn create_test_transaction(
    sender_id: &str,
    receiver_id: &str,
    amount: i64,
    arrival_tick: usize,
    deadline_tick: usize,
) -> Transaction {
    Transaction::new(
        sender_id.to_string(),
        receiver_id.to_string(),
        amount,
        arrival_tick,
        deadline_tick,
    )
}

// ============================================================================
// Basic Immediate Settlement Tests
// ============================================================================

#[test]
fn test_immediate_settlement_with_sufficient_balance() {
    // BANK_A has 1,000,000 cents ($10,000), BANK_B has 0
    let mut sender = create_test_agent("BANK_A", 1_000_000, 0);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);

    // Attempt settlement
    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );

    // Should succeed
    assert!(result.is_ok(), "Settlement should succeed with sufficient balance");

    // Check balances updated correctly
    assert_eq!(sender.balance(), 500_000, "Sender should be debited");
    assert_eq!(receiver.balance(), 500_000, "Receiver should be credited");

    // Check transaction marked as settled
    assert!(transaction.is_fully_settled(), "Transaction should be fully settled");
    assert_eq!(transaction.remaining_amount(), 0, "Remaining amount should be 0");
}

#[test]
fn test_settlement_with_credit_limit() {
    // BANK_A has 300,000 balance, 500,000 credit limit
    // Total liquidity = 800,000
    let mut sender = create_test_agent("BANK_A", 300_000, 500_000);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 600_000, 0, 100);

    // Attempt settlement (should use credit)
    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );

    // Should succeed
    assert!(result.is_ok(), "Settlement should succeed with credit");

    // Sender should be in overdraft
    assert_eq!(sender.balance(), -300_000, "Sender should use 300k credit");
    assert!(sender.is_using_credit(), "Sender should be using credit");
    assert_eq!(sender.credit_used(), 300_000, "Credit used should be 300k");

    // Receiver credited
    assert_eq!(receiver.balance(), 600_000, "Receiver should be credited");

    // Transaction settled
    assert!(transaction.is_fully_settled());
}

#[test]
fn test_insufficient_liquidity_returns_error() {
    // BANK_A has 300,000 balance, 500,000 credit limit
    // Total liquidity = 800,000
    // Trying to send 900,000 (exceeds liquidity)
    let mut sender = create_test_agent("BANK_A", 300_000, 500_000);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 900_000, 0, 100);

    // Attempt settlement
    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );

    // Should fail with InsufficientLiquidity error
    assert!(result.is_err(), "Settlement should fail");

    // Balances should be unchanged
    assert_eq!(sender.balance(), 300_000, "Sender balance should be unchanged");
    assert_eq!(receiver.balance(), 0, "Receiver balance should be unchanged");

    // Transaction should still be pending
    assert!(!transaction.is_fully_settled(), "Transaction should not be settled");
    assert_eq!(transaction.remaining_amount(), 900_000, "Full amount still pending");
}

#[test]
fn test_zero_balance_with_sufficient_credit() {
    // BANK_A has 0 balance but 1,000,000 credit
    let mut sender = create_test_agent("BANK_A", 0, 1_000_000);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);

    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );

    assert!(result.is_ok(), "Should settle using credit");
    assert_eq!(sender.balance(), -500_000, "Sender should be in overdraft");
    assert_eq!(receiver.balance(), 500_000);
    assert!(transaction.is_fully_settled());
}

#[test]
fn test_cannot_settle_already_settled_transaction() {
    let mut sender = create_test_agent("BANK_A", 1_000_000, 0);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);

    // First settlement
    let result1 = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );
    assert!(result1.is_ok());

    // Try to settle again
    let result2 = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        6,
    );

    // Should fail with AlreadySettled error
    assert!(result2.is_err(), "Cannot settle already settled transaction");

    // Balances should not change on second attempt
    assert_eq!(sender.balance(), 500_000, "No double debit");
    assert_eq!(receiver.balance(), 500_000, "No double credit");
}

// ============================================================================
// Partial Settlement Tests (Divisible Transactions)
// ============================================================================

#[test]
fn test_partial_settlement_divisible_transaction() {
    // BANK_A has 300,000, wants to send 1,000,000 (divisible)
    let mut sender = create_test_agent("BANK_A", 300_000, 0);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 1_000_000, 0, 100)
        .divisible(); // Mark as divisible

    // Try to settle what we can (300,000)
    let result = payment_simulator_core_rs::settlement::try_settle_partial(
        &mut sender,
        &mut receiver,
        &mut transaction,
        300_000,
        5,
    );

    assert!(result.is_ok(), "Partial settlement should succeed");

    // Check balances
    assert_eq!(sender.balance(), 0, "Sender used all available balance");
    assert_eq!(receiver.balance(), 300_000, "Receiver got partial amount");

    // Check transaction state
    assert!(!transaction.is_fully_settled(), "Not fully settled yet");
    assert!(
        matches!(
            transaction.status(),
            TransactionStatus::PartiallySettled { .. }
        ),
        "Should be partially settled"
    );
    assert_eq!(transaction.remaining_amount(), 700_000, "700k still pending");
    assert_eq!(transaction.settled_amount(), 300_000, "300k settled");
}

#[test]
fn test_full_settlement_after_partial() {
    // Start with partial settlement
    let mut sender = create_test_agent("BANK_A", 300_000, 0);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 1_000_000, 0, 100)
        .divisible();

    // Partial settlement of 300k
    payment_simulator_core_rs::settlement::try_settle_partial(
        &mut sender,
        &mut receiver,
        &mut transaction,
        300_000,
        5,
    )
    .unwrap();

    // Now sender receives 700k
    sender.credit(700_000);
    assert_eq!(sender.balance(), 700_000);

    // Complete the settlement
    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        10,
    );

    assert!(result.is_ok(), "Final settlement should succeed");

    // All balances settled
    assert_eq!(sender.balance(), 0, "Sender used all liquidity");
    assert_eq!(receiver.balance(), 1_000_000, "Receiver got full amount");

    // Transaction fully settled
    assert!(transaction.is_fully_settled());
    assert_eq!(transaction.remaining_amount(), 0);
    assert_eq!(transaction.settled_amount(), 1_000_000);
}

#[test]
fn test_indivisible_transaction_must_settle_fully() {
    // Transaction is NOT divisible - must settle all or nothing
    let mut sender = create_test_agent("BANK_A", 300_000, 0);
    let mut receiver = create_test_agent("BANK_B", 0, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    // Note: NOT calling .divisible(), so it's indivisible by default

    assert!(
        !transaction.is_divisible(),
        "Transaction should be indivisible"
    );

    // Try partial settlement - should fail or be rejected
    let result = payment_simulator_core_rs::settlement::try_settle_partial(
        &mut sender,
        &mut receiver,
        &mut transaction,
        300_000,
        5,
    );

    // Should error because indivisible
    assert!(
        result.is_err(),
        "Cannot partially settle indivisible transaction"
    );

    // Balances unchanged
    assert_eq!(sender.balance(), 300_000);
    assert_eq!(receiver.balance(), 0);
}

// ============================================================================
// Balance Conservation Tests (Critical Invariant)
// ============================================================================

#[test]
fn test_balance_conservation_on_settlement() {
    let mut sender = create_test_agent("BANK_A", 1_000_000, 500_000);
    let mut receiver = create_test_agent("BANK_B", 2_000_000, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 600_000, 0, 100);

    // Total system balance before
    let total_before = sender.balance() + receiver.balance();
    assert_eq!(total_before, 3_000_000);

    // Settle
    payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    )
    .unwrap();

    // Total system balance after
    let total_after = sender.balance() + receiver.balance();

    // CRITICAL: Total balance must be conserved
    assert_eq!(
        total_before, total_after,
        "Total system balance must be conserved"
    );
    assert_eq!(total_after, 3_000_000);
}

#[test]
fn test_balance_conservation_on_failed_settlement() {
    let mut sender = create_test_agent("BANK_A", 300_000, 0);
    let mut receiver = create_test_agent("BANK_B", 500_000, 0);
    let mut transaction = create_test_transaction("BANK_A", "BANK_B", 900_000, 0, 100);

    let total_before = sender.balance() + receiver.balance();
    assert_eq!(total_before, 800_000);

    // Try to settle (will fail)
    let result = payment_simulator_core_rs::settlement::try_settle(
        &mut sender,
        &mut receiver,
        &mut transaction,
        5,
    );

    assert!(result.is_err());

    // Balance should be unchanged
    let total_after = sender.balance() + receiver.balance();
    assert_eq!(total_before, total_after);
    assert_eq!(total_after, 800_000);
}

#[test]
fn test_balance_conservation_multiple_settlements() {
    let mut bank_a = create_test_agent("BANK_A", 1_000_000, 0);
    let mut bank_b = create_test_agent("BANK_B", 1_000_000, 0);
    let mut bank_c = create_test_agent("BANK_C", 1_000_000, 0);

    let total_before = bank_a.balance() + bank_b.balance() + bank_c.balance();
    assert_eq!(total_before, 3_000_000);

    // A → B: 300k
    let mut tx1 = create_test_transaction("BANK_A", "BANK_B", 300_000, 0, 100);
    payment_simulator_core_rs::settlement::try_settle(&mut bank_a, &mut bank_b, &mut tx1, 1)
        .unwrap();

    // B → C: 500k
    let mut tx2 = create_test_transaction("BANK_B", "BANK_C", 500_000, 0, 100);
    payment_simulator_core_rs::settlement::try_settle(&mut bank_b, &mut bank_c, &mut tx2, 2)
        .unwrap();

    // C → A: 200k
    let mut tx3 = create_test_transaction("BANK_C", "BANK_A", 200_000, 0, 100);
    payment_simulator_core_rs::settlement::try_settle(&mut bank_c, &mut bank_a, &mut tx3, 3)
        .unwrap();

    // Total must be conserved
    let total_after = bank_a.balance() + bank_b.balance() + bank_c.balance();
    assert_eq!(
        total_before, total_after,
        "Balance conserved across multiple settlements"
    );
}

// ============================================================================
// Tests to be implemented after queue processing
// ============================================================================

// Note: The following tests will be uncommented once we implement
// SimulationState and queue processing functions

/*
#[test]
fn test_submit_transaction_settles_immediately() {
    // Test will use submit_transaction() which attempts immediate settlement
}

#[test]
fn test_submit_transaction_queues_on_insufficient_liquidity() {
    // Test will verify transaction is added to rtgs_queue
}

#[test]
fn test_queue_retry_on_next_tick() {
    // Test process_queue() settling queued transaction after liquidity arrives
}

#[test]
fn test_queue_fifo_ordering() {
    // Test that queue processes in FIFO order
}

#[test]
fn test_drop_transaction_past_deadline() {
    // Test that queued transaction is dropped if past deadline
}
*/
