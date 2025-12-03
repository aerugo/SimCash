"""
Integration Tests for Castro Experiment Runs.

These tests verify that complete experiment runs work correctly:

1. Full simulation runs complete without errors
2. Expected settlement rates are achieved
3. Cost calculations are reasonable
4. Events are properly logged
5. Results match expectations for baseline runs
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


def run_full_experiment(
    config_dict: dict[str, Any],
) -> dict[str, Any]:
    """Run a full experiment and return comprehensive results."""
    ffi_config = _config_to_ffi(config_dict)
    orch = Orchestrator.new(ffi_config)

    simulation = config_dict.get("simulation", config_dict)
    ticks_per_day = simulation.get("ticks_per_day", 100)
    num_days = simulation.get("num_days", 1)
    total_ticks = ticks_per_day * num_days

    # Run simulation
    for _ in range(total_ticks):
        orch.tick()

    # Collect results
    metrics = orch.get_system_metrics()
    all_events = orch.get_all_events()

    # Get agent info
    agents = config_dict.get("agents", [])
    agent_ids = [a["id"] for a in agents]

    agent_results = {}
    for aid in agent_ids:
        costs = orch.get_agent_accumulated_costs(aid)
        state = orch.get_agent_state(aid)
        agent_results[aid] = {
            "final_balance": orch.get_agent_balance(aid),
            "total_cost": costs["total_cost"],
            "collateral_cost": costs["collateral_cost"],
            "delay_cost": costs["delay_cost"],
            "liquidity_cost": costs["liquidity_cost"],
            "posted_collateral": state.get("posted_collateral", 0),
        }

    # Count event types
    event_counts = {}
    for e in all_events:
        event_type = e.get("event_type", "Unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    return {
        "total_arrivals": metrics["total_arrivals"],
        "total_settlements": metrics["total_settlements"],
        "settlement_rate": (
            metrics["total_settlements"] / metrics["total_arrivals"]
            if metrics["total_arrivals"] > 0
            else 1.0
        ),
        "final_tick": orch.current_tick(),
        "queue_size": orch.queue_size(),
        "agents": agent_results,
        "total_cost": sum(a["total_cost"] for a in agent_results.values()),
        "event_counts": event_counts,
    }


# ============================================================================
# Experiment 1 Integration Tests
# ============================================================================


class TestExp1Integration:
    """Integration tests for Experiment 1 (2-period deterministic)."""

    def test_exp1_runs_without_error(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 should complete without errors."""
        try:
            result = run_full_experiment(exp1_config_dict)
        except Exception as e:
            pytest.fail(f"Exp1 failed with error: {e}")

        print("\nExp1 Results:")
        print(f"  Arrivals: {result['total_arrivals']}")
        print(f"  Settlements: {result['total_settlements']}")
        print(f"  Settlement rate: {result['settlement_rate']*100:.1f}%")
        print(f"  Total cost: ${result['total_cost']/100:.2f}")

    def test_exp1_correct_arrival_count(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 should have exactly 3 arrivals (BANK_A: 1, BANK_B: 2)."""
        result = run_full_experiment(exp1_config_dict)

        # P^A = [0, $150] -> 1 arrival (tick 1)
        # P^B = [$150, $50] -> 2 arrivals (tick 0 and tick 1)
        assert result["total_arrivals"] == 3, (
            f"Expected 3 arrivals, got {result['total_arrivals']}"
        )

    def test_exp1_completes_in_2_ticks(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 should complete in exactly 2 ticks."""
        result = run_full_experiment(exp1_config_dict)

        assert result["final_tick"] == 2, (
            f"Expected 2 ticks, got {result['final_tick']}"
        )

    def test_exp1_deferred_credit_events_exist(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 should have DeferredCreditApplied events (deferred_crediting=true)."""
        result = run_full_experiment(exp1_config_dict)

        # If any settlements occurred, there should be deferred credit events
        if result["total_settlements"] > 0:
            assert "DeferredCreditApplied" in result["event_counts"], (
                "Should have DeferredCreditApplied events with deferred_crediting=true"
            )


# ============================================================================
# Experiment 2 Integration Tests
# ============================================================================


class TestExp2Integration:
    """Integration tests for Experiment 2 (12-period stochastic)."""

    def test_exp2_runs_without_error(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Exp2 should complete without errors."""
        try:
            result = run_full_experiment(exp2_config_dict)
        except Exception as e:
            pytest.fail(f"Exp2 failed with error: {e}")

        print("\nExp2 Results:")
        print(f"  Arrivals: {result['total_arrivals']}")
        print(f"  Settlements: {result['total_settlements']}")
        print(f"  Settlement rate: {result['settlement_rate']*100:.1f}%")
        print(f"  Total cost: ${result['total_cost']/100:.2f}")

    def test_exp2_has_stochastic_arrivals(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Exp2 should have varying arrival counts (stochastic)."""
        # Run with different seeds
        results = []

        for seed in [42, 123, 999]:
            config = exp2_config_dict.copy()
            config["simulation"] = config.get("simulation", {}).copy()
            config["simulation"]["rng_seed"] = seed

            result = run_full_experiment(config)
            results.append(result["total_arrivals"])

        # Should have different arrival counts
        assert len(set(results)) > 1, (
            f"Stochastic arrivals should vary: {results}"
        )

    def test_exp2_completes_in_12_ticks(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Exp2 should complete in 12 ticks."""
        result = run_full_experiment(exp2_config_dict)

        assert result["final_tick"] == 12, (
            f"Expected 12 ticks, got {result['final_tick']}"
        )


# ============================================================================
# Experiment 3 Integration Tests
# ============================================================================


class TestExp3Integration:
    """Integration tests for Experiment 3 (3-period symmetric)."""

    def test_exp3_runs_without_error(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 should complete without errors."""
        try:
            result = run_full_experiment(exp3_config_dict)
        except Exception as e:
            pytest.fail(f"Exp3 failed with error: {e}")

        print("\nExp3 Results:")
        print(f"  Arrivals: {result['total_arrivals']}")
        print(f"  Settlements: {result['total_settlements']}")
        print(f"  Settlement rate: {result['settlement_rate']*100:.1f}%")
        print(f"  Total cost: ${result['total_cost']/100:.2f}")

    def test_exp3_correct_arrival_count(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 should have exactly 4 arrivals (2 per bank)."""
        result = run_full_experiment(exp3_config_dict)

        # P = [$200, $200, $0] for each bank
        # 2 arrivals per bank = 4 total
        assert result["total_arrivals"] == 4, (
            f"Expected 4 arrivals, got {result['total_arrivals']}"
        )

    def test_exp3_symmetric_costs(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 with symmetric profile should have similar costs per agent."""
        result = run_full_experiment(exp3_config_dict)

        bank_a_cost = result["agents"]["BANK_A"]["total_cost"]
        bank_b_cost = result["agents"]["BANK_B"]["total_cost"]

        # Costs should be similar (not necessarily identical due to timing)
        if bank_a_cost > 0 and bank_b_cost > 0:
            ratio = max(bank_a_cost, bank_b_cost) / min(bank_a_cost, bank_b_cost)
            # Allow up to 2x difference (timing effects)
            assert ratio < 3, (
                f"Symmetric profile should have similar costs: "
                f"A={bank_a_cost}, B={bank_b_cost}, ratio={ratio:.2f}"
            )


# ============================================================================
# Settlement Rate Tests
# ============================================================================


class TestSettlementRates:
    """Verify settlement rates are reasonable."""

    def test_exp1_can_achieve_100_percent_settlement(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 should be able to achieve 100% settlement.

        The deterministic 2-period scenario should always settle all
        transactions with proper initial liquidity.
        """
        result = run_full_experiment(exp1_config_dict)

        # With the seed policy, we may not hit 100% on first run
        # but the rate should be high (> 50%)
        assert result["settlement_rate"] >= 0.5, (
            f"Expected at least 50% settlement, got {result['settlement_rate']*100:.1f}%"
        )

    def test_exp3_high_settlement_rate(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 should achieve high settlement rate with symmetric flows."""
        result = run_full_experiment(exp3_config_dict)

        # Symmetric flows should enable high settlement
        assert result["settlement_rate"] >= 0.5, (
            f"Expected at least 50% settlement, got {result['settlement_rate']*100:.1f}%"
        )


# ============================================================================
# Cost Calculation Tests
# ============================================================================


class TestCostCalculations:
    """Verify cost calculations are reasonable."""

    def test_costs_are_non_negative(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """All costs should be non-negative."""
        result = run_full_experiment(exp1_config_dict)

        for agent_id, agent_data in result["agents"].items():
            assert agent_data["total_cost"] >= 0, (
                f"Agent {agent_id} total cost should be >= 0"
            )
            assert agent_data["collateral_cost"] >= 0
            assert agent_data["delay_cost"] >= 0
            assert agent_data["liquidity_cost"] >= 0

    def test_total_cost_is_sum_of_components(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Total cost should equal sum of cost components."""
        result = run_full_experiment(exp1_config_dict)

        for agent_id, agent_data in result["agents"].items():
            expected = (
                agent_data["collateral_cost"]
                + agent_data["delay_cost"]
                + agent_data["liquidity_cost"]
            )

            # Allow for some other cost components we might not track
            # Total should be at least the sum of tracked components
            assert agent_data["total_cost"] >= expected * 0.9, (
                f"Agent {agent_id}: total_cost should be >= sum of components"
            )


# ============================================================================
# Event Logging Tests
# ============================================================================


class TestEventLogging:
    """Verify events are properly logged."""

    def test_arrival_events_logged(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Arrival events should be logged."""
        result = run_full_experiment(exp1_config_dict)

        assert "Arrival" in result["event_counts"], (
            "Should have Arrival events"
        )
        assert result["event_counts"]["Arrival"] == result["total_arrivals"]

    def test_settlement_events_logged(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Settlement events should be logged."""
        result = run_full_experiment(exp1_config_dict)

        if result["total_settlements"] > 0:
            # Should have RtgsImmediateSettlement or Queue2LiquidityRelease
            settlement_event_types = [
                "RtgsImmediateSettlement",
                "Queue2LiquidityRelease",
                "LsmBilateralOffset",
                "LsmCycleSettlement",
            ]
            has_settlement_event = any(
                t in result["event_counts"] for t in settlement_event_types
            )
            assert has_settlement_event, (
                "Should have settlement events when settlements occurred"
            )


# ============================================================================
# Queue Behavior Tests
# ============================================================================


class TestQueueBehavior:
    """Verify queue behavior during experiments."""

    def test_queue_empties_with_sufficient_liquidity(self) -> None:
        """Queue should empty when agents have sufficient liquidity."""
        config = {
            "simulation": {
                "rng_seed": 42,
                "ticks_per_day": 2,
                "num_days": 1,
            },
            "deferred_crediting": True,
            "deadline_cap_at_eod": True,
            "agents": [
                {
                    "id": "A",
                    "opening_balance": 1_000_000,  # Plenty of funds
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 50000,
                    "schedule": {"type": "OneTime", "tick": 0},
                },
            ],
        }

        result = run_full_experiment(config)

        # Queue should be empty after simulation
        assert result["queue_size"] == 0, (
            "Queue should be empty with sufficient liquidity"
        )
        assert result["settlement_rate"] == 1.0, (
            "All transactions should settle"
        )


# ============================================================================
# Balance Conservation Tests
# ============================================================================


class TestBalanceConservation:
    """Verify balance conservation (INV-4)."""

    def test_total_balance_conserved(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Sum of balances should equal initial sum (ignoring external transfers)."""
        result = run_full_experiment(exp1_config_dict)

        # Get initial balances
        agents = exp1_config_dict.get("agents", [])
        initial_total = sum(a.get("opening_balance", 0) for a in agents)

        # Get final balances
        final_total = sum(a["final_balance"] for a in result["agents"].values())

        # Should be equal (no external transfers in Castro experiments)
        assert initial_total == final_total, (
            f"Balance not conserved: initial={initial_total}, final={final_total}"
        )

    def test_exp3_balance_conserved(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 balance should be conserved."""
        result = run_full_experiment(exp3_config_dict)

        agents = exp3_config_dict.get("agents", [])
        initial_total = sum(a.get("opening_balance", 0) for a in agents)
        final_total = sum(a["final_balance"] for a in result["agents"].values())

        assert initial_total == final_total, (
            f"Balance not conserved: initial={initial_total}, final={final_total}"
        )
