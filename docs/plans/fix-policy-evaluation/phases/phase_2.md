# Phase 2: Modify `_optimize_agent_temporal()`

**Status**: Pending
**Started**: -

---

## Objective

Modify the temporal optimization method to always accept LLM's policy (no cost-based rejection) and integrate the PolicyStabilityTracker to track `initial_liquidity_fraction` for each agent.

---

## Invariants Enforced in This Phase

- **INV-9**: Policy Evaluation Identity - Policy parameter extraction must be consistent
- **INV-2**: Determinism - Same inputs must produce same outputs

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Add to `api/tests/experiments/runner/test_temporal_optimization.py`:

**Test Cases**:

1. `test_temporal_always_accepts_policy` - Never rejects based on cost
2. `test_temporal_tracks_fraction` - Fraction recorded to stability tracker
3. `test_temporal_continues_on_cost_increase` - Doesn't revert when cost goes up
4. `test_temporal_extracts_fraction_from_policy` - Correctly extracts initial_liquidity_fraction
5. `test_temporal_uses_default_fraction_if_missing` - Defaults to 0.5 if not in policy
6. `test_temporal_logs_cost_for_analysis` - Costs still recorded in history

```python
"""Tests for temporal optimization changes."""

from __future__ import annotations

import pytest

from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker


class TestTemporalOptimizationChanges:
    """Tests for modified temporal optimization behavior."""

    @pytest.fixture
    def mock_runner(self):
        """Create a mock optimization runner for testing."""
        # This will need to be a proper fixture using the real runner
        # with mocked LLM responses
        ...

    def test_temporal_always_accepts_policy(self, mock_runner) -> None:
        """Temporal mode never rejects policies based on cost.

        Even when new policy results in higher cost than previous iteration,
        the policy should be accepted.
        """
        # Setup: iteration 1 cost = $100, iteration 2 cost = $150 (higher!)
        # Expected: policy still accepted (no revert)
        ...

    def test_temporal_tracks_fraction(self, mock_runner) -> None:
        """Fraction is recorded to stability tracker after each iteration."""
        # Run temporal optimization for agent
        # Verify stability tracker has the fraction recorded
        ...

    def test_temporal_continues_on_cost_increase(self, mock_runner) -> None:
        """Optimization continues even when costs increase.

        This is critical for multi-agent convergence where costs may
        increase temporarily as counterparty policies change.
        """
        ...

    def test_temporal_extracts_fraction_from_policy(self, mock_runner) -> None:
        """Correctly extracts initial_liquidity_fraction from policy dict."""
        policy = {
            "version": "2.0",
            "parameters": {"initial_liquidity_fraction": 0.7},
            "payment_tree": {"type": "action", "action": "Release"},
        }
        # Verify 0.7 is recorded to tracker
        ...

    def test_temporal_uses_default_fraction_if_missing(self, mock_runner) -> None:
        """Uses 0.5 as default if initial_liquidity_fraction not in policy."""
        policy = {
            "version": "2.0",
            "parameters": {},  # No fraction!
            "payment_tree": {"type": "action", "action": "Release"},
        }
        # Verify 0.5 is recorded to tracker
        ...

    def test_temporal_logs_cost_for_analysis(self, mock_runner) -> None:
        """Costs are still recorded for analysis even without rejection logic."""
        # Verify iteration history contains cost values
        ...
```

### Step 2.2: Implement Changes (GREEN)

Modify `api/payment_simulator/experiments/runner/optimization.py`:

#### 2.2.1: Add PolicyStabilityTracker to OptimizationRunner

```python
# In __init__ or initialization section:
from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker

# Add instance variable
self._stability_tracker = PolicyStabilityTracker()
```

#### 2.2.2: Modify `_optimize_agent_temporal()`

```python
async def _optimize_agent_temporal(self, agent_id: str, current_cost: int) -> None:
    """Optimize agent using temporal (cross-iteration) comparison.

    In multi-agent mode, always accepts LLM's policy and tracks
    initial_liquidity_fraction stability. Convergence is detected
    when ALL agents' fractions have been stable for stability_window
    iterations.

    This approach accounts for the fact that optimal policy depends on
    counterparty policies, which are also evolving. Cost-based rejection
    would cause oscillation as counterparty changes invalidate previous
    "optimal" solutions.

    Args:
        agent_id: Agent to optimize.
        current_cost: Current cost from _evaluate_policies() in integer cents.
    """
    # Get current policy
    current_policy = self._policies.get(
        agent_id, self._create_default_policy(agent_id)
    )

    # Store current policy for history (even though we won't revert)
    self._previous_policies[agent_id] = current_policy.copy()

    # Skip LLM if no constraints
    if self._constraints is None:
        self._accepted_changes[agent_id] = True
        # Still track the current fraction
        self._track_policy_fraction(agent_id, current_policy)
        return

    # Lazy initialize LLM client
    if self._llm_client is None:
        from payment_simulator.experiments.runner.llm_client import (
            ExperimentLLMClient,
        )
        self._llm_client = ExperimentLLMClient(self._config.llm)

    if self._policy_optimizer is None:
        self._policy_optimizer = PolicyOptimizer(
            constraints=self._constraints,
            max_retries=self._config.llm.max_retries,
        )

    # Build and inject dynamic system prompt
    dynamic_prompt = self._policy_optimizer.get_system_prompt(
        cost_rates=self._cost_rates,
        customization=None,
    )
    self._llm_client.set_system_prompt(dynamic_prompt)

    try:
        # Generate new policy via LLM
        current_metrics = {
            "total_cost_mean": current_cost,
            "iteration": self._current_iteration,
        }

        opt_result = await self._policy_optimizer.optimize(
            agent_id=agent_id,
            current_policy=current_policy,
            current_iteration=self._current_iteration,
            current_metrics=current_metrics,
            llm_client=self._llm_client,
            llm_model=self._config.llm.model,
            current_cost=float(current_cost),
            iteration_history=self._agent_iteration_history.get(agent_id),
            events=None,
            best_seed_output=None,
            worst_seed_output=None,
            best_seed=None,
            worst_seed=None,
            best_seed_cost=None,
            worst_seed_cost=None,
            cost_breakdown=None,
            cost_rates=self._cost_rates,
            debug_callback=None,
        )

        new_policy = opt_result.new_policy

        if new_policy is None:
            # Validation failed - keep current policy
            self._accepted_changes[agent_id] = True
            self._track_policy_fraction(agent_id, current_policy)
            return

        # Save LLM interaction event for audit
        self._save_llm_interaction_event(agent_id)

        # ALWAYS accept the new policy (no cost comparison!)
        self._record_iteration_history(
            agent_id=agent_id,
            policy=new_policy,
            cost=current_cost,
            was_accepted=True,
        )
        self._policies[agent_id] = new_policy
        self._accepted_changes[agent_id] = True

        # Track the fraction for stability detection
        self._track_policy_fraction(agent_id, new_policy)

        # Log policy change if verbose
        if self._verbose_logger and self._verbose_config.policy:
            self._verbose_logger.log_policy_change(
                agent_id=agent_id,
                old_policy=current_policy,
                new_policy=new_policy,
                old_cost=self._previous_iteration_costs.get(agent_id, current_cost),
                new_cost=current_cost,
                accepted=True,
            )

    except Exception as e:
        # Log error but don't crash
        error_msg = str(e)
        self._save_llm_interaction_event(agent_id)

        if self._verbose_logger and self._verbose_config.llm:
            from rich.console import Console as RichConsole
            console = RichConsole()
            console.print(f"[red]LLM error for {agent_id}: {error_msg}[/red]")

        # On error, keep current state
        self._accepted_changes[agent_id] = True
        self._track_policy_fraction(agent_id, current_policy)

    # Update previous cost for logging (not for acceptance)
    self._previous_iteration_costs[agent_id] = current_cost


def _track_policy_fraction(self, agent_id: str, policy: dict[str, Any]) -> None:
    """Extract and track initial_liquidity_fraction from policy.

    Args:
        agent_id: Agent identifier.
        policy: Policy dict containing parameters.
    """
    # Extract fraction with default of 0.5
    parameters = policy.get("parameters", {})
    fraction = parameters.get("initial_liquidity_fraction", 0.5)

    # Record to stability tracker
    self._stability_tracker.record_fraction(
        agent_id=agent_id,
        iteration=self._current_iteration,
        fraction=fraction,
    )
```

### Step 2.3: Refactor

- Remove old `_evaluate_temporal_acceptance()` method (no longer used)
- Update docstrings to reflect new behavior
- Ensure type annotations are complete

---

## Implementation Details

### Key Changes from Current Implementation

| Aspect | Old Behavior | New Behavior |
|--------|--------------|--------------|
| Cost comparison | Accept if cost <= previous | No cost comparison |
| Policy rejection | Revert if cost increased | Never revert |
| Fraction tracking | Not tracked | Recorded each iteration |
| Convergence basis | Cost stability | Fraction stability |

### Backwards Compatibility

- `deterministic-pairwise` mode is **unchanged** (still uses cost comparison)
- Only `deterministic-temporal` mode gets the new behavior
- This is controlled by `self._config.evaluation.is_deterministic_temporal`

### Edge Cases

1. **LLM returns same policy**: Fraction will be same, contributes to stability
2. **LLM validation failure**: Keep current policy, track its fraction
3. **LLM error**: Keep current policy, track its fraction
4. **Missing parameters in policy**: Default to 0.5

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY |
| `api/tests/experiments/runner/test_temporal_optimization.py` | CREATE |

---

## Verification

```bash
# Run new tests
cd api
.venv/bin/python -m pytest tests/experiments/runner/test_temporal_optimization.py -v

# Run existing tests to verify no regression
.venv/bin/python -m pytest tests/experiments/runner/ -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] All 6 new test cases pass
- [ ] All existing tests pass (no regression)
- [ ] Type check passes
- [ ] Lint passes
- [ ] `_track_policy_fraction()` extracts fraction correctly
- [ ] No cost-based rejection in temporal mode
- [ ] Fraction recorded to stability tracker each iteration
