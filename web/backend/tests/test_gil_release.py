"""Tests for GIL-releasing FFI methods.

These methods enable thread-parallel simulation by releasing the Python GIL
during Rust execution. The critical invariant: identical (config, seed) must
produce identical results regardless of which method or how many threads.
"""
import json
import copy
import concurrent.futures
from pathlib import Path

import pytest
import yaml
from payment_simulator._core import Orchestrator
from payment_simulator.config.schemas import SimulationConfig

# Navigate from web/backend/tests/ up to repo root
CONFIGS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "docs" / "papers" / "simcash-paper" / "paper_generator" / "configs"
)
EXP2_CONFIG = CONFIGS_DIR / "exp2_12period.yaml"

POLICY_JSON = json.dumps({
    "version": "2.0",
    "policy_id": "test",
    "parameters": {"initial_liquidity_fraction": 0.1},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
})


def _make_orchestrator(seed: int = 42) -> tuple:
    """Create an Orchestrator from exp2 config. Returns (orch, num_ticks)."""
    with open(EXP2_CONFIG) as f:
        raw = yaml.safe_load(f)
    raw["simulation"]["rng_seed"] = seed
    for a in raw["agents"]:
        a["liquidity_allocation_fraction"] = 0.1
        a["policy"] = {"type": "InlineJson", "json_string": POLICY_JSON}
    config = SimulationConfig.from_dict(raw)
    ffi = config.to_ffi_dict()
    orch = Orchestrator.new(ffi)
    ticks = ffi["ticks_per_day"] * ffi["num_days"]
    return orch, ticks


class TestRunAndGetTotalCost:
    """Tests for Orchestrator.run_and_get_total_cost()."""

    def test_method_exists(self):
        orch, _ticks = _make_orchestrator()
        assert hasattr(orch, "run_and_get_total_cost")

    def test_returns_int(self):
        orch, ticks = _make_orchestrator()
        cost = orch.run_and_get_total_cost("BANK_A", ticks)
        assert isinstance(cost, int)

    def test_matches_manual_tick_loop(self):
        """CRITICAL: Determinism invariant. Same config+seed must produce
        identical cost via run_and_get_total_cost() vs tick() loop."""
        seed = 42

        # Path A: new GIL-release method
        orch_a, ticks = _make_orchestrator(seed)
        cost_a = orch_a.run_and_get_total_cost("BANK_A", ticks)

        # Path B: manual tick loop (existing method)
        orch_b, ticks = _make_orchestrator(seed)
        for _ in range(ticks):
            orch_b.tick()
        costs_b = orch_b.get_agent_accumulated_costs("BANK_A")
        cost_b = costs_b["total_cost"]

        assert cost_a == cost_b, f"Determinism violation: {cost_a} != {cost_b}"

    def test_matches_manual_tick_loop_bank_b(self):
        """Determinism invariant for BANK_B too."""
        seed = 42

        orch_a, ticks = _make_orchestrator(seed)
        cost_a = orch_a.run_and_get_total_cost("BANK_B", ticks)

        orch_b, ticks = _make_orchestrator(seed)
        for _ in range(ticks):
            orch_b.tick()
        cost_b = orch_b.get_agent_accumulated_costs("BANK_B")["total_cost"]

        assert cost_a == cost_b

    def test_different_seeds_different_costs(self):
        """With a Hold policy, stochastic arrivals create different delay/penalty
        costs across seeds since payments queue up differently."""
        hold_policy = json.dumps({
            "version": "2.0", "policy_id": "hold",
            "parameters": {"initial_liquidity_fraction": 0.5},
            "payment_tree": {"type": "action", "node_id": "root", "action": "Hold"},
            "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
        })
        seeds = [42, 123, 9999, 777777, 1000000]
        costs = []
        for s in seeds:
            with open(EXP2_CONFIG) as f:
                raw = yaml.safe_load(f)
            raw["simulation"]["rng_seed"] = s
            for a in raw["agents"]:
                a["liquidity_allocation_fraction"] = 0.5
                a["policy"] = {"type": "InlineJson", "json_string": hold_policy}
            config = SimulationConfig.from_dict(raw)
            ffi = config.to_ffi_dict()
            orch = Orchestrator.new(ffi)
            ticks = ffi["ticks_per_day"] * ffi["num_days"]
            costs.append(orch.run_and_get_total_cost("BANK_A", ticks))
        assert len(set(costs)) >= 2, f"All seeds produced identical cost: {costs[0]}"

    def test_cost_is_positive(self):
        """Stochastic scenario should always have nonzero cost."""
        orch, ticks = _make_orchestrator()
        cost = orch.run_and_get_total_cost("BANK_A", ticks)
        assert cost > 0

    def test_invalid_agent_raises(self):
        orch, ticks = _make_orchestrator()
        with pytest.raises((ValueError, KeyError)):
            orch.run_and_get_total_cost("NONEXISTENT_BANK", ticks)

    def test_zero_ticks_raises(self):
        orch, _ = _make_orchestrator()
        with pytest.raises(ValueError):
            orch.run_and_get_total_cost("BANK_A", 0)


class TestRunAndGetAllCosts:
    """Tests for Orchestrator.run_and_get_all_costs()."""

    def test_method_exists(self):
        orch, _ticks = _make_orchestrator()
        assert hasattr(orch, "run_and_get_all_costs")

    def test_returns_json_string(self):
        orch, ticks = _make_orchestrator()
        result = orch.run_and_get_all_costs(ticks)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_all_agents(self):
        orch, ticks = _make_orchestrator()
        result = json.loads(orch.run_and_get_all_costs(ticks))
        assert "BANK_A" in result
        assert "BANK_B" in result

    def test_contains_cost_fields(self):
        orch, ticks = _make_orchestrator()
        result = json.loads(orch.run_and_get_all_costs(ticks))
        for aid, agent_costs in result.items():
            assert "total_cost" in agent_costs, f"{aid} missing total_cost"
            assert "liquidity_cost" in agent_costs, f"{aid} missing liquidity_cost"
            assert "delay_cost" in agent_costs, f"{aid} missing delay_cost"
            assert "penalty_cost" in agent_costs, f"{aid} missing penalty_cost"

    def test_matches_manual_tick_loop(self):
        """CRITICAL: Determinism invariant for all-costs path."""
        seed = 42

        orch_a, ticks = _make_orchestrator(seed)
        result_a = json.loads(orch_a.run_and_get_all_costs(ticks))

        orch_b, ticks = _make_orchestrator(seed)
        for _ in range(ticks):
            orch_b.tick()
        costs_a = orch_b.get_agent_accumulated_costs("BANK_A")
        costs_b = orch_b.get_agent_accumulated_costs("BANK_B")

        assert result_a["BANK_A"]["total_cost"] == costs_a["total_cost"]
        assert result_a["BANK_B"]["total_cost"] == costs_b["total_cost"]
        assert result_a["BANK_A"]["liquidity_cost"] == costs_a["liquidity_cost"]
        assert result_a["BANK_B"]["delay_cost"] == costs_b["delay_cost"]

    def test_zero_ticks_raises(self):
        orch, _ = _make_orchestrator()
        with pytest.raises(ValueError):
            orch.run_and_get_all_costs(0)


class TestThreadSafety:
    """Verify concurrent execution produces correct, deterministic results."""

    def test_concurrent_simulations_deterministic(self):
        """Run 10 simulations concurrently. Each must produce the same cost
        as running sequentially with the same seed."""
        seeds = [42 + i * 1000 for i in range(10)]

        # Sequential baseline
        sequential_costs = []
        for seed in seeds:
            orch, ticks = _make_orchestrator(seed)
            cost = orch.run_and_get_total_cost("BANK_A", ticks)
            sequential_costs.append(cost)

        # Concurrent execution
        def run_one(seed):
            orch, ticks = _make_orchestrator(seed)
            return orch.run_and_get_total_cost("BANK_A", ticks)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            concurrent_costs = list(pool.map(run_one, seeds))

        assert sequential_costs == concurrent_costs, (
            f"Thread safety violation!\n"
            f"Sequential: {sequential_costs}\n"
            f"Concurrent: {concurrent_costs}"
        )

    def test_concurrent_different_agents(self):
        """Two threads, same seed, different agents — must match sequential."""
        seed = 42

        def run_agent(agent_id):
            orch, ticks = _make_orchestrator(seed)
            return orch.run_and_get_total_cost(agent_id, ticks)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(run_agent, "BANK_A")
            future_b = pool.submit(run_agent, "BANK_B")
            cost_a = future_a.result()
            cost_b = future_b.result()

        # Verify against sequential
        orch_seq, ticks = _make_orchestrator(seed)
        for _ in range(ticks):
            orch_seq.tick()
        expected_a = orch_seq.get_agent_accumulated_costs("BANK_A")["total_cost"]
        expected_b = orch_seq.get_agent_accumulated_costs("BANK_B")["total_cost"]

        assert cost_a == expected_a
        assert cost_b == expected_b

    def test_concurrent_all_costs(self):
        """Concurrent run_and_get_all_costs() produces deterministic results."""
        seeds = [42 + i * 1000 for i in range(5)]

        def run_one(seed):
            orch, ticks = _make_orchestrator(seed)
            return json.loads(orch.run_and_get_all_costs(ticks))

        # Sequential
        sequential = [run_one(s) for s in seeds]

        # Concurrent
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            concurrent_results = list(pool.map(run_one, seeds))

        for i, seed in enumerate(seeds):
            for agent in ["BANK_A", "BANK_B"]:
                assert sequential[i][agent]["total_cost"] == concurrent_results[i][agent]["total_cost"], (
                    f"Seed {seed}, {agent}: {sequential[i][agent]['total_cost']} != {concurrent_results[i][agent]['total_cost']}"
                )


class TestParallelBootstrap:
    """Verify parallel bootstrap produces identical results to sequential."""

    def test_parallel_deterministic(self):
        """Two calls to evaluate() with same inputs produce identical results."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.bootstrap_eval import WebBootstrapEvaluator

        with open(EXP2_CONFIG) as f:
            raw = yaml.safe_load(f)

        old_policy = {
            "version": "2.0", "policy_id": "old",
            "parameters": {"initial_liquidity_fraction": 0.5},
            "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
            "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
        }
        new_policy = {
            "version": "2.0", "policy_id": "new",
            "parameters": {"initial_liquidity_fraction": 0.1},
            "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
            "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
        }

        evaluator = WebBootstrapEvaluator(num_samples=10, cv_threshold=0.5)
        r1 = evaluator.evaluate(raw, "BANK_A", old_policy, new_policy, 42)
        r2 = evaluator.evaluate(raw, "BANK_A", old_policy, new_policy, 42)

        assert r1.delta_sum == r2.delta_sum
        assert r1.accepted == r2.accepted
        assert r1.mean_delta == r2.mean_delta
        assert r1.old_mean_cost == r2.old_mean_cost
        assert r1.new_mean_cost == r2.new_mean_cost

    def test_fast_matches_legacy(self):
        """_run_sim_fast (GIL-release) produces same cost as _run_sim (tick loop)."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.bootstrap_eval import WebBootstrapEvaluator

        with open(EXP2_CONFIG) as f:
            raw = yaml.safe_load(f)

        policy = {
            "version": "2.0", "policy_id": "test",
            "parameters": {"initial_liquidity_fraction": 0.3},
            "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
            "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
        }

        ev = WebBootstrapEvaluator(num_samples=1)
        cost_fast = ev._run_sim_fast(raw, "BANK_A", policy, 42)
        cost_legacy = ev._run_sim(raw, "BANK_A", policy, 42)
        assert cost_fast == cost_legacy
