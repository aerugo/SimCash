"""
Castro-Specific Scenario Events Tests.

These tests verify that scenario events (CustomTransactionArrival) work
correctly for the Castro experiments:

1. Deterministic payment profiles are created as specified
2. Payment timing matches Castro paper exactly
3. Transaction amounts are in cents (i64)
4. Deadlines are correctly set (and capped at EOD)
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig


# ============================================================================
# Helper Functions
# ============================================================================


def _config_to_ffi(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw config dict to FFI-compatible format."""
    sim_config = SimulationConfig.from_dict(config_dict)
    return sim_config.to_ffi_dict()


# ============================================================================
# Experiment 1 Payment Profile Tests
# ============================================================================


class TestExp1PaymentProfile:
    """Test Experiment 1 payment profile matches Castro paper.

    Castro paper (Section 6.3):
    - Bank A: P^A = [0, $150] - No period 1 outgoing, $150 in period 2
    - Bank B: P^B = [$150, $50] - $150 in period 1, $50 in period 2
    """

    def test_bank_a_no_payment_period1(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Bank A should have no outgoing payment in period 1 (tick 0)."""
        orch = exp1_orchestrator

        # Run tick 0 (period 1)
        orch.tick()

        # Get arrivals at tick 0
        events = orch.get_tick_events(0)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        # Bank A outgoing arrivals at tick 0
        bank_a_arrivals = [
            a for a in arrivals if a.get("sender_id") == "BANK_A"
        ]

        assert len(bank_a_arrivals) == 0, (
            "Bank A should have no outgoing payment in period 1 (tick 0)"
        )

    def test_bank_a_150_payment_period2(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Bank A should have $150 outgoing in period 2 (tick 1)."""
        orch = exp1_orchestrator

        # Run ticks 0 and 1
        orch.tick()  # tick 0
        orch.tick()  # tick 1

        # Get arrivals at tick 1
        events = orch.get_tick_events(1)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        # Bank A outgoing at tick 1
        bank_a_arrivals = [
            a for a in arrivals if a.get("sender_id") == "BANK_A"
        ]

        assert len(bank_a_arrivals) == 1, (
            "Bank A should have exactly 1 outgoing payment in period 2"
        )
        assert bank_a_arrivals[0]["amount"] == 15000, (
            "Bank A's period 2 payment should be $150 (15000 cents)"
        )

    def test_bank_b_150_payment_period1(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Bank B should have $150 outgoing in period 1 (tick 0)."""
        orch = exp1_orchestrator

        # Run tick 0
        orch.tick()

        # Get arrivals at tick 0
        events = orch.get_tick_events(0)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        # Bank B outgoing at tick 0
        bank_b_arrivals = [
            a for a in arrivals if a.get("sender_id") == "BANK_B"
        ]

        # Should have $150 payment
        amount_150 = [a for a in bank_b_arrivals if a["amount"] == 15000]
        assert len(amount_150) == 1, (
            "Bank B should have $150 payment in period 1"
        )

    def test_bank_b_50_payment_period2(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Bank B should have $50 outgoing in period 2 (tick 1)."""
        orch = exp1_orchestrator

        # Run ticks 0 and 1
        orch.tick()  # tick 0
        orch.tick()  # tick 1

        # Get arrivals at tick 1
        events = orch.get_tick_events(1)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        # Bank B outgoing at tick 1
        bank_b_arrivals = [
            a for a in arrivals if a.get("sender_id") == "BANK_B"
        ]

        # Should have $50 payment
        amount_50 = [a for a in bank_b_arrivals if a["amount"] == 5000]
        assert len(amount_50) == 1, (
            "Bank B should have $50 payment in period 2"
        )


# ============================================================================
# Experiment 3 Symmetric Profile Tests
# ============================================================================


class TestExp3SymmetricProfile:
    """Test Experiment 3 symmetric payment profile.

    Castro paper (Section 8):
    - Both banks: P = [$200, $200, $0]
    """

    def test_symmetric_period1_payments(
        self, exp3_orchestrator: Orchestrator
    ) -> None:
        """Both banks should have $200 outgoing in period 1."""
        orch = exp3_orchestrator

        # Run tick 0
        orch.tick()

        events = orch.get_tick_events(0)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        bank_a_arrivals = [a for a in arrivals if a.get("sender_id") == "BANK_A"]
        bank_b_arrivals = [a for a in arrivals if a.get("sender_id") == "BANK_B"]

        # Both should have $200
        assert len(bank_a_arrivals) == 1
        assert bank_a_arrivals[0]["amount"] == 20000  # $200

        assert len(bank_b_arrivals) == 1
        assert bank_b_arrivals[0]["amount"] == 20000  # $200

    def test_symmetric_period2_payments(
        self, exp3_orchestrator: Orchestrator
    ) -> None:
        """Both banks should have $200 outgoing in period 2."""
        orch = exp3_orchestrator

        # Run ticks 0 and 1
        orch.tick()
        orch.tick()

        events = orch.get_tick_events(1)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        bank_a_arrivals = [a for a in arrivals if a.get("sender_id") == "BANK_A"]
        bank_b_arrivals = [a for a in arrivals if a.get("sender_id") == "BANK_B"]

        # Both should have $200
        assert len(bank_a_arrivals) == 1
        assert bank_a_arrivals[0]["amount"] == 20000

        assert len(bank_b_arrivals) == 1
        assert bank_b_arrivals[0]["amount"] == 20000

    def test_no_period3_payments(
        self, exp3_orchestrator: Orchestrator
    ) -> None:
        """No payments should arrive in period 3 (settlement only)."""
        orch = exp3_orchestrator

        # Run all 3 ticks
        orch.tick()  # tick 0
        orch.tick()  # tick 1
        orch.tick()  # tick 2

        events = orch.get_tick_events(2)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        assert len(arrivals) == 0, (
            "Period 3 should have no payment arrivals"
        )


# ============================================================================
# Transaction Amount Integrity Tests
# ============================================================================


class TestTransactionAmounts:
    """Verify transaction amounts are in cents (i64)."""

    def test_amounts_are_integers(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """All transaction amounts should be integers (cents)."""
        orch = exp1_orchestrator

        # Run full simulation
        orch.tick()
        orch.tick()

        events = orch.get_all_events()
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        for arrival in arrivals:
            amount = arrival["amount"]
            assert isinstance(amount, int), (
                f"Amount should be int, got {type(amount)}: {amount}"
            )
            assert amount > 0, "Amount should be positive"

    def test_no_float_contamination(
        self, exp1_orchestrator: Orchestrator
    ) -> None:
        """Verify no float values in financial calculations.

        This is a critical invariant (INV-1): Money is ALWAYS i64.
        """
        orch = exp1_orchestrator

        orch.tick()
        orch.tick()

        # Check agent balances
        for agent_id in ["BANK_A", "BANK_B"]:
            balance = orch.get_agent_balance(agent_id)
            assert isinstance(balance, int), (
                f"Balance should be int, got {type(balance)}"
            )

        # Check costs
        for agent_id in ["BANK_A", "BANK_B"]:
            costs = orch.get_agent_accumulated_costs(agent_id)
            for cost_type, value in costs.items():
                assert isinstance(value, int), (
                    f"Cost {cost_type} should be int, got {type(value)}: {value}"
                )


# ============================================================================
# Scenario Event Execution Timing Tests
# ============================================================================


class TestEventTiming:
    """Test that scenario events execute at correct ticks."""

    def test_events_execute_at_specified_tick(self) -> None:
        """Scenario events should execute at their specified tick."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 10000,
                    "schedule": {"type": "OneTime", "tick": 5},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run up to tick 5
        for tick in range(6):
            orch.tick()

            events = orch.get_tick_events(tick)
            arrivals = [e for e in events if e.get("event_type") == "Arrival"]

            if tick < 5:
                assert len(arrivals) == 0, f"No arrivals expected at tick {tick}"
            else:
                assert len(arrivals) == 1, f"1 arrival expected at tick {tick}"

    def test_multiple_events_same_tick(self) -> None:
        """Multiple events at same tick should all execute."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 10000,
                    "schedule": {"type": "OneTime", "tick": 3},
                },
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "B",
                    "to_agent": "A",
                    "amount": 20000,
                    "schedule": {"type": "OneTime", "tick": 3},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run to tick 3
        for _ in range(4):
            orch.tick()

        events = orch.get_tick_events(3)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        assert len(arrivals) == 2, "Both events should execute at tick 3"


# ============================================================================
# Deadline Assignment Tests
# ============================================================================


class TestDeadlineAssignment:
    """Test that deadlines are correctly assigned to transactions."""

    def test_explicit_deadline_used(self) -> None:
        """Transaction deadline from scenario event should be used."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "deadline_cap_at_eod": False,  # Don't cap for this test
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 10000,
                    "deadline": 7,  # Explicit deadline
                    "schedule": {"type": "OneTime", "tick": 2},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Run to tick 2
        for _ in range(3):
            orch.tick()

        events = orch.get_tick_events(2)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        assert len(arrivals) == 1
        # Deadline in Arrival event is absolute tick (arrival_tick + offset = 2 + 7 = 9)
        assert arrivals[0]["deadline"] == 9

    def test_deadline_capped_at_eod(self) -> None:
        """Deadline should be capped at EOD when feature enabled."""
        eod_tick = 9  # For 10 ticks/day

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 10,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,  # Enable cap
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 10000,
                    "deadline": 50,  # Beyond EOD
                    "schedule": {"type": "OneTime", "tick": 0},
                },
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        orch.tick()

        events = orch.get_tick_events(0)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        assert len(arrivals) == 1
        assert arrivals[0]["deadline"] <= eod_tick, (
            f"Deadline should be capped to EOD ({eod_tick})"
        )
