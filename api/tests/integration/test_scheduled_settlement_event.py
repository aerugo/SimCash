"""TDD Tests for ScheduledSettlement scenario event.

ScheduledSettlement creates a transaction AND immediately settles it via RTGS.
This differs from:
- DirectTransfer: bypasses RTGS (just balance adjustment)
- CustomTransactionArrival: creates pending transaction that waits for settlement

This event is critical for bootstrap evaluation where we need incoming liquidity
"beats" to go through the real RTGS engine, not bypass it.

RED PHASE: Tests written BEFORE implementation.
"""

import pytest
from payment_simulator._core import Orchestrator


# ===========================================================================
# Core Functionality Tests
# ===========================================================================


def test_scheduled_settlement_settles_at_exact_tick() -> None:
    """ScheduledSettlement must settle at exactly the specified tick.

    Unlike CustomTransactionArrival (which creates pending transaction),
    ScheduledSettlement creates AND settles in the same tick.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,  # $100,000
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 100_000,  # $1,000.00
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run ticks 0-4: nothing should happen yet
    for _ in range(5):
        orch.tick()

    # Verify TARGET still has 0 balance before tick 5
    target_balance = orch.get_agent_balance("TARGET")
    assert target_balance == 0, "TARGET should have $0 before tick 5"

    # Tick 5: ScheduledSettlement fires and settles
    orch.tick()

    # Verify settlement occurred at tick 5
    target_balance = orch.get_agent_balance("TARGET")
    assert target_balance == 100_000, f"TARGET should have $1,000 after tick 5, got {target_balance}"

    source_balance = orch.get_agent_balance("SOURCE")
    assert source_balance == 10_000_000 - 100_000, f"SOURCE should be debited $1,000"


def test_scheduled_settlement_produces_rtgs_event() -> None:
    """ScheduledSettlement must emit RtgsImmediateSettlement event.

    This proves the settlement goes through the real RTGS engine,
    not just a balance adjustment like DirectTransfer.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 5
    for _ in range(6):
        orch.tick()

    # Find RtgsImmediateSettlement event at tick 5
    all_events = orch.get_all_events()
    rtgs_events = [
        e
        for e in all_events
        if e.get("event_type") == "RtgsImmediateSettlement" and e.get("tick") == 5
    ]

    assert len(rtgs_events) == 1, (
        "Should emit exactly one RtgsImmediateSettlement at tick 5 "
        f"(proves RTGS engine was used). Found: {rtgs_events}"
    )

    event = rtgs_events[0]
    assert event["sender"] == "SOURCE"
    assert event["receiver"] == "TARGET"
    assert event["amount"] == 100_000


def test_scheduled_settlement_no_arrival_event() -> None:
    """ScheduledSettlement should NOT create an Arrival event.

    Unlike CustomTransactionArrival, there's no "pending" phase.
    The transaction is created and settled atomically.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run entire simulation
    for _ in range(20):
        orch.tick()

    # Should NOT have Arrival events from ScheduledSettlement
    all_events = orch.get_all_events()
    arrival_events = [e for e in all_events if e.get("event_type") == "Arrival"]

    assert len(arrival_events) == 0, (
        "ScheduledSettlement should NOT create Arrival events "
        f"(atomic create+settle). Found: {arrival_events}"
    )


# ===========================================================================
# Liquidity Constraint Tests
# ===========================================================================


def test_scheduled_settlement_respects_liquidity() -> None:
    """ScheduledSettlement must fail if sender lacks sufficient liquidity.

    Unlike DirectTransfer which can go negative, ScheduledSettlement
    uses the real RTGS engine which checks liquidity.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 100_000,  # Only $1,000
                "unsecured_cap": 0,  # No credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 500_000,  # $5,000 but SOURCE only has $1,000
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 6
    for _ in range(6):
        orch.tick()

    # TARGET should NOT receive funds (settlement failed)
    target_balance = orch.get_agent_balance("TARGET")
    assert target_balance == 0, (
        f"TARGET should not receive funds when SOURCE lacks liquidity, "
        f"got {target_balance}"
    )

    # SOURCE balance should be unchanged
    source_balance = orch.get_agent_balance("SOURCE")
    assert source_balance == 100_000, f"SOURCE should still have $1,000, got {source_balance}"


def test_scheduled_settlement_uses_credit_if_available() -> None:
    """ScheduledSettlement should use credit (unsecured_cap) if available."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 100_000,  # Only $1,000 cash
                "unsecured_cap": 500_000,  # But $5,000 credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 400_000,  # $4,000 (needs credit)
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 6
    for _ in range(6):
        orch.tick()

    # TARGET should receive funds (credit was available)
    target_balance = orch.get_agent_balance("TARGET")
    assert target_balance == 400_000, f"TARGET should have $4,000, got {target_balance}"

    # SOURCE should be negative (used credit)
    source_balance = orch.get_agent_balance("SOURCE")
    expected = 100_000 - 400_000  # -$3,000
    assert source_balance == expected, f"SOURCE should be at -$3,000, got {source_balance}"


# ===========================================================================
# Comparison Tests: ScheduledSettlement vs DirectTransfer vs CustomTransactionArrival
# ===========================================================================


def test_scheduled_settlement_vs_direct_transfer_event_logging() -> None:
    """ScheduledSettlement emits RTGS event; DirectTransfer does not.

    This is the key difference: DirectTransfer bypasses RTGS, while
    ScheduledSettlement goes through the real settlement engine.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            # DirectTransfer at tick 5
            {
                "type": "DirectTransfer",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 50_000,
                "schedule": "OneTime",
                "tick": 5,
            },
            # ScheduledSettlement at tick 10
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 50_000,
                "schedule": "OneTime",
                "tick": 10,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run entire simulation
    for _ in range(20):
        orch.tick()

    all_events = orch.get_all_events()

    # DirectTransfer at tick 5: should emit ScenarioEventExecuted, NOT RtgsImmediateSettlement
    tick5_rtgs = [
        e
        for e in all_events
        if e.get("event_type") == "RtgsImmediateSettlement" and e.get("tick") == 5
    ]
    assert len(tick5_rtgs) == 0, "DirectTransfer should NOT emit RtgsImmediateSettlement"

    # ScheduledSettlement at tick 10: SHOULD emit RtgsImmediateSettlement
    tick10_rtgs = [
        e
        for e in all_events
        if e.get("event_type") == "RtgsImmediateSettlement" and e.get("tick") == 10
    ]
    assert len(tick10_rtgs) == 1, "ScheduledSettlement SHOULD emit RtgsImmediateSettlement"


# ===========================================================================
# Schedule Tests
# ===========================================================================


def test_scheduled_settlement_repeating() -> None:
    """ScheduledSettlement supports repeating schedule."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 10_000,  # $100 per settlement
                "schedule": "Repeating",
                "start_tick": 5,
                "interval": 5,  # Every 5 ticks
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run entire simulation
    for _ in range(30):
        orch.tick()

    # Settlements at ticks 5, 10, 15, 20, 25 = 5 settlements
    all_events = orch.get_all_events()
    rtgs_events = [e for e in all_events if e.get("event_type") == "RtgsImmediateSettlement"]

    assert len(rtgs_events) == 5, f"Expected 5 settlements, got {len(rtgs_events)}"

    # Verify timing
    ticks = [e["tick"] for e in rtgs_events]
    assert ticks == [5, 10, 15, 20, 25], f"Expected ticks [5,10,15,20,25], got {ticks}"

    # Verify final balances
    target_balance = orch.get_agent_balance("TARGET")
    assert target_balance == 50_000, f"TARGET should have 5 * $100 = $500, got {target_balance}"


# ===========================================================================
# Determinism Tests (INV-2)
# ===========================================================================


def test_scheduled_settlement_determinism() -> None:
    """Same seed must produce identical results (INV-2: Determinism)."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,  # Fixed seed
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 5,
            },
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 200_000,
                "schedule": "OneTime",
                "tick": 10,
            },
        ],
    }

    def run_simulation() -> tuple[int, int, list[dict]]:  # type: ignore[type-arg]
        orch = Orchestrator.new(config)
        for _ in range(20):
            orch.tick()
        source_balance = orch.get_agent_balance("SOURCE")
        target_balance = orch.get_agent_balance("TARGET")
        events = orch.get_all_events()
        return (source_balance, target_balance, events)

    run1 = run_simulation()
    run2 = run_simulation()

    assert run1[0] == run2[0], "SOURCE balance must be deterministic"
    assert run1[1] == run2[1], "TARGET balance must be deterministic"
    assert len(run1[2]) == len(run2[2]), "Event count must be deterministic"


# ===========================================================================
# Event Logging Tests (Replay Identity)
# ===========================================================================


def test_scheduled_settlement_logs_scenario_event() -> None:
    """ScheduledSettlement should log ScenarioEventExecuted for replay identity."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 6
    for _ in range(6):
        orch.tick()

    all_events = orch.get_all_events()
    scenario_events = [e for e in all_events if e.get("event_type") == "ScenarioEventExecuted"]

    # Should have ScenarioEventExecuted for the ScheduledSettlement
    ss_events = [
        e for e in scenario_events if e.get("scenario_event_type") == "scheduled_settlement"
    ]
    assert len(ss_events) == 1, "Should log ScheduledSettlement as ScenarioEventExecuted"

    event = ss_events[0]
    assert event["tick"] == 5


# ===========================================================================
# Error Handling Tests
# ===========================================================================


def test_scheduled_settlement_invalid_agent() -> None:
    """ScheduledSettlement should fail for non-existent agents.

    Validation happens at event execution time, not config parsing time.
    """
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "NONEXISTENT",  # Agent doesn't exist
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    # Config parsing succeeds, but event execution fails at tick 5
    orch = Orchestrator.new(config)

    # Run until the event fires - should fail
    with pytest.raises(Exception):
        for _ in range(6):
            orch.tick()


def test_scheduled_settlement_requires_amount() -> None:
    """ScheduledSettlement requires amount field."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "SOURCE",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "TARGET",
                "opening_balance": 0,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "ScheduledSettlement",
                "from_agent": "SOURCE",
                "to_agent": "TARGET",
                # Missing: amount
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    with pytest.raises(Exception):
        Orchestrator.new(config)
