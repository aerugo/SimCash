# Phase 3: Wire Convergence Detection

**Status**: Pending
**Started**: -

---

## Objective

Integrate the PolicyStabilityTracker into the main optimization loop to detect convergence when ALL agents have been stable for `stability_window` iterations.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism - Convergence detection must be deterministic (same inputs = same iteration count)

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Create `api/tests/experiments/e2e/test_multiagent_convergence.py`:

**Test Cases**:

1. `test_convergence_on_all_agents_stable` - Converges when all stable for window
2. `test_no_convergence_one_agent_changing` - Continues if any agent changing
3. `test_convergence_reason_logged` - "policy_stability" recorded as reason
4. `test_max_iterations_fallback` - Stops at max even if not converged
5. `test_convergence_uses_stability_window` - Uses config's stability_window value

```python
"""E2E tests for multi-agent convergence detection."""

from __future__ import annotations

import pytest

from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner.optimization import OptimizationRunner


class TestMultiAgentConvergence:
    """E2E tests for multi-agent convergence."""

    @pytest.fixture
    def two_agent_config(self, tmp_path) -> ExperimentConfig:
        """Create config for 2-agent experiment."""
        # Create minimal experiment config with:
        # - 2 optimized agents
        # - deterministic-temporal mode
        # - stability_window = 5
        # - max_iterations = 20
        ...

    @pytest.mark.asyncio
    async def test_convergence_on_all_agents_stable(
        self, two_agent_config, mock_llm_stable_responses
    ) -> None:
        """Experiment converges when both agents stable for window iterations.

        Setup: Mock LLM returns same fraction for both agents after iteration 3.
        Expected: Convergence at iteration 8 (5 stable iterations after 3).
        """
        runner = OptimizationRunner(two_agent_config)

        # Mock LLM to return stable fractions after iteration 3
        # BANK_A: 0.5, 0.3, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4 (stable from iter 3)
        # BANK_B: 0.5, 0.6, 0.35, 0.35, 0.35, 0.35, 0.35, 0.35 (stable from iter 3)

        result = await runner.run()

        # Should converge at iteration 8 (iterations 3-7 are stable)
        assert result.converged is True
        assert result.convergence_reason == "policy_stability"
        assert result.total_iterations == 8

    @pytest.mark.asyncio
    async def test_no_convergence_one_agent_changing(
        self, two_agent_config, mock_llm_one_unstable
    ) -> None:
        """Continues optimization if any agent is still changing.

        Setup: BANK_A stable, BANK_B keeps changing.
        Expected: Runs to max_iterations.
        """
        runner = OptimizationRunner(two_agent_config)

        # Mock: BANK_A stable from iteration 2
        #       BANK_B changes every iteration

        result = await runner.run()

        assert result.converged is True  # Hit max iterations
        assert result.convergence_reason == "max_iterations"
        assert result.total_iterations == 20  # max_iterations

    @pytest.mark.asyncio
    async def test_convergence_reason_logged(
        self, two_agent_config, mock_llm_stable_responses
    ) -> None:
        """Convergence reason is correctly recorded."""
        runner = OptimizationRunner(two_agent_config)

        result = await runner.run()

        # Verify in persisted results
        assert "policy_stability" in result.convergence_reason

    @pytest.mark.asyncio
    async def test_max_iterations_fallback(
        self, two_agent_config, mock_llm_always_changing
    ) -> None:
        """Stops at max_iterations even if no convergence."""
        runner = OptimizationRunner(two_agent_config)

        # Mock LLM to always change fraction
        result = await runner.run()

        assert result.total_iterations == 20
        assert result.convergence_reason == "max_iterations"

    @pytest.mark.asyncio
    async def test_convergence_uses_stability_window(
        self, tmp_path
    ) -> None:
        """Uses convergence.stability_window from config."""
        # Create config with stability_window = 3 (shorter than default 5)
        config = create_config_with_stability_window(tmp_path, window=3)
        runner = OptimizationRunner(config)

        # Mock LLM stable from iteration 2
        # Should converge at iteration 5 (iterations 2,3,4 are stable = 3 iterations)

        result = await runner.run()

        assert result.total_iterations == 5
```

### Step 3.2: Implement Convergence Check (GREEN)

Modify the main optimization loop in `optimization.py`:

```python
async def run(self) -> ExperimentResult:
    """Run the optimization loop.

    Returns:
        ExperimentResult with final policies, costs, and convergence info.
    """
    # ... initialization code ...

    for iteration in range(1, max_iterations + 1):
        self._current_iteration = iteration

        # Evaluate current policies
        total_cost, per_agent_costs = await self._evaluate_policies()

        # Optimize each agent
        for agent_id in self._optimized_agents:
            if self._config.evaluation.is_deterministic_temporal:
                await self._optimize_agent_temporal(agent_id, per_agent_costs[agent_id])
            else:
                await self._optimize_agent(agent_id, per_agent_costs[agent_id])

        # Check multi-agent convergence (temporal mode only)
        if self._config.evaluation.is_deterministic_temporal:
            if self._check_multiagent_convergence():
                self._convergence_reason = "policy_stability"
                break

        # ... existing convergence checks for other modes ...

    # Build and return result
    ...


def _check_multiagent_convergence(self) -> bool:
    """Check if all agents have converged based on policy stability.

    Uses the stability_window from convergence config to determine
    how many consecutive iterations of unchanged initial_liquidity_fraction
    are required for convergence.

    Returns:
        True if all optimized agents are stable for stability_window iterations.
    """
    stability_window = self._config.convergence.stability_window

    return self._stability_tracker.all_agents_stable(
        agents=list(self._optimized_agents),
        window=stability_window,
    )
```

### Step 3.3: Add Convergence Logging

```python
def _log_convergence(self) -> None:
    """Log convergence information."""
    if self._verbose_logger and self._verbose_config.summary:
        if self._convergence_reason == "policy_stability":
            self._verbose_logger.log_info(
                f"Converged: All agents stable for "
                f"{self._config.convergence.stability_window} iterations"
            )

            # Log final fractions
            for agent_id in self._optimized_agents:
                fraction = self._stability_tracker.get_last_fraction(agent_id)
                self._verbose_logger.log_info(
                    f"  {agent_id}: initial_liquidity_fraction = {fraction}"
                )
```

---

## Implementation Details

### Convergence Check Placement

The convergence check happens **after** all agents have been optimized for an iteration:

```
Iteration N:
  1. Evaluate all policies → costs
  2. For each agent: Generate new policy via LLM
  3. For each agent: Track fraction in stability tracker
  4. Check: all_agents_stable(window=5)?
     - Yes → converged, break
     - No → continue to iteration N+1
```

This ensures we check stability only after all agents have had a chance to respond to each other's changes.

### Interaction with Existing Convergence Detection

The existing `ConvergenceDetector` class is cost-based. In temporal mode:
- We **do not** use the cost-based convergence
- We **only** use the policy stability convergence
- Max iterations is still enforced as a fallback

### Logging and Persistence

When convergence happens:
1. Log to console (verbose mode)
2. Record in experiment result
3. Save final fractions for each agent

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |
| `api/tests/experiments/e2e/test_multiagent_convergence.py` | CREATE |

---

## Verification

```bash
# Run E2E tests
cd api
.venv/bin/python -m pytest tests/experiments/e2e/test_multiagent_convergence.py -v

# Run full test suite to verify no regression
.venv/bin/python -m pytest tests/experiments/ -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] All 5 E2E test cases pass
- [ ] Convergence detected when all agents stable for window iterations
- [ ] Max iterations enforced as fallback
- [ ] Convergence reason logged correctly ("policy_stability")
- [ ] Final fractions logged for each agent
- [ ] No regression in existing tests
- [ ] INV-2 verified (same seed = same iteration count)
