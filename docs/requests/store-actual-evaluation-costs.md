# Feature Request: Store Actual Evaluation Costs (Not Estimates)

**Date**: 2025-12-16
**Priority**: High
**Supersedes**: `persist-policy-evaluation-metrics.md` (do not implement that request)
**Affects**: `payment_simulator.experiments.runner.optimization`, `payment_simulator.experiments.persistence`

## Summary

Refactor policy evaluation to capture and persist **actual computed costs** from simulations rather than reconstructed estimates. Currently, `_should_accept_policy()` returns an estimated `new_cost` derived from `current_cost - mean_delta`, discarding the real costs computed during evaluation.

## Problem Statement

### The Core Issue

In `_should_accept_policy()` (lines 2071-2081 of `optimization.py`):

```python
# Compute mean costs for display/logging
# Note: These are approximations based on deltas and current_cost
# For accurate display, we'd need to track costs during evaluation
num_samples = len(deltas)
mean_delta = delta_sum / num_samples if num_samples > 0 else 0

# Estimate old/new costs for display
# old_cost ≈ current_cost (from context simulation)
# new_cost ≈ old_cost - mean_delta
old_cost = current_cost
new_cost = current_cost - mean_delta
```

The `eval_new_cost` value being stored is **not** the actual cost computed during policy evaluation. It's reconstructed as:

```
eval_new_cost = current_cost - mean_delta
```

Where:
- `current_cost` = cost from a **single context simulation** at iteration start
- `mean_delta` = average of `(old_cost - new_cost)` across bootstrap samples

### Why This Is Wrong

#### Mathematical Inaccuracy

The estimate assumes `current_cost == mean(bootstrap_old_costs)`, which is only approximately true:

```
If: mean(bootstrap_old_costs) = 95,000 cents
    current_cost = 100,000 cents  (different scenario/seed)
    mean_delta = 10,000 cents

Then:
    Actual mean new cost = 95,000 - 10,000 = 85,000 cents
    Estimated new cost   = 100,000 - 10,000 = 90,000 cents  ← WRONG
```

#### Deterministic Mode: Real Costs Discarded

In deterministic mode (`_evaluate_policy_pair` lines 1506-1524), we **do** compute actual costs:

```python
# Evaluate old policy
self._policies[agent_id] = old_policy
_, old_costs = self._run_single_simulation(seed)
old_cost = old_costs.get(agent_id, 0)  # ← ACTUAL COST

# Evaluate new policy
self._policies[agent_id] = new_policy
_, new_costs = self._run_single_simulation(seed)
new_cost = new_costs.get(agent_id, 0)  # ← ACTUAL COST

delta = old_cost - new_cost
return [delta], delta  # ← ONLY DELTA RETURNED, COSTS DISCARDED!
```

We compute the real `new_cost` from simulation, then throw it away and reconstruct an estimate.

#### Bootstrap Mode: Per-Sample Costs Never Captured

In bootstrap mode, `BootstrapPolicyEvaluator.compute_paired_deltas()` returns `PairedDelta` objects containing only the delta:

```python
@dataclass
class PairedDelta:
    """Result of evaluating a policy pair on one sample."""
    sample_index: int
    delta: int  # old_cost - new_cost
    # Missing: old_cost, new_cost
```

The actual per-sample costs computed during evaluation are never captured.

### Impact on Data Quality

1. **Inaccurate cost values**: Charts and analysis show estimated costs, not actual
2. **Lost audit trail**: Cannot verify what costs were actually computed
3. **No per-sample visibility**: Cannot analyze cost distribution across bootstrap samples
4. **Research validity concerns**: Published results based on estimates, not measurements

## Proposed Solution

### Design Goals

1. **Capture actual costs**: Return real computed costs from evaluation, not estimates
2. **Per-sample granularity**: For bootstrap, store costs for each sample
3. **Both paths covered**: Handle deterministic and bootstrap modes consistently
4. **Minimal signature changes**: Extend return values rather than redesign

### Phase 1: Extend `_evaluate_policy_pair` Return Type

Change from returning `(deltas, delta_sum)` to returning a rich evaluation result:

```python
@dataclass(frozen=True)
class PolicyPairEvaluation:
    """Complete results from evaluating old vs new policy.

    All costs in integer cents (INV-1).
    """
    # Per-sample results
    sample_results: list[SampleEvaluationResult]

    # Aggregates (computed from sample_results)
    delta_sum: int  # Sum of (old_cost - new_cost) across samples
    mean_old_cost: int  # Mean of old_cost across samples
    mean_new_cost: int  # Mean of new_cost across samples

    @property
    def deltas(self) -> list[int]:
        """List of deltas for backward compatibility."""
        return [s.delta for s in self.sample_results]

    @property
    def num_samples(self) -> int:
        return len(self.sample_results)


@dataclass(frozen=True)
class SampleEvaluationResult:
    """Result of evaluating policy pair on a single sample.

    All costs in integer cents (INV-1).
    """
    sample_index: int
    seed: int  # Seed used for this sample (for reproducibility)
    old_cost: int  # Actual cost with old policy
    new_cost: int  # Actual cost with new policy
    delta: int  # old_cost - new_cost (positive = improvement)
```

### Phase 2: Update Deterministic Path

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

        # Evaluate old policy
        self._policies[agent_id] = old_policy
        _, old_costs = self._run_single_simulation(seed)
        old_cost = old_costs.get(agent_id, 0)

        # Evaluate new policy
        self._policies[agent_id] = new_policy
        _, new_costs = self._run_single_simulation(seed)
        new_cost = new_costs.get(agent_id, 0)

        # Restore old policy
        self._policies[agent_id] = old_policy

        delta = old_cost - new_cost

        # Return ACTUAL costs, not estimates
        sample_result = SampleEvaluationResult(
            sample_index=0,
            seed=seed,
            old_cost=old_cost,
            new_cost=new_cost,
            delta=delta,
        )

        return PolicyPairEvaluation(
            sample_results=[sample_result],
            delta_sum=delta,
            mean_old_cost=old_cost,
            mean_new_cost=new_cost,
        )
```

### Phase 3: Update Bootstrap Path

#### 3a: Extend `PairedDelta` in evaluator.py

```python
@dataclass(frozen=True)
class PairedDelta:
    """Result of evaluating a policy pair on one sample."""
    sample_index: int
    delta: int  # old_cost - new_cost
    old_cost: int  # NEW: Actual cost with policy A
    new_cost: int  # NEW: Actual cost with policy B
```

#### 3b: Update `compute_paired_deltas` to return costs

```python
def compute_paired_deltas(
    self,
    samples: list[BootstrapSample],
    policy_a: dict[str, Any],
    policy_b: dict[str, Any],
) -> list[PairedDelta]:
    """Compute paired deltas between two policies.

    Returns PairedDelta with actual costs for each sample.
    """
    results = []
    for i, sample in enumerate(samples):
        cost_a = self._evaluate_policy_on_sample(policy_a, sample)
        cost_b = self._evaluate_policy_on_sample(policy_b, sample)

        results.append(PairedDelta(
            sample_index=i,
            delta=cost_a - cost_b,
            old_cost=cost_a,  # Actual computed cost
            new_cost=cost_b,  # Actual computed cost
        ))

    return results
```

#### 3c: Update bootstrap path in `_evaluate_policy_pair`

```python
# Bootstrap mode
if self._bootstrap_samples and agent_id in self._bootstrap_samples:
    samples = self._bootstrap_samples[agent_id]
    evaluator = BootstrapPolicyEvaluator(...)

    paired_deltas = evaluator.compute_paired_deltas(
        samples=samples,
        policy_a=old_policy,
        policy_b=new_policy,
    )

    # Build sample results with ACTUAL costs
    sample_results = [
        SampleEvaluationResult(
            sample_index=pd.sample_index,
            seed=samples[pd.sample_index].seed if hasattr(samples[pd.sample_index], 'seed') else 0,
            old_cost=pd.old_cost,
            new_cost=pd.new_cost,
            delta=pd.delta,
        )
        for pd in paired_deltas
    ]

    return PolicyPairEvaluation(
        sample_results=sample_results,
        delta_sum=sum(pd.delta for pd in paired_deltas),
        mean_old_cost=sum(pd.old_cost for pd in paired_deltas) // len(paired_deltas),
        mean_new_cost=sum(pd.new_cost for pd in paired_deltas) // len(paired_deltas),
    )
```

### Phase 4: Update `_should_accept_policy`

```python
async def _should_accept_policy(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    current_cost: int,
) -> tuple[bool, int, int, list[int], int, PolicyPairEvaluation]:
    """Determine whether to accept a new policy.

    Returns:
        Tuple of (should_accept, old_cost, new_cost, deltas, delta_sum, evaluation)
        where old_cost and new_cost are ACTUAL MEAN COSTS, not estimates.
    """
    evaluation = self._evaluate_policy_pair(
        agent_id=agent_id,
        old_policy=old_policy,
        new_policy=new_policy,
    )

    # Use ACTUAL computed costs, not estimates
    should_accept = evaluation.delta_sum > 0

    return (
        should_accept,
        evaluation.mean_old_cost,  # ACTUAL, not current_cost
        evaluation.mean_new_cost,  # ACTUAL, not estimate
        evaluation.deltas,
        evaluation.delta_sum,
        evaluation,  # Full evaluation for persistence
    )
```

### Phase 5: Enhanced Persistence Schema

The schema must handle two semantically different evaluation modes:

#### Deterministic Mode
- **What**: Single paired simulation on the configured scenario
- **Purpose**: "How does this policy perform in THIS specific scenario?"
- **Data**: One old_cost, one new_cost from THE scenario
- **Interpretation**: Direct performance measurement

#### Bootstrap Mode
- **What**: Paired simulations across N resampled historical scenarios
- **Purpose**: "How does this policy perform across a DISTRIBUTION of scenarios?"
- **Data**: N pairs of (old_cost, new_cost) from synthetic scenarios
- **Interpretation**: Statistical estimate of expected performance

#### Unified Schema with Mode Indicator

```python
@dataclass(frozen=True)
class PolicyEvaluationRecord:
    """Complete record of a policy evaluation.

    All costs in integer cents (INV-1).

    The interpretation of cost fields depends on evaluation_mode:

    - "deterministic": old_cost/new_cost are from THE configured scenario.
      These are direct measurements of policy performance.

    - "bootstrap": old_cost/new_cost are means across N resampled scenarios.
      These are statistical estimates. Use sample_details for distribution.
    """
    run_id: str
    iteration: int
    agent_id: str

    # Evaluation mode - determines interpretation of other fields
    evaluation_mode: str  # "deterministic" | "bootstrap"

    # Proposed policy
    proposed_policy: dict[str, Any]

    # Costs from evaluation (interpretation depends on mode)
    # Deterministic: actual costs from THE scenario
    # Bootstrap: mean costs across N samples
    old_cost: int
    new_cost: int

    # For comparison: the context simulation cost (from iteration start)
    context_simulation_cost: int

    # Acceptance decision
    accepted: bool
    acceptance_reason: str

    # Aggregate metrics
    delta_sum: int
    num_samples: int  # 1 for deterministic, N for bootstrap

    # Bootstrap-only: per-sample details for distribution analysis
    # None for deterministic mode (no distribution, just THE scenario)
    # For bootstrap: list of {"index", "seed", "old_cost", "new_cost", "delta"}
    sample_details: list[dict[str, Any]] | None = None

    # Deterministic-only: the seed used for THE scenario evaluation
    # None for bootstrap (seeds are in sample_details)
    scenario_seed: int | None = None

    timestamp: str


# Database schema
"""
CREATE TABLE IF NOT EXISTS policy_evaluations (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,

    -- Evaluation mode: "deterministic" or "bootstrap"
    -- Determines interpretation of cost fields
    evaluation_mode VARCHAR NOT NULL,

    -- Proposed policy
    proposed_policy JSON NOT NULL,

    -- Costs from evaluation
    -- Deterministic: actual costs from THE scenario
    -- Bootstrap: mean costs across N samples
    old_cost INTEGER NOT NULL,
    new_cost INTEGER NOT NULL,

    -- Context simulation cost (from iteration start, for comparison)
    context_simulation_cost INTEGER NOT NULL,

    -- Acceptance
    accepted BOOLEAN NOT NULL,
    acceptance_reason VARCHAR NOT NULL,

    -- Aggregates
    delta_sum INTEGER NOT NULL,
    num_samples INTEGER NOT NULL,  -- 1 for deterministic, N for bootstrap

    -- Bootstrap-only: per-sample details (JSON array)
    -- NULL for deterministic mode
    sample_details JSON,

    -- Deterministic-only: seed used for THE scenario
    -- NULL for bootstrap (seeds in sample_details)
    scenario_seed INTEGER,

    timestamp VARCHAR NOT NULL,

    UNIQUE(run_id, iteration, agent_id)
);

CREATE INDEX idx_policy_evals_run_agent
ON policy_evaluations(run_id, agent_id);

CREATE INDEX idx_policy_evals_mode
ON policy_evaluations(run_id, evaluation_mode);
"""
```

### Phase 6: Update Persistence Call

```python
# In _optimize_agent(), after _should_accept_policy():
(
    should_accept,
    old_cost,
    new_cost,
    deltas,
    delta_sum,
    evaluation,
) = await self._should_accept_policy(...)

# Determine mode and mode-specific fields
is_deterministic = self._config.evaluation.mode == "deterministic"
evaluation_mode = "deterministic" if is_deterministic else "bootstrap"

# Persist with ACTUAL costs
self._save_policy_evaluation(
    agent_id=agent_id,
    evaluation_mode=evaluation_mode,
    proposed_policy=new_policy,
    old_cost=old_cost,
    new_cost=new_cost,
    context_simulation_cost=current_cost,
    accepted=should_accept,
    acceptance_reason="cost_improved" if should_accept else "cost_not_improved",
    delta_sum=delta_sum,
    num_samples=evaluation.num_samples,
    # Bootstrap-only: per-sample distribution data
    sample_details=[
        {
            "index": s.sample_index,
            "seed": s.seed,
            "old_cost": s.old_cost,
            "new_cost": s.new_cost,
            "delta": s.delta,
        }
        for s in evaluation.sample_results
    ] if not is_deterministic else None,

    # Deterministic-only: seed for THE scenario
    scenario_seed=evaluation.sample_results[0].seed if is_deterministic else None,
)
```

## Implementation Notes

### Invariants to Respect

- **INV-1 (Integer Cents)**: All costs stored as integer cents
- **INV-2 (Determinism)**: Seeds stored for reproducibility verification
- **INV-10 (Scenario Config)**: Use `ScenarioConfigBuilder` for agent config extraction

### Files to Modify

| File | Changes |
|------|---------|
| `api/payment_simulator/experiments/runner/optimization.py` | Add `SampleEvaluationResult`, `PolicyPairEvaluation` dataclasses; modify `_evaluate_policy_pair` to return actual costs; update `_should_accept_policy`; add `_save_policy_evaluation` |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` | Extend `PairedDelta` to include `old_cost` and `new_cost` fields |
| `api/payment_simulator/experiments/persistence/repository.py` | Add `PolicyEvaluationRecord` dataclass with `evaluation_mode`; add table schema; add CRUD methods |
| `api/payment_simulator/experiments/persistence/__init__.py` | Export new types |
| `api/payment_simulator/experiments/analysis/charting.py` | Update to use `new_cost` from `policy_evaluations`; handle both modes |

### Charting Considerations

When charting uses `policy_evaluations`, it should understand the `evaluation_mode`:

```python
def _extract_from_policy_evaluations(self, run_id: str, agent_filter: str | None) -> list[ChartDataPoint]:
    evaluations = self._repo.get_policy_evaluations(run_id, agent_filter)

    data_points = []
    for eval_record in evaluations:
        # new_cost interpretation:
        # - deterministic: cost from THE scenario (direct measurement)
        # - bootstrap: mean cost across N samples (statistical estimate)
        #
        # Both are valid for charting "proposed policy cost"
        cost_cents = eval_record.new_cost

        data_points.append(ChartDataPoint(
            iteration=eval_record.iteration + 1,
            cost_dollars=cost_cents / 100.0,
            accepted=eval_record.accepted,
            # For bootstrap, could also show confidence intervals from sample_details
        ))

    return data_points
```

### Backward Compatibility

- Old experiment databases won't have the new table
- Charting should fall back to `experiment_iterations` with inferred acceptance
- Add `has_policy_evaluations()` check before using new data source

### Migration Path

1. **Phase 1**: Add `SampleEvaluationResult` and `PolicyPairEvaluation` dataclasses
2. **Phase 2**: Update deterministic path to return actual costs
3. **Phase 3**: Extend `PairedDelta`, update bootstrap path
4. **Phase 4**: Update `_should_accept_policy` signature and implementation
5. **Phase 5**: Add database schema and `PolicyEvaluationRecord`
6. **Phase 6**: Implement persistence in `_optimize_agent`
7. **Phase 7**: Update charting to use actual costs
8. **Phase 8**: Fix `accepted_changes` bug in `experiment_iterations`

## Acceptance Criteria

### Core Evaluation Changes
- [ ] `_evaluate_policy_pair` returns `PolicyPairEvaluation` with actual costs
- [ ] `PairedDelta` extended to include `old_cost` and `new_cost` fields
- [ ] Deterministic mode: returns actual costs from THE scenario simulation
- [ ] Bootstrap mode: returns actual per-sample costs from each bootstrap simulation

### Schema and Persistence
- [ ] `policy_evaluations` table includes `evaluation_mode` column
- [ ] `old_cost` and `new_cost` columns store actual computed costs
- [ ] `context_simulation_cost` stored separately for audit/comparison
- [ ] `scenario_seed` populated for deterministic mode (NULL for bootstrap)
- [ ] `sample_details` populated for bootstrap mode (NULL for deterministic)
- [ ] `num_samples` = 1 for deterministic, N for bootstrap

### Charting and Analysis
- [ ] Charting uses `new_cost` from `policy_evaluations` when available
- [ ] Charting correctly interprets both deterministic and bootstrap modes
- [ ] Old experiments fall back to inferred acceptance from `experiment_iterations`

### Testing
- [ ] All existing tests pass
- [ ] New tests verify deterministic costs match simulation output
- [ ] New tests verify bootstrap costs match per-sample evaluations
- [ ] Tests verify `evaluation_mode` is correctly set

## Testing Requirements

### Unit Tests

1. **Deterministic evaluation returns actual costs**
   ```python
   def test_deterministic_returns_actual_costs():
       """Verify deterministic mode returns real computed costs."""
       evaluation = optimizer._evaluate_policy_pair(agent_id, old_policy, new_policy)

       # Run same simulation manually to verify
       optimizer._policies[agent_id] = new_policy
       _, costs = optimizer._run_single_simulation(expected_seed)
       actual_new_cost = costs[agent_id]

       assert evaluation.mean_new_cost == actual_new_cost
   ```

2. **Bootstrap evaluation returns per-sample costs**
   ```python
   def test_bootstrap_returns_per_sample_costs():
       """Verify bootstrap mode captures costs for each sample."""
       evaluation = optimizer._evaluate_policy_pair(agent_id, old_policy, new_policy)

       assert len(evaluation.sample_results) == num_bootstrap_samples
       for sample in evaluation.sample_results:
           assert sample.old_cost > 0
           assert sample.new_cost > 0
           assert sample.delta == sample.old_cost - sample.new_cost
   ```

3. **Mean costs match aggregation**
   ```python
   def test_mean_costs_correct():
       """Verify mean_old_cost and mean_new_cost are correct."""
       evaluation = optimizer._evaluate_policy_pair(...)

       expected_mean_old = sum(s.old_cost for s in evaluation.sample_results) // len(evaluation.sample_results)
       expected_mean_new = sum(s.new_cost for s in evaluation.sample_results) // len(evaluation.sample_results)

       assert evaluation.mean_old_cost == expected_mean_old
       assert evaluation.mean_new_cost == expected_mean_new
   ```

### Integration Tests

1. **End-to-end persistence of actual costs**
2. **Charting reads actual costs from new table**
3. **Backward compatibility with old databases**

### Invariant Tests

1. **All costs are integer cents (INV-1)**
2. **Same seed produces same costs (INV-2)**

## Related Documentation

- `docs/requests/persist-policy-evaluation-metrics.md` - Superseded by this request
- `docs/reference/patterns-and-conventions.md` - INV-1, INV-2

## Related Code

- `api/payment_simulator/experiments/runner/optimization.py` - Main evaluation logic
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` - Bootstrap evaluation
- `api/payment_simulator/experiments/persistence/repository.py` - Database operations

## Notes

### Why Not Just Fix the Estimate?

The estimate `current_cost - mean_delta` could theoretically be made more accurate by using `mean(bootstrap_old_costs)` instead of `current_cost`. However:

1. **We already compute the actual costs** - discarding them and reconstructing estimates is wasteful
2. **Per-sample data is valuable** - for analyzing cost distribution, confidence intervals, outliers
3. **Audit trail** - storing actual computed values provides verifiable records
4. **Seeds enable reproducibility** - can re-run any sample to verify stored cost

### Difference from Previous Request

The previous request (`persist-policy-evaluation-metrics.md`) would have stored the **estimated** `eval_new_cost`. This request ensures we store **actual** costs from the evaluation simulations.

### Estimated vs Actual: Quantifying the Difference

In practice, the estimate may be close to actual for many scenarios. However:

1. **Edge cases matter** - policy decisions near the acceptance threshold are most sensitive to errors
2. **Research validity** - published results should report measured values, not reconstructed estimates
3. **Debugging** - when investigating unexpected acceptance/rejection, actual costs are essential
