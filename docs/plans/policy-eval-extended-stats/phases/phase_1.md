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

Create tests in `api/tests/experiments/runner/test_policy_evaluation_metrics.py`.

**Reference**: See `test-matrix.md` for complete test IDs (PR-01 through PR-08).

**Test Cases** (18 tests total):

#### Schema Validation Tests
1. `test_policy_evaluation_record_has_extended_stats_fields` - All 6 new fields exist
2. `test_settlement_rate_type_is_float` - Type validation
3. `test_avg_delay_type_is_float` - Type validation
4. `test_cost_breakdown_type_is_dict` - Type validation
5. `test_cost_std_dev_type_is_int_or_none` - Type validation
6. `test_confidence_interval_type_is_list_or_none` - Type validation
7. `test_agent_stats_type_is_dict` - Type validation

#### Round-Trip Persistence Tests
8. `test_roundtrip_deterministic_single_agent` - PR-01
9. `test_roundtrip_deterministic_multi_agent` - PR-02
10. `test_roundtrip_bootstrap_single_agent` - PR-03
11. `test_roundtrip_bootstrap_multi_agent` - PR-04
12. `test_roundtrip_cost_breakdown_structure` - PR-05
13. `test_roundtrip_agent_stats_nested_cost_breakdown` - PR-06
14. `test_roundtrip_null_values_preserved` - PR-07
15. `test_roundtrip_empty_agent_stats` - PR-08

#### Backward Compatibility Tests
16. `test_load_record_without_extended_stats` - Old records load with None
17. `test_schema_migration_adds_columns` - ALTER TABLE works
18. `test_mixed_records_old_and_new` - Both coexist

```python
class TestPolicyEvaluationExtendedStatsSchema:
    """Tests for extended policy evaluation statistics schema."""

    def test_policy_evaluation_record_has_extended_stats_fields(self) -> None:
        """PolicyEvaluationRecord should have all 6 extended stats fields."""
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
            # Extended stats - all 6 fields
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
                    "cost_breakdown": {"delay_cost": 3000, "overdraft_cost": 5000, "deadline_penalty": 0, "eod_penalty": 0},
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                }
            },
        )

        # Verify all 6 extended fields exist and have correct values
        assert record.settlement_rate == 0.95
        assert record.avg_delay == 5.2
        assert record.cost_breakdown is not None
        assert record.cost_std_dev == 500
        assert record.confidence_interval_95 == [7800, 8200]
        assert record.agent_stats is not None


class TestPolicyEvaluationRoundTrip:
    """Round-trip persistence tests for all combinations."""

    def test_roundtrip_deterministic_single_agent(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-01: Deterministic single-agent record survives round-trip."""
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
            # Deterministic mode: std_dev and CI should be None
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={"delay_cost": 3000, "overdraft_cost": 4500, "deadline_penalty": 500, "eod_penalty": 0},
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {"delay_cost": 3000, "overdraft_cost": 4500, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify ALL fields
        assert loaded.settlement_rate == 0.95
        assert loaded.avg_delay == 5.2
        assert loaded.cost_breakdown == {"delay_cost": 3000, "overdraft_cost": 4500, "deadline_penalty": 500, "eod_penalty": 0}
        assert loaded.cost_std_dev is None
        assert loaded.confidence_interval_95 is None
        assert loaded.agent_stats["BANK_A"]["cost"] == 8000
        assert loaded.agent_stats["BANK_A"]["settlement_rate"] == 0.95
        assert loaded.agent_stats["BANK_A"]["std_dev"] is None

    def test_roundtrip_deterministic_multi_agent(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-02: Deterministic multi-agent record survives round-trip."""
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",  # Primary agent being optimized
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
            settlement_rate=0.93,
            avg_delay=4.8,
            cost_breakdown={"delay_cost": 5000, "overdraft_cost": 8000, "deadline_penalty": 1000, "eod_penalty": 0},
            cost_std_dev=None,
            confidence_interval_95=None,
            # Multi-agent: stats for all 3 agents
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {"delay_cost": 3000, "overdraft_cost": 4500, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
                "BANK_B": {
                    "cost": 7500,
                    "settlement_rate": 0.92,
                    "avg_delay": 4.5,
                    "cost_breakdown": {"delay_cost": 2000, "overdraft_cost": 5000, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
                "BANK_C": {
                    "cost": 6000,
                    "settlement_rate": 0.91,
                    "avg_delay": 4.2,
                    "cost_breakdown": {"delay_cost": 1500, "overdraft_cost": 4000, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 3 agents present
        assert len(loaded.agent_stats) == 3
        assert "BANK_A" in loaded.agent_stats
        assert "BANK_B" in loaded.agent_stats
        assert "BANK_C" in loaded.agent_stats

        # Verify each agent has all required fields
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = loaded.agent_stats[agent_id]
            assert "cost" in agent
            assert "settlement_rate" in agent
            assert "avg_delay" in agent
            assert "cost_breakdown" in agent
            assert isinstance(agent["cost"], int)
            assert isinstance(agent["settlement_rate"], float)

    def test_roundtrip_bootstrap_single_agent(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-03: Bootstrap single-agent record with std_dev and CI survives round-trip."""
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "LiquidityAware", "threshold": 50000},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=100000,  # Sum across 50 samples
            num_samples=50,
            sample_details=[{"index": 0, "seed": 111, "old_cost": 10000, "new_cost": 8000, "delta": 2000}],
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            # Bootstrap mode: std_dev and CI present
            settlement_rate=0.94,
            avg_delay=5.0,
            cost_breakdown={"delay_cost": 3500, "overdraft_cost": 4000, "deadline_penalty": 500, "eod_penalty": 0},
            cost_std_dev=450,
            confidence_interval_95=[7100, 8900],
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.94,
                    "avg_delay": 5.0,
                    "cost_breakdown": {"delay_cost": 3500, "overdraft_cost": 4000, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify bootstrap-specific fields
        assert loaded.cost_std_dev == 450
        assert loaded.confidence_interval_95 == [7100, 8900]
        assert loaded.agent_stats["BANK_A"]["std_dev"] == 450
        assert loaded.agent_stats["BANK_A"]["ci_95_lower"] == 7100
        assert loaded.agent_stats["BANK_A"]["ci_95_upper"] == 8900

    def test_roundtrip_bootstrap_multi_agent(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-04: Bootstrap multi-agent record with all agents having std_dev/CI."""
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "LiquidityAware", "threshold": 50000},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=100000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.93,
            avg_delay=4.8,
            cost_breakdown={"delay_cost": 5000, "overdraft_cost": 8000, "deadline_penalty": 1000, "eod_penalty": 0},
            cost_std_dev=600,
            confidence_interval_95=[7200, 8800],
            # Multi-agent bootstrap: all agents have std_dev and CI
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {"delay_cost": 3000, "overdraft_cost": 4500, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                },
                "BANK_B": {
                    "cost": 7500,
                    "settlement_rate": 0.92,
                    "avg_delay": 4.5,
                    "cost_breakdown": {"delay_cost": 2000, "overdraft_cost": 5000, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": 380,
                    "ci_95_lower": 6800,
                    "ci_95_upper": 8200,
                },
                "BANK_C": {
                    "cost": 6000,
                    "settlement_rate": 0.91,
                    "avg_delay": 4.2,
                    "cost_breakdown": {"delay_cost": 1500, "overdraft_cost": 4000, "deadline_penalty": 500, "eod_penalty": 0},
                    "std_dev": 320,
                    "ci_95_lower": 5400,
                    "ci_95_upper": 6600,
                },
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 3 agents have bootstrap stats
        assert len(loaded.agent_stats) == 3
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = loaded.agent_stats[agent_id]
            assert agent["std_dev"] is not None, f"{agent_id} missing std_dev"
            assert agent["ci_95_lower"] is not None, f"{agent_id} missing ci_95_lower"
            assert agent["ci_95_upper"] is not None, f"{agent_id} missing ci_95_upper"
            assert isinstance(agent["std_dev"], int)
            assert isinstance(agent["ci_95_lower"], int)
            assert isinstance(agent["ci_95_upper"], int)

    def test_roundtrip_cost_breakdown_all_components(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-05: cost_breakdown with all 4 components preserved exactly."""
        expected_breakdown = {
            "delay_cost": 3000,
            "overdraft_cost": 5000,
            "deadline_penalty": 1500,
            "eod_penalty": 500,
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=10000,
            context_simulation_cost=10000,
            accepted=False,
            acceptance_reason="cost_not_improved",
            delta_sum=0,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.90,
            avg_delay=6.0,
            cost_breakdown=expected_breakdown,
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={"BANK_A": {"cost": 10000}},
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 4 components exactly
        assert loaded.cost_breakdown["delay_cost"] == 3000
        assert loaded.cost_breakdown["overdraft_cost"] == 5000
        assert loaded.cost_breakdown["deadline_penalty"] == 1500
        assert loaded.cost_breakdown["eod_penalty"] == 500
        assert sum(loaded.cost_breakdown.values()) == 10000

    def test_roundtrip_agent_stats_nested_cost_breakdown(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-06: Nested cost_breakdown within agent_stats preserved."""
        agent_breakdown = {
            "delay_cost": 1500,
            "overdraft_cost": 2500,
            "deadline_penalty": 750,
            "eod_penalty": 250,
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=5000,
            new_cost=5000,
            context_simulation_cost=5000,
            accepted=False,
            acceptance_reason="cost_not_improved",
            delta_sum=0,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.92,
            avg_delay=5.5,
            cost_breakdown=agent_breakdown,
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={
                "BANK_A": {
                    "cost": 5000,
                    "settlement_rate": 0.92,
                    "avg_delay": 5.5,
                    "cost_breakdown": agent_breakdown,  # Nested!
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify nested cost_breakdown
        nested = loaded.agent_stats["BANK_A"]["cost_breakdown"]
        assert nested["delay_cost"] == 1500
        assert nested["overdraft_cost"] == 2500
        assert nested["deadline_penalty"] == 750
        assert nested["eod_penalty"] == 250

    def test_roundtrip_null_values_preserved(
        self, repo_with_experiment: ExperimentRepository
    ) -> None:
        """PR-07: None values stored and retrieved as None."""
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
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={"delay_cost": 8000, "overdraft_cost": 0, "deadline_penalty": 0, "eod_penalty": 0},
            cost_std_dev=None,  # Explicitly None
            confidence_interval_95=None,  # Explicitly None
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "std_dev": None,  # Explicitly None
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify None is preserved (not 0, not empty string)
        assert loaded.cost_std_dev is None
        assert loaded.confidence_interval_95 is None
        assert loaded.agent_stats["BANK_A"]["std_dev"] is None
        assert loaded.agent_stats["BANK_A"]["ci_95_lower"] is None
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
