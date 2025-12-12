# Phase 1: Seed Matrix Implementation

## Goal

Create a `SeedMatrix` class that pre-generates all seeds needed for an experiment, ensuring:
1. Deterministic generation from master_seed
2. Per-agent isolation per iteration
3. Bootstrap sample seeds derived from iteration seeds

## TDD Approach

### Test 1: Basic Reproducibility

```python
def test_seed_matrix_reproducibility():
    """Same master_seed produces identical seeds."""
    matrix1 = SeedMatrix(
        master_seed=42,
        max_iterations=10,
        agents=["BANK_A", "BANK_B"],
        num_bootstrap_samples=10,
    )
    matrix2 = SeedMatrix(
        master_seed=42,
        max_iterations=10,
        agents=["BANK_A", "BANK_B"],
        num_bootstrap_samples=10,
    )

    for iteration in range(10):
        for agent in ["BANK_A", "BANK_B"]:
            assert matrix1.get_iteration_seed(iteration, agent) == \
                   matrix2.get_iteration_seed(iteration, agent)

            for sample in range(10):
                assert matrix1.get_bootstrap_seed(iteration, agent, sample) == \
                       matrix2.get_bootstrap_seed(iteration, agent, sample)
```

### Test 2: Agent Isolation

```python
def test_seed_matrix_agent_isolation():
    """Different agents get different seeds for same iteration."""
    matrix = SeedMatrix(
        master_seed=42,
        max_iterations=10,
        agents=["BANK_A", "BANK_B"],
        num_bootstrap_samples=10,
    )

    for iteration in range(10):
        seed_a = matrix.get_iteration_seed(iteration, "BANK_A")
        seed_b = matrix.get_iteration_seed(iteration, "BANK_B")
        assert seed_a != seed_b, f"Iteration {iteration}: agents should have different seeds"
```

### Test 3: Iteration Isolation

```python
def test_seed_matrix_iteration_isolation():
    """Different iterations get different seeds for same agent."""
    matrix = SeedMatrix(
        master_seed=42,
        max_iterations=10,
        agents=["BANK_A"],
        num_bootstrap_samples=10,
    )

    seeds = [matrix.get_iteration_seed(i, "BANK_A") for i in range(10)]
    assert len(set(seeds)) == 10, "Each iteration should have unique seed"
```

### Test 4: Bootstrap Sample Isolation

```python
def test_seed_matrix_bootstrap_isolation():
    """Different bootstrap samples get different seeds."""
    matrix = SeedMatrix(
        master_seed=42,
        max_iterations=1,
        agents=["BANK_A"],
        num_bootstrap_samples=10,
    )

    seeds = [
        matrix.get_bootstrap_seed(0, "BANK_A", sample)
        for sample in range(10)
    ]
    assert len(set(seeds)) == 10, "Each sample should have unique seed"
```

### Test 5: Seed Range Validity

```python
def test_seed_matrix_valid_range():
    """Seeds are within valid i64 range for Rust FFI."""
    matrix = SeedMatrix(
        master_seed=42,
        max_iterations=100,
        agents=["BANK_A", "BANK_B", "BANK_C"],
        num_bootstrap_samples=50,
    )

    max_seed = 2**31 - 1  # i32 max for compatibility

    for iteration in range(100):
        for agent in ["BANK_A", "BANK_B", "BANK_C"]:
            seed = matrix.get_iteration_seed(iteration, agent)
            assert 0 <= seed <= max_seed, f"Seed {seed} out of range"

            for sample in range(50):
                bootstrap_seed = matrix.get_bootstrap_seed(iteration, agent, sample)
                assert 0 <= bootstrap_seed <= max_seed
```

### Test 6: Different Master Seeds

```python
def test_seed_matrix_different_master_seeds():
    """Different master seeds produce completely different matrices."""
    matrix1 = SeedMatrix(master_seed=42, max_iterations=5, agents=["A"], num_bootstrap_samples=5)
    matrix2 = SeedMatrix(master_seed=43, max_iterations=5, agents=["A"], num_bootstrap_samples=5)

    # All iteration seeds should differ
    for i in range(5):
        assert matrix1.get_iteration_seed(i, "A") != matrix2.get_iteration_seed(i, "A")
```

## Implementation

### File: `api/payment_simulator/experiments/runner/seed_matrix.py`

```python
"""Deterministic seed matrix for bootstrap evaluation.

Provides pre-generated seeds for:
- Each iteration
- Each agent within an iteration
- Each bootstrap sample within an agent's evaluation

This ensures reproducibility and proper isolation between agents.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SeedMatrix:
    """Pre-generated seed matrix for deterministic bootstrap evaluation.

    Seeds are generated hierarchically:
    - master_seed -> iteration_seed (per iteration)
    - iteration_seed -> agent_seed (per agent within iteration)
    - agent_seed -> bootstrap_seed (per sample within agent evaluation)

    All seeds are deterministically derived using SHA-256 to ensure:
    1. Reproducibility: same inputs always produce same seeds
    2. Isolation: different paths produce statistically independent seeds
    3. Range safety: all seeds fit within i32 for Rust FFI compatibility

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

    Attributes:
        master_seed: Root seed for all derivations.
        max_iterations: Total iterations to pre-generate.
        agents: Tuple of agent IDs.
        num_bootstrap_samples: Bootstrap samples per evaluation.
    """

    master_seed: int
    max_iterations: int
    agents: tuple[str, ...]
    num_bootstrap_samples: int

    # Internal cache (computed lazily)
    _iteration_seeds: dict[tuple[int, str], int] | None = None
    _bootstrap_seeds: dict[tuple[int, str, int], int] | None = None

    def __post_init__(self) -> None:
        """Pre-compute all seeds on initialization."""
        # Convert agents to tuple if needed (for hashability)
        if isinstance(self.agents, list):
            object.__setattr__(self, "agents", tuple(self.agents))

        # Initialize caches
        object.__setattr__(self, "_iteration_seeds", {})
        object.__setattr__(self, "_bootstrap_seeds", {})

        # Pre-compute all seeds
        self._precompute_seeds()

    def _precompute_seeds(self) -> None:
        """Pre-compute all seeds for fast access."""
        for iteration in range(self.max_iterations):
            for agent_id in self.agents:
                # Compute iteration seed
                iter_seed = self._derive_iteration_seed(iteration, agent_id)
                self._iteration_seeds[(iteration, agent_id)] = iter_seed  # type: ignore[index]

                # Compute bootstrap seeds
                for sample_idx in range(self.num_bootstrap_samples):
                    boot_seed = self._derive_bootstrap_seed(iter_seed, sample_idx)
                    self._bootstrap_seeds[(iteration, agent_id, sample_idx)] = boot_seed  # type: ignore[index]

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
        if self._iteration_seeds is None:
            msg = "SeedMatrix not initialized"
            raise RuntimeError(msg)
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
        if self._bootstrap_seeds is None:
            msg = "SeedMatrix not initialized"
            raise RuntimeError(msg)
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
```

## Integration Points

### In `OptimizationLoop.__init__`:

```python
# Create seed matrix on initialization
self._seed_matrix = SeedMatrix(
    master_seed=config.master_seed,
    max_iterations=config.convergence.max_iterations,
    agents=config.optimized_agents,
    num_bootstrap_samples=config.evaluation.num_samples or 1,
)
```

### In `_evaluate_policy_pair` (new method):

```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    iteration: int,
) -> list[int]:
    """Evaluate old vs new policy with paired bootstrap samples.

    Returns list of deltas (old_cost - new_cost).
    Positive delta = new policy is cheaper.
    """
    bootstrap_seeds = self._seed_matrix.get_bootstrap_seeds(iteration, agent_id)

    deltas = []
    for seed in bootstrap_seeds:
        old_cost = self._evaluate_policy_with_seed(old_policy, agent_id, seed)
        new_cost = self._evaluate_policy_with_seed(new_policy, agent_id, seed)
        deltas.append(old_cost - new_cost)

    return deltas
```

## Acceptance Criteria

- [ ] All 6 unit tests pass
- [ ] `SeedMatrix` class created in `seed_matrix.py`
- [ ] Type annotations complete (mypy passes)
- [ ] Docstrings follow project conventions
- [ ] No existing tests broken

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/seed_matrix.py` | Create |
| `api/tests/unit/test_seed_matrix.py` | Create |
| `api/payment_simulator/experiments/runner/__init__.py` | Add export |

## Estimated Time

1-2 hours with TDD approach
