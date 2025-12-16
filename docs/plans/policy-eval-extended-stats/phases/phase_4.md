# Phase 4: Queries and Integration

**Status**: Complete
**Started**: 2025-12-16
**Completed**: 2025-12-16

---

## Objective

Ensure extended statistics are accessible via repository queries, integrate with charting where appropriate, and verify full end-to-end flow.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - Query results maintain integer cents
- **INV-5**: Replay Identity - No changes to replay functionality (additive stats only)

---

## TDD Steps

### Step 4.1: Write Failing Tests (RED)

Add tests to `api/tests/experiments/runner/test_policy_evaluation_metrics.py`:

**Test Cases**:
1. `test_get_policy_evaluations_returns_extended_stats` - Query includes new fields
2. `test_get_all_policy_evaluations_returns_extended_stats` - Bulk query includes new fields
3. `test_extended_stats_json_deserialized_correctly` - Complex types round-trip
4. `test_end_to_end_bootstrap_with_extended_stats` - Full experiment flow

```python
class TestExtendedStatsQueries:
    """Tests for querying extended statistics."""

    def test_get_policy_evaluations_returns_extended_stats(
        self, repo_with_extended_stats_fixture
    ) -> None:
        """get_policy_evaluations should return extended stats fields."""
        repo = repo_with_extended_stats_fixture

        records = repo.get_policy_evaluations("test-run", "BANK_A")
        assert len(records) > 0

        record = records[0]
        # Verify extended stats are present
        assert record.settlement_rate is not None
        assert record.avg_delay is not None
        assert record.cost_breakdown is not None
        assert record.agent_stats is not None

    def test_cost_breakdown_deserialized_as_dict(
        self, repo_with_extended_stats_fixture
    ) -> None:
        """cost_breakdown should be deserialized as dict from JSON."""
        repo = repo_with_extended_stats_fixture

        records = repo.get_policy_evaluations("test-run", "BANK_A")
        record = records[0]

        assert isinstance(record.cost_breakdown, dict)
        assert "delay_cost" in record.cost_breakdown
        assert "overdraft_cost" in record.cost_breakdown
        assert isinstance(record.cost_breakdown["delay_cost"], int)

    def test_agent_stats_deserialized_as_dict(
        self, repo_with_extended_stats_fixture
    ) -> None:
        """agent_stats should be deserialized as nested dict from JSON."""
        repo = repo_with_extended_stats_fixture

        records = repo.get_policy_evaluations("test-run", "BANK_A")
        record = records[0]

        assert isinstance(record.agent_stats, dict)
        assert "BANK_A" in record.agent_stats
        assert isinstance(record.agent_stats["BANK_A"], dict)
        assert "cost" in record.agent_stats["BANK_A"]

    def test_confidence_interval_deserialized_as_list(
        self, repo_with_extended_stats_fixture
    ) -> None:
        """confidence_interval_95 should be deserialized as list from JSON."""
        repo = repo_with_extended_stats_fixture

        records = repo.get_policy_evaluations("test-run", "BANK_A")
        record = records[0]

        if record.confidence_interval_95 is not None:
            assert isinstance(record.confidence_interval_95, list)
            assert len(record.confidence_interval_95) == 2
            assert all(isinstance(v, int) for v in record.confidence_interval_95)


class TestEndToEndExtendedStats:
    """End-to-end tests for extended statistics."""

    @pytest.mark.integration
    def test_bootstrap_experiment_captures_extended_stats(
        self, tmp_path: Path
    ) -> None:
        """Full bootstrap experiment should persist extended stats."""
        from payment_simulator.experiments.runner.optimization import OptimizationLoop
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Setup experiment with bootstrap mode
        db_path = tmp_path / "test_experiment.db"
        repo = ExperimentRepository(db_path)

        # Create and run minimal experiment
        # ... (experiment setup with bootstrap mode)

        # Retrieve results
        records = repo.get_all_policy_evaluations(run_id)

        # Verify at least one record has extended stats
        assert any(r.settlement_rate is not None for r in records)
        assert any(r.cost_breakdown is not None for r in records)

        # Bootstrap should have std dev and CI
        bootstrap_records = [r for r in records if r.evaluation_mode == "bootstrap"]
        if bootstrap_records:
            assert any(r.cost_std_dev is not None for r in bootstrap_records)
            assert any(r.confidence_interval_95 is not None for r in bootstrap_records)

    @pytest.mark.integration
    def test_deterministic_experiment_no_stats_variance(
        self, tmp_path: Path
    ) -> None:
        """Deterministic experiment should have None for variance stats."""
        # ... (experiment setup with deterministic mode)

        records = repo.get_all_policy_evaluations(run_id)
        det_records = [r for r in records if r.evaluation_mode == "deterministic"]

        for record in det_records:
            # Should have basic metrics
            assert record.settlement_rate is not None
            assert record.avg_delay is not None
            # Should NOT have variance stats (N=1)
            assert record.cost_std_dev is None
            assert record.confidence_interval_95 is None
```

### Step 4.2: Implement to Pass Tests (GREEN)

**Verify** `api/payment_simulator/experiments/persistence/repository.py`:

The `_row_to_policy_evaluation_record()` method should already handle the new columns from Phase 1. Verify JSON deserialization:

```python
def _row_to_policy_evaluation_record(
    self, row: tuple[Any, ...]
) -> PolicyEvaluationRecord:
    """Convert database row to PolicyEvaluationRecord."""
    # ... existing field extraction ...

    # Extended stats (new columns)
    settlement_rate = row[15] if len(row) > 15 else None
    avg_delay = row[16] if len(row) > 16 else None

    cost_breakdown = row[17] if len(row) > 17 else None
    if cost_breakdown is not None and isinstance(cost_breakdown, str):
        cost_breakdown = json.loads(cost_breakdown)

    cost_std_dev = row[18] if len(row) > 18 else None
    if cost_std_dev is not None:
        cost_std_dev = int(cost_std_dev)

    confidence_interval_95 = row[19] if len(row) > 19 else None
    if confidence_interval_95 is not None and isinstance(confidence_interval_95, str):
        confidence_interval_95 = json.loads(confidence_interval_95)

    agent_stats = row[20] if len(row) > 20 else None
    if agent_stats is not None and isinstance(agent_stats, str):
        agent_stats = json.loads(agent_stats)

    return PolicyEvaluationRecord(
        # ... existing fields ...
        settlement_rate=settlement_rate,
        avg_delay=avg_delay,
        cost_breakdown=cost_breakdown,
        cost_std_dev=cost_std_dev,
        confidence_interval_95=confidence_interval_95,
        agent_stats=agent_stats,
    )
```

**Update** SELECT queries to include new columns:

```sql
SELECT run_id, iteration, agent_id, evaluation_mode,
       proposed_policy, old_cost, new_cost, context_simulation_cost,
       accepted, acceptance_reason, delta_sum, num_samples,
       sample_details, scenario_seed, timestamp,
       -- Extended stats
       settlement_rate, avg_delay, cost_breakdown,
       cost_std_dev, confidence_interval_95, agent_stats
FROM policy_evaluations
WHERE ...
```

### Step 4.3: Refactor

- Add helper methods for common query patterns (e.g., get evaluations with stats for a specific agent)
- Consider adding `get_policy_evaluation_summary()` for aggregate views
- Update any charting code that could benefit from extended stats

---

## Implementation Details

### Query Column Ordering

The SELECT statement column order must match the `_row_to_policy_evaluation_record()` index expectations. Define column names in a constant for consistency:

```python
_POLICY_EVAL_COLUMNS = """
    run_id, iteration, agent_id, evaluation_mode,
    proposed_policy, old_cost, new_cost, context_simulation_cost,
    accepted, acceptance_reason, delta_sum, num_samples,
    sample_details, scenario_seed, timestamp,
    settlement_rate, avg_delay, cost_breakdown,
    cost_std_dev, confidence_interval_95, agent_stats
"""
```

### Backward Compatibility

Old databases won't have the new columns. DuckDB's `ALTER TABLE ADD COLUMN IF NOT EXISTS` handles this during `_ensure_schema()`. When reading old rows:
- Missing columns return `NULL` which becomes `None`
- This is correct behavior - old records don't have extended stats

### JSON Handling in DuckDB

DuckDB stores JSON as a string but can parse it with `json_extract()`. For reads, we deserialize to Python dicts. For writes, we serialize dicts to JSON strings.

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/persistence/repository.py` | MODIFY (verify queries) |
| `api/tests/experiments/runner/test_policy_evaluation_metrics.py` | MODIFY (add tests) |

---

## Verification

```bash
# Run all extended stats tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_policy_evaluation_metrics.py -v

# Run integration tests
.venv/bin/python -m pytest tests/experiments/runner/test_policy_evaluation_metrics.py -v -m integration

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/persistence/repository.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/persistence/
```

---

## Completion Criteria

- [x] `get_policy_evaluations()` returns records with all extended stats
- [x] `get_all_policy_evaluations()` returns records with all extended stats
- [x] JSON fields (`cost_breakdown`, `agent_stats`, `confidence_interval_95`) deserialize correctly
- [x] Old records without extended stats load correctly (null handling)
- [x] End-to-end test passes for bootstrap experiment
- [x] End-to-end test passes for deterministic experiment
- [x] All test cases pass (82 total)
- [x] Type check passes
- [x] Lint passes
- [x] No regression in existing charting functionality
