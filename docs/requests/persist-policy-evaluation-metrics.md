# Feature Request: Persist Policy Evaluation Metrics with Actual Costs

**Date**: 2025-12-15
**Updated**: 2025-12-16
**Priority**: High
**Blocking**: Paper charts require re-running experiments after implementation
**Affects**: `payment_simulator.experiments.runner.optimization`, `payment_simulator.experiments.persistence`, `payment_simulator.experiments.analysis.charting`, `payment_simulator.ai_cash_mgmt.bootstrap.evaluator`

## Summary

Store complete policy evaluation metrics directly in the database during experiment runs, using **actual computed costs** from simulations (not reconstructed estimates). This enables accurate chart generation showing both proposed and accepted policy costs.

## Problem Statement

The current implementation has two categories of issues:

### 1. Data Integrity Issues (Original Problems)

1. **`accepted_changes` is always False**: Bug where the field is never set correctly
2. **`experiment_iterations` stores only current best**: No record of proposed policies that were rejected
3. **No dedicated table for evaluation metrics**: Bootstrap evaluation results are only logged, not persisted
4. **Manual log extraction unworkable**: Attempted 2025-12-16, too error-prone due to multiple LLM calls per iteration

### 2. Cost Accuracy Issue (Discovered During Implementation)

The `_should_accept_policy()` method returns an **estimated** cost, not the actual computed cost:

```python
# Current code in optimization.py (lines 2071-2081)
# Note: These are approximations based on deltas and current_cost
num_samples = len(deltas)
mean_delta = delta_sum / num_samples if num_samples > 0 else 0

# Estimate old/new costs for display
# old_cost ≈ current_cost (from context simulation)
# new_cost ≈ old_cost - mean_delta
old_cost = current_cost
new_cost = current_cost - mean_delta  # ← ESTIMATE, NOT ACTUAL
```

**Why This Matters**:
- The estimate assumes `current_cost == mean(bootstrap_old_costs)`, which is only approximately true
- In deterministic mode, we compute real costs but discard them, returning only the delta
- In bootstrap mode, per-sample costs are never captured at all
- Charts and analysis would show estimated costs, not actual measurements

### Current Workaround

The charting code infers acceptance from cost improvement:

```python
# Infer acceptance from cost improvement (loses information)
if previous_cost is None:
    accepted = True
else:
    accepted = cost_dollars < previous_cost
```

This approach works but loses information and cannot show proposed policy costs.

## Proposed Solution

### Design Goals

1. **Capture actual costs**: Return real computed costs from evaluation, not estimates
2. **Per-sample granularity**: For bootstrap, store costs for each sample
3. **Both modes supported**: Handle deterministic and bootstrap modes with appropriate semantics
4. **Enable charting**: Provide clean data source for chart generation
5. **Backward compatible**: Old experiments fall back to inferred acceptance

### Overview

The implementation requires changes across the evaluation pipeline:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. BootstrapPolicyEvaluator (evaluator.py)                     │
│     - Extend PairedDelta to include old_cost, new_cost          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│  2. _evaluate_policy_pair (optimization.py)                     │
│     - Return PolicyPairEvaluation with actual costs             │
│     - Handle both deterministic and bootstrap paths             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│  3. _should_accept_policy (optimization.py)                     │
│     - Return actual mean costs, not estimates                   │
│     - Pass full evaluation for persistence                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│  4. _save_policy_evaluation (optimization.py)                   │
│     - Persist PolicyEvaluationRecord to database                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│  5. ExperimentChartService (charting.py)                        │
│     - Read from policy_evaluations table                        │
│     - Fall back to experiment_iterations for old data           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Extend Bootstrap Evaluator

**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`

Extend `PairedDelta` to include actual costs:

```python
@dataclass(frozen=True)
class PairedDelta:
    """Result of evaluating a policy pair on one sample."""
    sample_index: int
    delta: int  # old_cost - new_cost (positive = improvement)
    old_cost: int  # NEW: Actual cost with old policy
    new_cost: int  # NEW: Actual cost with new policy
```

Update `compute_paired_deltas()`:

```python
def compute_paired_deltas(
    self,
    samples: list[BootstrapSample],
    policy_a: dict[str, Any],
    policy_b: dict[str, Any],
) -> list[PairedDelta]:
    """Compute paired deltas between two policies with actual costs."""
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

---

## Phase 2: New Dataclasses for Evaluation Results

**File**: `api/payment_simulator/experiments/runner/optimization.py`

Add dataclasses to capture complete evaluation results:

```python
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


@dataclass(frozen=True)
class PolicyPairEvaluation:
    """Complete results from evaluating old vs new policy.

    All costs in integer cents (INV-1).
    """
    sample_results: list[SampleEvaluationResult]
    delta_sum: int  # Sum of deltas across samples
    mean_old_cost: int  # Mean of old_cost across samples
    mean_new_cost: int  # Mean of new_cost across samples

    @property
    def deltas(self) -> list[int]:
        """List of deltas for backward compatibility."""
        return [s.delta for s in self.sample_results]

    @property
    def num_samples(self) -> int:
        return len(self.sample_results)
```

---

## Phase 3: Update `_evaluate_policy_pair`

**File**: `api/payment_simulator/experiments/runner/optimization.py`

Change return type from `tuple[list[int], int]` to `PolicyPairEvaluation`:

### Deterministic Path

```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> PolicyPairEvaluation:
    """Evaluate old vs new policy with paired samples."""

    iteration_idx = self._current_iteration - 1
    num_samples = self._config.evaluation.num_samples or 1

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

        # Return ACTUAL costs
        return PolicyPairEvaluation(
            sample_results=[SampleEvaluationResult(
                sample_index=0,
                seed=seed,
                old_cost=old_cost,
                new_cost=new_cost,
                delta=delta,
            )],
            delta_sum=delta,
            mean_old_cost=old_cost,
            mean_new_cost=new_cost,
        )
```

### Bootstrap Path

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
                seed=getattr(samples[pd.sample_index], 'seed', 0),
                old_cost=pd.old_cost,
                new_cost=pd.new_cost,
                delta=pd.delta,
            )
            for pd in paired_deltas
        ]

        n = len(paired_deltas)
        return PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=sum(pd.delta for pd in paired_deltas),
            mean_old_cost=sum(pd.old_cost for pd in paired_deltas) // n,
            mean_new_cost=sum(pd.new_cost for pd in paired_deltas) // n,
        )

    raise RuntimeError(f"No bootstrap samples available for agent {agent_id}")
```

---

## Phase 4: Update `_should_accept_policy`

**File**: `api/payment_simulator/experiments/runner/optimization.py`

Return actual costs and full evaluation:

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
        where old_cost and new_cost are ACTUAL COMPUTED COSTS.
    """
    evaluation = self._evaluate_policy_pair(
        agent_id=agent_id,
        old_policy=old_policy,
        new_policy=new_policy,
    )

    should_accept = evaluation.delta_sum > 0

    return (
        should_accept,
        evaluation.mean_old_cost,  # ACTUAL, not current_cost
        evaluation.mean_new_cost,  # ACTUAL, not estimate
        evaluation.deltas,
        evaluation.delta_sum,
        evaluation,
    )
```

---

## Phase 5: Persistence Schema

### Evaluation Mode Semantics

The schema handles two semantically different evaluation modes:

| Mode | What | Purpose | Data |
|------|------|---------|------|
| **Deterministic** | Single paired simulation on configured scenario | "How does this policy perform in THIS specific scenario?" | One old_cost, one new_cost, scenario_seed |
| **Bootstrap** | Paired simulations across N resampled scenarios | "How does this policy perform across a DISTRIBUTION of scenarios?" | Mean costs + sample_details array |

### Dataclass

**File**: `api/payment_simulator/experiments/persistence/repository.py`

```python
@dataclass(frozen=True)
class PolicyEvaluationRecord:
    """Complete record of a policy evaluation.

    All costs in integer cents (INV-1).

    The interpretation of cost fields depends on evaluation_mode:
    - "deterministic": old_cost/new_cost are from THE configured scenario
    - "bootstrap": old_cost/new_cost are means across N resampled scenarios
    """
    run_id: str
    iteration: int  # 0-indexed
    agent_id: str

    # Evaluation mode - determines interpretation of other fields
    evaluation_mode: str  # "deterministic" | "bootstrap"

    # Proposed policy
    proposed_policy: dict[str, Any]

    # Costs from evaluation (interpretation depends on mode)
    old_cost: int
    new_cost: int

    # Context simulation cost (from iteration start, for comparison)
    context_simulation_cost: int

    # Acceptance decision
    accepted: bool
    acceptance_reason: str  # "cost_improved", "cost_not_improved", "validation_failed"

    # Aggregate metrics
    delta_sum: int
    num_samples: int  # 1 for deterministic, N for bootstrap

    # Bootstrap-only: per-sample details for distribution analysis
    # For bootstrap: list of {"index", "seed", "old_cost", "new_cost", "delta"}
    sample_details: list[dict[str, Any]] | None = None

    # Deterministic-only: seed used for THE scenario evaluation
    scenario_seed: int | None = None

    timestamp: str
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS policy_evaluations (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,

    -- Evaluation mode: "deterministic" or "bootstrap"
    evaluation_mode VARCHAR NOT NULL,

    -- Proposed policy
    proposed_policy JSON NOT NULL,

    -- Costs from evaluation (actual, not estimates)
    old_cost INTEGER NOT NULL,
    new_cost INTEGER NOT NULL,

    -- Context simulation cost (for comparison/audit)
    context_simulation_cost INTEGER NOT NULL,

    -- Acceptance
    accepted BOOLEAN NOT NULL,
    acceptance_reason VARCHAR NOT NULL,

    -- Aggregates
    delta_sum INTEGER NOT NULL,
    num_samples INTEGER NOT NULL,

    -- Bootstrap-only: per-sample details (JSON array)
    sample_details JSON,

    -- Deterministic-only: seed used for THE scenario
    scenario_seed INTEGER,

    timestamp VARCHAR NOT NULL,

    UNIQUE(run_id, iteration, agent_id)
);

CREATE INDEX idx_policy_evals_run_agent
ON policy_evaluations(run_id, agent_id);

CREATE INDEX idx_policy_evals_mode
ON policy_evaluations(run_id, evaluation_mode);
```

### Repository Methods

Add to `ExperimentRepository`:

```python
def save_policy_evaluation(self, record: PolicyEvaluationRecord) -> None:
    """Save policy evaluation record."""
    # Use INSERT ... ON CONFLICT DO UPDATE for upsert

def get_policy_evaluations(
    self, run_id: str, agent_id: str
) -> list[PolicyEvaluationRecord]:
    """Get policy evaluations for a specific agent."""

def get_all_policy_evaluations(
    self, run_id: str
) -> list[PolicyEvaluationRecord]:
    """Get all policy evaluations for a run."""

def has_policy_evaluations(self, run_id: str) -> bool:
    """Check if run has policy evaluation records."""
```

---

## Phase 6: Update Persistence Call

**File**: `api/payment_simulator/experiments/runner/optimization.py`

In `_optimize_agent()`, after `_should_accept_policy()`:

```python
(
    should_accept,
    old_cost,
    new_cost,
    deltas,
    delta_sum,
    evaluation,
) = await self._should_accept_policy(
    agent_id=agent_id,
    old_policy=current_policy,
    new_policy=new_policy,
    current_cost=current_cost,
)

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
    scenario_seed=evaluation.sample_results[0].seed if is_deterministic else None,
)
```

---

## Phase 7: Update Charting

**File**: `api/payment_simulator/experiments/analysis/charting.py`

### Primary Data Source

```python
def extract_chart_data(
    self,
    run_id: str,
    agent_filter: str | None = None,
    parameter_name: str | None = None,
) -> ChartData:
    """Extract chart data from experiment run.

    Uses policy_evaluations table when available (actual costs),
    falls back to experiment_iterations with inferred acceptance.
    """
    experiment = self._repo.load_experiment(run_id)
    if experiment is None:
        raise ValueError(f"Experiment run not found: {run_id}")

    # Try new data source first
    if self._repo.has_policy_evaluations(run_id):
        return self._extract_from_policy_evaluations(
            run_id, experiment, agent_filter, parameter_name
        )

    # Fall back to iterations table with inferred acceptance
    return self._extract_from_iterations_table(
        run_id, experiment, agent_filter, parameter_name
    )
```

### New Extraction Method

```python
def _extract_from_policy_evaluations(
    self,
    run_id: str,
    experiment: ExperimentRecord,
    agent_filter: str | None,
    parameter_name: str | None,
) -> ChartData:
    """Extract chart data from policy_evaluations table."""
    if agent_filter:
        evaluations = self._repo.get_policy_evaluations(run_id, agent_filter)
    else:
        evaluations = self._repo.get_all_policy_evaluations(run_id)

    evaluation_mode = experiment.config.get("evaluation", {}).get(
        "mode", "deterministic"
    )

    data_points: list[ChartDataPoint] = []
    for eval_record in evaluations:
        # new_cost interpretation:
        # - deterministic: cost from THE scenario (direct measurement)
        # - bootstrap: mean cost across N samples (statistical estimate)
        cost_cents = eval_record.new_cost

        parameter_value = self._extract_parameter(
            eval_record.proposed_policy, parameter_name
        ) if parameter_name else None

        data_points.append(ChartDataPoint(
            iteration=eval_record.iteration + 1,  # 1-indexed display
            cost_dollars=cost_cents / 100.0,
            accepted=eval_record.accepted,
            parameter_value=parameter_value,
        ))

    return ChartData(
        run_id=run_id,
        experiment_name=experiment.experiment_name,
        evaluation_mode=evaluation_mode,
        agent_id=agent_filter,
        parameter_name=parameter_name,
        data_points=data_points,
    )
```

---

## Phase 8: Fix `accepted_changes` Bug

**File**: `api/payment_simulator/experiments/runner/optimization.py`

The `_save_iteration_record()` call must happen AFTER the optimization loop, not before:

```python
# WRONG: Before optimization (accepted_changes always False)
# self._save_iteration_record(agent_id, iteration, ...)
# for agent_id in self.optimized_agents:
#     await self._optimize_agent(...)

# CORRECT: After optimization
for agent_id in self.optimized_agents:
    await self._optimize_agent(agent_id, current_cost)

# Now save iteration record with correct accepted_changes
self._save_iteration_record(agent_id, iteration, accepted_changes=was_accepted)
```

---

## Implementation Notes

### Invariants to Respect

- **INV-1 (Integer Cents)**: All costs stored as integer cents in database
- **INV-2 (Determinism)**: Seeds stored for reproducibility verification
- **INV-10 (Scenario Config)**: Use `ScenarioConfigBuilder` for agent config extraction

### Files to Modify

| File | Changes |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` | Extend `PairedDelta` to include `old_cost` and `new_cost` |
| `api/payment_simulator/experiments/runner/optimization.py` | Add `SampleEvaluationResult`, `PolicyPairEvaluation`; modify `_evaluate_policy_pair`, `_should_accept_policy`; add `_save_policy_evaluation`; fix `accepted_changes` bug |
| `api/payment_simulator/experiments/persistence/repository.py` | Add `PolicyEvaluationRecord`; add table schema in `_ensure_schema()`; add CRUD methods |
| `api/payment_simulator/experiments/persistence/__init__.py` | Export `PolicyEvaluationRecord` |
| `api/payment_simulator/experiments/analysis/charting.py` | Add `_extract_from_policy_evaluations()`; update `extract_chart_data()` to use new source |

### Backward Compatibility

- Old experiment databases won't have `policy_evaluations` table
- `has_policy_evaluations()` check determines which data source to use
- Old experiments continue to work with inferred acceptance

---

## Acceptance Criteria

### Core Evaluation Changes
- [ ] `PairedDelta` extended to include `old_cost` and `new_cost` fields
- [ ] `_evaluate_policy_pair` returns `PolicyPairEvaluation` with actual costs
- [ ] Deterministic mode: returns actual costs from THE scenario simulation
- [ ] Bootstrap mode: returns actual per-sample costs from each bootstrap simulation
- [ ] `_should_accept_policy` returns actual mean costs, not estimates

### Schema and Persistence
- [ ] `policy_evaluations` table created with `evaluation_mode` column
- [ ] `old_cost` and `new_cost` columns store actual computed costs
- [ ] `context_simulation_cost` stored separately for audit/comparison
- [ ] `scenario_seed` populated for deterministic mode (NULL for bootstrap)
- [ ] `sample_details` populated for bootstrap mode (NULL for deterministic)
- [ ] `num_samples` = 1 for deterministic, N for bootstrap

### Charting and Analysis
- [ ] Charting uses `new_cost` from `policy_evaluations` when available
- [ ] Charting correctly interprets both deterministic and bootstrap modes
- [ ] Old experiments fall back to inferred acceptance from `experiment_iterations`

### Bug Fixes
- [ ] `accepted_changes` field bug fixed in `experiment_iterations`

### Testing
- [ ] All existing tests pass
- [ ] New tests verify deterministic costs match simulation output
- [ ] New tests verify bootstrap costs match per-sample evaluations
- [ ] Tests verify `evaluation_mode` is correctly set
- [ ] Tests verify backward compatibility with old databases

---

## Post-Implementation Required

After this feature is implemented:
- [ ] Re-run all paper experiments (exp1, exp2, exp3) with new persistence
- [ ] Generate updated charts using the new `policy_evaluations` data
- [ ] Verify charts show both "All Policies" and "Accepted Policies" lines correctly

---

## Testing Requirements

### Unit Tests

1. **PairedDelta includes costs**
   ```python
   def test_paired_delta_has_costs():
       pd = evaluator.compute_paired_deltas(samples, old_policy, new_policy)[0]
       assert hasattr(pd, 'old_cost')
       assert hasattr(pd, 'new_cost')
       assert pd.delta == pd.old_cost - pd.new_cost
   ```

2. **Deterministic evaluation returns actual costs**
   ```python
   def test_deterministic_returns_actual_costs():
       evaluation = optimizer._evaluate_policy_pair(agent_id, old_policy, new_policy)

       # Run same simulation manually to verify
       optimizer._policies[agent_id] = new_policy
       _, costs = optimizer._run_single_simulation(expected_seed)
       actual_new_cost = costs[agent_id]

       assert evaluation.mean_new_cost == actual_new_cost
   ```

3. **Bootstrap evaluation returns per-sample costs**
   ```python
   def test_bootstrap_returns_per_sample_costs():
       evaluation = optimizer._evaluate_policy_pair(agent_id, old_policy, new_policy)

       assert len(evaluation.sample_results) == num_bootstrap_samples
       for sample in evaluation.sample_results:
           assert sample.old_cost > 0
           assert sample.new_cost > 0
           assert sample.delta == sample.old_cost - sample.new_cost
   ```

4. **Policy evaluation record persistence**
   ```python
   def test_policy_evaluation_persisted():
       # Run optimization
       # Verify PolicyEvaluationRecord saved with all fields
       records = repo.get_policy_evaluations(run_id, agent_id)
       assert len(records) > 0
       assert records[0].new_cost > 0
       assert records[0].evaluation_mode in ("deterministic", "bootstrap")
   ```

5. **Charting uses new data source**
   ```python
   def test_chart_uses_policy_evaluations():
       # Create experiment with policy_evaluations
       chart_data = service.extract_chart_data(run_id, agent_filter="BANK_A")
       assert len(chart_data.data_points) > 0
       # Verify costs match policy_evaluations, not iterations table
   ```

### Integration Tests

1. **End-to-end deterministic experiment**
2. **End-to-end bootstrap experiment**
3. **Backward compatibility with old databases**
4. **Chart output matches expected format**

---

## Related Documentation

- `docs/reference/cli/commands/experiment.md` - Chart command documentation
- `docs/reference/patterns-and-conventions.md` - INV-1, INV-2, data persistence patterns

## Related Code

- `api/payment_simulator/experiments/runner/optimization.py` - Main evaluation logic
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` - Bootstrap evaluation
- `api/payment_simulator/experiments/persistence/repository.py` - Database operations
- `api/payment_simulator/experiments/analysis/charting.py` - Chart generation

---

## Notes

### Why Store Actual Costs Instead of Estimates?

The estimate `current_cost - mean_delta` could theoretically work, but:

1. **We already compute the actual costs** - discarding them is wasteful
2. **Per-sample data is valuable** - for confidence intervals, outliers
3. **Audit trail** - storing actual values provides verifiable records
4. **Seeds enable reproducibility** - can re-run any sample to verify
5. **Research validity** - published results should report measurements, not estimates

### Why Two Tables?

`experiment_iterations` and `policy_evaluations` serve different purposes:

- `experiment_iterations`: "What policy is active at iteration N?" (state tracking)
- `policy_evaluations`: "What was proposed and what happened?" (evaluation audit)

Both are needed for complete experiment analysis.
