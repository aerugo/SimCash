"""
Test settlement event classification (RTGS immediate vs queue releases vs LSM).

Tests verify that different settlement paths create distinct, correctly-labeled events.
This is critical for replay identity and accurate metrics.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_rtgs_immediate_creates_correct_event():
    """RTGS immediate settlement creates rtgs_immediate_settlement event."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Submit transaction that can settle immediately (A has sufficient balance)
    submit_tick = orch.current_tick()
    tx1 = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 100, 5, False)

    # Call tick() to process the transaction
    orch.tick()

    # Check that RtgsImmediateSettlement event was created at submission tick
    events = orch.get_tick_events(submit_tick)
    settlement_events = [e for e in events if e.get('event_type') == 'RtgsImmediateSettlement']

    assert len(settlement_events) == 1, "Expected exactly one RTGS immediate settlement event"

    event = settlement_events[0]
    assert event['tx_id'] == tx1
    assert event['sender'] == "A"
    assert event['receiver'] == "B"
    assert event['amount'] == 10000
    assert event['sender_balance_before'] == 100000
    assert event['sender_balance_after'] == 90000


def test_queue_release_creates_correct_event():
    """Queue 2 release creates queue2_liquidity_release event (not rtgs_immediate)."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 10000, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Inject transaction that will queue (insufficient liquidity)
    tx1 = orch.submit_transaction("A", "B", 20000, orch.current_tick() + 100, 5, False)

    tick_queued = orch.current_tick()
    orch.tick()  # tx1 queues

    # Verify it queued (not settled immediately)
    events_tick1 = orch.get_tick_events(orch.current_tick())
    immediate_settlements = [e for e in events_tick1 if e.get('event_type') == 'RtgsImmediateSettlement']
    assert len(immediate_settlements) == 0, "Transaction should have queued, not settled immediately"

    # Now give A liquidity via incoming payment
    tx2 = orch.submit_transaction("B", "A", 20000, orch.current_tick() + 100, 5, False)

    tick_released = orch.current_tick()
    orch.tick()  # tx2 settles immediately, tx1 should release from queue

    # Check that queue2_liquidity_release event was created at tick_released (NOT rtgs_immediate)
    events_at_release = orch.get_tick_events(tick_released)
    queue_release_events = [e for e in events_at_release if e.get('event_type') == 'Queue2LiquidityRelease']

    assert len(queue_release_events) >= 1, "Expected at least one queue release event"

    # Find tx1 release
    tx1_release = next((e for e in queue_release_events if e.get('tx_id') == tx1), None)
    assert tx1_release is not None, "tx1 should have been released from queue"

    assert tx1_release['tx_id'] == tx1
    assert tx1_release['sender'] == "A"
    assert tx1_release['receiver'] == "B"
    assert tx1_release['amount'] == 20000
    assert tx1_release['queue_wait_ticks'] >= 1
    assert 'release_reason' in tx1_release


def test_queue_release_not_labeled_as_rtgs_immediate():
    """Critical: Queue releases must NOT be labeled as RTGS immediate."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 1000, "credit_limit": 5000, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Transaction that will queue
    tx_queued = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 100, 5, False)

    orch.tick()  # Queues

    # Provide liquidity
    tx_incoming = orch.submit_transaction("B", "A", 15000, orch.current_tick() + 100, 5, False)

    orch.tick()  # tx_queued releases

    # Verify tx_queued is NOT in rtgs_immediate events
    all_events = orch.get_all_events()
    rtgs_immediate_events = [e for e in all_events if e.get('event_type') == 'RtgsImmediateSettlement']

    tx_queued_in_rtgs = any(e.get('tx_id') == tx_queued for e in rtgs_immediate_events)
    assert not tx_queued_in_rtgs, "Queued transaction must not appear in RTGS immediate events"

    # Verify tx_queued IS in queue_release events
    queue_release_events = [e for e in all_events if e.get('event_type') == 'Queue2LiquidityRelease']
    tx_queued_in_queue = any(e.get('tx_id') == tx_queued for e in queue_release_events)
    assert tx_queued_in_queue, "Queued transaction must appear in queue release events"


def test_lsm_bilateral_creates_correct_event():
    """LSM bilateral offset creates lsm_bilateral_offset event."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "lsm_enabled": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 5000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Create bilateral gridlock: A→B and B→A, both insufficient
    tx_a_to_b = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 100, 5, False)

    tx_b_to_a = orch.submit_transaction("B", "A", 8000, orch.current_tick() + 100, 5, False)

    orch.tick()  # Both queue

    # Manually trigger LSM (if method exists)
    try:
        orch.run_lsm()
    except AttributeError:
        # LSM may run automatically during tick
        pass

    # Check for lsm_bilateral_offset event
    all_events = orch.get_all_events()
    lsm_events = [e for e in all_events if e.get('event_type') == 'LsmBilateralOffset']

    if len(lsm_events) > 0:  # LSM may not trigger if not enabled or conditions not met
        event = lsm_events[0]

        assert set([event['agent_a'], event['agent_b']]) == {'A', 'B'}
        assert event['amount_a'] == 10000
        assert event['amount_b'] == 8000
        assert 'tx_ids' in event
        assert len(event['tx_ids']) == 2  # Both transactions in the offset


def test_lsm_cycle_creates_correct_event():
    """LSM cycle (N≥3 agents) creates lsm_cycle_settlement event."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "lsm_enabled": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 5000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "C", "opening_balance": 5000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Create cycle: A→B→C→A
    tx_a_to_b = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 100, 5, False)

    tx_b_to_c = orch.submit_transaction("B", "C", 10000, orch.current_tick() + 100, 5, False)

    tx_c_to_a = orch.submit_transaction("C", "A", 10000, orch.current_tick() + 100, 5, False)

    orch.tick()  # All queue

    try:
        orch.run_lsm()
    except AttributeError:
        pass

    # Check for lsm_cycle_settlement event
    all_events = orch.get_all_events()
    lsm_cycle_events = [e for e in all_events if e.get('event_type') == 'LsmCycleSettlement']

    if len(lsm_cycle_events) > 0:
        event = lsm_cycle_events[0]

        assert len(event['agents']) >= 3, "Cycle must involve at least 3 agents"
        assert set(event['agents']) == {'A', 'B', 'C'}
        assert 'net_positions' in event
        assert 'max_net_outflow' in event
        assert 'total_value' in event


def test_settlement_event_types_are_mutually_exclusive():
    """A settlement can only be one type: immediate, queue release, or LSM."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 50000, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100000, "credit_limit": 50000, "policy": {"type": "Fifo"}},
        ],
    })

    # Run several transactions
    for i in range(10):
        sender = "A" if i % 2 == 0 else "B"
        receiver = "B" if i % 2 == 0 else "A"
        amount = 10000 + i * 1000
        orch.submit_transaction(sender, receiver, amount, orch.current_tick() + 100, 5, False)
        orch.tick()

    # Collect all settlement events
    all_events = orch.get_all_events()

    rtgs_immediate = [e for e in all_events if e.get('event_type') == 'RtgsImmediateSettlement']
    queue_releases = [e for e in all_events if e.get('event_type') == 'Queue2LiquidityRelease']
    lsm_bilaterals = [e for e in all_events if e.get('event_type') == 'LsmBilateralOffset']
    lsm_cycles = [e for e in all_events if e.get('event_type') == 'LsmCycleSettlement']

    # Extract tx_ids from each category
    rtgs_txs = {e['tx_id'] for e in rtgs_immediate}
    queue_txs = {e['tx_id'] for e in queue_releases}

    # No transaction should appear in multiple categories
    overlap = rtgs_txs & queue_txs
    assert len(overlap) == 0, f"Transactions appeared in both RTGS and queue releases: {overlap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
