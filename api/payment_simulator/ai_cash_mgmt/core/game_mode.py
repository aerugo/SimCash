"""Game modes for AI Cash Management.

Defines the available game modes for LLM-based policy optimization.
"""

from __future__ import annotations

from enum import Enum


class GameMode(str, Enum):
    """Available game modes for AI Cash Management.

    Game modes determine when and how policy optimization occurs:

    - RL_OPTIMIZATION: Intra-simulation optimization. Policies are optimized
      during a single simulation run, triggered by tick intervals or end-of-day.

    - CAMPAIGN_LEARNING: Inter-simulation optimization. Complete simulations
      (campaigns) are run, and policies are optimized between campaigns based
      on full-run performance.

    Example:
        >>> mode = GameMode.RL_OPTIMIZATION
        >>> mode.is_intra_simulation
        True
        >>> mode.description
        'Optimize policies during simulation execution...'
    """

    RL_OPTIMIZATION = "rl_optimization"
    CAMPAIGN_LEARNING = "campaign_learning"

    @property
    def is_intra_simulation(self) -> bool:
        """Check if this mode optimizes during simulation.

        Returns:
            True if optimization happens during simulation execution,
            False if optimization happens between complete simulations.
        """
        return self == GameMode.RL_OPTIMIZATION

    @property
    def description(self) -> str:
        """Get human-readable description of this mode.

        Returns:
            Description string explaining the mode's behavior.
        """
        descriptions = {
            GameMode.RL_OPTIMIZATION: (
                "Optimize policies during simulation execution. "
                "Policies are updated at configured intervals (every X ticks, "
                "after end-of-day) and take effect immediately."
            ),
            GameMode.CAMPAIGN_LEARNING: (
                "Optimize policies between complete simulation runs. "
                "Each campaign runs to completion, and policies are optimized "
                "based on full-run performance before the next campaign."
            ),
        }
        return descriptions[self]
