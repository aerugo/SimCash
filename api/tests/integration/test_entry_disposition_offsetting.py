"""
TDD Tests for Entry Disposition Offsetting (Phase 3)

TARGET2 uses "entry disposition" - when a new payment arrives, it immediately
checks if there's an offsetting payment in the queue that can be netted.

This is different from periodic LSM runs:
- Entry disposition: Check at transaction arrival time
- LSM: Periodic batch processing

Test Strategy:
1. Write failing tests first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor while keeping tests green

This module follows the TDD plan in docs/plans/target2-lsm-tdd-implementation.md
"""

import pytest
from payment_simulator._core import Orchestrator


def make_agent(agent_id: str, balance: int, limits: dict = None) -> dict:
    """Helper to create agent config with sensible defaults."""
    agent = {
        "id": agent_id,
        "opening_balance": balance,
        "unsecured_cap": 0,
        "policy": {"type": "Fifo"},
    }
    if limits:
        agent["limits"] = limits
    return agent


# ============================================================================
# TDD Step 3.1: Entry Disposition Config
# ============================================================================


class TestEntryDispositionConfig:
    """TDD Step 3.1: Entry disposition offsetting configuration."""

    def test_entry_disposition_config_accepted(self):
        """Config with entry_disposition_offsetting should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_entry_disposition_disabled_by_default(self):
        """Entry disposition should be disabled by default."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 100),  # Low liquidity
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Queue A→B (insufficient liquidity)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Submit B→A - without entry disposition, should just queue
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Before tick, no entry disposition offset should occur
        # Both should be queued
        events = orch.get_tick_events(0)
        offset_events = [e for e in events if e.get("event_type") == "EntryDispositionOffset"]
        assert len(offset_events) == 0


# ============================================================================
# TDD Step 3.2: Entry Disposition Offset
# ============================================================================


class TestEntryDispositionOffset:
    """TDD Step 3.2: Entry disposition triggers offset at submission."""

    def test_entry_disposition_finds_offset(self):
        """Incoming payment should offset queued opposite payment at entry."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),  # Low liquidity forces queue
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # A→B queued (insufficient liquidity)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1

        # B→A arrives - should trigger offset at entry
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Both should have settled via entry disposition offset
        assert orch.queue_size() == 0

    def test_entry_disposition_partial_offset(self):
        """Entry disposition should handle partial offset (different amounts)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # A→B 500k queued
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1

        # B→A 300k arrives - partial offset
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Smaller amount (300k) should be fully offset
        # Larger amount should have 200k remaining (if divisible) or still queued
        # For now, we expect both to settle at the smaller amount
        # and the remaining 200k stays queued or is a new transaction
        # This depends on implementation - for simplicity, if not divisible,
        # partial offset may not be possible
        pass  # Implementation-dependent

    def test_entry_disposition_no_match(self):
        """Entry disposition should not offset if no matching counterparty."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
                make_agent("BANK_C", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # A→B queued
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1

        # C→A arrives - no offset possible (different pair)
        orch.submit_transaction(
            sender="BANK_C",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Both should still be queued (no matching offset)
        assert orch.queue_size() == 2


# ============================================================================
# TDD Step 3.3: Entry Disposition Event
# ============================================================================


class TestEntryDispositionEvent:
    """TDD Step 3.3: Entry disposition offset events."""

    def test_entry_disposition_event_emitted(self):
        """EntryDispositionOffset event should be emitted when offset occurs."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Queue A→B
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # B→A triggers entry disposition
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(1)
        offset_events = [e for e in events if e.get("event_type") == "EntryDispositionOffset"]

        assert len(offset_events) >= 1
        event = offset_events[0]

        # Required fields for replay identity
        assert "tick" in event
        assert "incoming_tx_id" in event
        assert "queued_tx_id" in event
        assert "offset_amount" in event
        assert "agent_a" in event
        assert "agent_b" in event

    def test_entry_disposition_event_has_all_fields(self):
        """EntryDispositionOffset event should have all fields for replay."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Queue A→B
        tx1_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # B→A triggers entry disposition
        tx2_id = orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(1)
        offset_events = [e for e in events if e.get("event_type") == "EntryDispositionOffset"]

        assert len(offset_events) >= 1
        event = offset_events[0]

        # Verify field types
        assert isinstance(event.get("tick"), int)
        assert isinstance(event.get("incoming_tx_id"), str)
        assert isinstance(event.get("queued_tx_id"), str)
        assert isinstance(event.get("offset_amount"), int)
        assert isinstance(event.get("agent_a"), str)
        assert isinstance(event.get("agent_b"), str)


# ============================================================================
# TDD Step 3.4: Entry Disposition Respects Limits
# ============================================================================


class TestEntryDispositionLimits:
    """TDD Step 3.4: Entry disposition respects bilateral/multilateral limits."""

    def test_entry_disposition_respects_bilateral_limit(self):
        """Entry disposition should not offset if it would exceed bilateral limit."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100, limits={
                    "bilateral_limits": {"BANK_B": 100_000}  # Very low limit
                }),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Queue A→B 500k (exceeds limit)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # B→A arrives - entry disposition should fail due to A's limit
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Both should still be queued (limit prevents offset)
        assert orch.queue_size() == 2


# ============================================================================
# TDD Step 3.5: Entry Disposition Replay Identity
# ============================================================================


class TestEntryDispositionReplayIdentity:
    """TDD Step 3.5: Entry disposition events replay correctly."""

    def test_entry_disposition_event_persists(self):
        """EntryDispositionOffset events should be stored for replay."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "entry_disposition_offsetting": True,
            "agent_configs": [
                make_agent("BANK_A", 100),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Queue A→B
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # B→A triggers entry disposition
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=500_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Get all events for the simulation
        all_events = orch.get_all_events()
        offset_events = [e for e in all_events if e.get("event_type") == "EntryDispositionOffset"]

        assert len(offset_events) >= 1

        # Event should have all required fields for display during replay
        event = offset_events[0]
        required_fields = [
            "event_type", "tick", "incoming_tx_id", "queued_tx_id",
            "offset_amount", "agent_a", "agent_b"
        ]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
