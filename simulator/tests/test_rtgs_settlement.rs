//! RTGS Settlement Engine Tests
//!
//! Tests for Phase 3: Basic RTGS settlement with central queue management.
//! Following TDD principles - these tests are written BEFORE implementation.

use payment_simulator_core_rs::{Agent, Transaction};

// ============================================================================
// Test Helpers
// ============================================================================

/// Create a test agent with given balance and unsecured overdraft capacity
fn create_test_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
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
    assert!(
        result.is_ok(),
        "Settlement should succeed with sufficient balance"
    );

    // Check balances updated correctly
    assert_eq!(sender.balance(), 500_000, "Sender should be debited");
    assert_eq!(receiver.balance(), 500_000, "Receiver should be credited");

    // Check transaction marked as settled
    assert!(
        transaction.is_fully_settled(),
        "Transaction should be fully settled"
    );
    assert_eq!(
        transaction.remaining_amount(),
        0,
        "Remaining amount should be 0"
    );
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
    assert_eq!(
        sender.balance(),
        300_000,
        "Sender balance should be unchanged"
    );
    assert_eq!(
        receiver.balance(),
        0,
        "Receiver balance should be unchanged"
    );

    // Transaction should still be pending
    assert!(
        !transaction.is_fully_settled(),
        "Transaction should not be settled"
    );
    assert_eq!(
        transaction.remaining_amount(),
        900_000,
        "Full amount still pending"
    );
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
    assert!(
        result2.is_err(),
        "Cannot settle already settled transaction"
    );

    // Balances should not change on second attempt
    assert_eq!(sender.balance(), 500_000, "No double debit");
    assert_eq!(receiver.balance(), 500_000, "No double credit");
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
// Queue Processing Tests (Phase 3a)
// ============================================================================

#[test]
fn test_submit_transaction_settles_immediately() {
    use payment_simulator_core_rs::{settlement::submit_transaction, SimulationState};

    // Setup: BANK_A has sufficient liquidity
    let agents = vec![
        create_test_agent("BANK_A", 1_000_000, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);

    // Submit transaction
    let result = submit_transaction(&mut state, tx, 5);

    // Should settle immediately
    assert!(
        matches!(
            result,
            Ok(payment_simulator_core_rs::settlement::SubmissionResult::SettledImmediately { .. })
        ),
        "Transaction should settle immediately with sufficient liquidity"
    );

    // Verify balances updated
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 500_000);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 500_000);

    // Verify queue is empty
    assert_eq!(
        state.queue_size(),
        0,
        "Queue should be empty after immediate settlement"
    );
}

#[test]
fn test_submit_transaction_queues_on_insufficient_liquidity() {
    use payment_simulator_core_rs::{settlement::submit_transaction, SimulationState};

    // Setup: BANK_A has insufficient liquidity
    let agents = vec![
        create_test_agent("BANK_A", 300_000, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_id = tx.id().to_string();

    // Submit transaction
    let result = submit_transaction(&mut state, tx, 5);

    // Should queue
    assert!(
        matches!(
            result,
            Ok(payment_simulator_core_rs::settlement::SubmissionResult::Queued { position: 1 })
        ),
        "Transaction should be queued when insufficient liquidity"
    );

    // Verify balances unchanged
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        300_000,
        "Sender balance should be unchanged"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        0,
        "Receiver balance should be unchanged"
    );

    // Verify transaction in queue
    assert_eq!(state.queue_size(), 1, "Queue should have 1 transaction");
    assert_eq!(
        state.rtgs_queue().get(0).unwrap(),
        &tx_id,
        "Transaction ID should be in queue"
    );

    // Verify transaction still pending
    let tx_state = state.get_transaction(&tx_id).unwrap();
    assert!(
        !tx_state.is_fully_settled(),
        "Transaction should not be settled"
    );
}

#[test]
fn test_queue_retry_on_next_tick() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Setup: BANK_A initially has insufficient liquidity
    let agents = vec![
        create_test_agent("BANK_A", 200_000, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx = create_test_transaction("BANK_A", "BANK_B", 500_000, 0, 100);
    let tx_id = tx.id().to_string();

    // Submit - should queue
    let result = submit_transaction(&mut state, tx, 5);
    assert!(matches!(
        result,
        Ok(payment_simulator_core_rs::settlement::SubmissionResult::Queued { .. })
    ));
    assert_eq!(state.queue_size(), 1);

    // Process queue - should not settle yet
    let process_result = process_queue(&mut state, 6);
    assert_eq!(
        process_result.settled_count, 0,
        "No settlements without liquidity"
    );
    assert_eq!(process_result.remaining_queue_size, 1, "Still queued");

    // Add liquidity to BANK_A
    state.get_agent_mut("BANK_A").unwrap().credit(300_000);
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 500_000);

    // Process queue again - should settle now
    let process_result2 = process_queue(&mut state, 7);
    assert_eq!(
        process_result2.settled_count, 1,
        "Transaction should settle after liquidity added"
    );
    assert_eq!(process_result2.settled_value, 500_000);
    assert_eq!(
        process_result2.remaining_queue_size, 0,
        "Queue should be empty"
    );

    // Verify balances
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        0,
        "BANK_A used all liquidity"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        500_000,
        "BANK_B received payment"
    );

    // Verify transaction settled
    assert!(
        state.get_transaction(&tx_id).unwrap().is_fully_settled(),
        "Transaction should be settled"
    );
}

#[test]
fn test_queue_fifo_ordering() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Setup: BANK_A has no liquidity initially
    let agents = vec![
        create_test_agent("BANK_A", 0, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Submit 3 transactions at different ticks (FIFO order)
    let tx1 = create_test_transaction("BANK_A", "BANK_B", 100_000, 1, 100);
    let tx2 = create_test_transaction("BANK_A", "BANK_B", 200_000, 2, 100);
    let tx3 = create_test_transaction("BANK_A", "BANK_B", 150_000, 3, 100);

    let tx1_id = tx1.id().to_string();
    let tx2_id = tx2.id().to_string();
    let tx3_id = tx3.id().to_string();

    // All should queue
    submit_transaction(&mut state, tx1, 1).unwrap();
    submit_transaction(&mut state, tx2, 2).unwrap();
    submit_transaction(&mut state, tx3, 3).unwrap();

    assert_eq!(state.queue_size(), 3, "All 3 transactions should be queued");

    // Add enough liquidity for first transaction only
    state.get_agent_mut("BANK_A").unwrap().credit(100_000);

    // Process queue - should settle tx1 (FIFO)
    let result = process_queue(&mut state, 4);

    assert_eq!(result.settled_count, 1, "Should settle 1 transaction");
    assert_eq!(result.settled_value, 100_000, "Should settle tx1's amount");
    assert_eq!(
        result.remaining_queue_size, 2,
        "2 transactions still queued"
    );

    // Verify FIFO: tx1 settled, tx2 and tx3 still pending
    assert!(
        state.get_transaction(&tx1_id).unwrap().is_fully_settled(),
        "tx1 (first in queue) should be settled"
    );
    assert!(
        !state.get_transaction(&tx2_id).unwrap().is_fully_settled(),
        "tx2 should still be pending"
    );
    assert!(
        !state.get_transaction(&tx3_id).unwrap().is_fully_settled(),
        "tx3 should still be pending"
    );

    // Verify queue order: tx2, tx3
    assert_eq!(
        state.rtgs_queue().get(0).unwrap(),
        &tx2_id,
        "tx2 should be first in queue"
    );
    assert_eq!(
        state.rtgs_queue().get(1).unwrap(),
        &tx3_id,
        "tx3 should be second in queue"
    );

    // Add more liquidity for next transaction
    state.get_agent_mut("BANK_A").unwrap().credit(200_000);

    // Process queue again - should settle tx2 next (FIFO)
    let result2 = process_queue(&mut state, 5);

    assert_eq!(result2.settled_count, 1, "Should settle 1 more transaction");
    assert_eq!(result2.settled_value, 200_000, "Should settle tx2's amount");
    assert_eq!(
        result2.remaining_queue_size, 1,
        "1 transaction still queued"
    );

    assert!(
        state.get_transaction(&tx2_id).unwrap().is_fully_settled(),
        "tx2 should now be settled"
    );
    assert!(
        !state.get_transaction(&tx3_id).unwrap().is_fully_settled(),
        "tx3 should still be pending"
    );
}

#[test]
fn test_mark_transaction_overdue_past_deadline() {
    // Phase 4: Transactions past deadline are marked overdue but remain settleable
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Setup: BANK_A has no liquidity
    let agents = vec![
        create_test_agent("BANK_A", 0, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Transaction with deadline at tick 10
    let tx = create_test_transaction("BANK_A", "BANK_B", 500_000, 1, 10);
    let tx_id = tx.id().to_string();

    // Submit - should queue
    submit_transaction(&mut state, tx, 1).unwrap();
    assert_eq!(state.queue_size(), 1);

    // Process queue before deadline (tick 9) - should remain queued
    let result = process_queue(&mut state, 9);
    assert_eq!(result.settled_count, 0, "No settlement without liquidity");
    assert_eq!(result.remaining_queue_size, 1, "Still queued");

    // Verify transaction not yet overdue
    let tx_state = state.get_transaction(&tx_id).unwrap();
    assert!(!tx_state.is_overdue(), "Should not be overdue yet");

    // Process queue past deadline (tick 11) - should mark overdue but NOT remove
    let result2 = process_queue(&mut state, 11);
    assert_eq!(result2.settled_count, 0, "No settlement without liquidity");
    assert_eq!(result2.remaining_queue_size, 1, "Should REMAIN in queue");

    // Verify transaction marked as overdue
    let tx_state = state.get_transaction(&tx_id).unwrap();
    assert!(tx_state.is_overdue(), "Transaction should be marked overdue");
    assert_eq!(state.queue_size(), 1, "Queue should still have 1 transaction");

    // Key behavior change: Even after deadline, transaction CAN settle with liquidity
    state.get_agent_mut("BANK_A").unwrap().credit(500_000);
    let result3 = process_queue(&mut state, 12);
    assert_eq!(
        result3.settled_count, 1,
        "Overdue transaction SHOULD settle when liquidity available"
    );
    assert_eq!(state.queue_size(), 0, "Queue should be empty after settlement");
}

// ============================================================================
// Liquidity Recycling Tests (Critical RTGS Feature)
// ============================================================================

#[test]
fn test_liquidity_recycling_enables_downstream_settlement() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Scenario: A→B→C payment chain
    // BANK_A: 500k (wants to send 500k to B)
    // BANK_B: 0 (wants to send 300k to C, queued until A→B settles)
    // BANK_C: 0
    let agents = vec![
        create_test_agent("BANK_A", 500_000, 0),
        create_test_agent("BANK_B", 0, 0),
        create_test_agent("BANK_C", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Create transactions
    let tx_ab = create_test_transaction("BANK_A", "BANK_B", 500_000, 1, 100);
    let tx_bc = create_test_transaction("BANK_B", "BANK_C", 300_000, 2, 100);

    let tx_ab_id = tx_ab.id().to_string();
    let tx_bc_id = tx_bc.id().to_string();

    // Submit B→C first (will queue - B has no liquidity)
    let result_bc = submit_transaction(&mut state, tx_bc, 1).unwrap();
    assert!(
        matches!(
            result_bc,
            payment_simulator_core_rs::settlement::SubmissionResult::Queued { .. }
        ),
        "B→C should queue (B has no initial liquidity)"
    );
    assert_eq!(state.queue_size(), 1);

    // Submit A→B (will settle immediately - A has liquidity)
    let result_ab = submit_transaction(&mut state, tx_ab, 2).unwrap();
    assert!(
        matches!(
            result_ab,
            payment_simulator_core_rs::settlement::SubmissionResult::SettledImmediately { .. }
        ),
        "A→B should settle immediately"
    );

    // Verify balances after A→B settlement
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 500_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 0);

    // Process queue - B now has 500k from A, can send 300k to C (liquidity recycling)
    let process_result = process_queue(&mut state, 3);

    assert_eq!(
        process_result.settled_count, 1,
        "B→C should settle using recycled liquidity from A"
    );
    assert_eq!(process_result.settled_value, 300_000);
    assert_eq!(process_result.remaining_queue_size, 0);

    // Verify final balances (liquidity recycled)
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 0);
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        200_000,
        "B keeps 200k after sending 300k from 500k received"
    );
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 300_000);

    // Verify both transactions settled
    assert!(state.get_transaction(&tx_ab_id).unwrap().is_fully_settled());
    assert!(state.get_transaction(&tx_bc_id).unwrap().is_fully_settled());
}

#[test]
fn test_liquidity_recycling_long_chain() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Longer chain: A→B→C→D with cascading settlements
    let agents = vec![
        create_test_agent("BANK_A", 1_000_000, 0),
        create_test_agent("BANK_B", 0, 0),
        create_test_agent("BANK_C", 0, 0),
        create_test_agent("BANK_D", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_test_transaction("BANK_A", "BANK_B", 1_000_000, 1, 100);
    let tx_bc = create_test_transaction("BANK_B", "BANK_C", 700_000, 2, 100);
    let tx_cd = create_test_transaction("BANK_C", "BANK_D", 400_000, 3, 100);

    // Submit downstream transactions first (will queue)
    submit_transaction(&mut state, tx_bc, 1).unwrap(); // Queues (B has no liquidity)
    submit_transaction(&mut state, tx_cd, 2).unwrap(); // Queues (C has no liquidity)
    assert_eq!(state.queue_size(), 2, "B→C and C→D queued");

    // Submit A→B (settles immediately)
    submit_transaction(&mut state, tx_ab, 3).unwrap();

    // Process queue - cascading settlements
    let result = process_queue(&mut state, 4);

    assert_eq!(result.settled_count, 2, "Both queued transactions settle");
    assert_eq!(result.settled_value, 1_100_000, "700k + 400k");
    assert_eq!(result.remaining_queue_size, 0);

    // Verify balances
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 300_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 300_000);
    assert_eq!(state.get_agent("BANK_D").unwrap().balance(), 400_000);
}

// ============================================================================
// Gridlock Scenarios (Critical for RTGS Stress Testing)
// ============================================================================

#[test]
fn test_gridlock_formation_circular_dependencies() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Classic gridlock: A→B, B→C, C→A with insufficient liquidity
    // Each bank has 100k but wants to send 500k
    let agents = vec![
        create_test_agent("BANK_A", 100_000, 0),
        create_test_agent("BANK_B", 100_000, 0),
        create_test_agent("BANK_C", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_test_transaction("BANK_A", "BANK_B", 500_000, 1, 100);
    let tx_bc = create_test_transaction("BANK_B", "BANK_C", 500_000, 2, 100);
    let tx_ca = create_test_transaction("BANK_C", "BANK_A", 500_000, 3, 100);

    // Submit all - all should queue (gridlock)
    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    assert_eq!(
        state.queue_size(),
        3,
        "All transactions queued - gridlock formed"
    );

    // Process queue - no settlements without liquidity injection
    let result = process_queue(&mut state, 4);

    assert_eq!(result.settled_count, 0, "Gridlock prevents any settlement");
    assert_eq!(result.remaining_queue_size, 3, "All still queued");

    // Verify balances unchanged (gridlock)
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 100_000);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 100_000);
    assert_eq!(state.get_agent("BANK_C").unwrap().balance(), 100_000);

    // Total system balance unchanged
    assert_eq!(state.total_balance(), 300_000);
}

#[test]
fn test_gridlock_resolution_via_liquidity_injection() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Four-bank ring: A→B, B→C, C→D, D→A
    let agents = vec![
        create_test_agent("BANK_A", 100_000, 0),
        create_test_agent("BANK_B", 100_000, 0),
        create_test_agent("BANK_C", 100_000, 0),
        create_test_agent("BANK_D", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_test_transaction("BANK_A", "BANK_B", 500_000, 1, 100);
    let tx_bc = create_test_transaction("BANK_B", "BANK_C", 500_000, 2, 100);
    let tx_cd = create_test_transaction("BANK_C", "BANK_D", 500_000, 3, 100);
    let tx_da = create_test_transaction("BANK_D", "BANK_A", 500_000, 4, 100);

    // Submit all - gridlock
    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_cd, 3).unwrap();
    submit_transaction(&mut state, tx_da, 4).unwrap();

    assert_eq!(state.queue_size(), 4, "Complete gridlock");

    // Process queue - no movement
    let result1 = process_queue(&mut state, 5);
    assert_eq!(result1.settled_count, 0, "Gridlock persists");

    // INTERVENTION: Inject liquidity to one bank
    state.get_agent_mut("BANK_A").unwrap().credit(400_000);
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        500_000,
        "A now has enough"
    );

    // Process queue - should trigger cascade via liquidity recycling
    let result2 = process_queue(&mut state, 6);

    assert_eq!(
        result2.settled_count, 4,
        "All 4 transactions settle via recycling"
    );
    assert_eq!(result2.remaining_queue_size, 0, "Queue cleared");

    // Verify final balances
    // Each bank started with 100k, sent 500k, received 500k
    // A injected extra 400k to break gridlock
    // Net: A has 500k (100k + 400k injection - 500k sent + 500k received)
    //      Others have 100k (100k - 500k sent + 500k received)
    assert_eq!(
        state.get_agent("BANK_A").unwrap().balance(),
        500_000,
        "A has 500k after injection and ring settlement"
    );
    assert_eq!(
        state.get_agent("BANK_B").unwrap().balance(),
        100_000,
        "B net zero (sent 500k, received 500k)"
    );
    assert_eq!(
        state.get_agent("BANK_C").unwrap().balance(),
        100_000,
        "C net zero (sent 500k, received 500k)"
    );
    assert_eq!(
        state.get_agent("BANK_D").unwrap().balance(),
        100_000,
        "D net zero (sent 500k, received 500k)"
    );

    // Total balance: original 400k + injected 400k = 800k
    assert_eq!(state.total_balance(), 800_000);
}

#[test]
fn test_partial_gridlock_resolution() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Scenario: A→B and B→A (bilateral gridlock), plus C→D (independent)
    let agents = vec![
        create_test_agent("BANK_A", 100_000, 0),
        create_test_agent("BANK_B", 100_000, 0),
        create_test_agent("BANK_C", 500_000, 0),
        create_test_agent("BANK_D", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    let tx_ab = create_test_transaction("BANK_A", "BANK_B", 500_000, 1, 100);
    let tx_ba = create_test_transaction("BANK_B", "BANK_A", 400_000, 2, 100);
    let tx_cd = create_test_transaction("BANK_C", "BANK_D", 500_000, 3, 100);

    let tx_cd_id = tx_cd.id().to_string();

    // Submit all
    submit_transaction(&mut state, tx_ab, 1).unwrap(); // Queues
    submit_transaction(&mut state, tx_ba, 2).unwrap(); // Queues
    let result_cd = submit_transaction(&mut state, tx_cd, 3).unwrap(); // Settles immediately

    // C→D settles (has liquidity), A↔B gridlocked
    assert!(matches!(
        result_cd,
        payment_simulator_core_rs::settlement::SubmissionResult::SettledImmediately { .. }
    ));
    assert_eq!(state.queue_size(), 2, "A↔B gridlocked");

    // Process queue - gridlock persists
    let result = process_queue(&mut state, 4);
    assert_eq!(
        result.settled_count, 0,
        "Bilateral gridlock not resolved without liquidity injection"
    );

    // Verify C→D settled, A↔B still pending
    assert!(state.get_transaction(&tx_cd_id).unwrap().is_fully_settled());
    assert_eq!(state.queue_size(), 2);

    // Note: In Phase 3b (LSM), bilateral offsetting would resolve A↔B gridlock
    // by netting: A sends net 100k to B (500k - 400k)
}

// ============================================================================
// Multiple Queue Processing Tests
// ============================================================================

#[test]
fn test_multiple_queue_processing_rounds() {
    use payment_simulator_core_rs::{
        settlement::{process_queue, submit_transaction},
        SimulationState,
    };

    // Test that queue processing works correctly over multiple ticks
    // with gradual liquidity arrival
    let agents = vec![
        create_test_agent("BANK_A", 0, 0),
        create_test_agent("BANK_B", 0, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Queue 5 transactions of 100k each
    let mut tx_ids = Vec::new();
    for i in 0..5 {
        let tx = create_test_transaction("BANK_A", "BANK_B", 100_000, i, 100);
        tx_ids.push(tx.id().to_string());
        submit_transaction(&mut state, tx, i).unwrap();
    }

    assert_eq!(state.queue_size(), 5, "All 5 transactions queued");

    // Process queue multiple times, adding liquidity gradually
    for round in 0..5 {
        // Add liquidity for one transaction
        state.get_agent_mut("BANK_A").unwrap().credit(100_000);

        // Process queue
        let result = process_queue(&mut state, 10 + round);

        assert_eq!(
            result.settled_count, 1,
            "Should settle 1 transaction in round {}",
            round
        );
        assert_eq!(result.remaining_queue_size, 4 - round, "Queue shrinking");

        // Verify progressive settlement (FIFO)
        for j in 0..=round {
            assert!(
                state
                    .get_transaction(&tx_ids[j])
                    .unwrap()
                    .is_fully_settled(),
                "tx{} should be settled after round {}",
                j,
                round
            );
        }
        for j in (round + 1)..5 {
            assert!(
                !state
                    .get_transaction(&tx_ids[j])
                    .unwrap()
                    .is_fully_settled(),
                "tx{} should still be pending after round {}",
                j,
                round
            );
        }
    }

    // Final state: all settled
    assert_eq!(state.queue_size(), 0, "Queue fully drained");
    assert_eq!(state.get_agent("BANK_A").unwrap().balance(), 0);
    assert_eq!(state.get_agent("BANK_B").unwrap().balance(), 500_000);
}
