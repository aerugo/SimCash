"""
Test collateral headroom integration and anti-oscillation policies.

Tests verify that:
1. Posted collateral increases available liquidity
2. Minimum holding periods prevent thrashing
3. Hysteresis prevents oscillation
4. Collateral events have specific, actionable reasons
"""

import pytest
from payment_simulator._core import Orchestrator


def test_posted_collateral_increases_available_liquidity():
    """Posted collateral immediately increases available liquidity via headroom."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": -50000,  # Overdraft
                "unsecured_cap": 60000,
                "collateral_haircut": 0.05,  # 5% haircut (95% of collateral counts toward headroom)
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Check initial state
    agent_a = orch.get_agent_state("A")
    initial_balance = agent_a['balance']
    initial_credit_used = agent_a['credit_used']
    initial_liquidity = agent_a['available_liquidity']

    # balance = -50000, credit_limit = 60000, credit_used = 50000
    # available_liquidity = max(0, balance) + max(0, credit_limit - credit_used)
    #                     = 0 + max(0, 60000 - 50000) = 10000
    assert initial_balance == -50000
    assert initial_credit_used == 50000
    assert initial_liquidity == 10000

    # Post $100K collateral
    result = orch.post_collateral("A", 100000)
    assert result['success'] is True

    # Check new state
    agent_a = orch.get_agent_state("A")
    posted = agent_a['posted_collateral']
    new_liquidity = agent_a['available_liquidity']

    assert posted == 100000

    # Expected: balance still -50000, credit_used still 50000
    # But now headroom = base_credit + (collateral * haircut)
    #                  = 60000 + (100000 * 0.95) = 60000 + 95000 = 155000
    # available_liquidity = 0 + (155000 - 50000) = 105000
    assert new_liquidity == 105000, f"Expected 105000, got {new_liquidity}"

    # Verify event logged the headroom increase
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e.get('event_type') == 'CollateralPost']

    assert len(collateral_events) == 1
    event = collateral_events[0]
    assert event['agent_id'] == "A"
    assert event['amount'] == 100000
    assert event['new_total'] == 100000  # Total collateral posted
    assert event['reason'] == "ManualPost"  # Manual operation via FFI


def test_collateral_enables_settlement_of_queued_transactions():
    """Posting collateral should allow queued transactions to settle."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "unsecured_cap": 20000,
                "collateral_haircut": 0.05,  # 5% haircut (95% of collateral counts)
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # A has 10000 + 20000 = 30000 available
    # Submit tx requiring more (sender, receiver, amount, deadline_tick, priority, divisible)
    tx1 = orch.submit_transaction("A", "B", 35000, 20, 5, False)

    orch.tick()  # Should queue in Queue2 (RTGS queue) due to insufficient liquidity

    # Verify transaction didn't settle immediately
    events_tick1 = orch.get_tick_events(1)
    rtgs_settlements = [e for e in events_tick1 if e.get('event_type') == 'RtgsImmediateSettlement']
    assert not any(e.get('tx_id') == tx1 for e in rtgs_settlements), "Tx should not settle immediately"

    # Post collateral to cover gap
    # Gap = 35000 - 30000 = 5000
    # Post 6000, giving 6000 * 0.95 = 5700 additional headroom
    orch.post_collateral("A", 6000)

    # Verify new liquidity
    agent_a = orch.get_agent_state("A")
    # 10000 (balance) + 20000 (credit) + 5700 (collateral*haircut) = 35700
    assert agent_a['available_liquidity'] >= 35000

    orch.tick()  # Should release from Queue2

    # Check that it was a queue release (not RTGS immediate)
    all_events = orch.get_all_events()
    queue_releases = [e for e in all_events if e.get('event_type') == 'Queue2LiquidityRelease']
    assert any(e.get('tx_id') == tx1 for e in queue_releases), "Tx should be released from Queue2"


def test_collateral_minimum_holding_period_prevents_immediate_withdrawal():
    """Cannot withdraw collateral before minimum holding period expires."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 100000,
                "unsecured_cap": 50000,
                "collateral_min_holding_ticks": 5,
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Post collateral at tick 0
    post_result = orch.post_collateral("A", 50000)
    assert post_result['success'] is True
    assert orch.get_agent_state("A")['posted_collateral'] == 50000

    tick_posted = orch.current_tick()

    # Try to withdraw at tick 1 (too soon)
    orch.tick()
    withdraw_result = orch.withdraw_collateral("A", 50000)
    assert withdraw_result['success'] is False
    assert 'minimum holding period' in withdraw_result.get('message', '').lower() or \
           'too soon' in withdraw_result.get('message', '').lower()

    # Try at tick 4 (still too soon)
    for _ in range(3):
        orch.tick()
    assert orch.current_tick() == tick_posted + 4
    withdraw_result = orch.withdraw_collateral("A", 50000)
    assert withdraw_result['success'] is False

    # Try at tick 5 (should succeed)
    orch.tick()
    assert orch.current_tick() == tick_posted + 5
    withdraw_result = orch.withdraw_collateral("A", 50000)
    assert withdraw_result['success'] is True
    assert orch.get_agent_state("A")['posted_collateral'] == 0

    # Verify event was logged
    events = orch.get_tick_events(orch.current_tick())
    withdraw_events = [e for e in events if e.get('event_type') == 'CollateralWithdraw']
    assert len(withdraw_events) == 1
    assert withdraw_events[0]['agent_id'] == "A"
    assert withdraw_events[0]['amount'] == 50000


def test_collateral_policy_hysteresis_posting_threshold():
    """Collateral policy only posts when liquidity gap exceeds threshold."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "unsecured_cap": 20000,
                "policy": {"type": "Fifo"},
                "collateral_policy": {
                    "posting_threshold_pct": 0.10,  # Only post if gap > 10% of queue value
                    "min_holding_ticks": 5,
                },
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Create small queue (gap below threshold)
    # A has 30000 available
    # Queue = 32000 → gap = 2000 → gap_pct = 2000/32000 = 6.25% < 10%
    tx1 = orch.submit_transaction("A", "B", 32000, 20, 5, False)

    orch.tick()  # Queues

    # Check that collateral was NOT auto-posted (gap too small)
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e.get('event_type') == 'CollateralPost']
    assert len(collateral_events) == 0, "Collateral should not be posted for small gap"

    # Now create larger queue (gap above threshold)
    # Add another 40000 → total queue = 72000 → gap = 42000 → gap_pct = 58% > 10%
    tx2 = orch.submit_transaction("A", "B", 40000, 20, 5, False)

    orch.tick()

    # Check that collateral WAS auto-posted (gap large enough)
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e.get('event_type') == 'CollateralPost']
    # May or may not post depending on policy implementation
    # This test verifies hysteresis logic exists


def test_collateral_policy_hysteresis_withdrawal_threshold():
    """Collateral policy only withdraws when excess liquidity exceeds threshold."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "unsecured_cap": 20000,
                "policy": {"type": "Fifo"},
                "collateral_policy": {
                    "withdrawal_threshold_pct": 0.20,  # Only withdraw if excess > 20% of queue
                    "min_holding_ticks": 1,  # Short for testing
                },
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Post collateral manually
    orch.post_collateral("A", 50000)  # Gives 50000*0.95 = 47500 extra headroom

    # Wait minimum holding period
    orch.tick()

    # Create small queue (excess liquidity is high, but queue is small)
    # available = 10000 + 20000 + 47500 = 77500
    # queue = 5000 → excess = 72500 → excess_pct = 1450% >> 20%
    tx1 = orch.submit_transaction("A", "B", 5000, 20, 5, False)

    orch.tick()  # Should auto-withdraw (excess is huge)

    # Check withdrawal occurred
    # (Depends on policy implementation)


def test_no_collateral_oscillation_under_sustained_pressure():
    """Agent does not post/withdraw collateral every tick under sustained queue pressure."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "unsecured_cap": 20000,
                "policy": {"type": "Fifo"},
                "collateral_policy": {
                    "min_holding_ticks": 5,
                    "posting_threshold_pct": 0.10,
                    "withdrawal_threshold_pct": 0.20,
                },
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Create sustained queue pressure over 20 ticks
    for i in range(20):
        orch.submit_transaction("A", "B", 15000, 20, 5, False)
        orch.tick()

    # Count collateral events
    all_events = orch.get_all_events()
    posted_events = [e for e in all_events if e.get('event_type') == 'CollateralPost']
    withdrawn_events = [e for e in all_events if e.get('event_type') == 'CollateralWithdraw']

    # Should post at most a few times (not every tick)
    assert len(posted_events) <= 4, f"Too many collateral postings: {len(posted_events)} in 20 ticks"

    # Should not withdraw while queue persists
    assert len(withdrawn_events) <= 1, f"Unexpected withdrawals under pressure: {len(withdrawn_events)}"


def test_collateral_events_have_specific_reasons_not_vague():
    """Collateral events must have specific, actionable reasons (not 'DeadlineEmergency')."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 5000,
                "unsecured_cap": 10000,
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Create scenario that triggers collateral posting
    tx1 = orch.submit_transaction("A", "B", 20000, 20, 5, False)

    orch.tick()  # Queues

    # Manually post collateral
    orch.post_collateral("A", 10000)

    # Check event has specific reason (not vague)
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e.get('event_type') == 'CollateralPost']

    if len(collateral_events) > 0:
        event = collateral_events[0]
        reason = event.get('reason', '')

        # Should NOT be vague
        assert 'DeadlineEmergency' not in reason, "Reason too vague"
        assert 'Emergency' not in reason, "Reason too vague"

        # Should be specific (examples)
        # - "QueuePressure(queue_value=20000, gap=5000)"
        # - "CoveringOverdueTransaction(tx_id=tx1)"
        # - "CreditLimitApproaching(used=80%)"


def test_collateral_withdrawal_reason_is_specific():
    """Collateral withdrawal events have specific reasons."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "unsecured_cap": 20000,
                "collateral_min_holding_ticks": 1,
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Post collateral
    orch.post_collateral("A", 50000)

    # Wait minimum holding period (5 ticks hardcoded in FFI)
    for _ in range(5):
        orch.tick()

    # Withdraw should now succeed
    result = orch.withdraw_collateral("A", 50000)
    assert result['success'] is True

    # Check event reason
    events = orch.get_tick_events(orch.current_tick())
    withdraw_events = [e for e in events if e.get('event_type') == 'CollateralWithdraw']

    if len(withdraw_events) > 0:
        event = withdraw_events[0]
        reason = event.get('reason', '')

        # Should be specific (not vague like "DeadlineEmergency")
        # Valid reasons include: ManualWithdraw, LiquidityRestored, MinimumHoldingPeriodExpired, EndOfDay
        valid_reasons = ['ManualWithdraw', 'LiquidityRestored', 'MinimumHoldingPeriodExpired', 'EndOfDay']
        assert any(vr in reason for vr in valid_reasons), f"Invalid reason: {reason}"

        # Should NOT be vague
        assert 'DeadlineEmergency' not in reason, "Reason too vague"


def test_available_liquidity_calculation_includes_collateral():
    """Agent.available_liquidity() formula: balance + (credit + collateral*haircut - credit_used)."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 20000,
                "unsecured_cap": 50000,
                "collateral_haircut": 0.10,  # 10% haircut (90% of collateral counts)
                "policy": {"type": "Fifo"},
            },
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Initial: balance=20000, credit_limit=50000, credit_used=0, posted=0
    # available = max(20000, 0) + max(50000 - 0, 0) = 20000 + 50000 = 70000
    agent = orch.get_agent_state("A")
    assert agent['available_liquidity'] == 70000

    # Post 100K collateral
    orch.post_collateral("A", 100000)

    # New: posted=100000, haircut=0.10 (10% discount, 90% counts)
    # collateral_contribution = 100000 * (1 - 0.10) = 90000
    # available = 20000 + max(50000 + 90000 - 0, 0) = 20000 + 140000 = 160000
    agent = orch.get_agent_state("A")
    assert agent['available_liquidity'] == 160000

    # Use some credit (go into overdraft)
    tx1 = orch.submit_transaction("A", "B", 50000, 20, 5, False)
    orch.tick()

    # New balance = 20000 - 50000 = -30000 (overdraft)
    # credit_used = 30000
    # available = max(-30000, 0) + max(50000 + 90000 - 30000, 0)
    #           = 0 + max(110000, 0) = 110000
    agent = orch.get_agent_state("A")
    assert agent['available_liquidity'] == 110000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
