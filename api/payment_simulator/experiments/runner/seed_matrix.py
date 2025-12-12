"""Deterministic seed matrix for bootstrap evaluation.

Provides pre-generated seeds for:
- Each iteration
- Each agent within an iteration
- Each bootstrap sample within an agent's evaluation

This ensures reproducibility and proper isolation between agents.

Example:
    >>> matrix = SeedMatrix(
    ...     master_seed=42,
    ...     max_iterations=25,
    ...     agents=["BANK_A", "BANK_B"],
    ...     num_bootstrap_samples=10,
    ... )
    >>> seed = matrix.get_iteration_seed(0, "BANK_A")
    >>> bootstrap_seeds = matrix.get_bootstrap_seeds(0, "BANK_A")
    >>> len(bootstrap_seeds)
    10
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass
class SeedMatrix:
    """Pre-generated seed matrix for deterministic bootstrap evaluation.

    Seeds are generated hierarchically:
    - master_seed -> iteration_seed (per iteration per agent)
    - iteration_seed -> bootstrap_seed (per sample within agent evaluation)

    All seeds are deterministically derived using SHA-256 to ensure:
    1. Reproducibility: same inputs always produce same seeds
    2. Isolation: different paths produce statistically independent seeds
    3. Range safety: all seeds fit within i32 for Rust FFI compatibility

    Attributes:
        master_seed: Root seed for all derivations.
        max_iterations: Total iterations to pre-generate.
        agents: Sequence of agent IDs.
        num_bootstrap_samples: Bootstrap samples per evaluation.
    """

    master_seed: int
    max_iterations: int
    agents: Sequence[str]
    num_bootstrap_samples: int

    # Internal caches (populated on __post_init__)
    _iteration_seeds: dict[tuple[int, str], int] = field(
        default_factory=dict, init=False, repr=False
    )
    _bootstrap_seeds: dict[tuple[int, str, int], int] = field(
        default_factory=dict, init=False, repr=False
    )
    _agents_tuple: tuple[str, ...] = field(default_factory=tuple, init=False, repr=False)

    def __post_init__(self) -> None:
        """Pre-compute all seeds on initialization."""
        # Convert agents to tuple for hashability
        self._agents_tuple = tuple(self.agents)

        # Pre-compute all seeds
        self._precompute_seeds()

    def _precompute_seeds(self) -> None:
        """Pre-compute all seeds for fast access."""
        for iteration in range(self.max_iterations):
            for agent_id in self._agents_tuple:
                # Compute iteration seed
                iter_seed = self._derive_iteration_seed(iteration, agent_id)
                self._iteration_seeds[(iteration, agent_id)] = iter_seed

                # Compute bootstrap seeds
                for sample_idx in range(self.num_bootstrap_samples):
                    boot_seed = self._derive_bootstrap_seed(iter_seed, sample_idx)
                    self._bootstrap_seeds[(iteration, agent_id, sample_idx)] = boot_seed

    def _derive_iteration_seed(self, iteration: int, agent_id: str) -> int:
        """Derive iteration seed for agent.

        Uses hierarchical derivation:
        master_seed -> iteration -> agent

        Args:
            iteration: Iteration index (0-based).
            agent_id: Agent identifier.

        Returns:
            Deterministic seed for this iteration/agent pair.
        """
        key = f"{self.master_seed}:iter:{iteration}:agent:{agent_id}"
        return self._hash_to_seed(key)

    def _derive_bootstrap_seed(self, iteration_seed: int, sample_idx: int) -> int:
        """Derive bootstrap sample seed.

        Args:
            iteration_seed: Parent iteration seed.
            sample_idx: Bootstrap sample index.

        Returns:
            Deterministic seed for this bootstrap sample.
        """
        key = f"{iteration_seed}:bootstrap:{sample_idx}"
        return self._hash_to_seed(key)

    @staticmethod
    def _hash_to_seed(key: str) -> int:
        """Convert string key to deterministic seed.

        Uses SHA-256 hash truncated to fit i32 range for Rust FFI compatibility.

        Args:
            key: String key to hash.

        Returns:
            Seed in range [0, 2^31 - 1].
        """
        hash_bytes = hashlib.sha256(key.encode()).digest()
        # Use first 4 bytes for i32 compatibility
        raw_value = int.from_bytes(hash_bytes[:4], byteorder="big")
        # Ensure positive value within i32 range
        return raw_value % (2**31)

    def get_iteration_seed(self, iteration: int, agent_id: str) -> int:
        """Get iteration seed for an agent.

        Args:
            iteration: Iteration index (0-based).
            agent_id: Agent identifier.

        Returns:
            Seed for this iteration/agent.

        Raises:
            KeyError: If iteration or agent not in matrix.
        """
        return self._iteration_seeds[(iteration, agent_id)]

    def get_bootstrap_seed(self, iteration: int, agent_id: str, sample_idx: int) -> int:
        """Get bootstrap sample seed.

        Args:
            iteration: Iteration index (0-based).
            agent_id: Agent identifier.
            sample_idx: Bootstrap sample index.

        Returns:
            Seed for this bootstrap sample.

        Raises:
            KeyError: If parameters not in matrix.
        """
        return self._bootstrap_seeds[(iteration, agent_id, sample_idx)]

    def get_bootstrap_seeds(self, iteration: int, agent_id: str) -> list[int]:
        """Get all bootstrap seeds for an iteration/agent.

        Args:
            iteration: Iteration index (0-based).
            agent_id: Agent identifier.

        Returns:
            List of seeds for all bootstrap samples.
        """
        return [
            self.get_bootstrap_seed(iteration, agent_id, sample_idx)
            for sample_idx in range(self.num_bootstrap_samples)
        ]
