# Phase 1: Create PolicyStabilityTracker

**Status**: Pending
**Started**: -

---

## Objective

Create a standalone `PolicyStabilityTracker` class that tracks `initial_liquidity_fraction` history per agent and detects when all agents have been stable for a configurable number of iterations.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism - Stability detection must be deterministic given same input history

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/experiments/runner/test_policy_stability.py`:

**Test Cases**:

1. `test_record_fraction_single_agent` - Basic recording works
2. `test_record_fraction_multiple_agents` - Can track multiple agents independently
3. `test_record_fraction_overwrites_same_iteration` - Re-recording same iteration overwrites
4. `test_agent_stable_for_exact_window` - True when unchanged for exact window
5. `test_agent_stable_for_less_than_window` - False when history shorter than window
6. `test_agent_stable_for_with_change_in_window` - False when changed within window
7. `test_all_agents_stable_true` - True when all agents stable
8. `test_all_agents_stable_one_unstable` - False when any agent unstable
9. `test_floating_point_tolerance` - Treats 0.5 and 0.500001 as equal

```python
"""Unit tests for PolicyStabilityTracker."""

from __future__ import annotations

import pytest

from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker


class TestPolicyStabilityTracker:
    """Tests for PolicyStabilityTracker."""

    def test_record_fraction_single_agent(self) -> None:
        """Recording a fraction stores it correctly."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)

        history = tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_record_fraction_multiple_agents(self) -> None:
        """Can track multiple agents independently."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=1, fraction=0.7)

        assert tracker.get_history("BANK_A") == [(1, 0.3)]
        assert tracker.get_history("BANK_B") == [(1, 0.7)]

    def test_record_fraction_overwrites_same_iteration(self) -> None:
        """Recording same iteration overwrites previous value."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)

        history = tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_agent_stable_for_exact_window(self) -> None:
        """Agent is stable when fraction unchanged for exact window."""
        tracker = PolicyStabilityTracker()
        # 5 iterations with same fraction
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_agent_stable_for_less_than_window(self) -> None:
        """Agent is NOT stable when history shorter than window."""
        tracker = PolicyStabilityTracker()
        # Only 3 iterations
        for i in range(1, 4):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is False

    def test_agent_stable_for_with_change_in_window(self) -> None:
        """Agent is NOT stable when fraction changed within window."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.6)  # Changed!
        tracker.record_fraction("BANK_A", iteration=4, fraction=0.6)
        tracker.record_fraction("BANK_A", iteration=5, fraction=0.6)

        # Only 3 iterations at 0.6, need 5
        assert tracker.agent_stable_for("BANK_A", window=5) is False

    def test_agent_stable_after_initial_changes(self) -> None:
        """Agent becomes stable after initial exploration."""
        tracker = PolicyStabilityTracker()
        # Initial exploration
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.4)
        # Stabilized
        for i in range(4, 9):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.4)

        # Last 5 iterations (4,5,6,7,8) all at 0.4
        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_all_agents_stable_true(self) -> None:
        """All agents stable returns True when all are stable."""
        tracker = PolicyStabilityTracker()
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)
            tracker.record_fraction("BANK_B", iteration=i, fraction=0.3)

        assert tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5) is True

    def test_all_agents_stable_one_unstable(self) -> None:
        """All agents stable returns False when any agent unstable."""
        tracker = PolicyStabilityTracker()
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        # BANK_B changed at iteration 4
        tracker.record_fraction("BANK_B", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=2, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=3, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=4, fraction=0.4)  # Changed!
        tracker.record_fraction("BANK_B", iteration=5, fraction=0.4)

        assert tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5) is False

    def test_floating_point_tolerance(self) -> None:
        """Treats minor floating-point differences as equal."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.50000001)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=4, fraction=0.49999999)
        tracker.record_fraction("BANK_A", iteration=5, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_unknown_agent_not_stable(self) -> None:
        """Unknown agent is not stable (no history)."""
        tracker = PolicyStabilityTracker()

        assert tracker.agent_stable_for("UNKNOWN", window=5) is False

    def test_get_last_fraction(self) -> None:
        """Can retrieve last recorded fraction for an agent."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.5)

        assert tracker.get_last_fraction("BANK_A") == 0.5

    def test_get_last_fraction_unknown_agent(self) -> None:
        """Returns None for unknown agent."""
        tracker = PolicyStabilityTracker()

        assert tracker.get_last_fraction("UNKNOWN") is None
```

### Step 1.2: Implement to Pass Tests (GREEN)

Create `api/payment_simulator/experiments/runner/policy_stability.py`:

```python
"""Policy stability tracking for multi-agent convergence detection.

This module provides a tracker for monitoring when agents' policy parameters
(specifically initial_liquidity_fraction) have stabilized, indicating
convergence in multi-agent optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Tolerance for floating-point comparison of fractions
FRACTION_TOLERANCE = 0.001


@dataclass
class PolicyStabilityTracker:
    """Tracks initial_liquidity_fraction stability across agents.

    In multi-agent policy optimization, convergence is detected when ALL
    agents have not changed their initial_liquidity_fraction for a
    configurable number of consecutive iterations.

    This differs from cost-based convergence because:
    1. Costs depend on counterparty policies (which change)
    2. Policy stability indicates the LLM has found its best answer
    3. Multi-agent equilibrium requires ALL agents to be stable

    Example:
        >>> tracker = PolicyStabilityTracker()
        >>> for i in range(1, 6):
        ...     tracker.record_fraction("BANK_A", i, 0.5)
        ...     tracker.record_fraction("BANK_B", i, 0.3)
        >>> tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5)
        True
    """

    # History of (iteration, fraction) per agent
    _history: dict[str, list[tuple[int, float]]] = field(default_factory=dict)

    def record_fraction(
        self,
        agent_id: str,
        iteration: int,
        fraction: float,
    ) -> None:
        """Record an agent's initial_liquidity_fraction for an iteration.

        If the same iteration is recorded twice, the new value overwrites
        the previous one.

        Args:
            agent_id: Agent identifier.
            iteration: Iteration number (1-indexed).
            fraction: The initial_liquidity_fraction value (0.0 to 1.0).
        """
        if agent_id not in self._history:
            self._history[agent_id] = []

        history = self._history[agent_id]

        # Check if this iteration already exists
        for i, (iter_num, _) in enumerate(history):
            if iter_num == iteration:
                history[i] = (iteration, fraction)
                return

        # Append new iteration (keep sorted by iteration)
        history.append((iteration, fraction))
        history.sort(key=lambda x: x[0])

    def get_history(self, agent_id: str) -> list[tuple[int, float]]:
        """Get the fraction history for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            List of (iteration, fraction) tuples, sorted by iteration.
            Empty list if agent unknown.
        """
        return list(self._history.get(agent_id, []))

    def get_last_fraction(self, agent_id: str) -> float | None:
        """Get the most recent fraction for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            The last recorded fraction, or None if no history.
        """
        history = self._history.get(agent_id, [])
        if not history:
            return None
        return history[-1][1]

    def agent_stable_for(self, agent_id: str, window: int) -> bool:
        """Check if agent's fraction has been unchanged for `window` iterations.

        "Unchanged" uses a small tolerance (FRACTION_TOLERANCE) to handle
        floating-point representation differences.

        Args:
            agent_id: Agent identifier.
            window: Number of consecutive iterations required for stability.

        Returns:
            True if the last `window` recorded fractions are effectively equal.
            False if agent unknown, history too short, or fraction changed.
        """
        history = self._history.get(agent_id, [])

        # Need at least `window` data points
        if len(history) < window:
            return False

        # Check last `window` fractions are all equal (within tolerance)
        last_window = history[-window:]
        reference_fraction = last_window[0][1]

        return all(
            abs(fraction - reference_fraction) <= FRACTION_TOLERANCE
            for _, fraction in last_window
        )

    def all_agents_stable(self, agents: list[str], window: int) -> bool:
        """Check if ALL agents have been stable for `window` iterations.

        This is the multi-agent convergence criterion: all agents must
        have stopped changing their policy parameter.

        Args:
            agents: List of agent identifiers to check.
            window: Number of consecutive iterations required for stability.

        Returns:
            True if all agents are stable, False otherwise.
        """
        return all(self.agent_stable_for(agent_id, window) for agent_id in agents)

    def reset(self) -> None:
        """Reset all tracking state.

        Use when starting a new optimization run.
        """
        self._history = {}
```

### Step 1.3: Refactor

- Ensure type safety (no bare `Any`)
- Add docstrings with examples
- Optimize for readability
- Consider edge cases

---

## Implementation Details

### Edge Cases to Handle

1. **Empty history**: `agent_stable_for()` returns False
2. **Single iteration**: Not stable unless window=1
3. **Re-recording same iteration**: Overwrite previous value
4. **Unknown agent**: Not stable (no history)
5. **Floating-point precision**: Use tolerance comparison

### Tolerance Choice

Use `FRACTION_TOLERANCE = 0.001` which corresponds to 0.1% difference:
- 0.500 and 0.501 are considered equal
- 0.50 and 0.51 are considered different

This matches the precision typically used in policy outputs.

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/policy_stability.py` | CREATE |
| `api/tests/experiments/runner/test_policy_stability.py` | CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/runner/test_policy_stability.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/policy_stability.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/runner/policy_stability.py
```

---

## Completion Criteria

- [ ] All 13 test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added with examples
- [ ] Edge cases handled
- [ ] INV-2 verified (deterministic given same inputs)
