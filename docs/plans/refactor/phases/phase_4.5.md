# Phase 4.5: Bootstrap Integration Tests with Mocked LLM

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Low
**Breaking Changes:** None (tests only)

---

## Objectives

1. Create comprehensive integration tests for bootstrap policy evaluation
2. Verify bootstrap samples are processed by both old and new policies
3. Verify delta costs are correctly calculated
4. Verify policies are accepted/rejected based on paired comparison

---

## Key Concepts

### Bootstrap Paired Comparison

The bootstrap evaluation system works as follows:

1. **Generate samples**: `BootstrapSampler.generate_samples()` creates N bootstrap samples
2. **Evaluate old policy**: `evaluate_samples(samples, old_policy)` → costs_old
3. **Evaluate new policy**: `evaluate_samples(samples, new_policy)` → costs_new (SAME samples!)
4. **Compute paired delta**: For each sample i: `delta_i = cost_old_i - cost_new_i`
5. **Mean delta**: `mean_delta = mean(all deltas)`
6. **Accept/reject**:
   - If `mean_delta > 0`: NEW policy is CHEAPER → ACCEPT
   - If `mean_delta <= 0`: OLD policy is same or better → REJECT

### Critical Invariant

**The SAME bootstrap samples MUST be used for evaluating both old and new policies.**

This is what makes it a "paired comparison" - we eliminate variance by comparing
policies on identical scenarios.

---

## TDD Test Specifications

### Test File: `api/tests/experiments/integration/test_bootstrap_policy_acceptance.py`

```python
"""Integration tests for bootstrap policy acceptance.

These tests verify the critical property that:
1. The same bootstrap samples are used for old and new policy evaluation
2. Paired deltas are computed correctly
3. Policy acceptance/rejection is based on mean_delta > 0
"""

import pytest
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
    BootstrapPolicyEvaluator,
    EvaluationResult,
    PairedDelta,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)


class TestBootstrapPairedComparison:
    """Tests for bootstrap paired comparison evaluation."""

    @pytest.fixture
    def simple_sample(self) -> BootstrapSample:
        """Create a simple bootstrap sample for testing."""
        return BootstrapSample(
            agent_id="TEST_AGENT",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(
                RemappedTransaction(
                    tx_id="tx1",
                    sender_id="TEST_AGENT",
                    receiver_id="OTHER",
                    amount=100000,  # $1000
                    priority=5,
                    arrival_tick=1,
                    deadline_tick=10,
                    settlement_tick=None,
                ),
            ),
            incoming_settlements=(),
            total_ticks=12,
        )

    def test_evaluate_samples_returns_results_for_each_sample(
        self, simple_sample: BootstrapSample
    ) -> None:
        """evaluate_samples returns one result per sample."""
        ...

    def test_compute_paired_deltas_uses_same_samples(
        self, simple_sample: BootstrapSample
    ) -> None:
        """Paired deltas use the exact same samples for both policies."""
        ...

    def test_paired_delta_formula_is_cost_a_minus_cost_b(
        self, simple_sample: BootstrapSample
    ) -> None:
        """delta = cost_a - cost_b (positive means A is more expensive)."""
        ...

    def test_mean_delta_positive_means_policy_b_is_cheaper(
        self,
    ) -> None:
        """When mean_delta > 0, policy B costs less on average."""
        ...

    def test_mean_delta_negative_means_policy_a_is_cheaper(
        self,
    ) -> None:
        """When mean_delta < 0, policy A costs less on average."""
        ...


class TestPolicyAcceptanceLogic:
    """Tests for policy acceptance based on mean delta."""

    def test_policy_accepted_when_mean_delta_positive(self) -> None:
        """Policy B accepted when mean_delta > 0 (B is cheaper)."""
        # mean_delta = cost_old - cost_new
        # If positive, new policy is cheaper → ACCEPT
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=800, delta=200),
            PairedDelta(sample_idx=1, seed=2, cost_a=1200, cost_b=900, delta=300),
        ]
        # mean_delta = (200 + 300) / 2 = 250 > 0 → ACCEPT
        ...

    def test_policy_rejected_when_mean_delta_zero(self) -> None:
        """Policy B rejected when mean_delta == 0 (same cost)."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=1000, delta=0),
            PairedDelta(sample_idx=1, seed=2, cost_a=1000, cost_b=1000, delta=0),
        ]
        # mean_delta = 0 → REJECT (no improvement)
        ...

    def test_policy_rejected_when_mean_delta_negative(self) -> None:
        """Policy B rejected when mean_delta < 0 (B is more expensive)."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=800, cost_b=1000, delta=-200),
            PairedDelta(sample_idx=1, seed=2, cost_a=900, cost_b=1100, delta=-200),
        ]
        # mean_delta = -200 < 0 → REJECT (regression)
        ...
```

---

## Implementation Plan

### Step 4.5.1: Create Test Fixtures

Create reusable test fixtures for bootstrap samples with known characteristics.

### Step 4.5.2: Write Paired Comparison Tests

Test that:
- `compute_paired_deltas()` evaluates both policies on same samples
- Delta formula is correct (cost_a - cost_b)
- Mean delta calculation is correct

### Step 4.5.3: Write Policy Acceptance Tests

Test the acceptance logic:
- `mean_delta > 0` → ACCEPT (new policy cheaper)
- `mean_delta <= 0` → REJECT (old policy same or better)

### Step 4.5.4: Verify with Real Evaluator

Create integration tests that use actual `BootstrapPolicyEvaluator` with
simple scenarios to verify end-to-end behavior.

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/tests/experiments/integration/__init__.py` | Package init |
| `api/tests/experiments/integration/test_bootstrap_policy_acceptance.py` | Main tests |

---

## Verification Checklist

### TDD Tests
- [ ] `test_evaluate_samples_returns_results_for_each_sample` passes
- [ ] `test_compute_paired_deltas_uses_same_samples` passes
- [ ] `test_paired_delta_formula_is_cost_a_minus_cost_b` passes
- [ ] `test_mean_delta_positive_means_policy_b_is_cheaper` passes
- [ ] `test_mean_delta_negative_means_policy_a_is_cheaper` passes
- [ ] `test_policy_accepted_when_mean_delta_positive` passes
- [ ] `test_policy_rejected_when_mean_delta_zero` passes
- [ ] `test_policy_rejected_when_mean_delta_negative` passes

### Run Tests
```bash
cd api && .venv/bin/python -m pytest tests/experiments/integration/ -v
```

---

## Notes

These tests are CRITICAL for ensuring statistical validity of policy
comparisons. Without proper paired comparison:
- Variance would be too high
- Acceptance/rejection would be noisy
- Policy "improvements" might be random chance

The paired comparison approach ensures that differences between policies
are real differences, not just random variation in samples.

---

*Phase 4.5 Plan v1.0 - 2025-12-10*
