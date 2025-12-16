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

Add tests to `api/tests/experiments/runner/test_policy_evaluation_metrics.py`.

**Reference**: See `test-matrix.md` for complete test IDs.

**Test Cases** (56 tests total across all combinations):

#### A. Deterministic Mode - Total Metrics (DT-01 through DT-09)
1. `test_det_total_settlement_rate_type_and_range` - DT-01
2. `test_det_total_avg_delay_type_and_range` - DT-02
3. `test_det_total_cost_breakdown_delay_cost` - DT-03
4. `test_det_total_cost_breakdown_overdraft_cost` - DT-04
5. `test_det_total_cost_breakdown_deadline_penalty` - DT-05
6. `test_det_total_cost_breakdown_eod_penalty` - DT-06
7. `test_det_total_cost_breakdown_sum_matches_cost` - DT-07
8. `test_det_total_std_dev_is_none` - DT-08
9. `test_det_total_ci_is_none` - DT-09

#### B. Deterministic Mode - Per-Agent Single (DA-01 through DA-10)
10. `test_det_agent_cost_type` - DA-01
11. `test_det_agent_settlement_rate` - DA-02
12. `test_det_agent_avg_delay` - DA-03
13. `test_det_agent_cost_breakdown_delay` - DA-04
14. `test_det_agent_cost_breakdown_overdraft` - DA-05
15. `test_det_agent_cost_breakdown_deadline` - DA-06
16. `test_det_agent_cost_breakdown_eod` - DA-07
17. `test_det_agent_std_dev_is_none` - DA-08
18. `test_det_agent_ci_lower_is_none` - DA-09
19. `test_det_agent_ci_upper_is_none` - DA-10

#### C. Deterministic Mode - Per-Agent Multi (DM-01 through DM-08)
20. `test_det_multi_agent_stats_has_all_agents` - DM-01
21. `test_det_multi_each_agent_has_cost` - DM-02
22. `test_det_multi_each_agent_has_settlement_rate` - DM-03
23. `test_det_multi_each_agent_has_avg_delay` - DM-04
24. `test_det_multi_each_agent_has_cost_breakdown` - DM-05
25. `test_det_multi_sum_agent_costs_approx_total` - DM-06
26. `test_det_multi_each_agent_std_dev_none` - DM-07
27. `test_det_multi_each_agent_ci_none` - DM-08

#### D. Bootstrap Mode - Total Metrics (BT-01 through BT-12)
28. `test_boot_total_settlement_rate_type_and_range` - BT-01
29. `test_boot_total_avg_delay_type_and_range` - BT-02
30. `test_boot_total_cost_breakdown_delay_cost` - BT-03
31. `test_boot_total_cost_breakdown_overdraft_cost` - BT-04
32. `test_boot_total_cost_breakdown_deadline_penalty` - BT-05
33. `test_boot_total_cost_breakdown_eod_penalty` - BT-06
34. `test_boot_total_cost_breakdown_sum_approx_cost` - BT-07
35. `test_boot_total_std_dev_present_and_nonneg` - BT-08
36. `test_boot_total_ci_lower_present` - BT-09
37. `test_boot_total_ci_upper_present` - BT-10
38. `test_boot_total_ci_width_positive` - BT-11
39. `test_boot_total_ci_contains_mean` - BT-12

#### E. Bootstrap Mode - Per-Agent Single (BA-01 through BA-08)
40. `test_boot_agent_cost_is_mean` - BA-01
41. `test_boot_agent_settlement_rate` - BA-02
42. `test_boot_agent_avg_delay` - BA-03
43. `test_boot_agent_cost_breakdown_present` - BA-04
44. `test_boot_agent_std_dev_present` - BA-05
45. `test_boot_agent_ci_lower_present` - BA-06
46. `test_boot_agent_ci_upper_present` - BA-07
47. `test_boot_agent_ci_contains_mean` - BA-08

#### F. Bootstrap Mode - Per-Agent Multi (BM-01 through BM-09)
48. `test_boot_multi_agent_stats_has_all_agents` - BM-01
49. `test_boot_multi_each_agent_has_cost` - BM-02
50. `test_boot_multi_each_agent_has_settlement_rate` - BM-03
51. `test_boot_multi_each_agent_has_avg_delay` - BM-04
52. `test_boot_multi_each_agent_has_cost_breakdown` - BM-05
53. `test_boot_multi_each_agent_has_std_dev` - BM-06
54. `test_boot_multi_each_agent_has_ci_lower` - BM-07
55. `test_boot_multi_each_agent_has_ci_upper` - BM-08
56. `test_boot_multi_sum_agent_costs_approx_total` - BM-09

```python
class TestDeterministicTotalMetrics:
    """DT-* tests: Deterministic mode total metrics."""

    def test_det_total_settlement_rate_type_and_range(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-01: settlement_rate is float in [0.0, 1.0]."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.settlement_rate is not None
        assert isinstance(evaluation.settlement_rate, float)
        assert 0.0 <= evaluation.settlement_rate <= 1.0

    def test_det_total_avg_delay_type_and_range(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-02: avg_delay is float >= 0."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.avg_delay is not None
        assert isinstance(evaluation.avg_delay, float)
        assert evaluation.avg_delay >= 0.0

    def test_det_total_cost_breakdown_all_components(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-03 through DT-06: All 4 cost_breakdown components present."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.cost_breakdown is not None
        assert "delay_cost" in evaluation.cost_breakdown
        assert "overdraft_cost" in evaluation.cost_breakdown
        assert "deadline_penalty" in evaluation.cost_breakdown
        assert "eod_penalty" in evaluation.cost_breakdown

        # All are integers >= 0
        for key in ["delay_cost", "overdraft_cost", "deadline_penalty", "eod_penalty"]:
            assert isinstance(evaluation.cost_breakdown[key], int)
            assert evaluation.cost_breakdown[key] >= 0

    def test_det_total_cost_breakdown_sum_matches_cost(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-07: Sum of cost_breakdown approximately equals new_cost."""
        evaluation = deterministic_evaluation_fixture

        breakdown_sum = sum(evaluation.cost_breakdown.values())
        # Allow some tolerance for rounding
        assert abs(breakdown_sum - evaluation.mean_new_cost) < 100

    def test_det_total_std_dev_is_none(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-08: cost_std_dev must be None for N=1."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.cost_std_dev is None

    def test_det_total_ci_is_none(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DT-09: confidence_interval_95 must be None for N=1."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.confidence_interval_95 is None


class TestDeterministicPerAgentSingle:
    """DA-* tests: Deterministic mode per-agent (single agent)."""

    def test_det_agent_all_fields_present(
        self, deterministic_evaluation_fixture
    ) -> None:
        """DA-01 through DA-10: Single agent has all required fields."""
        evaluation = deterministic_evaluation_fixture

        assert evaluation.agent_stats is not None
        assert "BANK_A" in evaluation.agent_stats

        agent = evaluation.agent_stats["BANK_A"]

        # DA-01: cost is int
        assert "cost" in agent
        assert isinstance(agent["cost"], int)
        assert agent["cost"] >= 0

        # DA-02: settlement_rate is float in [0, 1]
        assert "settlement_rate" in agent
        assert isinstance(agent["settlement_rate"], float)
        assert 0.0 <= agent["settlement_rate"] <= 1.0

        # DA-03: avg_delay is float >= 0
        assert "avg_delay" in agent
        assert isinstance(agent["avg_delay"], float)
        assert agent["avg_delay"] >= 0.0

        # DA-04 through DA-07: cost_breakdown components
        assert "cost_breakdown" in agent
        for key in ["delay_cost", "overdraft_cost", "deadline_penalty", "eod_penalty"]:
            assert key in agent["cost_breakdown"]
            assert isinstance(agent["cost_breakdown"][key], int)
            assert agent["cost_breakdown"][key] >= 0

        # DA-08 through DA-10: std_dev and CI are None for deterministic
        assert agent.get("std_dev") is None
        assert agent.get("ci_95_lower") is None
        assert agent.get("ci_95_upper") is None


class TestDeterministicPerAgentMulti:
    """DM-* tests: Deterministic mode per-agent (multiple agents)."""

    def test_det_multi_all_agents_present(
        self, deterministic_multi_agent_evaluation_fixture
    ) -> None:
        """DM-01: agent_stats has all 3 agents."""
        evaluation = deterministic_multi_agent_evaluation_fixture

        assert len(evaluation.agent_stats) == 3
        assert "BANK_A" in evaluation.agent_stats
        assert "BANK_B" in evaluation.agent_stats
        assert "BANK_C" in evaluation.agent_stats

    def test_det_multi_each_agent_complete(
        self, deterministic_multi_agent_evaluation_fixture
    ) -> None:
        """DM-02 through DM-05: Each agent has all required fields."""
        evaluation = deterministic_multi_agent_evaluation_fixture

        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = evaluation.agent_stats[agent_id]

            # DM-02: cost present
            assert "cost" in agent, f"{agent_id} missing cost"
            assert isinstance(agent["cost"], int)

            # DM-03: settlement_rate present
            assert "settlement_rate" in agent, f"{agent_id} missing settlement_rate"
            assert isinstance(agent["settlement_rate"], float)

            # DM-04: avg_delay present
            assert "avg_delay" in agent, f"{agent_id} missing avg_delay"
            assert isinstance(agent["avg_delay"], float)

            # DM-05: cost_breakdown present with all 4 components
            assert "cost_breakdown" in agent, f"{agent_id} missing cost_breakdown"
            for key in ["delay_cost", "overdraft_cost", "deadline_penalty", "eod_penalty"]:
                assert key in agent["cost_breakdown"], f"{agent_id} missing {key}"

    def test_det_multi_sum_costs_approx_total(
        self, deterministic_multi_agent_evaluation_fixture
    ) -> None:
        """DM-06: Sum of agent costs approximates total."""
        evaluation = deterministic_multi_agent_evaluation_fixture

        agent_sum = sum(
            agent["cost"] for agent in evaluation.agent_stats.values()
        )
        # Total cost is across all agents
        assert abs(agent_sum - evaluation.mean_new_cost) < 100

    def test_det_multi_all_agents_no_stats(
        self, deterministic_multi_agent_evaluation_fixture
    ) -> None:
        """DM-07, DM-08: All agents have None for std_dev and CI."""
        evaluation = deterministic_multi_agent_evaluation_fixture

        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = evaluation.agent_stats[agent_id]
            assert agent.get("std_dev") is None, f"{agent_id} std_dev should be None"
            assert agent.get("ci_95_lower") is None, f"{agent_id} ci_lower should be None"
            assert agent.get("ci_95_upper") is None, f"{agent_id} ci_upper should be None"


class TestBootstrapTotalMetrics:
    """BT-* tests: Bootstrap mode total metrics."""

    def test_boot_total_settlement_rate(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BT-01: settlement_rate is float in [0.0, 1.0]."""
        evaluation = bootstrap_evaluation_fixture

        assert evaluation.settlement_rate is not None
        assert isinstance(evaluation.settlement_rate, float)
        assert 0.0 <= evaluation.settlement_rate <= 1.0

    def test_boot_total_avg_delay(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BT-02: avg_delay is float >= 0."""
        evaluation = bootstrap_evaluation_fixture

        assert evaluation.avg_delay is not None
        assert isinstance(evaluation.avg_delay, float)
        assert evaluation.avg_delay >= 0.0

    def test_boot_total_cost_breakdown(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BT-03 through BT-07: cost_breakdown complete."""
        evaluation = bootstrap_evaluation_fixture

        assert evaluation.cost_breakdown is not None
        for key in ["delay_cost", "overdraft_cost", "deadline_penalty", "eod_penalty"]:
            assert key in evaluation.cost_breakdown
            assert isinstance(evaluation.cost_breakdown[key], int)
            assert evaluation.cost_breakdown[key] >= 0

    def test_boot_total_std_dev_present(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BT-08: cost_std_dev is int >= 0 for bootstrap."""
        evaluation = bootstrap_evaluation_fixture

        assert evaluation.cost_std_dev is not None
        assert isinstance(evaluation.cost_std_dev, int)
        assert evaluation.cost_std_dev >= 0

    def test_boot_total_ci_present_and_valid(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BT-09 through BT-12: CI present, valid, contains mean."""
        evaluation = bootstrap_evaluation_fixture

        # BT-09, BT-10: CI bounds present
        assert evaluation.confidence_interval_95 is not None
        assert len(evaluation.confidence_interval_95) == 2

        lower, upper = evaluation.confidence_interval_95
        assert isinstance(lower, int)
        assert isinstance(upper, int)

        # BT-11: Width positive
        assert upper > lower, "CI upper must be > lower"

        # BT-12: Contains mean
        assert lower <= evaluation.mean_new_cost <= upper, "CI must contain mean"


class TestBootstrapPerAgentSingle:
    """BA-* tests: Bootstrap mode per-agent (single agent)."""

    def test_boot_agent_all_fields(
        self, bootstrap_evaluation_fixture
    ) -> None:
        """BA-01 through BA-08: Single agent has all fields with stats."""
        evaluation = bootstrap_evaluation_fixture

        assert "BANK_A" in evaluation.agent_stats
        agent = evaluation.agent_stats["BANK_A"]

        # BA-01: cost (mean)
        assert "cost" in agent
        assert isinstance(agent["cost"], int)

        # BA-02: settlement_rate
        assert "settlement_rate" in agent
        assert 0.0 <= agent["settlement_rate"] <= 1.0

        # BA-03: avg_delay
        assert "avg_delay" in agent
        assert agent["avg_delay"] >= 0.0

        # BA-04: cost_breakdown
        assert "cost_breakdown" in agent

        # BA-05: std_dev present (bootstrap)
        assert "std_dev" in agent
        assert agent["std_dev"] is not None
        assert isinstance(agent["std_dev"], int)
        assert agent["std_dev"] >= 0

        # BA-06, BA-07: CI bounds present
        assert "ci_95_lower" in agent
        assert "ci_95_upper" in agent
        assert agent["ci_95_lower"] is not None
        assert agent["ci_95_upper"] is not None

        # BA-08: CI contains mean
        assert agent["ci_95_lower"] <= agent["cost"] <= agent["ci_95_upper"]


class TestBootstrapPerAgentMulti:
    """BM-* tests: Bootstrap mode per-agent (multiple agents)."""

    def test_boot_multi_all_agents_have_all_fields(
        self, bootstrap_multi_agent_evaluation_fixture
    ) -> None:
        """BM-01 through BM-09: All 3 agents have complete stats."""
        evaluation = bootstrap_multi_agent_evaluation_fixture

        # BM-01: All agents present
        assert len(evaluation.agent_stats) == 3
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            assert agent_id in evaluation.agent_stats

            agent = evaluation.agent_stats[agent_id]

            # BM-02: cost
            assert "cost" in agent, f"{agent_id} missing cost"

            # BM-03: settlement_rate
            assert "settlement_rate" in agent, f"{agent_id} missing settlement_rate"

            # BM-04: avg_delay
            assert "avg_delay" in agent, f"{agent_id} missing avg_delay"

            # BM-05: cost_breakdown
            assert "cost_breakdown" in agent, f"{agent_id} missing cost_breakdown"

            # BM-06: std_dev (bootstrap, so NOT None)
            assert "std_dev" in agent, f"{agent_id} missing std_dev"
            assert agent["std_dev"] is not None, f"{agent_id} std_dev should NOT be None"

            # BM-07: ci_95_lower
            assert "ci_95_lower" in agent, f"{agent_id} missing ci_95_lower"
            assert agent["ci_95_lower"] is not None

            # BM-08: ci_95_upper
            assert "ci_95_upper" in agent, f"{agent_id} missing ci_95_upper"
            assert agent["ci_95_upper"] is not None

    def test_boot_multi_sum_costs(
        self, bootstrap_multi_agent_evaluation_fixture
    ) -> None:
        """BM-09: Sum of agent costs approximates total."""
        evaluation = bootstrap_multi_agent_evaluation_fixture

        agent_sum = sum(
            agent["cost"] for agent in evaluation.agent_stats.values()
        )
        # Allow tolerance
        assert abs(agent_sum - evaluation.mean_new_cost) < 500
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
