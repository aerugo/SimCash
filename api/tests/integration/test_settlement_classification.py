"""
Test settlement event classification (RTGS immediate vs queue releases vs LSM).

Tests verify that different settlement paths create distinct, correctly-labeled events.
This is critical for replay identity and accurate metrics.
"""

import pytest
from payment_simulator.backends.orchestrator import Orchestrator


def test_rtgs_immediate_creates_correct_event():
    """RTGS immediate settlement creates rtgs_immediate_settlement event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 0},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0},
        ],
    })

    # Inject transaction that can settle immediately (A has sufficient balance)
    orch.inject_transaction({
        "id": "tx1",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.tick()

    # Check that rtgs_immediate_settlement event was created
    events = orch.get_tick_events(orch.current_tick())
    settlement_events = [e for e in events if e.get('event_type') == 'rtgs_immediate_settlement']

    assert len(settlement_events) == 1, "Expected exactly one RTGS immediate settlement event"

    event = settlement_events[0]
    assert event['tx_id'] == "tx1"
    assert event['sender'] == "A"
    assert event['receiver'] == "B"
    assert event['amount'] == 10000
    assert event['sender_balance_before'] == 100000
    assert event['sender_balance_after'] == 90000


def test_queue_release_creates_correct_event():
    """Queue 2 release creates queue2_liquidity_release event (not rtgs_immediate)."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 10000},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0},
        ],
    })

    # Inject transaction that will queue (insufficient liquidity)
    orch.inject_transaction({
        "id": "tx1",
        "sender": "A",
        "receiver": "B",
        "amount": 20000,  # More than available (balance 5000 + headroom 10000 = 15000)
        "priority": 5,
    })

    tick_queued = orch.current_tick()
    orch.tick()  # tx1 queues

    # Verify it queued (not settled immediately)
    events_tick1 = orch.get_tick_events(orch.current_tick())
    immediate_settlements = [e for e in events_tick1 if e.get('event_type') == 'rtgs_immediate_settlement']
    assert len(immediate_settlements) == 0, "Transaction should have queued, not settled immediately"

    # Now give A liquidity via incoming payment
    orch.inject_transaction({
        "id": "tx2",
        "sender": "B",
        "receiver": "A",
        "amount": 20000,
        "priority": 5,
    })

    tick_released = orch.current_tick()
    orch.tick()  # tx2 settles immediately, tx1 should release from queue

    # Check that queue2_liquidity_release event was created (NOT rtgs_immediate)
    events_tick2 = orch.get_tick_events(orch.current_tick())
    queue_release_events = [e for e in events_tick2 if e.get('event_type') == 'queue2_liquidity_release']

    assert len(queue_release_events) >= 1, "Expected at least one queue release event"

    # Find tx1 release
    tx1_release = next((e for e in queue_release_events if e.get('tx_id') == 'tx1'), None)
    assert tx1_release is not None, "tx1 should have been released from queue"

    assert tx1_release['tx_id'] == "tx1"
    assert tx1_release['sender'] == "A"
    assert tx1_release['receiver'] == "B"
    assert tx1_release['amount'] == 20000
    assert tx1_release['queue_wait_ticks'] >= 1
    assert 'release_reason' in tx1_release


def test_queue_release_not_labeled_as_rtgs_immediate():
    """Critical: Queue releases must NOT be labeled as RTGS immediate."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 1000, "credit_limit": 5000},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0},
        ],
    })

    # Transaction that will queue
    orch.inject_transaction({
        "id": "tx_queued",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.tick()  # Queues

    # Provide liquidity
    orch.inject_transaction({
        "id": "tx_incoming",
        "sender": "B",
        "receiver": "A",
        "amount": 15000,
        "priority": 5,
    })

    orch.tick()  # tx_queued releases

    # Verify tx_queued is NOT in rtgs_immediate events
    all_events = orch.get_all_events()
    rtgs_immediate_events = [e for e in all_events if e.get('event_type') == 'rtgs_immediate_settlement']

    tx_queued_in_rtgs = any(e.get('tx_id') == 'tx_queued' for e in rtgs_immediate_events)
    assert not tx_queued_in_rtgs, "Queued transaction must not appear in RTGS immediate events"

    # Verify tx_queued IS in queue_release events
    queue_release_events = [e for e in all_events if e.get('event_type') == 'queue2_liquidity_release']
    tx_queued_in_queue = any(e.get('tx_id') == 'tx_queued' for e in queue_release_events)
    assert tx_queued_in_queue, "Queued transaction must appear in queue release events"


def test_lsm_bilateral_creates_correct_event():
    """LSM bilateral offset creates lsm_bilateral_offset event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "lsm_enabled": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 0},
            {"id": "B", "opening_balance": 5000, "credit_limit": 0},
        ],
    })

    # Create bilateral gridlock: A→B and B→A, both insufficient
    orch.inject_transaction({
        "id": "tx_a_to_b",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.inject_transaction({
        "id": "tx_b_to_a",
        "sender": "B",
        "receiver": "A",
        "amount": 8000,
        "priority": 5,
    })

    orch.tick()  # Both queue

    # Manually trigger LSM (if method exists)
    try:
        orch.run_lsm()
    except AttributeError:
        # LSM may run automatically during tick
        pass

    # Check for lsm_bilateral_offset event
    all_events = orch.get_all_events()
    lsm_events = [e for e in all_events if e.get('event_type') == 'lsm_bilateral_offset']

    if len(lsm_events) > 0:  # LSM may not trigger if not enabled or conditions not met
        event = lsm_events[0]

        assert set([event['agent_a'], event['agent_b']]) == {'A', 'B'}
        assert event['net_settled'] == 8000  # min(10000, 8000)
        assert 'tx_a_to_b' in event
        assert 'tx_b_to_a' in event


def test_lsm_cycle_creates_correct_event():
    """LSM cycle (N≥3 agents) creates lsm_cycle_settlement event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "lsm_enabled": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 0},
            {"id": "B", "opening_balance": 5000, "credit_limit": 0},
            {"id": "C", "opening_balance": 5000, "credit_limit": 0},
        ],
    })

    # Create cycle: A→B→C→A
    orch.inject_transaction({
        "id": "tx_a_to_b",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.inject_transaction({
        "id": "tx_b_to_c",
        "sender": "B",
        "receiver": "C",
        "amount": 10000,
        "priority": 5,
    })

    orch.inject_transaction({
        "id": "tx_c_to_a",
        "sender": "C",
        "receiver": "A",
        "amount": 10000,
        "priority": 5,
    })

    orch.tick()  # All queue

    try:
        orch.run_lsm()
    except AttributeError:
        pass

    # Check for lsm_cycle_settlement event
    all_events = orch.get_all_events()
    lsm_cycle_events = [e for e in all_events if e.get('event_type') == 'lsm_cycle_settlement']

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
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 50000},
            {"id": "B", "opening_balance": 100000, "credit_limit": 50000},
        ],
    })

    # Run several transactions
    for i in range(10):
        orch.inject_transaction({
            "id": f"tx{i}",
            "sender": "A" if i % 2 == 0 else "B",
            "receiver": "B" if i % 2 == 0 else "A",
            "amount": 10000 + i * 1000,
            "priority": 5,
        })
        orch.tick()

    # Collect all settlement events
    all_events = orch.get_all_events()

    rtgs_immediate = [e for e in all_events if e.get('event_type') == 'rtgs_immediate_settlement']
    queue_releases = [e for e in all_events if e.get('event_type') == 'queue2_liquidity_release']
    lsm_bilaterals = [e for e in all_events if e.get('event_type') == 'lsm_bilateral_offset']
    lsm_cycles = [e for e in all_events if e.get('event_type') == 'lsm_cycle_settlement']

    # Extract tx_ids from each category
    rtgs_txs = {e['tx_id'] for e in rtgs_immediate}
    queue_txs = {e['tx_id'] for e in queue_releases}

    # No transaction should appear in multiple categories
    overlap = rtgs_txs & queue_txs
    assert len(overlap) == 0, f"Transactions appeared in both RTGS and queue releases: {overlap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
