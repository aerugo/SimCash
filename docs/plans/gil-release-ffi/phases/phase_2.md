# Phase 2: Thread-Parallel Bootstrap Evaluation

**Status**: Planned  
**Depends on**: Phase 1 (GIL-release FFI methods)

## Objective

Replace the sequential simulation loop in `WebBootstrapEvaluator.evaluate()` with a `ThreadPoolExecutor` using the new `run_and_get_total_cost()` method. This parallelizes the 2×N simulation runs in bootstrap evaluation.

## Invariants

- INV-1: Bootstrap evaluation produces **identical acceptance decisions** for given inputs (determinism)
- INV-2: All 8 existing `test_bootstrap_eval.py` tests continue to pass
- INV-3: Cost deltas are identical whether computed sequentially or in parallel

## TDD Steps

### Step 2.1: RED — Write Failing Test

Add to `web/backend/tests/test_gil_release.py`:

```python
class TestParallelBootstrap:
    """Verify parallel bootstrap produces identical results to sequential."""

    def test_parallel_matches_sequential(self):
        """CRITICAL: Parallel and sequential bootstrap must produce
        identical EvaluationResult for same inputs."""
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
        result = evaluator.evaluate(
            raw_yaml=raw,
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            base_seed=42,
        )

        # Run again — must be deterministic
        result2 = evaluator.evaluate(
            raw_yaml=raw,
            agent_id="BANK_A",
            old_policy=old_policy,
            new_policy=new_policy,
            base_seed=42,
        )

        assert result.delta_sum == result2.delta_sum
        assert result.accepted == result2.accepted
        assert result.paired_deltas == result2.paired_deltas
```

### Step 2.2: GREEN — Implement Parallel Bootstrap

Modify `web/backend/app/bootstrap_eval.py`:

```python
import concurrent.futures

class WebBootstrapEvaluator:
    def __init__(self, num_samples=10, cv_threshold=0.5, max_workers=None):
        self.num_samples = num_samples
        self.cv_threshold = cv_threshold
        self.max_workers = max_workers  # None = ThreadPoolExecutor default

    def evaluate(self, raw_yaml, agent_id, old_policy, new_policy, base_seed, other_policies=None):
        seeds = [base_seed + i * 1000 for i in range(self.num_samples)]

        # Run all simulations in parallel using GIL-releasing FFI
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            old_futures = {
                seed: pool.submit(self._run_sim_fast, raw_yaml, agent_id, old_policy, seed, other_policies)
                for seed in seeds
            }
            new_futures = {
                seed: pool.submit(self._run_sim_fast, raw_yaml, agent_id, new_policy, seed, other_policies)
                for seed in seeds
            }

            old_costs = [old_futures[s].result() for s in seeds]
            new_costs = [new_futures[s].result() for s in seeds]

        # ... rest of evaluation unchanged (delta computation, CI, acceptance)

    def _run_sim_fast(self, raw_yaml, agent_id, policy, seed, other_policies):
        """Run a simulation using GIL-releasing run_and_get_total_cost()."""
        scenario = copy.deepcopy(raw_yaml)
        # ... same setup as _run_sim ...
        orch = Orchestrator.new(ffi_config)
        return orch.run_and_get_total_cost(agent_id, ticks)
```

### Step 2.3: REFACTOR

- Keep `_run_sim()` as fallback (in case anyone calls it directly)
- Add `parallel: bool = True` parameter to `evaluate()` for easy toggle
- Ensure thread pool is not created for `num_samples=1` (wasteful)

## Files Changed

| File | Action |
|------|--------|
| `web/backend/app/bootstrap_eval.py` | Modify — add thread parallelism |
| `web/backend/tests/test_gil_release.py` | Add `TestParallelBootstrap` |

## Verification

```bash
# New tests
uv run pytest web/backend/tests/test_gil_release.py -v

# Existing bootstrap tests (regression)
uv run pytest web/backend/tests/test_bootstrap_eval.py -v

# Full web backend suite
uv run pytest web/backend/tests/ -v --ignore=.../test_real_llm.py
```
