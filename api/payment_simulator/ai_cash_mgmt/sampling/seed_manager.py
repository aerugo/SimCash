"""Deterministic seed derivation for reproducible AI cash management.

All randomness in the ai_cash_mgmt module flows through this manager,
ensuring that the same master_seed produces identical results.
"""

from __future__ import annotations

import hashlib


class SeedManager:
    """Manages deterministic seed derivation for reproducibility.

    All randomness in the ai_cash_mgmt module flows through this manager,
    ensuring that the same master_seed produces identical results.

    Seed derivation hierarchy:
    - master_seed
      ├── simulation_seed (for running the main simulation)
      ├── sampling_seed (for bootstrap transaction sampling)
      │   ├── iteration_N_agent_A
      │   ├── iteration_N_agent_B
      │   └── ...
      ├── llm_seed (for LLM temperature if stochastic)
      └── tiebreaker_seed (for equal-cost policy selection)

    Example:
        >>> manager = SeedManager(master_seed=42)
        >>> manager.simulation_seed(0)
        1234567890  # Always the same for seed 42, iteration 0
        >>> manager.sampling_seed(0, "BANK_A")
        9876543210  # Always the same for seed 42, iteration 0, BANK_A
    """

    def __init__(self, master_seed: int) -> None:
        """Initialize the seed manager.

        Args:
            master_seed: The master seed for all derived seeds.
        """
        self.master_seed = master_seed

    def derive_seed(self, *components: str | int) -> int:
        """Derive a sub-seed from master seed and components.

        Uses SHA-256 hashing to deterministically derive seeds from
        hierarchical components. This ensures:
        - Same inputs always produce same outputs
        - Different inputs produce statistically independent outputs
        - Output is within valid seed range [0, 2^31)

        Args:
            *components: Hierarchical components (e.g., "simulation", 0, "BANK_A")

        Returns:
            Deterministic seed derived from master + components
        """
        key = ":".join(str(c) for c in [self.master_seed, *components])
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)

    def simulation_seed(self, iteration: int) -> int:
        """Seed for running simulation at given iteration.

        Args:
            iteration: The campaign/optimization iteration number.

        Returns:
            Deterministic seed for the simulation.
        """
        return self.derive_seed("simulation", iteration)

    def sampling_seed(self, iteration: int, agent_id: str) -> int:
        """Seed for bootstrap sampling for specific agent/iteration.

        Args:
            iteration: The optimization iteration number.
            agent_id: The agent ID being sampled for.

        Returns:
            Deterministic seed for transaction sampling.
        """
        return self.derive_seed("sampling", iteration, agent_id)

    def llm_seed(self, iteration: int, agent_id: str) -> int:
        """Seed for LLM randomness (if temperature > 0).

        Args:
            iteration: The optimization iteration number.
            agent_id: The agent ID being optimized.

        Returns:
            Deterministic seed for LLM sampling.
        """
        return self.derive_seed("llm", iteration, agent_id)

    def tiebreaker_seed(self, iteration: int) -> int:
        """Seed for breaking ties between equal-cost policies.

        Args:
            iteration: The optimization iteration number.

        Returns:
            Deterministic seed for tiebreaking.
        """
        return self.derive_seed("tiebreaker", iteration)
