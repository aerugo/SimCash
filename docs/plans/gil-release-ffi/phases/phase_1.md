# Phase 1: Rust FFI Methods

**Status**: Planned

## Objective

Add two new GIL-releasing methods to `PyOrchestrator` in `simulator/src/ffi/orchestrator.rs`.

## Invariants

- INV-1: All 105 existing Rust tests continue to pass
- INV-2: All 581 existing Python unit tests continue to pass
- INV-3: Determinism — same (config, seed) produces identical cost via `run_and_get_total_cost()` and via manual `tick()` + `get_agent_accumulated_costs()`
- INV-4: Error handling — invalid agent_id returns PyErr, not panic

## TDD Steps

### Step 1.1: RED — Rust Doc Test for `run_and_get_total_cost`

Add a doc test that calls the new method. It won't compile yet (method doesn't exist).

```rust
/// Run N ticks with GIL released and return one agent's total accumulated cost.
///
/// This is the "bootstrap fast path" — releases the Python GIL during
/// simulation so multiple simulations can run in parallel via Python threads.
///
/// Each `Orchestrator` instance is independent (own state, own RNG),
/// so concurrent execution on separate instances is safe.
///
/// # Arguments
///
/// * `agent_id` - Agent identifier (e.g., "BANK_A")
/// * `num_ticks` - Number of ticks to simulate
///
/// # Returns
///
/// Total accumulated cost for the agent (i64, in cents)
///
/// # Errors
///
/// - `PyValueError` if agent_id not found
/// - `PyValueError` if num_ticks is 0
/// - `PyRuntimeError` if tick execution fails
fn run_and_get_total_cost(&mut self, py: Python, agent_id: String, num_ticks: usize) -> PyResult<i64>
```

Note: Doc tests require PyO3 (`--features pyo3`) which we skip in CI. So the **real** RED test is a Python test.

### Step 1.2: RED — Python Test for `run_and_get_total_cost`

Create `web/backend/tests/test_gil_release.py`:

```python
"""Tests for GIL-releasing FFI methods."""
import json
import copy
import yaml
import concurrent.futures
from pathlib import Path

import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.config.schemas import SimulationConfig

CONFIGS_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs" / "papers" / "simcash-paper" / "paper_generator" / "configs"
EXP2_CONFIG = CONFIGS_DIR / "exp2_12period.yaml"

POLICY_JSON = json.dumps({
    "version": "2.0",
    "policy_id": "test",
    "parameters": {"initial_liquidity_fraction": 0.1},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
})


def _make_orchestrator(seed: int = 42) -> tuple[dict, int]:
    """Create an Orchestrator from exp2 config with given seed. Returns (orch, num_ticks)."""
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
        """The method is callable on Orchestrator."""
        orch, ticks = _make_orchestrator()
        assert hasattr(orch, "run_and_get_total_cost")

    def test_returns_i64(self):
        """Returns an integer cost."""
        orch, ticks = _make_orchestrator()
        cost = orch.run_and_get_total_cost("BANK_A", ticks)
        assert isinstance(cost, int)

    def test_matches_manual_tick_loop(self):
        """CRITICAL: Same config+seed must produce identical cost whether
        we use run_and_get_total_cost() or manual tick() + get_agent_accumulated_costs().
        This is the determinism invariant."""
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

    def test_different_seeds_different_costs(self):
        """Stochastic scenario produces different costs with different seeds."""
        orch1, ticks = _make_orchestrator(seed=42)
        orch2, ticks = _make_orchestrator(seed=9999)
        cost1 = orch1.run_and_get_total_cost("BANK_A", ticks)
        cost2 = orch2.run_and_get_total_cost("BANK_A", ticks)
        # Very unlikely to be equal with different seeds on stochastic scenario
        assert cost1 != cost2

    def test_invalid_agent_raises(self):
        """Invalid agent_id raises ValueError."""
        orch, ticks = _make_orchestrator()
        with pytest.raises((ValueError, KeyError)):
            orch.run_and_get_total_cost("NONEXISTENT_BANK", ticks)

    def test_zero_ticks_raises(self):
        """Zero ticks should raise ValueError."""
        orch, _ = _make_orchestrator()
        with pytest.raises(ValueError):
            orch.run_and_get_total_cost("BANK_A", 0)

    def test_both_agents_same_seed(self):
        """Can get costs for both agents from same Orchestrator run."""
        orch, ticks = _make_orchestrator()
        cost_a = orch.run_and_get_total_cost("BANK_A", ticks)
        # Note: Orchestrator already ran all ticks. Getting cost for B
        # should just read accumulated state (0 additional ticks).
        # Actually, we need a SEPARATE orchestrator for B because
        # run_and_get_total_cost already consumed all ticks.
        orch2, ticks = _make_orchestrator()
        cost_b = orch2.run_and_get_total_cost("BANK_B", ticks)
        # Both should have costs > 0 (stochastic scenario has arrivals)
        assert cost_a > 0
        assert cost_b > 0


class TestRunAndGetAllCosts:
    """Tests for Orchestrator.run_and_get_all_costs()."""

    def test_method_exists(self):
        orch, ticks = _make_orchestrator()
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
        for agent_costs in result.values():
            assert "total_cost" in agent_costs
            assert "liquidity_cost" in agent_costs
            assert "delay_cost" in agent_costs

    def test_matches_manual_tick_loop(self):
        """CRITICAL: Determinism invariant for all-costs path."""
        seed = 42

        # Path A: new method
        orch_a, ticks = _make_orchestrator(seed)
        result_a = json.loads(orch_a.run_and_get_all_costs(ticks))

        # Path B: manual tick loop
        orch_b, ticks = _make_orchestrator(seed)
        for _ in range(ticks):
            orch_b.tick()
        costs_b_a = orch_b.get_agent_accumulated_costs("BANK_A")
        costs_b_b = orch_b.get_agent_accumulated_costs("BANK_B")

        assert result_a["BANK_A"]["total_cost"] == costs_b_a["total_cost"]
        assert result_a["BANK_B"]["total_cost"] == costs_b_b["total_cost"]

    def test_zero_ticks_raises(self):
        orch, _ = _make_orchestrator()
        with pytest.raises(ValueError):
            orch.run_and_get_all_costs(0)


class TestThreadSafety:
    """Verify concurrent execution produces correct, deterministic results."""

    def test_concurrent_simulations_deterministic(self):
        """Run 10 simulations concurrently on threads. Each must produce the
        same cost as running sequentially with the same seed."""
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
            f"Thread safety violation: sequential != concurrent\n"
            f"Sequential: {sequential_costs}\n"
            f"Concurrent: {concurrent_costs}"
        )

    def test_concurrent_different_agents(self):
        """Two threads running the same seed but querying different agents."""
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
```

### Step 1.3: GREEN — Implement Rust Methods

Add to `simulator/src/ffi/orchestrator.rs` inside `#[pymethods] impl PyOrchestrator`:

```rust
/// Run N ticks with GIL released, return one agent's total cost (i64).
///
/// Releases the Python GIL during simulation for thread-level parallelism.
/// Each Orchestrator is independent, so concurrent execution is safe.
///
/// # Arguments
/// * `agent_id` - Agent identifier
/// * `num_ticks` - Number of ticks to run
///
/// # Returns
/// Total accumulated cost for the agent (cents, i64)
fn run_and_get_total_cost(
    &mut self,
    py: Python,
    agent_id: String,
    num_ticks: usize,
) -> PyResult<i64> {
    // Validate BEFORE releasing GIL
    if num_ticks == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "num_ticks must be > 0",
        ));
    }
    if self.inner.get_costs(&agent_id).is_none() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            format!("Agent not found: {}", agent_id),
        ));
    }

    // Release GIL — other Python threads can run
    let result = py.allow_threads(|| {
        for _ in 0..num_ticks {
            self.inner.tick().map_err(|e| format!("{}", e))?;
        }
        self.inner
            .get_costs(&agent_id)
            .map(|c| c.total())
            .ok_or_else(|| format!("Agent {} costs missing after simulation", agent_id))
    });

    result.map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

/// Run N ticks with GIL released, return all agents' costs as JSON.
///
/// Returns a JSON object: { "BANK_A": { "total_cost": ..., "liquidity_cost": ..., ... }, ... }
fn run_and_get_all_costs(
    &mut self,
    py: Python,
    num_ticks: usize,
) -> PyResult<String> {
    if num_ticks == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "num_ticks must be > 0",
        ));
    }

    let agent_ids = self.inner.get_agent_ids();

    let result = py.allow_threads(|| {
        for _ in 0..num_ticks {
            self.inner.tick().map_err(|e| format!("{}", e))?;
        }

        let mut map = serde_json::Map::new();
        for aid in &agent_ids {
            if let Some(costs) = self.inner.get_costs(aid) {
                let mut entry = serde_json::Map::new();
                entry.insert("total_cost".into(), serde_json::Value::Number(costs.total().into()));
                entry.insert("liquidity_cost".into(), serde_json::Value::Number(costs.total_liquidity_cost.into()));
                entry.insert("delay_cost".into(), serde_json::Value::Number(costs.total_delay_cost.into()));
                entry.insert("collateral_cost".into(), serde_json::Value::Number(costs.total_collateral_cost.into()));
                entry.insert("penalty_cost".into(), serde_json::Value::Number(costs.total_penalty_cost.into()));
                entry.insert("split_friction_cost".into(), serde_json::Value::Number(costs.total_split_friction_cost.into()));
                map.insert(aid.clone(), serde_json::Value::Object(entry));
            }
        }
        serde_json::to_string(&serde_json::Value::Object(map))
            .map_err(|e| format!("JSON serialization failed: {}", e))
    });

    result.map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}
```

### Step 1.4: Build and Test

```bash
# 1. Build the Rust extension
cd api && maturin develop --release

# 2. Run new Python tests (should pass now)
uv run pytest web/backend/tests/test_gil_release.py -v

# 3. Run ALL existing test suites (regression check)
cargo test --manifest-path simulator/Cargo.toml --no-default-features
cd api && uv run pytest tests/unit/ -v
uv run pytest web/backend/tests/ -v --ignore=web/backend/tests/test_real_llm.py
```

### Step 1.5: REFACTOR

Review the Rust code for:
- Doc comment completeness
- Error message clarity
- Consistent naming with existing FFI methods

## Files Changed

| File | Action | Risk |
|------|--------|------|
| `simulator/src/ffi/orchestrator.rs` | Add 2 methods (~60 lines) | Medium — core FFI |
| `web/backend/tests/test_gil_release.py` | Create (~170 lines) | None — test only |

## Verification Checklist

- [ ] `run_and_get_total_cost` returns identical cost as `tick()` loop (determinism)
- [ ] `run_and_get_all_costs` returns identical costs for all agents (determinism)
- [ ] Invalid agent_id raises ValueError (not panic)
- [ ] Zero ticks raises ValueError (not panic)
- [ ] 10 concurrent threads produce deterministic results
- [ ] 105 Rust tests still pass
- [ ] 581 Python unit tests still pass
- [ ] 63 web backend tests still pass
