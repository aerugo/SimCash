# Phase 1: Fix Seed Inconsistency

**Status**: Pending
**Started**:

---

## Objective

Fix the bug where `_evaluate_policies()` uses `master_seed` but `_evaluate_policy_pair()` uses `get_iteration_seed()` in deterministic mode. Both should use the iteration-varying seed for consistency.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism is Sacred - Using iteration-varying seed is still deterministic (same iteration + same agent = same seed)
- **INV-9**: Policy Evaluation Identity - The seed used for cost display must equal the seed used for acceptance decision

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/experiments/runner/test_seed_consistency.py`:

**Test Cases**:
1. `test_evaluate_policies_uses_iteration_seed_in_deterministic_mode` - Verify `_evaluate_policies` uses iteration seed, not master seed
2. `test_seed_matches_between_evaluate_policies_and_evaluate_policy_pair` - Verify same seed is used in both methods
3. `test_displayed_cost_matches_acceptance_cost` - End-to-end verification that cost shown equals cost used for decision
4. `test_different_iterations_use_different_seeds` - Verify iteration 0 and iteration 1 use different seeds

```python
"""Tests for seed consistency in deterministic evaluation mode.

Verifies INV-9: Policy Evaluation Identity - the seed used for cost display
must equal the seed used for acceptance decision.
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
    OutputConfig,
)
from payment_simulator.llm.config import LLMConfig


class TestSeedConsistency:
    """Tests for seed consistency between _evaluate_policies and _evaluate_policy_pair."""

    def test_evaluate_policies_uses_iteration_seed_in_deterministic_mode(
        self, minimal_deterministic_config: ExperimentConfig
    ) -> None:
        """_evaluate_policies should use iteration seed, not master seed.

        Previously, _evaluate_policies used master_seed directly, which caused
        inconsistency with _evaluate_policy_pair which used iteration seed.
        """
        # Setup
        loop = self._create_loop(minimal_deterministic_config)
        loop._current_iteration = 1  # Non-zero to show iteration matters

        # Track which seed is used
        seeds_used: list[int] = []
        original_run_sim = loop._run_simulation_with_events

        def tracking_run_sim(seed: int, sample_idx: int) -> MagicMock:
            seeds_used.append(seed)
            return original_run_sim(seed, sample_idx)

        with patch.object(loop, '_run_simulation_with_events', tracking_run_sim):
            loop._evaluate_policies()

        # The seed should NOT be master_seed (42)
        # It should be derived from iteration and agent
        expected_seed = loop._seed_matrix.get_iteration_seed(0, loop.optimized_agents[0])
        assert seeds_used[0] == expected_seed
        assert seeds_used[0] != minimal_deterministic_config.master_seed

    def test_seed_matches_between_evaluate_policies_and_evaluate_policy_pair(
        self, minimal_deterministic_config: ExperimentConfig
    ) -> None:
        """The seed used in _evaluate_policies must match _evaluate_policy_pair.

        This is critical for INV-9: the cost displayed to user/LLM must be
        computed with the same seed as the cost used for acceptance decision.
        """
        loop = self._create_loop(minimal_deterministic_config)
        loop._current_iteration = 1

        # Track seeds from both methods
        evaluate_policies_seed: int | None = None
        evaluate_pair_seed: int | None = None

        # ... implementation to capture seeds from both methods ...

        assert evaluate_policies_seed == evaluate_pair_seed

    def test_different_iterations_use_different_seeds(
        self, minimal_deterministic_config: ExperimentConfig
    ) -> None:
        """Different iterations should use different seeds for diversity."""
        loop = self._create_loop(minimal_deterministic_config)
        agent_id = loop.optimized_agents[0]

        seed_iter_0 = loop._seed_matrix.get_iteration_seed(0, agent_id)
        seed_iter_1 = loop._seed_matrix.get_iteration_seed(1, agent_id)

        assert seed_iter_0 != seed_iter_1

    def _create_loop(self, config: ExperimentConfig) -> OptimizationLoop:
        """Create OptimizationLoop for testing."""
        # ... setup code ...
        pass


@pytest.fixture
def minimal_deterministic_config() -> ExperimentConfig:
    """Minimal config for deterministic mode testing."""
    return ExperimentConfig(
        name="test_seed_consistency",
        description="Test seed consistency",
        scenario_path=Path("test.yaml"),
        evaluation=EvaluationConfig(ticks=2, mode="deterministic", num_samples=1),
        convergence=ConvergenceConfig(max_iterations=5),
        llm=LLMConfig(model="test:model"),
        optimized_agents=("BANK_A",),
        constraints_module="",
        output=None,
        master_seed=42,
    )
```

### Step 1.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/experiments/runner/optimization.py`:

**Change 1**: In `_evaluate_policies()`, replace master_seed with iteration seed:

```python
# BEFORE (line 1394-1398):
if eval_mode == "deterministic" or num_samples <= 1:
    # Single simulation - deterministic mode
    # Use constant seed for reproducibility (same seed each iteration)
    # This ensures policy changes are the ONLY variable affecting cost
    seed = self._config.master_seed

# AFTER:
if eval_mode == "deterministic" or num_samples <= 1:
    # Single simulation - deterministic mode
    # Use iteration seed for consistency with _evaluate_policy_pair
    # (INV-9: Policy Evaluation Identity)
    iteration_idx = self._current_iteration - 1  # 0-indexed
    # Use first optimized agent for seed derivation in single-agent case
    # For multi-agent, this provides consistent baseline
    agent_id = self.optimized_agents[0]
    seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)
```

### Step 1.3: Refactor

- Update the comment to explain WHY we use iteration seed
- Ensure type annotations are complete
- Run mypy and ruff

---

## Implementation Details

### Why Iteration Seed Instead of Master Seed?

The original comment claimed using master_seed "ensures policy changes are the ONLY variable affecting cost". This is misleading because:

1. In deterministic mode, the same seed always produces identical results
2. The real issue is CONSISTENCY between methods
3. Using master_seed in one place and iteration_seed in another causes displayed cost ≠ acceptance cost

### Edge Cases to Handle

- **First iteration (iteration_idx = 0)**: Should work normally
- **Multi-agent scenarios**: Use consistent approach for seed derivation
- **Bootstrap mode**: Should be unaffected (uses different code path)

---

## Files

| File | Action |
|------|--------|
| `api/tests/experiments/runner/test_seed_consistency.py` | CREATE |
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/runner/test_seed_consistency.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] `_evaluate_policies()` uses iteration seed in deterministic mode
- [ ] Seed matches between `_evaluate_policies()` and `_evaluate_policy_pair()`
- [ ] Type check passes
- [ ] Lint passes
- [ ] Existing tests still pass
- [ ] INV-9 verified by tests
