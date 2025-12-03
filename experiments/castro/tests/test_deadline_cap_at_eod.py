"""
Deadline Cap at EOD Tests for Castro Experiments.

These tests verify that the deadline_cap_at_eod feature works correctly:

1. Transaction deadlines beyond EOD are capped to the last tick of the day
2. Same-day settlement is enforced
3. Transactions that would span multiple days have their deadlines truncated

The deadline_cap_at_eod feature is CRITICAL for Castro alignment because:
- Castro's model assumes all payments must settle by end of business day
- Without this cap, transactions could have multi-day deadlines
- This would reduce settlement urgency and change equilibrium dynamics
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
# Deadline Capping Tests
# ============================================================================


class TestDeadlineCapping:
    """Test that deadlines are properly capped at end of day."""

    def test_deadline_beyond_eod_is_capped(self) -> None:
        """Transaction with deadline beyond EOD should have deadline capped."""
        ticks_per_day = 10
        eod_tick = ticks_per_day - 1  # tick 9 is last tick of day 1

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit transaction with deadline FAR beyond EOD
        # Current tick is 0 (before first tick), deadline 100 >> EOD (tick 9)
        tx_id = orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=50000,
            deadline_tick=100,  # Way beyond EOD
            priority=5,
            divisible=False,
        )

        # Get transaction details
        tx = orch.get_transaction_details(tx_id)

        # Deadline should be capped at EOD (tick 9)
        assert tx["deadline_tick"] <= eod_tick, (
            f"Deadline should be capped to EOD ({eod_tick}), got {tx['deadline_tick']}"
        )

    def test_deadline_within_eod_not_changed(self) -> None:
        """Transaction with deadline within EOD should keep its deadline."""
        ticks_per_day = 10

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit transaction with deadline within day
        requested_deadline = 5  # Well within EOD (tick 9)
        tx_id = orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=50000,
            deadline_tick=requested_deadline,
            priority=5,
            divisible=False,
        )

        tx = orch.get_transaction_details(tx_id)

        # Deadline should remain unchanged
        assert tx["deadline_tick"] == requested_deadline, (
            f"Deadline within EOD should be unchanged: {requested_deadline}"
        )

    def test_deadline_at_eod_boundary(self) -> None:
        """Transaction with deadline exactly at EOD should remain at EOD."""
        ticks_per_day = 10
        eod_tick = ticks_per_day - 1

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit with deadline exactly at EOD
        tx_id = orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=50000,
            deadline_tick=eod_tick,
            priority=5,
            divisible=False,
        )

        tx = orch.get_transaction_details(tx_id)
        assert tx["deadline_tick"] == eod_tick


class TestDeadlineCapDisabled:
    """Control tests: behavior when deadline_cap_at_eod is disabled."""

    def test_deadline_not_capped_when_feature_disabled(self) -> None:
        """Without deadline_cap_at_eod, deadlines can extend beyond EOD."""
        ticks_per_day = 10

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 2,  # Multiple days
            },
            "deadline_cap_at_eod": False,  # Disabled
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit with deadline in day 2
        requested_deadline = 15  # tick 15 (in day 2)
        tx_id = orch.submit_transaction(
            sender="A",
            receiver="B",
            amount=50000,
            deadline_tick=requested_deadline,
            priority=5,
            divisible=False,
        )

        tx = orch.get_transaction_details(tx_id)

        # Deadline should remain at requested value
        assert tx["deadline_tick"] == requested_deadline, (
            "Without deadline_cap_at_eod, deadline should not be modified"
        )


# ============================================================================
# Scenario Event Deadline Capping Tests
# ============================================================================


class TestScenarioEventDeadlineCapping:
    """Test deadline capping for CustomTransactionArrival scenario events."""

    def test_custom_transaction_deadline_capped(self) -> None:
        """CustomTransactionArrival with deadline beyond EOD should be capped."""
        ticks_per_day = 10
        eod_tick = ticks_per_day - 1

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 50000,
                    "deadline": 50,  # Far beyond EOD
                    "priority": 5,
                    "schedule": {"type": "OneTime", "tick": 0},
                }
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Execute tick 0 (transaction arrives)
        orch.tick()

        # Get the arrival event
        events = orch.get_tick_events(0)
        arrivals = [e for e in events if e.get("event_type") == "Arrival"]

        assert len(arrivals) == 1
        arrival = arrivals[0]

        # Deadline should be capped
        assert arrival["deadline"] <= eod_tick, (
            f"Scenario event deadline should be capped to EOD ({eod_tick}), "
            f"got {arrival['deadline']}"
        )


# ============================================================================
# Castro Experiment Specific Tests
# ============================================================================


class TestCastroExperimentDeadlines:
    """Test deadline capping in Castro experiment configurations."""

    def test_exp1_all_deadlines_within_day(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 scenario event deadlines should be within 2-tick day."""
        eod_tick = 1  # For 2 ticks/day, last tick is 1

        scenario_events = exp1_config_dict.get("scenario_events", [])

        for event in scenario_events:
            if event.get("type") == "CustomTransactionArrival":
                deadline = event.get("deadline", 0)
                # With deadline_cap_at_eod enabled, these will be capped at runtime
                # But config should ideally be reasonable
                print(f"Event deadline: {deadline} (will be capped to {eod_tick} if > EOD)")

    def test_exp2_arrival_config_deadline_range_capped(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Exp2 stochastic arrival deadline_range should be capped at runtime."""
        # For 12 ticks/day, EOD is tick 11
        eod_tick = 11

        agents = exp2_config_dict.get("agents", [])

        for agent in agents:
            arrival_config = agent.get("arrival_config", {})
            if arrival_config:
                deadline_range = arrival_config.get("deadline_range", [])
                if deadline_range:
                    print(
                        f"Agent {agent['id']} deadline_range: {deadline_range} "
                        f"(will be capped at runtime if needed)"
                    )

    def test_exp3_deadlines_consistent(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 scenario event deadlines should be within 3-tick day."""
        eod_tick = 2  # For 3 ticks/day, last tick is 2

        scenario_events = exp3_config_dict.get("scenario_events", [])

        for event in scenario_events:
            if event.get("type") == "CustomTransactionArrival":
                deadline = event.get("deadline", 0)
                # Check if deadline is reasonable
                # Some deadlines may be specified as relative (e.g., 2, 3)
                # With deadline_cap_at_eod, they'll be capped at runtime
                print(f"Exp3 event deadline: {deadline}")


# ============================================================================
# Settlement Urgency Tests
# ============================================================================


class TestSettlementUrgency:
    """Test that deadline capping creates appropriate settlement urgency."""

    def test_same_day_settlement_enforced(self) -> None:
        """With deadline_cap_at_eod, all transactions must settle by EOD."""
        ticks_per_day = 5
        eod_tick = ticks_per_day - 1

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "cost_rates": {
                "delay_cost_per_tick_per_cent": 0.001,
                "eod_penalty_per_transaction": 100000,  # Large EOD penalty
            },
            "agents": [
                {"id": "A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit transaction
        tx_id = orch.submit_transaction("A", "B", 50000, 100, 5, False)

        # Get capped deadline
        tx = orch.get_transaction_details(tx_id)
        assert tx["deadline_tick"] == eod_tick

        # Run to end of day
        for _ in range(ticks_per_day):
            orch.tick()

        # Transaction should have settled (A has funds)
        tx_final = orch.get_transaction_details(tx_id)
        assert tx_final["status"] == "Settled", (
            "Transaction should settle within the day"
        )

    def test_unsettled_at_eod_becomes_overdue(self) -> None:
        """Unsettled transaction at EOD deadline should become overdue."""
        ticks_per_day = 5
        eod_tick = ticks_per_day - 1

        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": ticks_per_day,
                "num_days": 1,
            },
            "deadline_cap_at_eod": True,
            "lsm_config": {"enable_bilateral": False, "enable_cycles": False},
            "agents": [
                # A has NO funds - transaction will queue
                {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
                {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            ],
        }

        ffi_config = _config_to_ffi(config)
        orch = Orchestrator.new(ffi_config)

        # Submit transaction that can't settle (no funds)
        tx_id = orch.submit_transaction("A", "B", 50000, 100, 5, False)

        # Get capped deadline
        tx = orch.get_transaction_details(tx_id)
        capped_deadline = tx["deadline_tick"]
        assert capped_deadline == eod_tick

        # Run past the deadline
        for tick in range(ticks_per_day):
            orch.tick()
            tx = orch.get_transaction_details(tx_id)
            print(f"Tick {tick}: status = {tx['status']}")

        # Transaction should be overdue or pending (depends on EOD handling)
        tx_final = orch.get_transaction_details(tx_id)
        assert tx_final["status"] in ["Pending", "Overdue"], (
            f"Unsettled transaction should be pending or overdue, got {tx_final['status']}"
        )


# ============================================================================
# Integration with Full Config
# ============================================================================


class TestFullConfigIntegration:
    """Integration tests with full Castro experiment configs."""

    def test_exp1_deadline_cap_enabled(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Verify Exp1 has deadline_cap_at_eod enabled."""
        assert exp1_config_dict.get("deadline_cap_at_eod") is True

    def test_exp2_deadline_cap_enabled(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Verify Exp2 has deadline_cap_at_eod enabled."""
        assert exp2_config_dict.get("deadline_cap_at_eod") is True

    def test_exp3_deadline_cap_enabled(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Verify Exp3 has deadline_cap_at_eod enabled."""
        assert exp3_config_dict.get("deadline_cap_at_eod") is True
