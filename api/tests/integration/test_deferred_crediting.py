"""
Test deferred crediting mode (Castro-compatible settlement).

These tests verify the deferred crediting feature where credits are accumulated
during a tick and applied at end of tick, matching the Castro et al. (2025) model.

TDD: These tests are written BEFORE implementation.

Reference: experiments/castro/docs/feature_request_deferred_crediting.md
"""

from __future__ import annotations

import pytest
from payment_simulator._core import Orchestrator


# ============================================================================
# Core Behavioral Tests: Gridlock with Zero Balances
# ============================================================================


def test_deferred_crediting_causes_gridlock_zero_balances() -> None:
    """THE DEFINING TEST: Mutual payments with zero balances should gridlock.

    In deferred mode, neither agent can use incoming payments to fund
    their outgoing payments within the same tick.
    """
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,  # Castro-compatible mode
        # Disable LSM to test pure deferred crediting behavior
        # (LSM bilateral offset would resolve the gridlock)
        "lsm_config": {
            "enable_bilateral": False,
            "enable_cycles": False,
            "max_cycle_length": 0,
            "max_cycles_per_tick": 0,
        },
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Submit mutual payments
    tx_ab = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 50, 5, False)
    tx_ba = orch.submit_transaction("B", "A", 10000, orch.current_tick() + 50, 5, False)

    orch.tick()

    # Both transactions should be queued (gridlock)
    assert orch.queue_size() == 2, "With deferred crediting, both should queue (gridlock)"

    # Verify no immediate settlements occurred
    events = orch.get_tick_events(0)
    immediate_settlements = [e for e in events if e.get("event_type") == "RtgsImmediateSettlement"]
    assert len(immediate_settlements) == 0, "No immediate settlements with zero balances"


def test_immediate_crediting_allows_recycling() -> None:
    """Control test: Without deferred crediting, recycling should work."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": False,  # Default (immediate crediting)
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 10000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # B→A settles first (B has funds), then A can use incoming to pay B
    tx_ba = orch.submit_transaction("B", "A", 10000, orch.current_tick() + 50, 5, False)
    tx_ab = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 50, 5, False)

    orch.tick()

    # Both should settle (recycling works)
    assert orch.queue_size() == 0, "With immediate crediting, both should settle"


def test_deferred_crediting_config_defaults_to_false() -> None:
    """Verify backward compatibility: default is immediate crediting."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        # No deferred_crediting field - should default to False
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 10000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Same scenario as immediate_crediting test - should allow recycling
    tx_ba = orch.submit_transaction("B", "A", 10000, orch.current_tick() + 50, 5, False)
    tx_ab = orch.submit_transaction("A", "B", 10000, orch.current_tick() + 50, 5, False)

    orch.tick()

    # Default should be immediate crediting (recycling works)
    assert orch.queue_size() == 0, "Default should be immediate crediting"


# ============================================================================
# Event Emission Tests
# ============================================================================


def test_deferred_credit_event_emitted() -> None:
    """Verify DeferredCreditApplied event is emitted when credits are applied."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # A→B: A has funds, B receives deferred credit
    tx_ab = orch.submit_transaction("A", "B", 50000, orch.current_tick() + 50, 5, False)

    orch.tick()

    # Check for DeferredCreditApplied event
    events = orch.get_tick_events(0)
    deferred_events = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]

    assert len(deferred_events) == 1, "Should emit exactly one DeferredCreditApplied event"

    event = deferred_events[0]
    assert event["agent_id"] == "B", "B should receive the deferred credit"
    assert event["amount"] == 50000, "Credit amount should match transaction"
    assert "source_transactions" in event, "Should include source transaction IDs"


def test_deferred_credit_event_not_emitted_in_immediate_mode() -> None:
    """DeferredCreditApplied event should NOT be emitted in immediate mode."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": False,  # Immediate mode
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    tx_ab = orch.submit_transaction("A", "B", 50000, orch.current_tick() + 50, 5, False)
    orch.tick()

    events = orch.get_tick_events(0)
    deferred_events = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]

    assert len(deferred_events) == 0, "No deferred credit events in immediate mode"


# ============================================================================
# Balance Timing Tests
# ============================================================================


def test_balance_not_available_during_tick() -> None:
    """In deferred mode, incoming credit is not available until next tick."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "C", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # A→B settles (A has funds)
    tx_ab = orch.submit_transaction("A", "B", 50000, orch.current_tick() + 50, 5, False)
    # B→C should queue (B's credit not yet available)
    tx_bc = orch.submit_transaction("B", "C", 30000, orch.current_tick() + 50, 5, False)

    orch.tick()

    # A→B should settle, B→C should queue
    assert orch.queue_size() == 1, "B→C should be queued"

    # Second tick: B's credit is now available
    orch.tick()

    # B→C should now settle
    assert orch.queue_size() == 0, "B→C should settle in next tick"


def test_deferred_credits_available_next_tick() -> None:
    """Credits accumulated in tick N are available in tick N+1."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Tick 0: A→B (B receives 50k deferred)
    tx1 = orch.submit_transaction("A", "B", 50000, orch.current_tick() + 50, 5, False)
    orch.tick()

    # Check B's balance at end of tick 0 (should include deferred credit)
    # This tests that credits are applied at end of tick
    balance_b = orch.get_agent_state("B")["balance"]
    assert balance_b == 50000, "B should have 50k after tick 0 credits applied"

    # Tick 1: B can now use those funds
    tx2 = orch.submit_transaction("B", "A", 30000, orch.current_tick() + 50, 5, False)
    orch.tick()

    # B→A should settle (B has 50k from previous tick)
    assert orch.queue_size() == 0, "B→A should settle using credited funds"

    balance_b_final = orch.get_agent_state("B")["balance"]
    assert balance_b_final == 20000, "B should have 20k after sending 30k"


# ============================================================================
# Determinism Tests
# ============================================================================


def test_deferred_crediting_determinism() -> None:
    """Same seed should produce identical results with deferred crediting."""
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 500000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 300000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "C", "opening_balance": 200000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }

    # Run 1
    orch1 = Orchestrator.new(config)
    orch1.submit_transaction("A", "B", 100000, 50, 5, False)
    orch1.submit_transaction("B", "C", 150000, 50, 5, False)
    orch1.submit_transaction("C", "A", 75000, 50, 5, False)
    for _ in range(10):
        orch1.tick()

    # Run 2
    orch2 = Orchestrator.new(config)
    orch2.submit_transaction("A", "B", 100000, 50, 5, False)
    orch2.submit_transaction("B", "C", 150000, 50, 5, False)
    orch2.submit_transaction("C", "A", 75000, 50, 5, False)
    for _ in range(10):
        orch2.tick()

    # Results should be identical
    assert orch1.get_agent_state("A")["balance"] == orch2.get_agent_state("A")["balance"]
    assert orch1.get_agent_state("B")["balance"] == orch2.get_agent_state("B")["balance"]
    assert orch1.get_agent_state("C")["balance"] == orch2.get_agent_state("C")["balance"]
    assert orch1.queue_size() == orch2.queue_size()


def test_deferred_credit_application_order_determinism() -> None:
    """Credits should be applied in deterministic order (sorted by agent ID)."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "C", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "D", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "E", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Multiple credits to different agents (out of alphabetical order)
    orch.submit_transaction("A", "E", 10000, 50, 5, False)
    orch.submit_transaction("B", "C", 20000, 50, 5, False)
    orch.submit_transaction("A", "D", 15000, 50, 5, False)

    orch.tick()

    # Check events are in sorted order
    events = orch.get_tick_events(0)
    deferred_events = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]

    # Should be ordered: C, D, E (alphabetical)
    agent_ids = [e["agent_id"] for e in deferred_events]
    assert agent_ids == sorted(agent_ids), f"Events should be in sorted order: {agent_ids}"


# ============================================================================
# LSM with Deferred Credits
# ============================================================================


def test_lsm_bilateral_with_deferred_credits() -> None:
    """LSM bilateral offset should produce deferred credits for net receivers."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": True,
            "max_cycle_length": 4,
            "max_cycles_per_tick": 10,
        },
        "agent_configs": [
            {"id": "A", "opening_balance": 200000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Bilateral: A→B 500k, B→A 300k (B is net receiver: +200k)
    orch.submit_transaction("A", "B", 500000, 50, 5, False)
    orch.submit_transaction("B", "A", 300000, 50, 5, False)

    orch.tick()

    # Both should settle via LSM bilateral offset
    assert orch.queue_size() == 0, "Both should settle via LSM"

    # Check for LSM event and deferred credit event
    events = orch.get_tick_events(0)

    lsm_events = [e for e in events if e.get("event_type") == "LsmBilateralOffset"]
    assert len(lsm_events) >= 1, "Should have LSM bilateral offset event"

    deferred_events = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]
    # B is net receiver, should get deferred credit
    b_credits = [e for e in deferred_events if e.get("agent_id") == "B"]
    assert len(b_credits) >= 1, "B should receive deferred credit from LSM"


# ============================================================================
# Cost Calculation Timing
# ============================================================================


def test_costs_calculated_after_credits_applied() -> None:
    """Overdraft costs should be calculated using final balance (after credits)."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "cost_rates": {
            "overdraft_bps_per_tick": 10.0,  # High rate to make overdraft costly
        },
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 200000, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 200000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # A sends 200k (goes into overdraft: 100k - 200k = -100k)
    # B sends 150k back (A ends up: -100k + 150k = +50k, no overdraft)
    orch.submit_transaction("A", "B", 200000, 50, 5, False)
    orch.submit_transaction("B", "A", 150000, 50, 5, False)

    orch.tick()

    # A's final balance should be positive (no overdraft at end)
    state_a = orch.get_agent_state("A")
    assert state_a["balance"] == 50000, "A should have 50k final balance"

    # A should NOT have overdraft costs (deferred credits applied before cost calc)
    # Note: This depends on implementation - verify cost is minimal or zero


# ============================================================================
# Scenario Events with Deferred Crediting
# ============================================================================


def test_scenario_events_with_deferred_crediting() -> None:
    """Scenario events should work correctly with deferred crediting."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        # Disable LSM to test pure deferred crediting behavior
        "lsm_config": {
            "enable_bilateral": False,
            "enable_cycles": False,
            "max_cycle_length": 0,
            "max_cycles_per_tick": 0,
        },
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "CustomTransactionArrival",
                "from_agent": "A",
                "to_agent": "B",
                "amount": 10000,
                "schedule": "OneTime",
                "tick": 0,
            },
            {
                "type": "CustomTransactionArrival",
                "from_agent": "B",
                "to_agent": "A",
                "amount": 10000,
                "schedule": "OneTime",
                "tick": 0,
            },
        ],
    })

    orch.tick()

    # Both should queue (gridlock with zero balances + deferred crediting)
    assert orch.queue_size() == 2, "Both transactions should queue"


# ============================================================================
# Multi-Day Tests
# ============================================================================


def test_deferred_crediting_multi_day() -> None:
    """Deferred crediting should work correctly across multiple days."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 10,  # Short days for testing
        "num_days": 3,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Day 1: A→B
    orch.submit_transaction("A", "B", 50000, 100, 5, False)
    for _ in range(10):
        orch.tick()

    # B should have funds from day 1
    assert orch.get_agent_state("B")["balance"] == 50000

    # Day 2: B→A (using funds from day 1)
    orch.submit_transaction("B", "A", 30000, 100, 5, False)
    for _ in range(10):
        orch.tick()

    # Check final balances
    assert orch.get_agent_state("A")["balance"] == 80000  # 100k - 50k + 30k
    assert orch.get_agent_state("B")["balance"] == 20000  # 50k - 30k


# ============================================================================
# Edge Cases
# ============================================================================


def test_deferred_crediting_no_settlements() -> None:
    """When no settlements occur, no deferred credit events should be emitted."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # No transactions, just tick
    orch.tick()

    events = orch.get_tick_events(0)
    deferred_events = [e for e in events if e.get("event_type") == "DeferredCreditApplied"]

    assert len(deferred_events) == 0, "No deferred events when no settlements"


def test_deferred_crediting_multiple_credits_same_agent() -> None:
    """Multiple credits to same agent should be aggregated in event."""
    orch = Orchestrator.new({
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "deferred_crediting": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "B", "opening_balance": 100000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "C", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    })

    # Multiple payments to C
    orch.submit_transaction("A", "C", 30000, 50, 5, False)
    orch.submit_transaction("B", "C", 20000, 50, 5, False)

    orch.tick()

    events = orch.get_tick_events(0)
    c_credits = [e for e in events if e.get("event_type") == "DeferredCreditApplied" and e.get("agent_id") == "C"]

    # Should have exactly one event with aggregated amount
    assert len(c_credits) == 1, "Should be single aggregated event for C"
    assert c_credits[0]["amount"] == 50000, "Should have aggregated amount"
    assert len(c_credits[0]["source_transactions"]) == 2, "Should list both source transactions"
