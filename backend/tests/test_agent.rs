//! Tests for Agent model
//!
//! Following TDD: Tests written BEFORE implementation.
//! CRITICAL: All money values are i64 (cents)

use payment_simulator_core_rs::Agent;

#[test]
fn test_agent_new() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    assert_eq!(agent.id(), "BANK_A");
    assert_eq!(agent.balance(), 1000000); // $10,000.00 in cents
    assert_eq!(agent.unsecured_cap(), 500000); // $5,000.00 in cents
}

#[test]
fn test_available_liquidity_positive_balance() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    // Available = balance + unsecured_cap
    assert_eq!(agent.available_liquidity(), 1500000);
}

#[test]
fn test_available_liquidity_zero_balance() {
    let mut agent = Agent::new("BANK_A".to_string(), 0);
    agent.set_unsecured_cap(500000);

    // Can use credit
    assert_eq!(agent.available_liquidity(), 500000);
}

#[test]
fn test_available_liquidity_negative_balance() {
    // Agent is using some credit
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);
    agent.debit(1200000).unwrap(); // Use $2,000 more than balance

    // Balance = -200000, unsecured_cap = 500000
    // Available = 500000 - 200000 = 300000
    assert_eq!(agent.balance(), -200000);
    assert_eq!(agent.available_liquidity(), 300000);
}

#[test]
fn test_can_pay_sufficient_balance() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    assert!(agent.can_pay(500000)); // Can pay $5,000
    assert!(agent.can_pay(1000000)); // Can pay exactly balance
    assert!(agent.can_pay(1500000)); // Can pay using all credit
}

#[test]
fn test_can_pay_insufficient_liquidity() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    // Total available = 1,500,000
    assert!(!agent.can_pay(1500001)); // Can't pay more than available
    assert!(!agent.can_pay(2000000)); // Can't pay $20,000
}

#[test]
fn test_debit_success() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);

    let result = agent.debit(300000); // Debit $3,000
    assert!(result.is_ok());
    assert_eq!(agent.balance(), 700000);
}

#[test]
fn test_debit_into_credit() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    // Debit more than balance but within credit limit
    let result = agent.debit(1200000);
    assert!(result.is_ok());
    assert_eq!(agent.balance(), -200000); // Negative = using credit
}

#[test]
fn test_debit_exceeds_liquidity() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    // Try to debit more than available liquidity
    let result = agent.debit(2000000);
    assert!(result.is_err());
    assert_eq!(agent.balance(), 1000000); // Balance unchanged
}

#[test]
fn test_credit_success() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);

    agent.credit(500000); // Credit $5,000
    assert_eq!(agent.balance(), 1500000);
}

#[test]
fn test_credit_from_negative_balance() {
    let mut agent = Agent::new("BANK_A".to_string(), -200000);

    agent.credit(300000); // Credit $3,000
    assert_eq!(agent.balance(), 100000); // Back to positive
}

#[test]
fn test_multiple_transactions() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);

    // Sequence of operations
    agent.debit(300000).unwrap(); // -$3,000 → 700,000
    agent.credit(200000); // +$2,000 → 900,000
    agent.debit(400000).unwrap(); // -$4,000 → 500,000
    agent.credit(100000); // +$1,000 → 600,000

    assert_eq!(agent.balance(), 600000);
}

#[test]
fn test_zero_amount_operations() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);

    agent.debit(0).unwrap();
    assert_eq!(agent.balance(), 1000000);

    agent.credit(0);
    assert_eq!(agent.balance(), 1000000);
}

#[test]
fn test_is_using_credit() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    assert!(!agent.is_using_credit());

    // Debit into negative
    agent.debit(1200000).unwrap();
    assert!(agent.is_using_credit());
}

#[test]
fn test_credit_used() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.set_unsecured_cap(500000);

    assert_eq!(agent.credit_used(), 0);

    // Debit into negative
    agent.debit(1200000).unwrap();
    assert_eq!(agent.credit_used(), 200000); // Using $2,000 of credit
}

#[test]
#[should_panic(expected = "amount must be positive")]
fn test_debit_negative_amount_panics() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    let _ = agent.debit(-100);
}

#[test]
#[should_panic(expected = "amount must be positive")]
fn test_credit_negative_amount_panics() {
    let mut agent = Agent::new("BANK_A".to_string(), 1000000);
    agent.credit(-100);
}
