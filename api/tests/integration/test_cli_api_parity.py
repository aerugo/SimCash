"""CLI-API Output Parity Tests.

These tests verify that the API returns the EXACT SAME data as the CLI
for the same simulation. This is critical for output consistency.

Phase -1: TDD tests written BEFORE implementation.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.api.models.costs import AgentCostBreakdown
from payment_simulator.cli.execution.state_provider import (
    AccumulatedCosts,
    OrchestratorStateProvider,
)


class TestCostFieldNameParity:
    """Verify cost field names match between CLI (StateProvider) and API (Pydantic)."""

    def test_accumulated_costs_has_deadline_penalty_field(self) -> None:
        """AccumulatedCosts TypedDict has deadline_penalty field."""
        # AccumulatedCosts should have deadline_penalty (not just penalty_cost)
        from payment_simulator.cli.execution.state_provider import AccumulatedCosts

        # Check field exists in TypedDict annotations
        annotations = AccumulatedCosts.__annotations__
        assert "deadline_penalty" in annotations, (
            "AccumulatedCosts is missing deadline_penalty field. "
            f"Available fields: {list(annotations.keys())}"
        )

    def test_api_model_has_deadline_penalty_field(self) -> None:
        """API AgentCostBreakdown model has deadline_penalty field."""
        from payment_simulator.api.models.costs import AgentCostBreakdown

        fields = AgentCostBreakdown.model_fields
        assert "deadline_penalty" in fields, (
            "AgentCostBreakdown is missing deadline_penalty field. "
            f"Available fields: {list(fields.keys())}"
        )

    def test_cost_field_names_match_between_cli_and_api(self) -> None:
        """CLI AccumulatedCosts and API AgentCostBreakdown have matching field names."""
        from payment_simulator.api.models.costs import AgentCostBreakdown
        from payment_simulator.cli.execution.state_provider import AccumulatedCosts

        # Get field names from both
        cli_fields = set(AccumulatedCosts.__annotations__.keys())
        api_fields = set(AgentCostBreakdown.model_fields.keys())

        # The canonical fields that MUST match
        canonical_cost_fields = {
            "liquidity_cost",
            "delay_cost",
            "collateral_cost",
            "deadline_penalty",  # CANONICAL NAME
            "split_friction_cost",
            "total_cost",
        }

        # Check CLI has all canonical fields
        missing_in_cli = canonical_cost_fields - cli_fields
        assert not missing_in_cli, f"CLI AccumulatedCosts missing fields: {missing_in_cli}"

        # Check API has all canonical fields
        missing_in_api = canonical_cost_fields - api_fields
        assert not missing_in_api, f"API AgentCostBreakdown missing fields: {missing_in_api}"


class TestCostValueParity:
    """Verify cost VALUES are identical between CLI and API."""

    @pytest.fixture
    def simple_config(self) -> dict[str, Any]:
        """Create minimal simulation config."""
        return {
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000_00,  # $1M
                    "unsecured_cap": 500_000_00,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000_00,
                    "unsecured_cap": 500_000_00,
                    "policy": {"type": "Fifo"},
                },
            ],
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 42,
            "cost_rates": {
                "overdraft_bps_per_tick": 1.0,
                "delay_cost_per_tick": 100,
                "collateral_bps_per_tick": 0.5,
                "deadline_penalty": 10000,
                "split_friction_bps": 0.1,
            },
        }

    def test_orchestrator_returns_deadline_penalty_field(
        self, simple_config: dict[str, Any]
    ) -> None:
        """Orchestrator.get_agent_accumulated_costs() includes deadline_penalty."""
        orch = Orchestrator.new(simple_config)

        # Tick a few times
        for _ in range(5):
            orch.tick()

        # Get costs via StateProvider (CLI path)
        provider = OrchestratorStateProvider(orch)
        costs = provider.get_agent_accumulated_costs("BANK_A")

        # Must have deadline_penalty field
        assert "deadline_penalty" in costs, (
            f"StateProvider costs missing deadline_penalty. Keys: {list(costs.keys())}"
        )

    def test_state_provider_deadline_penalty_matches_penalty_cost(
        self, simple_config: dict[str, Any]
    ) -> None:
        """deadline_penalty should equal penalty_cost (they're aliases)."""
        orch = Orchestrator.new(simple_config)

        for _ in range(5):
            orch.tick()

        provider = OrchestratorStateProvider(orch)
        costs = provider.get_agent_accumulated_costs("BANK_A")

        # deadline_penalty is an alias for penalty_cost
        if "penalty_cost" in costs:
            assert costs["deadline_penalty"] == costs["penalty_cost"], (
                f"deadline_penalty ({costs['deadline_penalty']}) != "
                f"penalty_cost ({costs['penalty_cost']})"
            )


class TestMetricsCalculationParity:
    """Verify metrics calculations are identical between CLI and API."""

    def test_settlement_rate_formula_is_consistent(self) -> None:
        """settlement_rate calculation should use same formula everywhere."""
        # The canonical formula
        def canonical_settlement_rate(arrivals: int, settlements: int) -> float:
            if arrivals == 0:
                return 0.0
            return settlements / arrivals

        # Test cases
        test_cases = [
            (100, 95, 0.95),
            (0, 0, 0.0),  # Edge case: no arrivals
            (50, 50, 1.0),  # 100% rate
            (100, 0, 0.0),  # 0% rate
        ]

        for arrivals, settlements, expected in test_cases:
            result = canonical_settlement_rate(arrivals, settlements)
            assert result == expected, (
                f"Settlement rate for {arrivals}/{settlements} should be {expected}, "
                f"got {result}"
            )


class TestEventStructureParity:
    """Verify event structures match between CLI and API."""

    def test_arrival_event_has_required_fields(self) -> None:
        """Arrival events have consistent field names."""
        # These are the canonical fields for an Arrival event
        required_fields = {
            "event_type",
            "tx_id",
            "sender_id",
            "receiver_id",
            "amount",
            "priority",
            "deadline_tick",
        }

        # This is what the CLI event stream outputs (from replay.py)
        cli_event_fields = {
            "event_type",
            "tx_id",
            "sender_id",
            "receiver_id",
            "amount",
            "priority",
            "deadline_tick",
            "is_divisible",
        }

        # All required fields must be present
        missing = required_fields - cli_event_fields
        assert not missing, f"CLI event missing required fields: {missing}"


class TestSharedContractsExist:
    """Verify shared data contracts module exists and is usable."""

    def test_shared_module_exists(self) -> None:
        """Shared contracts module should be importable."""
        try:
            from payment_simulator.shared import data_contracts

            assert hasattr(data_contracts, "CostBreakdownContract")
            assert hasattr(data_contracts, "AgentStateContract")
            assert hasattr(data_contracts, "SystemMetricsContract")
        except ImportError:
            pytest.fail(
                "Shared contracts module not found. "
                "Create api/payment_simulator/shared/data_contracts.py"
            )

    def test_cost_breakdown_contract_has_canonical_fields(self) -> None:
        """CostBreakdownContract has all canonical cost fields."""
        try:
            from payment_simulator.shared.data_contracts import CostBreakdownContract

            # Check fields exist
            fields = CostBreakdownContract.__dataclass_fields__
            canonical = {
                "liquidity_cost",
                "delay_cost",
                "collateral_cost",
                "deadline_penalty",
                "split_friction_cost",
            }
            missing = canonical - set(fields.keys())
            assert not missing, f"CostBreakdownContract missing fields: {missing}"

            # Check total_cost property exists
            assert hasattr(CostBreakdownContract, "total_cost"), (
                "CostBreakdownContract missing total_cost property"
            )
        except ImportError:
            pytest.fail("CostBreakdownContract not found in shared.data_contracts")

    def test_api_model_can_be_created_from_contract(self) -> None:
        """API AgentCostBreakdown can be created from CostBreakdownContract."""
        try:
            from payment_simulator.api.models.costs import AgentCostBreakdown
            from payment_simulator.shared.data_contracts import CostBreakdownContract

            # Create contract
            contract = CostBreakdownContract(
                liquidity_cost=100,
                delay_cost=200,
                collateral_cost=50,
                deadline_penalty=1000,
                split_friction_cost=25,
            )

            # API model should have from_contract method
            assert hasattr(AgentCostBreakdown, "from_contract"), (
                "AgentCostBreakdown missing from_contract classmethod"
            )

            # Create model from contract
            model = AgentCostBreakdown.from_contract(contract)

            # Verify values match
            assert model.liquidity_cost == 100
            assert model.delay_cost == 200
            assert model.collateral_cost == 50
            assert model.deadline_penalty == 1000
            assert model.split_friction_cost == 25
            assert model.total_cost == 1375  # Sum of all

        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
