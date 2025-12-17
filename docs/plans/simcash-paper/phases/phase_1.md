# Phase 1: Data Provider

**Status**: Pending
**Started**:
**Completed**:

---

## Objective

Create a typed, tested data access layer that provides all experiment data needed for paper generation. This is the foundation—all numbers in the paper will flow through this layer.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - All costs returned as integer cents
- **NEW: Paper Generation Identity** - Query functions are the single source of truth

---

## TDD Steps

### Step 1.1: Define TypedDicts for Query Results (RED)

Create `tests/test_data_provider.py` with type assertions:

**Test Cases**:
1. `test_agent_iteration_result_has_required_fields` - TypedDict completeness
2. `test_bootstrap_stats_has_required_fields` - TypedDict completeness
3. `test_experiment_summary_has_required_fields` - TypedDict completeness

```python
from typing import get_type_hints
from src.data_provider import AgentIterationResult, BootstrapStats

class TestTypedDicts:
    def test_agent_iteration_result_has_required_fields(self) -> None:
        """AgentIterationResult must have iteration, agent_id, cost, liquidity_fraction."""
        hints = get_type_hints(AgentIterationResult)
        assert "iteration" in hints
        assert "agent_id" in hints
        assert "cost" in hints  # int (cents)
        assert "liquidity_fraction" in hints  # float
        assert "accepted" in hints  # bool

    def test_bootstrap_stats_has_required_fields(self) -> None:
        """BootstrapStats must have mean, std_dev, ci_lower, ci_upper, num_samples."""
        hints = get_type_hints(BootstrapStats)
        assert "mean_cost" in hints
        assert "std_dev" in hints
        assert "ci_lower" in hints
        assert "ci_upper" in hints
        assert "num_samples" in hints
```

### Step 1.2: Define DataProvider Protocol (RED)

Add to `tests/test_data_provider.py`:

**Test Cases**:
1. `test_data_provider_has_get_iteration_results` - Method exists
2. `test_data_provider_has_get_final_bootstrap_stats` - Method exists
3. `test_data_provider_has_get_convergence_iteration` - Method exists
4. `test_data_provider_has_get_experiment_config` - Method exists

```python
from typing import Protocol, runtime_checkable

class TestDataProviderProtocol:
    def test_database_provider_implements_protocol(self) -> None:
        """DatabaseDataProvider must implement DataProvider protocol."""
        from src.data_provider import DatabaseDataProvider, DataProvider
        provider = DatabaseDataProvider(Path("data/"))
        assert isinstance(provider, DataProvider)
```

### Step 1.3: Implement TypedDicts and Protocol (GREEN)

Create `src/data_provider.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypedDict, runtime_checkable

import duckdb


class AgentIterationResult(TypedDict):
    """Per-agent results for one iteration of an experiment."""

    iteration: int
    agent_id: str
    cost: int  # cents - never dollars!
    liquidity_fraction: float
    accepted: bool


class BootstrapStats(TypedDict):
    """Bootstrap evaluation statistics for one agent's final policy."""

    mean_cost: int  # cents
    std_dev: int  # cents
    ci_lower: int  # cents
    ci_upper: int  # cents
    num_samples: int


class ExperimentConfig(TypedDict):
    """Configuration extracted from experiment YAML."""

    ticks_per_day: int
    num_agents: int
    arrival_mode: str  # "deterministic" or "stochastic"
    # Add more as needed


@runtime_checkable
class DataProvider(Protocol):
    """Protocol for accessing experiment data.

    All paper values must come through this interface.
    Implementations: DatabaseDataProvider (production), MockDataProvider (testing)
    """

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Get per-agent costs for all iterations of an experiment pass.

        Args:
            exp_id: Experiment identifier ("exp1", "exp2", "exp3")
            pass_num: Pass number (1, 2, or 3)

        Returns:
            List of results ordered by (iteration, agent_id)
        """
        ...

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Get bootstrap statistics for the final iteration.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Dict mapping agent_id to bootstrap statistics
        """
        ...

    def get_convergence_iteration(self, exp_id: str, pass_num: int) -> int:
        """Get the iteration number where convergence was detected.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Iteration number (1-indexed)
        """
        ...

    def get_run_id(self, exp_id: str, pass_num: int) -> str:
        """Get the run_id for an experiment pass.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Run ID string (e.g., "exp1-20251217-001234-abc123")
        """
        ...
```

### Step 1.4: Write Query Tests Against Real Data (RED)

Add integration tests:

**Test Cases**:
1. `test_exp1_pass1_has_correct_final_costs` - Verify BANK_A=0, BANK_B=2000
2. `test_exp2_pass1_has_different_agent_costs` - Verify costs differ (bug fix check)
3. `test_exp3_pass1_has_symmetric_equilibrium` - Verify both ~2000 cents
4. `test_bootstrap_stats_match_database` - Verify CI values

```python
class TestDatabaseDataProvider:
    @pytest.fixture
    def provider(self) -> DatabaseDataProvider:
        return DatabaseDataProvider(Path("data/"))

    def test_exp1_pass1_final_iteration_costs(self, provider: DataProvider) -> None:
        """Exp1 Pass 1 should converge to BANK_A=0, BANK_B=2000 cents."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        bank_b = next(r for r in final_results if r["agent_id"] == "BANK_B")

        assert bank_a["cost"] == 0, "BANK_A should have 0 cost (free-rider)"
        assert bank_b["cost"] == 2000, "BANK_B should have $20.00 = 2000 cents"

    def test_exp2_pass1_agents_have_different_costs(self, provider: DataProvider) -> None:
        """Exp2 agents should have DIFFERENT costs (bug fix verification)."""
        results = provider.get_iteration_results("exp2", pass_num=1)

        # Check iteration 2 specifically (where bug was observed)
        iter2_results = [r for r in results if r["iteration"] == 2]

        if len(iter2_results) >= 2:
            costs = [r["cost"] for r in iter2_results]
            assert len(set(costs)) > 1, "Exp2 agents should have different costs!"

    def test_exp2_bootstrap_stats_have_nonzero_std_dev(self, provider: DataProvider) -> None:
        """Exp2 bootstrap should show variance for stochastic scenario."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)

        # At least one agent should have nonzero std dev
        std_devs = [s["std_dev"] for s in stats.values()]
        assert any(sd > 0 for sd in std_devs), "Exp2 should have variance"
```

### Step 1.5: Implement DatabaseDataProvider (GREEN)

Add implementation to `src/data_provider.py`:

```python
class DatabaseDataProvider:
    """DataProvider implementation using DuckDB databases."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize with directory containing exp{1,2,3}.db files."""
        self._data_dir = data_dir
        self._run_id_cache: dict[tuple[str, int], str] = {}

    def _get_db_path(self, exp_id: str) -> Path:
        """Get database path for experiment."""
        return self._data_dir / f"{exp_id}.db"

    def _get_connection(self, exp_id: str) -> duckdb.DuckDBPyConnection:
        """Get read-only connection to experiment database."""
        return duckdb.connect(str(self._get_db_path(exp_id)), read_only=True)

    def get_run_id(self, exp_id: str, pass_num: int) -> str:
        """Get run_id for experiment pass (cached)."""
        cache_key = (exp_id, pass_num)
        if cache_key not in self._run_id_cache:
            conn = self._get_connection(exp_id)
            result = conn.execute("""
                SELECT run_id FROM policy_evaluations
                ORDER BY run_id
            """).fetchall()

            # Get unique run_ids in order
            run_ids = list(dict.fromkeys(r[0] for r in result))
            if pass_num > len(run_ids):
                raise ValueError(f"Pass {pass_num} not found for {exp_id}")

            self._run_id_cache[cache_key] = run_ids[pass_num - 1]

        return self._run_id_cache[cache_key]

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Get per-agent costs for all iterations."""
        run_id = self.get_run_id(exp_id, pass_num)
        conn = self._get_connection(exp_id)

        result = conn.execute("""
            SELECT
                iteration,
                agent_id,
                new_cost as cost,
                json_extract(proposed_policy, '$.parameters.initial_liquidity_fraction')::DOUBLE as liquidity_fraction,
                accepted
            FROM policy_evaluations
            WHERE run_id = ?
            ORDER BY iteration, agent_id
        """, [run_id]).fetchall()

        return [
            AgentIterationResult(
                iteration=row[0],
                agent_id=row[1],
                cost=row[2],
                liquidity_fraction=row[3],
                accepted=row[4],
            )
            for row in result
        ]

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Get bootstrap statistics for final iteration."""
        run_id = self.get_run_id(exp_id, pass_num)
        conn = self._get_connection(exp_id)

        # Get max iteration
        max_iter = conn.execute("""
            SELECT MAX(iteration) FROM policy_evaluations WHERE run_id = ?
        """, [run_id]).fetchone()[0]

        result = conn.execute("""
            SELECT
                agent_id,
                new_cost as mean_cost,
                COALESCE(cost_std_dev, 0) as std_dev,
                confidence_interval_95
            FROM policy_evaluations
            WHERE run_id = ? AND iteration = ?
        """, [run_id, max_iter]).fetchall()

        stats: dict[str, BootstrapStats] = {}
        for row in result:
            agent_id, mean_cost, std_dev, ci_json = row

            # Parse CI JSON
            if ci_json:
                import json
                ci = json.loads(ci_json) if isinstance(ci_json, str) else ci_json
                ci_lower, ci_upper = ci[0], ci[1]
            else:
                ci_lower, ci_upper = mean_cost, mean_cost

            stats[agent_id] = BootstrapStats(
                mean_cost=mean_cost,
                std_dev=std_dev,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                num_samples=50,  # Fixed in our experiments
            )

        return stats

    def get_convergence_iteration(self, exp_id: str, pass_num: int) -> int:
        """Get iteration where convergence was detected."""
        results = self.get_iteration_results(exp_id, pass_num)
        return max(r["iteration"] for r in results)
```

### Step 1.6: Refactor

- Ensure all queries are well-documented
- Add docstrings with example return values
- Optimize connection handling if needed

---

## Implementation Details

### Database Schema Reference

The `policy_evaluations` table has:
- `run_id`: Unique identifier for experiment run
- `iteration`: 1-indexed iteration number
- `agent_id`: "BANK_A" or "BANK_B"
- `new_cost`: Cost in cents (integer)
- `cost_std_dev`: Standard deviation in cents (nullable)
- `confidence_interval_95`: JSON array [lower, upper] in cents
- `proposed_policy`: JSON with `parameters.initial_liquidity_fraction`
- `accepted`: Boolean

### Edge Cases to Handle

- Missing `cost_std_dev` (deterministic experiments) → return 0
- Missing `confidence_interval_95` → return [mean, mean]
- Pass number out of range → raise ValueError

---

## Files

| File | Action |
|------|--------|
| `src/__init__.py` | CREATE |
| `src/data_provider.py` | CREATE |
| `tests/__init__.py` | CREATE |
| `tests/test_data_provider.py` | CREATE |

---

## Verification

```bash
# Run tests
cd docs/papers/simcash-paper/v5
python -m pytest tests/test_data_provider.py -v

# Type check
python -m mypy src/

# Lint
python -m ruff check src/
```

---

## Completion Criteria

- [ ] All TypedDicts defined with complete fields
- [ ] DataProvider protocol defined
- [ ] DatabaseDataProvider implements protocol
- [ ] All test cases pass
- [ ] Type check passes
- [ ] Exp2 returns DIFFERENT costs for agents (bug fix verified)
- [ ] Bootstrap stats retrieved correctly
