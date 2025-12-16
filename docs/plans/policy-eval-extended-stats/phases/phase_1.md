# Phase 1: Schema Extension

**Status**: Pending
**Started**:

---

## Objective

Extend `PolicyEvaluationRecord` dataclass and database schema to include fields for extended statistics: settlement rate, average delay, cost breakdown, cost std dev, confidence interval, and per-agent stats.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - New cost fields (`cost_std_dev`, CI bounds) use integer cents
- **INV-5**: Replay Identity - Changes are additive; existing replay functionality unaffected

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create tests in `api/tests/experiments/runner/test_policy_evaluation_metrics.py`:

**Test Cases**:
1. `test_policy_evaluation_record_has_extended_stats_fields` - Verify dataclass has new fields
2. `test_extended_stats_fields_have_correct_types` - Type validation
3. `test_save_load_with_extended_stats` - Round-trip persistence
4. `test_load_record_without_extended_stats` - Backward compat (null handling)
5. `test_cost_breakdown_json_serialization` - Complex type handling
6. `test_agent_stats_json_serialization` - Per-agent data handling

```python
class TestPolicyEvaluationExtendedStats:
    """Tests for extended policy evaluation statistics."""

    def test_policy_evaluation_record_has_extended_stats_fields(self) -> None:
        """PolicyEvaluationRecord should have all extended stats fields."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Verify fields exist by creating record with all fields
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            # Extended stats
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={"delay_cost": 3000, "overdraft_cost": 5000, "deadline_penalty": 0, "eod_penalty": 0},
            cost_std_dev=500,
            confidence_interval_95=[7800, 8200],
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {"delay_cost": 3000, "overdraft_cost": 5000, "deadline_penalty": 0, "eod_penalty": 0}
                }
            },
        )

        assert record.settlement_rate == 0.95
        assert record.avg_delay == 5.2
        assert record.cost_breakdown is not None
        assert record.cost_std_dev == 500
        assert record.confidence_interval_95 == [7800, 8200]
        assert record.agent_stats is not None

    def test_extended_stats_nullable_for_deterministic(self) -> None:
        """Extended stats should be nullable for deterministic mode."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            # Extended stats - some nullable for deterministic
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={"delay_cost": 3000, "overdraft_cost": 5000, "deadline_penalty": 0, "eod_penalty": 0},
            cost_std_dev=None,  # Not applicable for N=1
            confidence_interval_95=None,  # Not applicable for N=1
            agent_stats={"BANK_A": {"cost": 8000, "settlement_rate": 0.95, "avg_delay": 5.2}},
        )

        assert record.cost_std_dev is None
        assert record.confidence_interval_95 is None
```

### Step 1.2: Implement to Pass Tests (GREEN)

**Modify** `api/payment_simulator/experiments/persistence/repository.py`:

1. Update `PolicyEvaluationRecord` dataclass:

```python
@dataclass(frozen=True)
class PolicyEvaluationRecord:
    """Complete record of a policy evaluation.

    All costs in integer cents (INV-1 compliance).
    """
    # ... existing fields ...

    # Extended statistics (NEW)
    settlement_rate: float | None = None  # 0.0 to 1.0
    avg_delay: float | None = None  # Average delay in ticks
    cost_breakdown: dict[str, int] | None = None  # {delay_cost, overdraft_cost, ...}
    cost_std_dev: int | None = None  # Bootstrap only, integer cents
    confidence_interval_95: list[int] | None = None  # Bootstrap only, [lower, upper] in cents
    agent_stats: dict[str, dict[str, Any]] | None = None  # Per-agent metrics
```

2. Update database schema in `_ensure_schema()`:

```sql
-- Add columns to policy_evaluations table
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS settlement_rate DOUBLE;
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS avg_delay DOUBLE;
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS cost_breakdown JSON;
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS cost_std_dev INTEGER;
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS confidence_interval_95 JSON;
ALTER TABLE policy_evaluations ADD COLUMN IF NOT EXISTS agent_stats JSON;
```

3. Update `save_policy_evaluation()` to include new columns.

4. Update `_row_to_policy_evaluation_record()` to read new columns.

### Step 1.3: Refactor

- Add docstrings explaining each new field
- Ensure type hints are complete
- Add validation for cost_breakdown keys

---

## Implementation Details

### PolicyEvaluationRecord Extended Fields

| Field | Type | Nullable | Mode | Description |
|-------|------|----------|------|-------------|
| `settlement_rate` | `float` | Yes | Both | System-wide settlement rate (0.0-1.0) |
| `avg_delay` | `float` | Yes | Both | System-wide average delay in ticks |
| `cost_breakdown` | `dict[str, int]` | Yes | Both | Total cost by type |
| `cost_std_dev` | `int` | Yes | Bootstrap | Std dev of costs in cents |
| `confidence_interval_95` | `list[int]` | Yes | Bootstrap | [lower, upper] bounds in cents |
| `agent_stats` | `dict[str, dict]` | Yes | Both | Per-agent metrics keyed by agent_id |

### cost_breakdown Structure

```json
{
  "delay_cost": 3000,
  "overdraft_cost": 5000,
  "deadline_penalty": 0,
  "eod_penalty": 0
}
```

### agent_stats Structure

```json
{
  "BANK_A": {
    "cost": 8000,
    "settlement_rate": 0.95,
    "avg_delay": 5.2,
    "cost_breakdown": {
      "delay_cost": 3000,
      "overdraft_cost": 5000,
      "deadline_penalty": 0,
      "eod_penalty": 0
    }
  },
  "BANK_B": {
    "cost": 7500,
    "settlement_rate": 0.92,
    "avg_delay": 4.8,
    "cost_breakdown": {...}
  }
}
```

### Edge Cases to Handle

- Records created before this feature: All extended fields should be `None`
- Bootstrap with N=1: `cost_std_dev` and `confidence_interval_95` should be `None`
- JSON serialization/deserialization of nested dicts

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/persistence/repository.py` | MODIFY |
| `api/payment_simulator/experiments/persistence/__init__.py` | VERIFY exports |
| `api/tests/experiments/runner/test_policy_evaluation_metrics.py` | MODIFY (add tests) |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_policy_evaluation_metrics.py -v -k "extended_stats"

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/persistence/repository.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/persistence/repository.py
```

---

## Completion Criteria

- [ ] `PolicyEvaluationRecord` has all 6 new fields with correct types
- [ ] Database schema includes new columns (nullable)
- [ ] `save_policy_evaluation()` persists new fields
- [ ] `_row_to_policy_evaluation_record()` reads new fields
- [ ] Old records without extended stats load correctly (null handling)
- [ ] New records with extended stats round-trip correctly
- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
