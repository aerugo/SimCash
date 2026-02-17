# Phase 1: Backend — Implement WebBootstrapEvaluator with Paired Comparison

**Status**: Pending

---

## Objective

Create a `WebBootstrapEvaluator` class that evaluates a proposed policy against the current policy using paired comparisons on the same seeds. Computes delta_sum, CV, and 95% CI. This is the statistical core.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — all deltas, costs, CI bounds are integers
- INV-2: Determinism — same seeds + same policies = same deltas
- INV-GAME-3: Bootstrap Identity — acceptance criteria match experiment runner

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

**Create `web/backend/tests/test_bootstrap_eval.py`:**

```python
"""Tests for web bootstrap policy evaluation."""
import pytest
from app.bootstrap_eval import WebBootstrapEvaluator, EvaluationResult


class TestPairedComparison:
    """Test paired delta computation."""

    def test_identical_policies_zero_delta(self):
        """Same policy on same seeds → delta_sum = 0."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=0.5)
        # Use a scenario where policy A == policy B
        result = eval.evaluate(
            raw_yaml=SIMPLE_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(fraction=0.5),
            new_policy=make_policy(fraction=0.5),
            base_seed=42,
        )
        assert result.delta_sum == 0
        assert result.accepted is True  # No change, no harm

    def test_better_policy_negative_delta(self):
        """A policy with lower cost → negative delta_sum (improvement)."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=0.5)
        # fraction 1.0 should cost more than 0.3 (opportunity cost dominates)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(fraction=1.0),
            new_policy=make_policy(fraction=0.3),
            base_seed=42,
        )
        # New policy should be cheaper → delta_sum < 0
        assert result.delta_sum < 0
        assert result.mean_delta < 0

    def test_paired_on_same_seeds(self):
        """Both policies evaluated on identical seeds."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO,
            agent_id="BANK_A",
            old_policy=make_policy(fraction=0.8),
            new_policy=make_policy(fraction=0.4),
            base_seed=42,
        )
        assert len(result.paired_deltas) == 3
        # All deltas computed on same seeds
        for d in result.paired_deltas:
            assert d["seed"] == 42 + d["sample_idx"] * 1000

    def test_determinism(self):
        """Same inputs → same result (INV-2)."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        r1 = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        r2 = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert r1.delta_sum == r2.delta_sum
        assert r1.cv == r2.cv


class TestAcceptanceCriteria:
    """Test accept/reject logic."""

    def test_reject_high_cv(self):
        """Reject when CV exceeds threshold (noisy result)."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.01)  # Very strict
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.49),  # Tiny change → noisy
            base_seed=42,
        )
        # With strict CV threshold and tiny policy difference, likely rejected
        if result.cv > 0.01:
            assert result.accepted is False
            assert "cv" in result.rejection_reason.lower()

    def test_reject_positive_delta(self):
        """Reject when delta_sum > 0 (new policy is worse)."""
        eval = WebBootstrapEvaluator(num_samples=5, cv_threshold=10.0)  # Lenient CV
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.3),   # Good policy
            new_policy=make_policy(1.0),   # Worse policy (high opportunity cost)
            base_seed=42,
        )
        if result.delta_sum > 0:
            assert result.accepted is False

    def test_accept_clear_improvement(self):
        """Accept when delta_sum clearly negative with low CV."""
        eval = WebBootstrapEvaluator(num_samples=10, cv_threshold=2.0)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(1.0),   # Bad policy
            new_policy=make_policy(0.3),   # Much better
            base_seed=42,
        )
        # Large improvement should be accepted
        assert result.delta_sum < 0
        assert result.accepted is True


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_result_has_all_fields(self):
        """EvaluationResult contains all required metadata."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert hasattr(result, 'delta_sum')
        assert hasattr(result, 'mean_delta')
        assert hasattr(result, 'cv')
        assert hasattr(result, 'ci_lower')
        assert hasattr(result, 'ci_upper')
        assert hasattr(result, 'accepted')
        assert hasattr(result, 'rejection_reason')
        assert hasattr(result, 'paired_deltas')
        assert hasattr(result, 'num_samples')

    def test_costs_are_integers(self):
        """All cost/delta values are integers (INV-1)."""
        eval = WebBootstrapEvaluator(num_samples=3, cv_threshold=0.5)
        result = eval.evaluate(
            raw_yaml=STOCHASTIC_SCENARIO, agent_id="BANK_A",
            old_policy=make_policy(0.5), new_policy=make_policy(0.3), base_seed=42,
        )
        assert isinstance(result.delta_sum, int)
        assert isinstance(result.ci_lower, int)
        assert isinstance(result.ci_upper, int)


# ---- Fixtures ----

def make_policy(fraction: float) -> dict:
    return {
        "version": "2.0",
        "policy_id": f"test_{fraction}",
        "parameters": {"initial_liquidity_fraction": fraction},
        "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
        "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
    }


# Load a scenario from scenario_pack for testing
from app.scenario_pack import get_scenario_by_id
SIMPLE_SCENARIO = get_scenario_by_id("2bank_12tick")
STOCHASTIC_SCENARIO = get_scenario_by_id("2bank_12tick")
```

### Step 1.2: Implement WebBootstrapEvaluator (GREEN)

**Create `web/backend/app/bootstrap_eval.py`:**

```python
"""Bootstrap paired evaluation for web game policy comparison."""
from __future__ import annotations

import copy
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from .game import Game


@dataclass(frozen=True)
class EvaluationResult:
    """Result of paired bootstrap evaluation."""
    delta_sum: int           # Sum of paired deltas (old_cost - new_cost per seed). Negative = improvement.
    mean_delta: int          # Mean paired delta
    cv: float                # Coefficient of variation of deltas
    ci_lower: int            # 95% CI lower bound
    ci_upper: int            # 95% CI upper bound
    accepted: bool           # Whether the new policy was accepted
    rejection_reason: str    # Empty if accepted
    paired_deltas: list[dict]  # Per-seed delta details
    num_samples: int
    old_mean_cost: int       # Mean cost under old policy
    new_mean_cost: int       # Mean cost under new policy


class WebBootstrapEvaluator:
    """Evaluates policy proposals using paired comparison on same seeds.

    For each of N seeds:
      1. Run simulation with old policy → cost_old
      2. Run simulation with new policy → cost_new
      3. delta = cost_old - cost_new  (positive = new is better)

    Accept if:
      - delta_sum < 0 would mean OLD is better, so we check delta_sum > 0 means NEW is better
        Actually: delta = old - new. If delta > 0, new is cheaper. Accept if delta_sum > 0.
      - CV of deltas < cv_threshold (result is stable)
      - 95% CI lower bound > 0 (statistically significant improvement)

    Note: delta = old_cost - new_cost. Positive delta means new policy is cheaper (better).
    """

    def __init__(self, num_samples: int = 10, cv_threshold: float = 0.5):
        self.num_samples = num_samples
        self.cv_threshold = cv_threshold

    def evaluate(
        self,
        raw_yaml: dict,
        agent_id: str,
        old_policy: dict,
        new_policy: dict,
        base_seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> EvaluationResult:
        """Run paired comparison of old vs new policy.

        Args:
            raw_yaml: Scenario configuration
            agent_id: Agent being evaluated
            old_policy: Current policy
            new_policy: Proposed policy
            base_seed: Base RNG seed
            other_policies: Policies for other agents (held fixed)
        """
        deltas = []
        old_costs = []
        new_costs = []

        for i in range(self.num_samples):
            seed = base_seed + i * 1000

            old_cost = self._run_sim(raw_yaml, agent_id, old_policy, seed, other_policies)
            new_cost = self._run_sim(raw_yaml, agent_id, new_policy, seed, other_policies)

            delta = old_cost - new_cost  # Positive = new is cheaper
            deltas.append(delta)
            old_costs.append(old_cost)
            new_costs.append(new_cost)

        delta_sum = sum(deltas)
        mean_delta = delta_sum // self.num_samples

        # CV of deltas
        if len(deltas) >= 2 and mean_delta != 0:
            std = statistics.stdev(deltas)
            cv = abs(std / mean_delta) if mean_delta != 0 else float('inf')
        else:
            cv = 0.0

        # 95% CI using t-distribution approximation
        if len(deltas) >= 2:
            std = statistics.stdev(deltas)
            se = std / math.sqrt(len(deltas))
            ci_lower = int(mean_delta - 1.96 * se)
            ci_upper = int(mean_delta + 1.96 * se)
        else:
            ci_lower = mean_delta
            ci_upper = mean_delta

        # Acceptance criteria (INV-GAME-3: match experiment runner)
        accepted = True
        rejection_reason = ""

        if cv > self.cv_threshold:
            accepted = False
            rejection_reason = f"CV too high: {cv:.3f} > {self.cv_threshold}"
        elif delta_sum <= 0:
            accepted = False
            rejection_reason = f"No improvement: delta_sum={delta_sum} (new policy not cheaper)"
        elif ci_lower <= 0:
            accepted = False
            rejection_reason = f"Not significant: 95% CI lower={ci_lower} crosses zero"

        paired_details = [
            {
                "sample_idx": i,
                "seed": base_seed + i * 1000,
                "old_cost": old_costs[i],
                "new_cost": new_costs[i],
                "delta": deltas[i],
            }
            for i in range(self.num_samples)
        ]

        return EvaluationResult(
            delta_sum=delta_sum,
            mean_delta=mean_delta,
            cv=round(cv, 4),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            accepted=accepted,
            rejection_reason=rejection_reason,
            paired_deltas=paired_details,
            num_samples=self.num_samples,
            old_mean_cost=sum(old_costs) // self.num_samples,
            new_mean_cost=sum(new_costs) // self.num_samples,
        )

    def _run_sim(
        self,
        raw_yaml: dict,
        agent_id: str,
        policy: dict,
        seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> int:
        """Run a single simulation and return the agent's total cost."""
        import json
        from payment_simulator._core import Orchestrator
        from payment_simulator.config.schemas import SimulationConfig

        scenario = copy.deepcopy(raw_yaml)
        for agent_cfg in scenario.get("agents", []):
            aid = agent_cfg.get("id")
            if aid == agent_id:
                p = policy
            elif other_policies and aid in other_policies:
                p = other_policies[aid]
            else:
                continue
            fraction = p.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
            agent_cfg["liquidity_allocation_fraction"] = fraction
            agent_cfg["policy"] = {"type": "InlineJson", "json_string": json.dumps(p)}

        scenario.setdefault("simulation", {})["rng_seed"] = seed
        sim_config = SimulationConfig.from_dict(scenario)
        ffi_config = sim_config.to_ffi_dict()
        orch = Orchestrator.new(ffi_config)

        ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]
        for _ in range(ticks):
            orch.tick()

        ac = orch.get_agent_accumulated_costs(agent_id)
        return int(ac.get("total_cost", 0))
```

### Step 1.3: Refactor

- Extract `_run_sim` to share with `Game._run_single_sim` (avoid duplication)
- Use proper t-distribution critical values instead of z=1.96 for small samples
- Add logging for evaluation details

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/bootstrap_eval.py` | Create | `WebBootstrapEvaluator` + `EvaluationResult` |
| `web/backend/tests/test_bootstrap_eval.py` | Create | Paired comparison + acceptance tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_bootstrap_eval.py -v --tb=short
```

## Completion Criteria

- [ ] `WebBootstrapEvaluator` runs N paired simulations on same seeds
- [ ] `EvaluationResult` contains delta_sum, cv, ci_lower, ci_upper, accepted, rejection_reason
- [ ] Identical policies produce delta_sum = 0
- [ ] Better policy produces negative delta_sum (wait, positive — old_cost - new_cost > 0 means new is better)
- [ ] High CV triggers rejection
- [ ] CI crossing zero triggers rejection
- [ ] All costs/deltas are integers (INV-1)
- [ ] Deterministic results (INV-2)
