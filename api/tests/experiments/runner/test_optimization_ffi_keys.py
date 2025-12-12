"""TDD tests for FFI key mapping in optimization loop.

These tests verify that the optimization loop correctly uses the keys
returned by the Rust FFI methods:
- get_agent_accumulated_costs()
- get_system_metrics()

Bug discovered: The optimization loop was using wrong keys:
- `settled_count` instead of `total_settlements`
- `total_transactions` instead of `total_arrivals`
- `overdraft_cost` instead of `liquidity_cost`
- `eod_penalty` which doesn't exist in FFI (use penalty_cost from CostBreakdown)
"""

from __future__ import annotations

import pytest


def _make_simple_policy() -> dict:
    """Create a simple FIFO policy for tests."""
    return {"type": "Fifo"}


class TestFFIKeyMapping:
    """Tests that verify the correct keys are used from FFI responses."""

    def test_get_system_metrics_returns_correct_keys(self) -> None:
        """Verify get_system_metrics returns the expected keys."""
        from payment_simulator._core import Orchestrator

        config = {
            "ticks_per_day": 2,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run a tick to generate some metrics
        orch.tick()

        metrics = orch.get_system_metrics()

        # These are the CORRECT keys from the Rust FFI
        assert "total_arrivals" in metrics, "FFI should return 'total_arrivals'"
        assert "total_settlements" in metrics, "FFI should return 'total_settlements'"
        assert "settlement_rate" in metrics, "FFI should return 'settlement_rate'"

        # These should NOT exist - they're wrong keys used in the buggy code
        assert "settled_count" not in metrics, "FFI does NOT return 'settled_count'"
        assert "total_transactions" not in metrics, "FFI does NOT return 'total_transactions'"

    def test_get_agent_accumulated_costs_returns_correct_keys(self) -> None:
        """Verify get_agent_accumulated_costs returns the expected keys."""
        from payment_simulator._core import Orchestrator

        config = {
            "ticks_per_day": 2,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
            ],
        }

        orch = Orchestrator.new(config)
        orch.tick()

        costs = orch.get_agent_accumulated_costs("BANK_A")

        # These are the CORRECT keys from the Rust FFI
        assert "liquidity_cost" in costs, "FFI should return 'liquidity_cost'"
        assert "collateral_cost" in costs, "FFI should return 'collateral_cost'"
        assert "delay_cost" in costs, "FFI should return 'delay_cost'"
        assert "split_friction_cost" in costs, "FFI should return 'split_friction_cost'"
        assert "deadline_penalty" in costs, "FFI should return 'deadline_penalty'"
        assert "total_cost" in costs, "FFI should return 'total_cost'"

        # These should NOT exist - they're wrong keys used in the buggy code
        assert "overdraft_cost" not in costs, "FFI does NOT return 'overdraft_cost'"
        assert "eod_penalty" not in costs, "FFI does NOT return 'eod_penalty'"


class TestCostBreakdownModel:
    """Tests for CostBreakdown model field names matching FFI."""

    def test_cost_breakdown_fields_match_ffi(self) -> None:
        """CostBreakdown model fields should match FFI keys."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import CostBreakdown

        # Create a CostBreakdown - the fields should match FFI naming
        # Currently the model has: delay_cost, overdraft_cost, deadline_penalty, eod_penalty
        # But FFI returns: delay_cost, liquidity_cost (not overdraft), deadline_penalty (no eod_penalty)

        # Verify the fields exist (this tests the model structure)
        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=200,  # This field name is WRONG - should be liquidity_cost
            deadline_penalty=300,
            eod_penalty=400,  # This field doesn't exist in FFI
        )

        # This test documents the current buggy state
        # After fix, we should rename overdraft_cost → liquidity_cost
        # and remove or repurpose eod_penalty
        assert breakdown.delay_cost == 100
        assert breakdown.overdraft_cost == 200
        assert breakdown.deadline_penalty == 300
        assert breakdown.eod_penalty == 400


class TestCostComponentExtraction:
    """Tests for cost component extraction using correct keys."""

    def test_costs_extraction_uses_correct_keys(self) -> None:
        """Test that costs are extracted using correct FFI keys.

        This test simulates what the optimization loop does:
        1. Create orchestrator with agents
        2. Run simulation
        3. Extract costs using correct keys
        """
        from payment_simulator._core import Orchestrator

        config = {
            "ticks_per_day": 2,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 0,  # Start with no balance
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
            ],
            "cost_config": {
                "overdraft_bps_per_tick": 100,
                "delay_cost_per_tick_per_cent": 0.01,
                "collateral_cost_per_tick_bps": 10,
                "deadline_penalty": 1000,
            },
        }

        orch = Orchestrator.new(config)

        # Run simulation
        for _ in range(2):
            orch.tick()

        costs = orch.get_agent_accumulated_costs("BANK_A")

        # The CORRECT keys from FFI - all should exist
        assert "liquidity_cost" in costs
        assert "collateral_cost" in costs
        assert "delay_cost" in costs
        assert "split_friction_cost" in costs
        assert "deadline_penalty" in costs
        assert "total_cost" in costs

        # These are the WRONG keys that were used in the buggy code
        assert "overdraft_cost" not in costs
        assert "eod_penalty" not in costs

    def test_settlement_rate_extraction_uses_correct_keys(self) -> None:
        """Test that settlement rate is extracted using correct FFI keys."""
        from payment_simulator._core import Orchestrator

        config = {
            "ticks_per_day": 2,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "unsecured_cap": 50000,
                    "policy": _make_simple_policy(),
                },
            ],
        }

        orch = Orchestrator.new(config)
        orch.tick()

        metrics = orch.get_system_metrics()

        # The CORRECT keys from FFI
        assert "total_arrivals" in metrics
        assert "total_settlements" in metrics
        assert "settlement_rate" in metrics
        assert "avg_delay_ticks" in metrics

        # These are the WRONG keys that were used in the buggy code
        assert "settled_count" not in metrics
        assert "total_transactions" not in metrics
        assert "avg_settlement_delay" not in metrics


def _make_mock_config() -> "MagicMock":
    """Create a mock ExperimentConfig with nested attributes."""
    from pathlib import Path
    from unittest.mock import MagicMock

    config = MagicMock()
    config.name = "test_exp"
    config.master_seed = 42
    config.optimized_agents = ("BANK_A",)

    # Create nested evaluation mock
    config.evaluation = MagicMock()
    config.evaluation.mode = "deterministic"
    config.evaluation.num_samples = 1
    config.evaluation.ticks = 2

    # Create nested convergence mock
    config.convergence = MagicMock()
    config.convergence.max_iterations = 5
    config.convergence.stability_threshold = 0.05
    config.convergence.stability_window = 3
    config.convergence.improvement_threshold = 0.01

    config.scenario_path = Path("test.yaml")
    config.get_constraints.return_value = None

    # Create nested llm mock
    config.llm = MagicMock()
    config.llm.system_prompt = None

    return config


class TestPolicyAcceptance:
    """Tests for policy acceptance/rejection logic."""

    @pytest.mark.asyncio
    async def test_should_accept_returns_tuple_with_cost(self) -> None:
        """Verify _should_accept_policy returns (bool, cost) tuple."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = _make_mock_config()
        loop = OptimizationLoop(config)

        # Mock _evaluate_policy_on_samples to return known costs
        loop._evaluate_policy_on_samples = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                [100],  # old policy cost
                [80],  # new policy cost (better)
            ]
        )

        old_policy = {"type": "old"}
        new_policy = {"type": "new"}

        should_accept, new_cost = await loop._should_accept_policy(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
        )

        # New policy is cheaper (80 < 100), should accept
        assert should_accept is True
        assert new_cost == 80

    @pytest.mark.asyncio
    async def test_should_reject_policy_with_higher_cost(self) -> None:
        """Verify policies with higher cost are rejected."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = _make_mock_config()
        loop = OptimizationLoop(config)

        # Mock _evaluate_policy_on_samples: new policy is WORSE
        loop._evaluate_policy_on_samples = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                [100],  # old policy cost
                [500],  # new policy cost (WORSE!)
            ]
        )

        old_policy = {"type": "old"}
        new_policy = {"type": "new"}

        should_accept, new_cost = await loop._should_accept_policy(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
        )

        # New policy is more expensive (500 > 100), should REJECT
        assert should_accept is False
        assert new_cost == 500

    @pytest.mark.asyncio
    async def test_should_accept_same_cost_policy(self) -> None:
        """Verify policies with same cost are accepted (no regression)."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = _make_mock_config()
        loop = OptimizationLoop(config)

        # Mock _evaluate_policy_on_samples: same cost
        loop._evaluate_policy_on_samples = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                [100],  # old policy cost
                [100],  # new policy cost (same)
            ]
        )

        old_policy = {"type": "old"}
        new_policy = {"type": "new"}

        should_accept, new_cost = await loop._should_accept_policy(
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
        )

        # Same cost should be accepted (allows exploration)
        assert should_accept is True
        assert new_cost == 100
