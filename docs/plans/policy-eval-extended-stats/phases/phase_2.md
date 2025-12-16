# Phase 2: Metrics Capture

**Status**: Pending
**Started**:

---

## Objective

Capture extended metrics (settlement rate, avg delay, cost breakdown, per-agent stats) during policy evaluation simulations and propagate them through to persistence.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - Cost breakdown values remain integer cents
- **INV-2**: Determinism is Sacred - Metrics captured from deterministic simulations are reproducible

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Add tests to `api/tests/experiments/runner/test_policy_evaluation_metrics.py`:

**Test Cases**:
1. `test_simulation_result_includes_system_metrics` - SimulationResult has settlement_rate, avg_delay
2. `test_simulation_result_includes_cost_breakdown` - Cost breakdown captured
3. `test_deterministic_eval_captures_metrics` - Metrics captured in deterministic mode
4. `test_bootstrap_eval_captures_aggregate_metrics` - Aggregate metrics from bootstrap
5. `test_evaluate_policy_pair_returns_metrics` - PolicyPairEvaluation includes metrics
6. `test_per_agent_stats_captured` - Per-agent metrics captured
7. `test_metrics_propagate_to_persistence` - Full flow from simulation to database
8. `test_metrics_match_orchestrator_values` - Values match FFI queries

```python
class TestMetricsCapture:
    """Tests for capturing extended metrics during evaluation."""

    def test_simulation_result_has_settlement_rate(self) -> None:
        """SimulationResult should include settlement_rate from orchestrator."""
        # Existing SimulationResult already has settlement_rate field
        from payment_simulator.experiments.runner.bootstrap_support import SimulationResult

        # Verify field exists (it does)
        assert hasattr(SimulationResult, '__dataclass_fields__')
        assert 'settlement_rate' in SimulationResult.__dataclass_fields__

    def test_evaluate_policy_pair_deterministic_captures_metrics(
        self, optimization_loop_fixture
    ) -> None:
        """Deterministic evaluation should capture system metrics."""
        loop = optimization_loop_fixture

        # Run evaluation
        evaluation = loop._evaluate_policy_pair(
            agent_id="BANK_A",
            old_policy={"type": "Fifo"},
            new_policy={"type": "Fifo"},  # Same policy for simplicity
        )

        # Verify metrics are captured (new fields to be added)
        assert evaluation.settlement_rate is not None
        assert evaluation.avg_delay is not None
        assert evaluation.cost_breakdown is not None
        assert isinstance(evaluation.settlement_rate, float)
        assert 0.0 <= evaluation.settlement_rate <= 1.0

    def test_evaluate_policy_pair_bootstrap_captures_aggregate_metrics(
        self, optimization_loop_with_bootstrap_fixture
    ) -> None:
        """Bootstrap evaluation should capture aggregate metrics across samples."""
        loop = optimization_loop_with_bootstrap_fixture

        evaluation = loop._evaluate_policy_pair(
            agent_id="BANK_A",
            old_policy={"type": "Fifo"},
            new_policy={"type": "LiquidityAware", "threshold": 50000},
        )

        # Verify aggregate metrics
        assert evaluation.settlement_rate is not None
        assert evaluation.avg_delay is not None
        assert evaluation.agent_stats is not None

        # Per-agent stats should exist
        assert "BANK_A" in evaluation.agent_stats
        assert "cost" in evaluation.agent_stats["BANK_A"]

    def test_metrics_propagate_to_saved_record(
        self, optimization_loop_with_repo_fixture
    ) -> None:
        """Extended metrics should be saved to PolicyEvaluationRecord."""
        loop = optimization_loop_with_repo_fixture

        # Run optimization which triggers _save_policy_evaluation
        # ... (implementation-specific setup)

        # Retrieve saved record
        records = loop._repository.get_policy_evaluations(loop._run_id, "BANK_A")
        assert len(records) > 0

        record = records[0]
        # Verify extended stats are persisted
        assert record.settlement_rate is not None
        assert record.avg_delay is not None
        assert record.cost_breakdown is not None
```

### Step 2.2: Implement to Pass Tests (GREEN)

**Modify** `api/payment_simulator/experiments/runner/optimization.py`:

1. **Extend `PolicyPairEvaluation`** to include aggregate metrics:

```python
@dataclass(frozen=True)
class PolicyPairEvaluation:
    """Complete results from evaluating old vs new policy."""

    sample_results: list[SampleEvaluationResult]
    delta_sum: int
    mean_old_cost: int
    mean_new_cost: int

    # Extended metrics (NEW)
    settlement_rate: float | None = None  # System-wide
    avg_delay: float | None = None  # System-wide
    cost_breakdown: dict[str, int] | None = None  # Total cost breakdown
    agent_stats: dict[str, dict[str, Any]] | None = None  # Per-agent metrics
```

2. **Update `_run_single_simulation()`** to return extended metrics:

The `SimulationResult` already has `settlement_rate`, `avg_delay`, and `cost_breakdown`. We need to ensure these are captured and aggregated.

3. **Update `_evaluate_policy_pair()`** - Deterministic path:

```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> PolicyPairEvaluation:
    """Evaluate old vs new policy with paired samples."""

    if self._config.evaluation.mode == "deterministic" or num_samples <= 1:
        seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

        # Evaluate new policy (we care about new policy metrics for persistence)
        self._policies[agent_id] = new_policy
        sim_result, new_costs = self._run_single_simulation(seed)
        new_cost = new_costs.get(agent_id, 0)

        # Capture metrics from simulation result
        settlement_rate = sim_result.settlement_rate
        avg_delay = sim_result.avg_delay
        cost_breakdown = {
            "delay_cost": sim_result.cost_breakdown.delay_cost,
            "overdraft_cost": sim_result.cost_breakdown.overdraft_cost,
            "deadline_penalty": sim_result.cost_breakdown.deadline_penalty,
            "eod_penalty": sim_result.cost_breakdown.eod_penalty,
        }

        # Build per-agent stats
        agent_stats = {}
        for aid, cost in sim_result.per_agent_costs.items():
            agent_stats[aid] = {
                "cost": cost,
                "settlement_rate": settlement_rate,  # System-wide for now
                "avg_delay": avg_delay,
            }

        # ... rest of implementation

        return PolicyPairEvaluation(
            sample_results=[...],
            delta_sum=delta,
            mean_old_cost=old_cost,
            mean_new_cost=new_cost,
            settlement_rate=settlement_rate,
            avg_delay=avg_delay,
            cost_breakdown=cost_breakdown,
            agent_stats=agent_stats,
        )
```

4. **Update `_evaluate_policy_pair()`** - Bootstrap path:

For bootstrap, we need to aggregate metrics across samples. Use the last sample's metrics or compute means.

```python
# Bootstrap mode - aggregate metrics from samples
if self._bootstrap_samples and agent_id in self._bootstrap_samples:
    # ... existing evaluation code ...

    # Capture metrics from final sample (representative)
    # Or compute mean across samples if we track per-sample metrics
    last_result = evaluator.evaluate_sample(samples[-1], new_policy)

    settlement_rate = last_result.settlement_rate
    avg_delay = last_result.avg_delay
    # ... build agent_stats ...
```

5. **Update `_save_policy_evaluation()`** to accept and pass extended metrics:

```python
def _save_policy_evaluation(
    self,
    agent_id: str,
    evaluation_mode: str,
    proposed_policy: dict[str, Any],
    old_cost: int,
    new_cost: int,
    context_simulation_cost: int,
    accepted: bool,
    acceptance_reason: str,
    delta_sum: int,
    num_samples: int,
    sample_details: list[dict[str, Any]] | None,
    scenario_seed: int | None,
    # Extended metrics (NEW)
    settlement_rate: float | None = None,
    avg_delay: float | None = None,
    cost_breakdown: dict[str, int] | None = None,
    cost_std_dev: int | None = None,
    confidence_interval_95: list[int] | None = None,
    agent_stats: dict[str, dict[str, Any]] | None = None,
) -> None:
    # ... build record with extended fields ...
```

### Step 2.3: Refactor

- Extract metrics capture logic into helper functions
- Ensure consistent metrics aggregation across paths
- Add type hints and docstrings

---

## Implementation Details

### Metrics Sources

| Metric | Source | Path |
|--------|--------|------|
| `settlement_rate` | `orch.get_system_metrics()["settlement_rate"]` | Via SimulationResult |
| `avg_delay` | `orch.get_system_metrics()["avg_delay_ticks"]` | Via SimulationResult |
| `cost_breakdown` | `SimulationResult.cost_breakdown` | Already captured |
| `per_agent_costs` | `SimulationResult.per_agent_costs` | Already captured |

### Per-Agent Metrics

For per-agent metrics, the system-level `settlement_rate` and `avg_delay` are used as approximations. True per-agent settlement rates would require additional FFI methods or event filtering. This is acceptable for the initial implementation.

### Bootstrap Aggregation

For bootstrap mode with N samples:
- `settlement_rate`: Mean across samples (if tracked) or last sample
- `avg_delay`: Mean across samples or last sample
- `cost_breakdown`: Mean per component across samples (or representative sample)
- `agent_stats`: Aggregated per-agent costs with representative metrics

### Edge Cases to Handle

- No transactions arrived (settlement_rate = 1.0 by convention)
- No transactions settled (avg_delay = 0.0)
- Agent not present in some samples (bootstrap)

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |
| `api/tests/experiments/runner/test_policy_evaluation_metrics.py` | MODIFY (add tests) |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_policy_evaluation_metrics.py -v -k "metrics_capture or evaluate_policy"

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] `PolicyPairEvaluation` has extended metrics fields
- [ ] Deterministic evaluation captures `settlement_rate`, `avg_delay`, `cost_breakdown`
- [ ] Bootstrap evaluation captures aggregate metrics
- [ ] Per-agent stats captured in `agent_stats` dict
- [ ] Metrics propagate from `_evaluate_policy_pair()` to `_save_policy_evaluation()`
- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
