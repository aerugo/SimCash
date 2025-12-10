# Phase 0: Fix Bootstrap Paired Comparison Bug

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Low (contained change)
**Breaking Changes:** None (bug fix)

---

## Problem Analysis

### Current Behavior (BROKEN)

The runner.py evaluates policies with **different bootstrap samples**, breaking statistical validity:

```
Iteration N:
  1. _evaluate_policies() called
     - Generates samples S1 (new RNG state)
     - Evaluates OLD policy on S1 → cost_old

  2. LLM proposes new_policy

  3. _evaluate_policies() called AGAIN for new policy
     - Generates samples S2 (DIFFERENT from S1!)
     - Evaluates NEW policy on S2 → cost_new

  4. Accept if cost_new < cost_old
     ❌ BROKEN: Comparing apples to oranges!
```

**Evidence from runner.py (lines 419-468):**
```python
# Line 430-431: Re-evaluate creates NEW samples
_eval_total, eval_per_agent, _, _ = await self._evaluate_policies(
    iteration, capture_verbose=False
)
```

The `_evaluate_policies()` method (lines 704-820) generates NEW samples on every call:
```python
# Line 748: Generates NEW samples each time
samples = self._bootstrap_sampler.generate_samples(
    agent_id=agent_id,
    n_samples=num_samples,
    ...
)
```

### Key Discovery

The `compute_paired_deltas()` method **EXISTS** in `evaluator.py` (lines 169-202) but is **NEVER CALLED**:

```python
def compute_paired_deltas(
    self,
    samples: list[BootstrapSample],
    policy_a: dict[str, Any],
    policy_b: dict[str, Any],
) -> list[PairedDelta]:
    """Compute paired deltas between two policies.

    Evaluates both policies on each sample and computes the
    difference. Paired comparison reduces variance.
    """
    results_a = self.evaluate_samples(samples, policy_a)
    results_b = self.evaluate_samples(samples, policy_b)
    # ...
```

### Expected Behavior (CORRECT)

```
Iteration N:
  1. Generate samples S ONCE for this iteration

  2. Evaluate OLD policy on S → old_costs[]

  3. LLM proposes new_policy

  4. Evaluate NEW policy on SAME S → new_costs[]

  5. Compute paired delta: delta_i = new_cost_i - old_cost_i

  6. Accept if mean(delta) < 0
     ✅ CORRECT: Same samples, valid comparison!
```

### Statistical Impact

Without paired comparison:
- High variance from different samples masks real improvements
- Can accept worse policies due to lucky samples
- Can reject better policies due to unlucky samples
- Violates the paper's methodology (Castro et al.)

---

## TDD Test Specifications

### Test File: `api/tests/experiments/castro/test_bootstrap_paired_comparison.py`

```python
"""Tests for paired comparison bug fix.

These tests verify that the runner uses the SAME bootstrap samples
when comparing old and new policies, as required for valid
paired statistical comparison.

References:
- Castro et al. methodology requires paired comparison
- BootstrapPolicyEvaluator.compute_paired_deltas() should be used
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from payment_simulator.ai_cash_mgmt.bootstrap import (
    BootstrapSample,
    BootstrapPolicyEvaluator,
    PairedDelta,
)


class TestPairedComparisonInvariant:
    """Tests that paired comparison uses same samples."""

    def test_same_samples_used_for_policy_comparison(self) -> None:
        """Same bootstrap samples MUST be used for both policies.

        This is the critical test: when comparing old vs new policy,
        both must be evaluated on identical samples.
        """
        # Arrange: Create evaluator with tracking
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Create deterministic sample
        sample = create_test_sample(sample_idx=0, seed=42)
        samples = [sample]

        old_policy = {"type": "Fifo"}
        new_policy = {"type": "LiquidityAware", "threshold": 5.0}

        # Act: Compute paired deltas (which evaluates both policies)
        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a=old_policy,
            policy_b=new_policy,
        )

        # Assert: Same sample indices
        assert len(deltas) == len(samples)
        for delta, sample in zip(deltas, samples, strict=True):
            assert delta.sample_idx == sample.sample_idx
            assert delta.seed == sample.seed

    def test_acceptance_based_on_paired_delta_not_absolute(self) -> None:
        """Policy acceptance must use paired delta, not absolute costs.

        Scenario:
        - Sample 1: old=1000, new=900 → delta=-100 (improvement)
        - Sample 2: old=1200, new=1100 → delta=-100 (improvement)
        - Sample 3: old=800, new=850 → delta=+50 (regression)

        Mean delta = (-100 + -100 + 50) / 3 = -50

        Should accept because mean delta < 0.
        """
        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=1000, cost_b=900, delta=-100),
            PairedDelta(sample_idx=1, seed=101, cost_a=1200, cost_b=1100, delta=-100),
            PairedDelta(sample_idx=2, seed=102, cost_a=800, cost_b=850, delta=50),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta is negative → should accept
        assert mean_delta == pytest.approx(-50.0)
        assert mean_delta < 0  # Accept criterion


class TestRunnerUsesPairedComparison:
    """Tests that ExperimentRunner uses compute_paired_deltas."""

    @pytest.mark.asyncio
    async def test_runner_stores_samples_for_reuse(self) -> None:
        """Runner must store samples from initial evaluation for reuse."""
        # This test verifies the runner returns samples from _evaluate_policies
        # The actual implementation will need to modify the return signature
        pass  # Implemented when runner is modified

    @pytest.mark.asyncio
    async def test_runner_calls_compute_paired_deltas(self) -> None:
        """Runner must call compute_paired_deltas when comparing policies.

        Verifies that when a new policy is proposed, the runner
        evaluates both old and new on the SAME samples using
        compute_paired_deltas().
        """
        # This test uses mocking to verify the method is called
        pass  # Implemented when runner is modified


# Helper function
def create_test_sample(sample_idx: int, seed: int) -> BootstrapSample:
    """Create a minimal bootstrap sample for testing."""
    from payment_simulator.ai_cash_mgmt.bootstrap.models import (
        BootstrapSample,
        RemappedTransaction,
    )

    tx = RemappedTransaction(
        tx_id=f"tx-{sample_idx}",
        sender_id="TARGET",
        receiver_id="SINK",
        amount=100_00,  # $100.00 in cents
        priority=5,
        arrival_tick=0,
        deadline_tick=10,
        settlement_tick=5,
    )

    return BootstrapSample(
        agent_id="TARGET",
        sample_idx=sample_idx,
        seed=seed,
        outgoing_txns=(tx,),
        incoming_settlements=(),
        total_ticks=12,
    )
```

---

## Implementation Plan

### Step 1: Modify `_evaluate_policies()` Return Signature

**File:** `experiments/castro/castro/runner.py`

**Change:** Return the generated samples along with evaluation results.

**Before (line 704-708):**
```python
async def _evaluate_policies(
    self,
    iteration: int,
    capture_verbose: bool = True,
) -> tuple[int, dict[str, int], MonteCarloContextBuilder, list[MonteCarloSeedResult]]:
```

**After:**
```python
async def _evaluate_policies(
    self,
    iteration: int,
    capture_verbose: bool = True,
) -> tuple[
    int,  # total_cost
    dict[str, int],  # per_agent_costs
    MonteCarloContextBuilder,  # context_builder
    list[MonteCarloSeedResult],  # seed_results
    dict[str, list[BootstrapSample]],  # NEW: samples per agent
]:
```

### Step 2: Store Samples in `_evaluate_policies()`

**Before (lines 748-765):**
```python
# Generate bootstrap samples
samples = self._bootstrap_sampler.generate_samples(...)

# Evaluate on each sample
agent_costs: list[int] = []
for sample in samples:
    eval_result = self._bootstrap_evaluator.evaluate_sample(...)
    agent_costs.append(eval_result.total_cost)
```

**After:**
```python
# Generate bootstrap samples ONCE
samples = self._bootstrap_sampler.generate_samples(...)
all_samples[agent_id] = samples  # Store for reuse

# Evaluate on each sample
agent_costs: list[int] = []
for sample in samples:
    eval_result = self._bootstrap_evaluator.evaluate_sample(...)
    agent_costs.append(eval_result.total_cost)
```

### Step 3: Add `_evaluate_policy_with_samples()` Method

New method that evaluates on provided samples (no new generation):

```python
def _evaluate_policy_with_samples(
    self,
    agent_id: str,
    policy: dict[str, Any],
    samples: list[BootstrapSample],
) -> int:
    """Evaluate a policy using pre-generated samples.

    Used for paired comparison - evaluates new policy on SAME
    samples used for old policy evaluation.

    Args:
        agent_id: Agent being evaluated.
        policy: Policy to evaluate.
        samples: Pre-generated bootstrap samples.

    Returns:
        Mean cost across samples.
    """
    costs = [
        self._bootstrap_evaluator.evaluate_sample(sample, policy).total_cost
        for sample in samples
    ]
    return sum(costs) // len(costs) if costs else 0
```

### Step 4: Use Paired Comparison in Policy Acceptance

**Before (lines 419-468):**
```python
if result.was_accepted and result.new_policy:
    # Temporarily apply new policy and evaluate
    old_policy = self._policies[agent_id]
    self._policies[agent_id] = result.new_policy

    # Re-evaluate without verbose capture (performance optimization)
    # ❌ BUG: This generates NEW samples!
    _eval_total, eval_per_agent, _, _ = await self._evaluate_policies(
        iteration, capture_verbose=False
    )
    new_cost = eval_per_agent.get(agent_id, result.old_cost)

    # Only accept if cost improved
    if new_cost < result.old_cost:
        actually_accepted = True
```

**After:**
```python
if result.was_accepted and result.new_policy:
    old_policy = self._policies[agent_id]

    # ✅ FIXED: Use compute_paired_deltas with SAME samples
    agent_samples = iteration_samples.get(agent_id, [])
    if agent_samples:
        deltas = self._bootstrap_evaluator.compute_paired_deltas(
            samples=agent_samples,
            policy_a=old_policy,
            policy_b=result.new_policy,
        )
        mean_delta = self._bootstrap_evaluator.compute_mean_delta(deltas)

        # Accept if new policy is better (delta < 0 means B costs less than A)
        if mean_delta > 0:  # policy_a - policy_b > 0 means B is cheaper
            actually_accepted = True
            self._policies[agent_id] = result.new_policy

            # Calculate new cost for logging (use mean from policy_b results)
            new_cost = sum(d.cost_b for d in deltas) // len(deltas)
            console.print(
                f"    [green]Policy improved by mean delta: "
                f"${mean_delta/100:.2f}[/green]"
            )
        else:
            new_cost = sum(d.cost_a for d in deltas) // len(deltas)
            console.print(
                f"    [yellow]Rejected: mean delta ${mean_delta/100:.2f} "
                f"(not improved)[/yellow]"
            )
```

### Step 5: Update Verbose Logging

Add verbose logging for paired comparison:

```python
# In verbose_logging.py, add new logging method
def log_paired_comparison(
    self,
    agent_id: str,
    deltas: list[PairedDelta],
    mean_delta: float,
    accepted: bool,
) -> None:
    """Log paired comparison results."""
    if not self._config.monte_carlo:
        return

    self._console.print(f"\n[dim]Paired Comparison for {agent_id}:[/dim]")
    self._console.print(f"  Mean delta: ${mean_delta/100:.2f}")
    self._console.print(f"  Decision: {'Accepted' if accepted else 'Rejected'}")

    # Show individual samples
    for delta in deltas[:5]:  # Limit display
        sign = "+" if delta.delta > 0 else ""
        self._console.print(
            f"  Sample {delta.sample_idx}: "
            f"old=${delta.cost_a/100:.2f} new=${delta.cost_b/100:.2f} "
            f"delta={sign}${delta.delta/100:.2f}"
        )
```

---

## Files to Modify

| File | Change |
|------|--------|
| `experiments/castro/castro/runner.py` | Store samples, use `compute_paired_deltas()` |
| `experiments/castro/castro/verbose_logging.py` | Add `log_paired_comparison()` |

## Files to Create

| File | Purpose |
|------|---------|
| `api/tests/experiments/castro/test_bootstrap_paired_comparison.py` | TDD tests |

---

## Verification Checklist

### Unit Tests
- [ ] `test_same_samples_used_for_policy_comparison` passes
- [ ] `test_acceptance_based_on_paired_delta_not_absolute` passes
- [ ] `test_runner_stores_samples_for_reuse` passes
- [ ] `test_runner_calls_compute_paired_deltas` passes

### Integration Tests
- [ ] `pytest experiments/castro/tests/ -v` passes
- [ ] `pytest api/tests/ -v` passes

### Manual Verification
```bash
# Run with verbose Monte Carlo to see paired comparison
castro run exp1 --verbose-monte-carlo

# Expected output includes:
# Paired Comparison for BANK_A:
#   Mean delta: $-X.XX
#   Decision: Accepted/Rejected
#   Sample 0: old=$XXX new=$YYY delta=$ZZZ
```

### Type Checking
```bash
cd api && .venv/bin/python -m mypy payment_simulator/
```

---

## Notes

### Why This Bug Matters

1. **Statistical Validity**: Paired comparison is fundamental to reducing variance in Monte Carlo estimation. Without it, we're adding noise to our acceptance decisions.

2. **Paper Compliance**: The Castro methodology explicitly requires paired comparison for valid policy updates.

3. **Practical Impact**: The optimization loop may be:
   - Accepting worse policies (false positives)
   - Rejecting better policies (false negatives)
   - Taking longer to converge due to noise

### Design Decision: Where to Store Samples

**Option A**: Store in runner state (`self._current_samples`)
- Pro: Simple implementation
- Con: Mutable state management complexity

**Option B**: Return from `_evaluate_policies()` ← **CHOSEN**
- Pro: Explicit data flow, immutable
- Con: Changes method signature

Option B is preferred because it makes the data flow explicit and avoids hidden state dependencies.

---

*Phase 0 Plan v1.0 - 2025-12-10*
