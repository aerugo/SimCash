"""Unit test for Queue-2 explicit settlement events.

Tests that transactions settling from Queue-2 (RTGS queue) generate
distinct Queue2LiquidityRelease events that are visible and auditable in replay.
"""

import pytest


def test_queue2_settlement_generates_distinct_event():
    """
    GIVEN a transaction in Queue-2 that can now settle
    WHEN liquidity becomes available and queue processes
    THEN a distinct Queue2LiquidityRelease event should be emitted
    """
    from payment_simulator._core import Orchestrator

    config = {
        "seed": 12345,
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10000,  # $100 - insufficient for $500 payment
                "credit_limit": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100000,
                "credit_limit": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "arrival_configs": [],  # No automatic arrivals
        "cost_model": {
            "overdraft_bps_per_tick": 0.8,
            "delay_per_tick_bps": 0.01,
            "deadline_penalty_bps": 5.0,
            "eod_penalty": 100000,
            "collateral_cost_per_tick_bps": 0.0005,
            "overdue_delay_multiplier": 5,
        },
        "settlement_config": {
            "lsm_enabled": False,  # Disable LSM to isolate Queue-2 behavior
        },
    }

    orch = Orchestrator.new(config)

    # Submit a transaction that will queue (insufficient liquidity)
    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=50000,  # $500 - more than BANK_A's $100 balance
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Tick 0: Transaction should queue in Queue-2 (insufficient liquidity)
    orch.tick()

    tick0_events = orch.get_tick_events(0)
    queued_events = [e for e in tick0_events if e.get("event_type") == "QueuedRtgs"]
    assert len(queued_events) == 1, "Transaction should be queued in Queue-2"
    assert queued_events[0]["tx_id"] == tx_id

    # Verify tx is in Queue-2
    rtgs_queue = orch.get_rtgs_queue_contents()
    assert tx_id in rtgs_queue, f"TX {tx_id} should be in RTGS queue"

    # Add liquidity to BANK_A by submitting a transaction from BANK_B
    orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_A",
        amount=50000,  # Give BANK_A enough to settle
        deadline_tick=50,
        priority=10,  # High priority to settle immediately
        divisible=False,
    )

    # Tick 1: Transaction should settle from Queue-2
    orch.tick()

    tick1_events = orch.get_tick_events(1)

    # ASSERTION: Expect distinct Queue2LiquidityRelease event (not generic Settlement)
    queue2_settle_events = [e for e in tick1_events if e.get("event_type") == "Queue2LiquidityRelease"]

    assert len(queue2_settle_events) == 1, (
        f"Expected 1 Queue2LiquidityRelease event for Queue-2 settlement, "
        f"but got {len(queue2_settle_events)}. "
        f"Available events: {[e.get('event_type') for e in tick1_events]}"
    )

    settle_event = queue2_settle_events[0]

    # Verify event has all required fields
    assert settle_event["tx_id"] == tx_id
    assert settle_event["sender"] == "BANK_A"
    assert settle_event["receiver"] == "BANK_B"
    assert settle_event["amount"] == 50000
    assert "release_reason" in settle_event, "Event should explain why it settled (liquidity_restored, etc.)"
    assert "queue_wait_ticks" in settle_event, "Event should track how long transaction waited in queue"

    # Verify tx is NO LONGER in Queue-2
    rtgs_queue_after = orch.get_rtgs_queue_contents()
    assert tx_id not in rtgs_queue_after, f"TX {tx_id} should be removed from RTGS queue after settlement"


def test_queue2_drop_at_deadline():
    """
    GIVEN a transaction in Queue-2 that passes its deadline
    WHEN the deadline tick arrives with no liquidity
    THEN a RtgsQueue2DropDeadline event should be emitted

    NOTE: This test may fail if the system design doesn't support drops.
    Current design: Transactions become "overdue" but stay in queue.
    This test documents the IDEAL behavior per Issue #2.
    """
    pytest.skip("System currently marks transactions overdue rather than dropping them. "
                "This test documents intended behavior if drop logic is added.")


def test_settlement_event_still_emitted():
    """
    GIVEN a transaction settling from Queue-2
    WHEN Queue2LiquidityRelease event is emitted
    THEN a generic Settlement event should ALSO be emitted for compatibility

    (Ensures backward compatibility with existing metrics/analysis that rely on Settlement events)
    """
    from payment_simulator._core import Orchestrator

    config = {
        "seed": 12345,
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10000,
                "credit_limit": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100000,
                "credit_limit": 0,
                "collateral_pool": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "arrival_configs": [],
        "cost_model": {
            "overdraft_bps_per_tick": 0.8,
            "delay_per_tick_bps": 0.01,
            "deadline_penalty_bps": 5.0,
            "eod_penalty": 100000,
            "collateral_cost_per_tick_bps": 0.0005,
            "overdue_delay_multiplier": 5,
        },
        "settlement_config": {
            "lsm_enabled": False,
        },
    }

    orch = Orchestrator.new(config)

    tx_id = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=50000,
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    orch.tick()  # Tick 0: Queue

    # Transfer funds to BANK_A to enable settlement
    # The transaction settles in the same tick as it arrives and then triggers queue processing
    orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_A",
        amount=50000,
        deadline_tick=55,
        priority=5,
        divisible=False,
    )
    orch.tick()  # Tick 1: Process transfer and settle queued transaction

    tick1_events = orch.get_tick_events(1)

    # Should have BOTH events
    settlement_events = [e for e in tick1_events if e.get("event_type") == "Settlement"]
    queue2_settle_events = [e for e in tick1_events if e.get("event_type") == "Queue2LiquidityRelease"]

    assert len(settlement_events) >= 1, "Generic Settlement event should still exist for compatibility"
    assert len(queue2_settle_events) == 1, "Queue2LiquidityRelease event should also exist for audit trail"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
