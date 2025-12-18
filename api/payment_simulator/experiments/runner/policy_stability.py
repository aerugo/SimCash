"""Policy stability tracking for multi-agent convergence detection.

This module provides a tracker for monitoring when agents' policy parameters
(specifically initial_liquidity_fraction) have stabilized, indicating
convergence in multi-agent optimization.

In deterministic-temporal evaluation mode, convergence is detected when ALL
agents have not changed their initial_liquidity_fraction for a configurable
number of consecutive iterations (stability_window).

This differs from cost-based convergence because:
1. Costs depend on counterparty policies (which change simultaneously)
2. Policy stability indicates the LLM has found its best answer
3. Multi-agent equilibrium requires ALL agents to be stable
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tolerance for floating-point comparison of fractions.
# 0.001 means 0.500 and 0.501 are considered equal.
FRACTION_TOLERANCE = 0.001


@dataclass
class PolicyStabilityTracker:
    """Tracks initial_liquidity_fraction stability across agents.

    In multi-agent policy optimization, convergence is detected when ALL
    agents have not changed their initial_liquidity_fraction for a
    configurable number of consecutive iterations.

    Example:
        >>> tracker = PolicyStabilityTracker()
        >>> for i in range(1, 6):
        ...     tracker.record_fraction("BANK_A", i, 0.5)
        ...     tracker.record_fraction("BANK_B", i, 0.3)
        >>> tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5)
        True
    """

    # History of (iteration, fraction) per agent, sorted by iteration
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

        # Check if this iteration already exists - overwrite if so
        for i, (iter_num, _) in enumerate(history):
            if iter_num == iteration:
                history[i] = (iteration, fraction)
                return

        # Append new iteration and keep sorted by iteration number
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
            Empty agent list returns True (trivially stable).
        """
        return all(self.agent_stable_for(agent_id, window) for agent_id in agents)

    def reset(self) -> None:
        """Reset all tracking state.

        Use when starting a new optimization run.
        """
        self._history = {}
