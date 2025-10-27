//! Tests for Transaction model
//!
//! Following TDD: Tests written BEFORE implementation.
//! CRITICAL: All money values are i64 (cents)

use payment_simulator_core_rs::{Transaction, TransactionStatus};

#[test]
fn test_transaction_new() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000, // $1,000.00
        10,     // arrival_tick
        50,     // deadline_tick
    );

    assert_eq!(tx.sender_id(), "BANK_A");
    assert_eq!(tx.receiver_id(), "BANK_B");
    assert_eq!(tx.amount(), 100000);
    assert_eq!(tx.remaining_amount(), 100000);
    assert_eq!(tx.arrival_tick(), 10);
    assert_eq!(tx.deadline_tick(), 50);
    assert_eq!(tx.status(), &TransactionStatus::Pending);
    assert_eq!(tx.priority(), 5); // Default priority
    assert!(!tx.is_divisible()); // Default not divisible
    assert!(!tx.id().is_empty()); // Should have a UUID
}

#[test]
fn test_transaction_with_priority() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .with_priority(8);

    assert_eq!(tx.priority(), 8);
}

#[test]
fn test_transaction_divisible() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    assert!(tx.is_divisible());
}

#[test]
fn test_transaction_builder_chain() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .with_priority(9)
    .divisible();

    assert_eq!(tx.priority(), 9);
    assert!(tx.is_divisible());
}

#[test]
fn test_transaction_settle_full() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    let result = tx.settle(100000, 20);
    assert!(result.is_ok());
    assert_eq!(tx.remaining_amount(), 0);
    assert_eq!(tx.status(), &TransactionStatus::Settled { tick: 20 });
    assert!(tx.is_fully_settled());
}

#[test]
fn test_transaction_settle_partial() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    // Settle 40% of transaction
    let result = tx.settle(40000, 20);
    assert!(result.is_ok());
    assert_eq!(tx.remaining_amount(), 60000);
    assert_eq!(
        tx.status(),
        &TransactionStatus::PartiallySettled {
            first_settlement_tick: 20
        }
    );
    assert!(!tx.is_fully_settled());
}

#[test]
fn test_transaction_settle_multiple_partials() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    // First partial settlement
    tx.settle(30000, 20).unwrap();
    assert_eq!(tx.remaining_amount(), 70000);
    assert_eq!(
        tx.status(),
        &TransactionStatus::PartiallySettled {
            first_settlement_tick: 20
        }
    );

    // Second partial settlement
    tx.settle(40000, 25).unwrap();
    assert_eq!(tx.remaining_amount(), 30000);
    // Status should still show first settlement tick
    assert_eq!(
        tx.status(),
        &TransactionStatus::PartiallySettled {
            first_settlement_tick: 20
        }
    );

    // Final settlement
    tx.settle(30000, 30).unwrap();
    assert_eq!(tx.remaining_amount(), 0);
    assert_eq!(tx.status(), &TransactionStatus::Settled { tick: 30 });
}

#[test]
fn test_transaction_settle_exceeds_remaining() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    // Try to settle more than remaining
    let result = tx.settle(150000, 20);
    assert!(result.is_err());
    assert_eq!(tx.remaining_amount(), 100000); // Unchanged
}

#[test]
fn test_transaction_settle_indivisible_partial() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    ); // Not divisible

    // Try to partially settle an indivisible transaction
    let result = tx.settle(50000, 20);
    assert!(result.is_err());
    assert_eq!(tx.remaining_amount(), 100000); // Unchanged
}

#[test]
fn test_transaction_drop() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    tx.drop_transaction(60);
    assert_eq!(tx.status(), &TransactionStatus::Dropped { tick: 60 });
}

#[test]
fn test_transaction_is_pending() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    assert!(tx.is_pending());
}

#[test]
fn test_transaction_is_past_deadline() {
    let tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50, // Deadline at tick 50
    );

    assert!(!tx.is_past_deadline(49));
    assert!(!tx.is_past_deadline(50)); // At deadline is OK
    assert!(tx.is_past_deadline(51)); // Past deadline
}

#[test]
fn test_transaction_settled_amount() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    assert_eq!(tx.settled_amount(), 0);

    tx.settle(30000, 20).unwrap();
    assert_eq!(tx.settled_amount(), 30000);

    tx.settle(40000, 25).unwrap();
    assert_eq!(tx.settled_amount(), 70000);
}

#[test]
fn test_transaction_zero_amount_fails() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    let result = tx.settle(0, 20);
    assert!(result.is_err());
}

#[test]
fn test_transaction_settle_already_settled() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    tx.settle(100000, 20).unwrap();

    // Try to settle again
    let result = tx.settle(1, 25);
    assert!(result.is_err());
}

#[test]
fn test_transaction_settle_dropped() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    tx.drop_transaction(40);

    // Try to settle a dropped transaction
    let result = tx.settle(100000, 50);
    assert!(result.is_err());
}

#[test]
fn test_transaction_status_transitions() {
    let mut tx = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    )
    .divisible();

    // Pending -> PartiallySettled
    assert_eq!(tx.status(), &TransactionStatus::Pending);
    tx.settle(40000, 20).unwrap();
    assert!(matches!(
        tx.status(),
        TransactionStatus::PartiallySettled { .. }
    ));

    // PartiallySettled -> Settled
    tx.settle(60000, 30).unwrap();
    assert!(matches!(tx.status(), TransactionStatus::Settled { .. }));
}

#[test]
fn test_transaction_with_id() {
    let tx1 = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    let tx2 = Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        10,
        50,
    );

    // IDs should be unique
    assert_ne!(tx1.id(), tx2.id());
}

#[test]
#[should_panic(expected = "deadline must be after arrival")]
fn test_transaction_invalid_deadline() {
    Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        100000,
        50, // arrival
        40, // deadline before arrival - should panic
    );
}

#[test]
#[should_panic(expected = "amount must be positive")]
fn test_transaction_negative_amount() {
    Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        -100000, // Negative amount - should panic
        10,
        50,
    );
}

#[test]
#[should_panic(expected = "amount must be positive")]
fn test_transaction_zero_initial_amount() {
    Transaction::new(
        "BANK_A".to_string(),
        "BANK_B".to_string(),
        0, // Zero amount - should panic
        10,
        50,
    );
}
