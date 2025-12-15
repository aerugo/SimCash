# Feature Request: Persist Policy Evaluation Metrics in Database

**Date**: 2025-12-15
**Priority**: Medium
**Affects**: `payment_simulator.experiments.runner.optimization`, `payment_simulator.experiments.persistence`, `payment_simulator.experiments.analysis.charting`

## Summary

Store complete policy evaluation metrics (including proposed policy costs and acceptance status) directly in the database during experiment runs, eliminating the need to parse LLM prompts for chart generation.

## Problem Statement

Currently, the charting code (`charting.py`) has to parse iteration history from LLM user_prompts to get accurate data for bootstrap experiments. This is because:

1. **`experiment_iterations` table stores incomplete data**: Only the CURRENT BEST policy cost is stored, not the PROPOSED policy cost
2. **`accepted_changes` is always False**: Bug where the field is set before optimization happens
3. **No dedicated table for evaluation metrics**: Bootstrap evaluation results (old_cost, new_cost, deltas) are only logged, not persisted

### Current Behavior

```python
# In charting.py - current workaround parses LLM prompts!
def _parse_iteration_history_from_llm_prompt(user_prompt: str) -> list[ParsedIterationData]:
    """Parse iteration history from LLM user_prompt.

    Extracts cost and acceptance status from the Metrics Summary Table
    in the LLM user_prompt...
    """
    # Regex parsing of markdown tables in prompts - fragile!
    metrics_pattern = r"\|\s*(\d+)\s*\|\s*(⭐ BEST|✅ KEPT|❌ REJECTED)\s*\|\s*\$([0-9,]+)\s*\|"
```

This approach is:
- **Fragile**: Depends on prompt format not changing
- **Indirect**: Data exists in memory during run but isn't persisted properly
- **Inefficient**: Requires parsing large text prompts
- **Limited**: Only works for bootstrap experiments with LLM events

### Why This Is a Problem

1. **Maintenance burden**: Any change to LLM prompt format can break chart generation
2. **Data duplication**: Same data exists in multiple places (memory, logs, prompts)
3. **Missing data for deterministic mode**: Deterministic experiments don't have LLM events, so charts can't show rejected policies
4. **Audit trail gaps**: No structured record of what policies were proposed and why they were rejected

## Proposed Solution

### Design Goals

1. Create a dedicated table for policy evaluation metrics
2. Persist both PROPOSED and ACCEPTED policy costs per iteration
3. Fix the `accepted_changes` bug in `experiment_iterations`
4. Update charting to use the new structured data

### Proposed Data Model

```python
# New dataclass for evaluation metrics
@dataclass(frozen=True)
class PolicyEvaluationRecord:
    """Record of a single policy evaluation.

    Captures both the proposed policy and its evaluation results,
    regardless of whether it was accepted.

    All costs in integer cents (INV-1).
    """
    run_id: str
    iteration: int  # 0-indexed
    agent_id: str

    # Proposed policy
    proposed_policy: dict[str, Any]

    # Evaluation results
    proposed_cost: int  # Mean cost of proposed policy (bootstrap) or single cost (deterministic)
    current_best_cost: int  # Cost of current best policy before this evaluation

    # Acceptance decision
    accepted: bool
    acceptance_reason: str  # "cost_improved", "cost_not_improved", "validation_failed"

    # Bootstrap-specific (optional)
    bootstrap_deltas: list[int] | None = None  # (old_cost - new_cost) per sample
    delta_sum: int | None = None
    num_samples: int | None = None

    # Metadata
    timestamp: str
```

### Proposed Database Schema

```sql
CREATE TABLE IF NOT EXISTS policy_evaluations (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,

    -- Proposed policy
    proposed_policy JSON NOT NULL,

    -- Evaluation results
    proposed_cost INTEGER NOT NULL,  -- Cost of proposed policy
    current_best_cost INTEGER NOT NULL,  -- Cost before this evaluation

    -- Acceptance decision
    accepted BOOLEAN NOT NULL,
    acceptance_reason VARCHAR NOT NULL,

    -- Bootstrap-specific (NULL for deterministic)
    bootstrap_deltas JSON,
    delta_sum INTEGER,
    num_samples INTEGER,

    timestamp VARCHAR NOT NULL,

    UNIQUE(run_id, iteration, agent_id)
);

CREATE INDEX idx_policy_evals_run_agent
ON policy_evaluations(run_id, agent_id);
```

### Proposed Changes to optimization.py

```python
# In _should_accept_policy() or after it returns:
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    # ... existing code ...

    (should_accept, eval_old_cost, eval_new_cost, deltas, delta_sum) = \
        await self._should_accept_policy(...)

    # NEW: Persist evaluation record immediately after evaluation
    self._save_policy_evaluation(
        agent_id=agent_id,
        proposed_policy=new_policy,
        proposed_cost=eval_new_cost,
        current_best_cost=eval_old_cost,
        accepted=should_accept,
        acceptance_reason="cost_improved" if should_accept else "cost_not_improved",
        bootstrap_deltas=deltas if deltas else None,
        delta_sum=delta_sum if deltas else None,
        num_samples=len(deltas) if deltas else None,
    )

    # ... rest of existing code ...

def _save_policy_evaluation(self, ...) -> None:
    """Save policy evaluation record to repository."""
    if self._repository is None:
        return

    record = PolicyEvaluationRecord(
        run_id=self._run_id,
        iteration=self._current_iteration - 1,  # 0-indexed
        agent_id=agent_id,
        proposed_policy=proposed_policy,
        proposed_cost=proposed_cost,
        current_best_cost=current_best_cost,
        accepted=accepted,
        acceptance_reason=acceptance_reason,
        bootstrap_deltas=bootstrap_deltas,
        delta_sum=delta_sum,
        num_samples=num_samples,
        timestamp=datetime.now().isoformat(),
    )
    self._repository.save_policy_evaluation(record)
```

### Proposed Changes to charting.py (After Implementation)

Once the data is properly persisted, the charting code can be simplified:

```python
# REMOVE: _parse_iteration_history_from_llm_prompt() function
# REMOVE: _extract_from_llm_events() method

class ExperimentChartService:
    def extract_chart_data(
        self,
        run_id: str,
        agent_filter: str | None = None,
        parameter_name: str | None = None,
    ) -> ChartData:
        """Extract chart data from experiment run.

        Uses policy_evaluations table for accurate proposed/accepted costs.
        """
        experiment = self._repo.load_experiment(run_id)
        if experiment is None:
            raise ValueError(f"Experiment run not found: {run_id}")

        evaluation_mode = experiment.config.get("evaluation", {}).get(
            "mode", "deterministic"
        )

        # Get evaluation records - this replaces LLM prompt parsing!
        if agent_filter:
            evaluations = self._repo.get_policy_evaluations(run_id, agent_filter)
        else:
            evaluations = self._repo.get_all_policy_evaluations(run_id)

        data_points: list[ChartDataPoint] = []
        for eval_record in evaluations:
            # Cost is the PROPOSED cost (what we want for "All Policies" line)
            if agent_filter:
                cost_cents = eval_record.proposed_cost
            else:
                # Sum across agents for system total
                # (would need to aggregate differently)
                cost_cents = eval_record.proposed_cost

            parameter_value = self._extract_parameter(
                eval_record.proposed_policy,
                parameter_name,
            ) if parameter_name else None

            data_points.append(
                ChartDataPoint(
                    iteration=eval_record.iteration + 1,  # 1-indexed display
                    cost_dollars=cost_cents / 100.0,
                    accepted=eval_record.accepted,
                    parameter_value=parameter_value,
                )
            )

        return ChartData(
            run_id=run_id,
            experiment_name=experiment.experiment_name,
            evaluation_mode=evaluation_mode,
            agent_id=agent_filter,
            parameter_name=parameter_name,
            data_points=data_points,
        )
```

### Usage Example (After Fix)

```bash
# Chart generation works identically, but uses clean data source
payment-sim experiment chart exp2-20251215-100212-680ad2 \
    --db results/exp2.db \
    --agent BANK_A \
    --parameter initial_liquidity_fraction \
    --output chart.png

# Data query for analysis (new capability)
payment-sim experiment evaluations exp2-20251215-100212-680ad2 \
    --db results/exp2.db \
    --agent BANK_A \
    --format json
```

## Implementation Notes

### Invariants to Respect

- **INV-1 (Integer Cents)**: All costs stored as integer cents in database
- **Determinism**: Evaluation records should be timestamped but not affect simulation determinism

### Related Components

| Component | Impact |
|-----------|--------|
| `api/payment_simulator/experiments/persistence/repository.py` | Add `policy_evaluations` table, `save_policy_evaluation()`, `get_policy_evaluations()` |
| `api/payment_simulator/experiments/persistence/models.py` | Add `PolicyEvaluationRecord` dataclass |
| `api/payment_simulator/experiments/runner/optimization.py` | Add `_save_policy_evaluation()` call after each evaluation |
| `api/payment_simulator/experiments/analysis/charting.py` | Remove LLM prompt parsing, use new data source |
| `api/migrations/` | Database migration for new table |

### Migration Path

1. **Phase 1 (Schema)**: Add `policy_evaluations` table with migration
2. **Phase 2 (Persistence)**: Update `optimization.py` to persist evaluation records
3. **Phase 3 (Charting)**: Refactor `charting.py` to use new data source, remove prompt parsing
4. **Phase 4 (Cleanup)**: Remove `_parse_iteration_history_from_llm_prompt()` and `_extract_from_llm_events()`

### Backward Compatibility

- Old experiment databases won't have `policy_evaluations` table
- Charting should fall back to current LLM prompt parsing for old data
- Add version check or table existence check

```python
def extract_chart_data(self, run_id: str, ...) -> ChartData:
    # Try new data source first
    if self._repo.has_policy_evaluations(run_id):
        return self._extract_from_evaluations(run_id, ...)

    # Fall back to LLM prompt parsing for old experiments
    if evaluation_mode == "bootstrap" and agent_filter:
        return self._extract_from_llm_events(run_id, ...)

    # Final fallback to iterations table
    return self._extract_from_iterations_table(run_id, ...)
```

## Acceptance Criteria

- [ ] `policy_evaluations` table created with migration
- [ ] `PolicyEvaluationRecord` dataclass defined with all fields
- [ ] `optimization.py` persists evaluation record after each `_should_accept_policy()` call
- [ ] `charting.py` uses `policy_evaluations` for chart data extraction
- [ ] LLM prompt parsing code removed from `charting.py`
- [ ] Charts show identical output for new experiments
- [ ] Old experiments (without `policy_evaluations`) still render correctly
- [ ] Tests verify correct persistence of proposed vs accepted costs

## Testing Requirements

1. **Unit tests**:
   - `test_policy_evaluation_record_persisted` - Verify record saved with all fields
   - `test_proposed_cost_different_from_accepted` - Verify rejected policy costs stored
   - `test_chart_uses_evaluation_records` - Verify charting reads from new table

2. **Integration tests**:
   - `test_end_to_end_bootstrap_experiment` - Run experiment, verify evaluations persisted
   - `test_chart_matches_current_output` - Compare new vs old chart data extraction
   - `test_backward_compatibility` - Old DB without table still works

3. **Migration tests**:
   - `test_migration_creates_table` - Verify schema migration
   - `test_old_db_graceful_fallback` - Verify fallback to LLM parsing

## Related Documentation

- `docs/reference/cli/commands/experiment.md` - Chart command documentation
- `docs/reference/patterns-and-conventions.md` - Data persistence patterns

## Related Code

- `api/payment_simulator/experiments/analysis/charting.py` - Current LLM prompt parsing workaround
- `api/payment_simulator/experiments/runner/optimization.py` - Where evaluations happen
- `api/payment_simulator/experiments/persistence/repository.py` - Database operations
- `api/payment_simulator/experiments/runner/verbose.py` - `BootstrapDeltaResult` dataclass (similar structure)

## Notes

### Current Workaround

The current implementation in `charting.py` parses iteration history from LLM user_prompts:

```python
# Pattern to match metrics table rows in LLM prompt:
# | 1 | ⭐ BEST | $39,840 | ...
metrics_pattern = r"\|\s*(\d+)\s*\|\s*(⭐ BEST|✅ KEPT|❌ REJECTED)\s*\|\s*\$([0-9,]+)\s*\|"
```

This works but is fragile and should be replaced with proper data persistence.

### Data Already Available

The data needed for proper persistence already exists in `optimization.py`:

```python
# In _should_accept_policy():
# Returns: (should_accept, old_cost, new_cost, deltas, delta_sum)

# In _record_iteration_history():
# Creates SingleAgentIterationRecord with cost and was_accepted
```

The fix is straightforward: persist this data to a dedicated table instead of only to the LLM prompt context.

### Why Not Fix `experiment_iterations`?

The `experiment_iterations` table has a different purpose - it tracks the CURRENT STATE at each iteration (what policy is active, what cost it achieves). The proposed `policy_evaluations` table tracks the EVALUATION PROCESS (what was proposed, what cost it achieved, why it was accepted/rejected).

These are complementary:
- `experiment_iterations`: "What policy is active at iteration N?"
- `policy_evaluations`: "What policy was proposed at iteration N and what happened?"
