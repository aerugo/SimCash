# Phase 3: Implement Deterministic-Temporal

**Status**: Pending
**Started**:

---

## Objective

Implement the deterministic-temporal evaluation mode, which compares cost across iterations rather than comparing old vs new policy within the same iteration.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism is Sacred - Temporal mode must be reproducible with same seed
- **INV-9**: Policy Evaluation Identity - Cost computation must be consistent

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Create `api/tests/experiments/runner/test_temporal_evaluation.py`:

**Test Cases**:
1. `test_first_iteration_always_accepts` - No previous cost to compare, always accept
2. `test_cost_decrease_accepts_policy` - If cost_N < cost_{N-1}, accept
3. `test_cost_increase_reverts_policy` - If cost_N > cost_{N-1}, revert to previous policy
4. `test_cost_equal_keeps_policy` - If cost_N == cost_{N-1}, keep current (no improvement)
5. `test_previous_cost_stored_for_next_iteration` - Verify cost is tracked
6. `test_temporal_skips_paired_evaluation` - `_evaluate_policy_pair` not called in temporal mode

```python
"""Tests for deterministic-temporal evaluation mode.

Temporal mode compares cost across iterations rather than
old vs new policy within the same iteration.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.experiments.config.experiment_config import (
    ExperimentConfig,
    EvaluationConfig,
    ConvergenceConfig,
)
from payment_simulator.llm.config import LLMConfig


class TestTemporalEvaluation:
    """Tests for deterministic-temporal evaluation mode."""

    def test_first_iteration_always_accepts(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """First iteration has no previous cost, should always accept."""
        loop = self._create_loop(temporal_config)

        # First iteration
        loop._current_iteration = 1
        loop._previous_iteration_costs = {}  # No previous

        # Should accept regardless of cost (no baseline)
        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1000,
        )

        assert accepted is True

    def test_cost_decrease_accepts_policy(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """If current cost < previous cost, accept the policy."""
        loop = self._create_loop(temporal_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=800,  # Less than 1000
        )

        assert accepted is True

    def test_cost_increase_reverts_policy(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """If current cost > previous cost, revert to previous policy."""
        loop = self._create_loop(temporal_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1200,  # Greater than 1000
        )

        assert accepted is False

    def test_cost_equal_keeps_policy(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """If current cost == previous cost, keep current (no improvement needed)."""
        loop = self._create_loop(temporal_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        # Equal cost - could go either way, but we'll treat as "no improvement"
        # so don't revert (keep current to allow exploration)
        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1000,
        )

        # Design decision: equal cost = keep current = accepted
        assert accepted is True

    def test_previous_cost_stored_for_next_iteration(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """After evaluation, current cost should be stored for next iteration."""
        loop = self._create_loop(temporal_config)

        loop._current_iteration = 1
        loop._previous_iteration_costs = {}

        # Evaluate and accept
        loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1000,
        )

        # Cost should be stored
        assert loop._previous_iteration_costs.get("BANK_A") == 1000

    def test_temporal_mode_uses_evaluate_temporal_not_pair(
        self, temporal_config: ExperimentConfig
    ) -> None:
        """In temporal mode, optimization should use temporal evaluation, not paired."""
        loop = self._create_loop(temporal_config)

        # Mock to track which evaluation method is called
        pair_called = False
        temporal_called = False

        original_pair = loop._evaluate_policy_pair
        original_temporal = loop._evaluate_temporal_acceptance

        def mock_pair(*args, **kwargs):
            nonlocal pair_called
            pair_called = True
            return original_pair(*args, **kwargs)

        def mock_temporal(*args, **kwargs):
            nonlocal temporal_called
            temporal_called = True
            return original_temporal(*args, **kwargs)

        # In temporal mode, _evaluate_policy_pair should not be called
        # during the normal optimization flow

        # ... test implementation ...

    def _create_loop(self, config: ExperimentConfig) -> OptimizationLoop:
        """Create OptimizationLoop for testing."""
        # ... setup code ...
        pass


@pytest.fixture
def temporal_config() -> ExperimentConfig:
    """Config for deterministic-temporal mode testing."""
    return ExperimentConfig(
        name="test_temporal",
        description="Test temporal evaluation",
        scenario_path=Path("test.yaml"),
        evaluation=EvaluationConfig(ticks=2, mode="deterministic-temporal"),
        convergence=ConvergenceConfig(max_iterations=5),
        llm=LLMConfig(model="test:model"),
        optimized_agents=("BANK_A",),
        constraints_module="",
        output=None,
        master_seed=42,
    )
```

### Step 3.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/experiments/runner/optimization.py`:

**Change 1**: Add tracking for previous iteration costs:

```python
class OptimizationLoop:
    def __init__(self, ...):
        # ... existing init ...
        self._previous_iteration_costs: dict[str, int] = {}
```

**Change 2**: Add temporal evaluation method:

```python
def _evaluate_temporal_acceptance(
    self,
    agent_id: str,
    current_cost: int,
) -> bool:
    """Evaluate policy acceptance using temporal comparison.

    Compares current iteration cost to previous iteration cost.
    First iteration always accepts (no baseline).

    Args:
        agent_id: Agent being evaluated.
        current_cost: Cost from current iteration.

    Returns:
        True if policy should be accepted, False to revert.
    """
    previous_cost = self._previous_iteration_costs.get(agent_id)

    # First iteration: always accept (no baseline)
    if previous_cost is None:
        self._previous_iteration_costs[agent_id] = current_cost
        return True

    # Compare: accept if cost decreased or stayed same
    accepted = current_cost <= previous_cost

    # Update stored cost for next iteration
    if accepted:
        self._previous_iteration_costs[agent_id] = current_cost
    # If rejected, keep previous cost (policy will be reverted)

    return accepted
```

**Change 3**: Integrate into optimization loop:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    """Optimize policy for a single agent."""
    # ... existing LLM call to generate new_policy ...

    # Evaluate based on mode
    if self._config.evaluation.is_deterministic_temporal:
        # Temporal: compare current cost to previous iteration
        accepted = self._evaluate_temporal_acceptance(agent_id, current_cost)
        if not accepted:
            # Revert to previous policy
            self._policies[agent_id] = self._previous_policies[agent_id]
    else:
        # Pairwise or bootstrap: use paired evaluation
        eval_result = self._evaluate_policy_pair(agent_id, old_policy, new_policy)
        accepted = eval_result.delta_sum > 0
        # ... rest of existing logic ...
```

### Step 3.3: Refactor

- Ensure `_previous_policies` is tracked for revert capability
- Add logging for temporal acceptance decisions
- Add docstrings and type hints

---

## Implementation Details

### Temporal Flow

```
Iteration 1:
  1. Run simulation with current_policy → cost_1
  2. Store cost_1 in _previous_iteration_costs
  3. Accept (first iteration, no baseline)
  4. LLM generates new_policy for next iteration
  5. Update _policies[agent_id] = new_policy

Iteration 2:
  1. Run simulation with new_policy → cost_2
  2. Compare: cost_2 vs cost_1
  3. If cost_2 <= cost_1:
       - Accept: store cost_2
       - LLM generates new_policy
  4. If cost_2 > cost_1:
       - Reject: revert _policies[agent_id] = previous_policy
       - Keep cost_1 as baseline
       - LLM generates different new_policy
```

### Policy Revert Logic

Need to track `_previous_policies: dict[str, dict]` to enable revert:

```python
# Before optimization
self._previous_policies[agent_id] = copy.deepcopy(self._policies[agent_id])

# If rejected
self._policies[agent_id] = self._previous_policies[agent_id]
```

### Edge Cases

- **Agent not in previous_costs**: Treat as first iteration
- **Multi-agent**: Each agent compared independently
- **Cost exactly equal**: Accept (allows exploration without penalty)

---

## Files

| File | Action |
|------|--------|
| `api/tests/experiments/runner/test_temporal_evaluation.py` | CREATE |
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_temporal_evaluation.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] First iteration always accepts
- [ ] Cost decrease → accept
- [ ] Cost increase → revert to previous policy
- [ ] Cost equal → accept (keep current)
- [ ] Previous cost stored correctly
- [ ] Policy revert works correctly
- [ ] Type check passes
- [ ] Lint passes
- [ ] INV-2 verified (deterministic with same seed)
