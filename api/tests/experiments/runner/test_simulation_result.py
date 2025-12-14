"""Tests for SimulationResult dataclass.

Tests for the unified simulation result type that captures all output
from _run_simulation(). Following TDD - tests written before implementation.

All cost values must be integers (INV-1: Money is ALWAYS i64).
"""

from __future__ import annotations

from typing import Any

import pytest


class TestSimulationResult:
    """Tests for SimulationResult dataclass."""

    def test_create_simulation_result_with_all_fields(self) -> None:
        """Test creating SimulationResult with all required fields."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        result = SimulationResult(
            seed=12345,
            simulation_id="exp1-20251214-143022-a1b2c3-sim-001-init",
            total_cost=15000,  # $150.00 in cents
            per_agent_costs={"BANK_A": 7500, "BANK_B": 7500},
            events=({"event_type": "Arrival", "tick": 0},),
            cost_breakdown=CostBreakdown(
                delay_cost=5000,
                overdraft_cost=8000,
                deadline_penalty=2000,
                eod_penalty=0,
            ),
            settlement_rate=0.95,
            avg_delay=5.2,
        )

        assert result.seed == 12345
        assert result.simulation_id == "exp1-20251214-143022-a1b2c3-sim-001-init"
        assert result.total_cost == 15000
        assert result.per_agent_costs == {"BANK_A": 7500, "BANK_B": 7500}
        assert len(result.events) == 1
        assert result.settlement_rate == 0.95
        assert result.avg_delay == 5.2

    def test_simulation_result_is_frozen(self) -> None:
        """Test that SimulationResult is immutable."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        result = SimulationResult(
            seed=12345,
            simulation_id="test-sim-001",
            total_cost=10000,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0,
                overdraft_cost=0,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        with pytest.raises(AttributeError):
            result.total_cost = 20000  # type: ignore[misc]

    def test_costs_are_integer_cents(self) -> None:
        """Test that cost fields accept only integers (INV-1)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        result = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=10000,  # Must be int
            per_agent_costs={"A": 5000, "B": 5000},  # Must be int values
            events=(),
            cost_breakdown=CostBreakdown(
                delay_cost=1000,  # Must be int
                overdraft_cost=2000,
                deadline_penalty=3000,
                eod_penalty=4000,
            ),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # Verify types at runtime
        assert isinstance(result.total_cost, int)
        assert all(isinstance(v, int) for v in result.per_agent_costs.values())
        assert isinstance(result.cost_breakdown.delay_cost, int)

    def test_events_are_immutable_tuple(self) -> None:
        """Test that events are stored as immutable tuple."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        events_list: list[dict[str, Any]] = [{"tick": 0}, {"tick": 1}]
        result = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=0,
            per_agent_costs={},
            events=tuple(events_list),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # Events should be a tuple
        assert isinstance(result.events, tuple)
        # Modifying original list shouldn't affect result
        events_list.append({"tick": 2})
        assert len(result.events) == 2

    def test_cost_breakdown_total_property(self) -> None:
        """Test that CostBreakdown.total sums all costs."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        cost_breakdown = CostBreakdown(
            delay_cost=1000,
            overdraft_cost=2000,
            deadline_penalty=3000,
            eod_penalty=4000,
        )
        result = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=cost_breakdown.total,
            per_agent_costs={},
            events=(),
            cost_breakdown=cost_breakdown,
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # CostBreakdown.total should sum all components
        assert result.cost_breakdown.total == 10000  # 1000+2000+3000+4000

    def test_simulation_id_format(self) -> None:
        """Test that simulation_id follows expected format."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        # Format: {run_id}-sim-{counter:03d}-{purpose}
        sim_id = "exp1-20251214-143022-a1b2c3-sim-001-init"
        result = SimulationResult(
            seed=1,
            simulation_id=sim_id,
            total_cost=0,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        # Verify format components
        assert "-sim-" in result.simulation_id
        assert result.simulation_id.endswith("-init")

    def test_simulation_result_with_empty_events(self) -> None:
        """Test creating SimulationResult with no events."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        result = SimulationResult(
            seed=0,
            simulation_id="empty-sim",
            total_cost=0,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        assert result.events == ()
        assert len(result.events) == 0

    def test_simulation_result_with_multiple_agents(self) -> None:
        """Test creating SimulationResult with multiple agents."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        per_agent_costs = {
            "BANK_A": 3000,
            "BANK_B": 4000,
            "BANK_C": 5000,
            "BANK_D": 8000,
        }
        total_cost = sum(per_agent_costs.values())

        result = SimulationResult(
            seed=99999,
            simulation_id="multi-agent-sim-001-eval",
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            events=(),
            cost_breakdown=CostBreakdown(
                delay_cost=5000,
                overdraft_cost=10000,
                deadline_penalty=3000,
                eod_penalty=2000,
            ),
            settlement_rate=0.87,
            avg_delay=3.5,
        )

        assert result.total_cost == 20000  # 3000+4000+5000+8000
        assert len(result.per_agent_costs) == 4
        assert result.per_agent_costs["BANK_A"] == 3000

    def test_settlement_rate_bounds(self) -> None:
        """Test that settlement_rate is between 0.0 and 1.0."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        # Test with 0% settlement
        result_zero = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=0,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=0.0,
            avg_delay=0.0,
        )
        assert result_zero.settlement_rate == 0.0

        # Test with 100% settlement
        result_full = SimulationResult(
            seed=1,
            simulation_id="test",
            total_cost=0,
            per_agent_costs={},
            events=(),
            cost_breakdown=CostBreakdown(0, 0, 0, 0),
            settlement_rate=1.0,
            avg_delay=0.0,
        )
        assert result_full.settlement_rate == 1.0

    def test_can_import_from_bootstrap_support(self) -> None:
        """Test that SimulationResult can be imported from bootstrap_support."""
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        assert SimulationResult is not None

    def test_simulation_result_with_rich_event_data(self) -> None:
        """Test SimulationResult with detailed event data."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        events = (
            {
                "event_type": "TransactionArrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
            {
                "event_type": "RtgsImmediateSettlement",
                "tick": 0,
                "tx_id": "tx-001",
                "amount": 100000,
            },
            {
                "event_type": "DelayCostAccrual",
                "tick": 1,
                "agent_id": "BANK_A",
                "cost": 500,
            },
        )

        result = SimulationResult(
            seed=42,
            simulation_id="rich-events-sim",
            total_cost=500,
            per_agent_costs={"BANK_A": 500},
            events=events,
            cost_breakdown=CostBreakdown(
                delay_cost=500,
                overdraft_cost=0,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            settlement_rate=1.0,
            avg_delay=0.0,
        )

        assert len(result.events) == 3
        assert result.events[0]["event_type"] == "TransactionArrival"
        assert result.events[1]["event_type"] == "RtgsImmediateSettlement"
        assert result.events[2]["event_type"] == "DelayCostAccrual"
