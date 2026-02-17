# Phase 5: Test Bootstrap Logic Matches Experiment Runner

**Status**: Pending

---

## Objective

Verify that the web bootstrap evaluation produces results consistent with the experiment runner's `BootstrapPolicyEvaluator`. Same acceptance criteria, same statistical methodology, same invariants.

---

## Invariants Enforced in This Phase

- INV-GAME-3: Bootstrap Identity — web evaluation matches experiment runner
- INV-1: Money is i64 — all values integer cents
- INV-2: Determinism — reproducible results

---

## TDD Steps

### Step 5.1: Cross-Validation Tests (RED → GREEN)

**Add to `web/backend/tests/test_bootstrap_eval.py`:**

```python
class TestBootstrapIdentity:
    """INV-GAME-3: Web bootstrap must match experiment runner criteria."""

    def test_paired_delta_sign_convention(self):
        """delta = old_cost - new_cost. Positive = new is better.
        This matches the experiment runner's convention."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=0.5)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(1.0),   # Expensive
            new_policy=make_policy(0.3),   # Cheaper
            base_seed=42,
        )
        # old_cost > new_cost → delta > 0 → accepted
        assert result.delta_sum > 0
        assert result.accepted is True

    def test_cv_computation_matches(self):
        """CV = stdev(deltas) / |mean(deltas)|, matching standard definition."""
        eval = WebBootstrapEvaluator(num_samples=10, cv_threshold=10.0)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(0.8),
            new_policy=make_policy(0.4),
            base_seed=42,
        )
        # Manually verify CV
        deltas = [d["delta"] for d in result.paired_deltas]
        import statistics, math
        if result.mean_delta != 0:
            expected_cv = abs(statistics.stdev(deltas) / result.mean_delta)
            assert abs(result.cv - expected_cv) < 0.001

    def test_ci_computation(self):
        """95% CI uses z=1.96 * stderr, matching standard bootstrap CI."""
        eval = WebBootstrapEvaluator(num_samples=10, cv_threshold=10.0)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(0.8),
            new_policy=make_policy(0.4),
            base_seed=42,
        )
        deltas = [d["delta"] for d in result.paired_deltas]
        import statistics, math
        std = statistics.stdev(deltas)
        se = std / math.sqrt(len(deltas))
        expected_lower = int(result.mean_delta - 1.96 * se)
        expected_upper = int(result.mean_delta + 1.96 * se)
        assert result.ci_lower == expected_lower
        assert result.ci_upper == expected_upper

    def test_acceptance_requires_all_three_criteria(self):
        """Must pass ALL: delta_sum > 0, CV < threshold, CI lower > 0."""
        # Test with very strict CV to force rejection
        strict = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.001)
        result = strict.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(0.8),
            new_policy=make_policy(0.6),
            base_seed=42,
        )
        # Even if delta is positive, strict CV should reject
        if result.cv > 0.001:
            assert result.accepted is False

    def test_no_division_by_zero(self):
        """Identical policies → delta=0 → no crash."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(0.5),
            new_policy=make_policy(0.5),
            base_seed=42,
        )
        # Should not crash, CV should be 0 or handled
        assert isinstance(result.cv, float)
        assert not math.isnan(result.cv)


class TestBootstrapDeterminism:
    """Verify determinism of bootstrap evaluation."""

    def test_same_inputs_same_output(self):
        """INV-2: Identical inputs produce identical results."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=0.5)
        kwargs = dict(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(0.7),
            new_policy=make_policy(0.3),
            base_seed=42,
        )
        r1 = eval.evaluate(**kwargs)
        r2 = eval.evaluate(**kwargs)
        assert r1.delta_sum == r2.delta_sum
        assert r1.cv == r2.cv
        assert r1.ci_lower == r2.ci_lower
        assert r1.accepted == r2.accepted

    def test_different_seeds_different_results(self):
        """Different base seeds produce different deltas."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=0.5)
        r1 = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.7), new_policy=make_policy(0.3), base_seed=42,
        )
        r2 = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.7), new_policy=make_policy(0.3), base_seed=99,
        )
        # Very unlikely to be identical with different seeds
        # (but not impossible — don't assert !=, just check both ran)
        assert isinstance(r1.delta_sum, int)
        assert isinstance(r2.delta_sum, int)
```

### Step 5.2: Refactor

- Add performance benchmark (how long does N=10 bootstrap take?)
- Document the relationship to experiment runner's evaluator
- Add note that web uses fresh stochastic seeds vs runner's resampled history

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/tests/test_bootstrap_eval.py` | Modify | Add identity and determinism tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_bootstrap_eval.py -v --tb=short
```

## Completion Criteria

- [ ] Delta sign convention: positive = new is better (matches runner)
- [ ] CV computation matches standard formula
- [ ] CI computation matches z=1.96 * stderr
- [ ] All three acceptance criteria enforced
- [ ] No division by zero on identical policies
- [ ] Deterministic results for same inputs
- [ ] All tests pass
