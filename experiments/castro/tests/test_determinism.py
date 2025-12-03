"""
Determinism Tests for Castro Experiments.

These tests verify that the Castro experiments are perfectly reproducible:

1. Same seed produces identical results across runs
2. Tick-by-tick state is deterministic
3. Event ordering is deterministic
4. Cost calculations are deterministic

Determinism is a CRITICAL INVARIANT (INV-2) because:
- Experimental results must be reproducible for validation
- Different seeds should produce different (but repeatable) results
- Debugging requires exact replay capability
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


def run_full_simulation(config: dict[str, Any]) -> dict[str, Any]:
    """Run a full simulation and return final state summary."""
    ffi_config = _config_to_ffi(config)
    orch = Orchestrator.new(ffi_config)

    simulation = config.get("simulation", config)
    ticks_per_day = simulation.get("ticks_per_day", 100)
    num_days = simulation.get("num_days", 1)
    total_ticks = ticks_per_day * num_days

    for _ in range(total_ticks):
        orch.tick()

    # Collect final state
    metrics = orch.get_system_metrics()
    agents = config.get("agents", [])
    agent_ids = [a["id"] for a in agents]

    return {
        "total_arrivals": metrics["total_arrivals"],
        "total_settlements": metrics["total_settlements"],
        "final_tick": orch.current_tick(),
        "queue_size": orch.queue_size(),
        "agent_balances": {
            aid: orch.get_agent_balance(aid) for aid in agent_ids
        },
        "agent_costs": {
            aid: orch.get_agent_accumulated_costs(aid) for aid in agent_ids
        },
    }


# ============================================================================
# Basic Determinism Tests
# ============================================================================


class TestBasicDeterminism:
    """Basic determinism tests for Castro experiments."""

    def test_same_seed_produces_identical_results(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Same seed should produce identical results across 5 runs."""
        results = []

        for run_num in range(5):
            result = run_full_simulation(exp1_config_dict)
            results.append(result)

            print(f"\nRun {run_num + 1}:")
            print(f"  Arrivals: {result['total_arrivals']}")
            print(f"  Settlements: {result['total_settlements']}")
            print(f"  Queue size: {result['queue_size']}")

        # All results must be identical
        reference = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == reference, (
                f"Run {i} differs from run 1:\n"
                f"  Run 1: {reference}\n"
                f"  Run {i}: {result}"
            )

    def test_exp1_determinism(self, exp1_config_dict: dict[str, Any]) -> None:
        """Experiment 1 should be deterministic."""
        result1 = run_full_simulation(exp1_config_dict)
        result2 = run_full_simulation(exp1_config_dict)

        assert result1 == result2, "Exp1 should be deterministic"

    def test_exp2_determinism(self, exp2_config_dict: dict[str, Any]) -> None:
        """Experiment 2 should be deterministic (even with stochastic arrivals)."""
        result1 = run_full_simulation(exp2_config_dict)
        result2 = run_full_simulation(exp2_config_dict)

        assert result1 == result2, "Exp2 should be deterministic"

    def test_exp3_determinism(self, exp3_config_dict: dict[str, Any]) -> None:
        """Experiment 3 should be deterministic."""
        result1 = run_full_simulation(exp3_config_dict)
        result2 = run_full_simulation(exp3_config_dict)

        assert result1 == result2, "Exp3 should be deterministic"


# ============================================================================
# Tick-by-Tick Determinism Tests
# ============================================================================


class TestTickByTickDeterminism:
    """Verify determinism at each tick, not just final results."""

    def test_tick_by_tick_state_identical(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """State should be identical at every tick between two runs."""
        ffi_config = _config_to_ffi(exp1_config_dict)

        orch1 = Orchestrator.new(ffi_config)
        orch2 = Orchestrator.new(ffi_config)

        simulation = exp1_config_dict.get("simulation", exp1_config_dict)
        total_ticks = simulation.get("ticks_per_day", 2) * simulation.get("num_days", 1)
        agents = exp1_config_dict.get("agents", [])
        agent_ids = [a["id"] for a in agents]

        for tick in range(total_ticks):
            orch1.tick()
            orch2.tick()

            # Verify state identical at this tick
            assert orch1.current_tick() == orch2.current_tick() == tick + 1

            for aid in agent_ids:
                bal1 = orch1.get_agent_balance(aid)
                bal2 = orch2.get_agent_balance(aid)
                assert bal1 == bal2, (
                    f"Tick {tick}: Agent {aid} balance differs: {bal1} vs {bal2}"
                )

            assert orch1.queue_size() == orch2.queue_size(), (
                f"Tick {tick}: Queue sizes differ"
            )

    def test_event_ordering_deterministic(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Events should appear in identical order across runs."""
        ffi_config = _config_to_ffi(exp1_config_dict)

        orch1 = Orchestrator.new(ffi_config)
        orch2 = Orchestrator.new(ffi_config)

        simulation = exp1_config_dict.get("simulation", exp1_config_dict)
        total_ticks = simulation.get("ticks_per_day", 2) * simulation.get("num_days", 1)

        for tick in range(total_ticks):
            orch1.tick()
            orch2.tick()

            events1 = orch1.get_tick_events(tick)
            events2 = orch2.get_tick_events(tick)

            assert len(events1) == len(events2), (
                f"Tick {tick}: Event count differs: {len(events1)} vs {len(events2)}"
            )

            for i, (e1, e2) in enumerate(zip(events1, events2)):
                # Events should have same type and key fields
                assert e1.get("event_type") == e2.get("event_type"), (
                    f"Tick {tick}, event {i}: Type differs"
                )


# ============================================================================
# Different Seeds Produce Different Results
# ============================================================================


class TestDifferentSeeds:
    """Verify different seeds produce different (but deterministic) results."""

    def test_different_seeds_produce_different_arrivals(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Different seeds should produce different arrival patterns.

        This is a sanity check that the RNG is actually being used.
        """
        results = []

        for seed in [42, 123, 999, 7777]:
            config = exp2_config_dict.copy()
            config["simulation"] = config.get("simulation", {}).copy()
            config["simulation"]["rng_seed"] = seed

            result = run_full_simulation(config)
            results.append({
                "seed": seed,
                "arrivals": result["total_arrivals"],
                "settlements": result["total_settlements"],
            })

        # Should have different arrival counts (stochastic)
        arrival_counts = [r["arrivals"] for r in results]
        unique_counts = set(arrival_counts)

        assert len(unique_counts) > 1, (
            f"Different seeds should produce different arrivals: {results}"
        )

        print("\nDifferent seeds produced different results:")
        for r in results:
            print(f"  Seed {r['seed']}: {r['arrivals']} arrivals")

    def test_same_seed_same_result_different_seed_different_result(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Verify: seed=42 twice gives same result, seed=43 gives different."""
        config_42a = exp2_config_dict.copy()
        config_42a["simulation"] = config_42a.get("simulation", {}).copy()
        config_42a["simulation"]["rng_seed"] = 42

        config_42b = exp2_config_dict.copy()
        config_42b["simulation"] = config_42b.get("simulation", {}).copy()
        config_42b["simulation"]["rng_seed"] = 42

        config_43 = exp2_config_dict.copy()
        config_43["simulation"] = config_43.get("simulation", {}).copy()
        config_43["simulation"]["rng_seed"] = 43

        result_42a = run_full_simulation(config_42a)
        result_42b = run_full_simulation(config_42b)
        result_43 = run_full_simulation(config_43)

        # Same seed should give same result
        assert result_42a == result_42b, "Same seed should give identical result"

        # Different seed should (very likely) give different result
        # Note: Could theoretically be same, but extremely unlikely
        assert result_42a != result_43, (
            "Different seeds should give different results "
            "(unless extremely unlucky - probability negligible)"
        )


# ============================================================================
# Cost Calculation Determinism
# ============================================================================


class TestCostDeterminism:
    """Verify cost calculations are deterministic."""

    def test_accumulated_costs_deterministic(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Accumulated costs should be identical across runs."""
        result1 = run_full_simulation(exp1_config_dict)
        result2 = run_full_simulation(exp1_config_dict)

        # Compare agent costs
        for agent_id in result1["agent_costs"]:
            costs1 = result1["agent_costs"][agent_id]
            costs2 = result2["agent_costs"][agent_id]

            assert costs1["total_cost"] == costs2["total_cost"], (
                f"Agent {agent_id} total cost differs"
            )
            assert costs1["collateral_cost"] == costs2["collateral_cost"], (
                f"Agent {agent_id} collateral cost differs"
            )
            assert costs1["delay_cost"] == costs2["delay_cost"], (
                f"Agent {agent_id} delay cost differs"
            )
            assert costs1["overdraft_cost"] == costs2["overdraft_cost"], (
                f"Agent {agent_id} overdraft cost differs"
            )


# ============================================================================
# Deferred Crediting Determinism
# ============================================================================


class TestDeferredCreditingDeterminism:
    """Verify deferred crediting behavior is deterministic."""

    def test_deferred_credit_events_deterministic(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """DeferredCreditApplied events should be identical across runs."""
        ffi_config = _config_to_ffi(exp1_config_dict)

        orch1 = Orchestrator.new(ffi_config)
        orch2 = Orchestrator.new(ffi_config)

        simulation = exp1_config_dict.get("simulation", exp1_config_dict)
        total_ticks = simulation.get("ticks_per_day", 2) * simulation.get("num_days", 1)

        for _ in range(total_ticks):
            orch1.tick()
            orch2.tick()

        # Compare all events
        events1 = orch1.get_all_events()
        events2 = orch2.get_all_events()

        deferred1 = [e for e in events1 if e.get("event_type") == "DeferredCreditApplied"]
        deferred2 = [e for e in events2 if e.get("event_type") == "DeferredCreditApplied"]

        assert len(deferred1) == len(deferred2)

        for e1, e2 in zip(deferred1, deferred2):
            assert e1["agent_id"] == e2["agent_id"]
            assert e1["amount"] == e2["amount"]
            assert e1["tick"] == e2["tick"]


# ============================================================================
# Policy Evaluation Determinism
# ============================================================================


class TestPolicyDeterminism:
    """Verify policy decisions are deterministic."""

    def test_policy_decisions_deterministic(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Policy decisions should produce identical queue states."""
        ffi_config = _config_to_ffi(exp1_config_dict)

        orch1 = Orchestrator.new(ffi_config)
        orch2 = Orchestrator.new(ffi_config)

        simulation = exp1_config_dict.get("simulation", exp1_config_dict)
        total_ticks = simulation.get("ticks_per_day", 2) * simulation.get("num_days", 1)

        for tick in range(total_ticks):
            orch1.tick()
            orch2.tick()

            # Queue contents should be identical
            q1 = orch1.queue_size()
            q2 = orch2.queue_size()
            assert q1 == q2, f"Tick {tick}: Queue sizes differ: {q1} vs {q2}"
