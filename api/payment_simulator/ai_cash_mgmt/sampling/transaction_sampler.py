"""Transaction sampling for Monte Carlo evaluation.

Samples transactions from historical data for evaluating policy performance
through Monte Carlo simulation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class HistoricalTransaction:
    """Immutable record of a historical transaction.

    Stores all relevant transaction data for Monte Carlo resampling.
    The frozen=True makes instances immutable and hashable.

    Example:
        >>> tx = HistoricalTransaction(
        ...     tx_id="TX001",
        ...     sender_id="BANK_A",
        ...     receiver_id="BANK_B",
        ...     amount=100000,
        ...     priority=5,
        ...     arrival_tick=10,
        ...     deadline_tick=20,
        ...     is_divisible=True,
        ... )
    """

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents
    priority: int
    arrival_tick: int
    deadline_tick: int
    is_divisible: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for simulation injection.

        Returns:
            Dict suitable for passing to simulation as a transaction spec.
        """
        return {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "amount": self.amount,
            "priority": self.priority,
            "deadline_ticks": self.deadline_tick - self.arrival_tick,
            "is_divisible": self.is_divisible,
        }


class TransactionSampler:
    """Samples transactions from historical data for Monte Carlo evaluation.

    Key Design Decisions:
    - Deterministic: Same seed produces same samples
    - Agent-filtered: Can sample only transactions relevant to specific agent
    - Tick-bounded: For intra-simulation, only uses transactions up to current tick

    Example:
        >>> sampler = TransactionSampler(seed=42)
        >>> sampler.collect_transactions(orchestrator.get_all_transactions())
        >>> samples = sampler.create_samples(
        ...     agent_id="BANK_A",
        ...     num_samples=20,
        ...     max_tick=50,  # Only txns from ticks 0-50
        ... )
    """

    def __init__(self, seed: int) -> None:
        """Initialize sampler with deterministic seed.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        self._rng = self._create_rng(seed)
        self._transactions: list[HistoricalTransaction] = []

    @staticmethod
    def _create_rng(seed: int) -> np.random.Generator:
        """Create deterministic RNG from seed.

        Args:
            seed: Seed value.

        Returns:
            Numpy random generator.
        """
        return np.random.Generator(np.random.PCG64(seed))

    @property
    def transaction_count(self) -> int:
        """Get number of collected transactions."""
        return len(self._transactions)

    def collect_transactions(
        self,
        transactions: list[dict[str, Any]],
    ) -> None:
        """Collect transactions from simulation state.

        Args:
            transactions: List of transaction dicts from orchestrator.
        """
        for tx in transactions:
            self._transactions.append(
                HistoricalTransaction(
                    tx_id=tx["tx_id"],
                    sender_id=tx["sender_id"],
                    receiver_id=tx["receiver_id"],
                    amount=tx["amount"],
                    priority=tx.get("priority", 5),
                    arrival_tick=tx["arrival_tick"],
                    deadline_tick=tx["deadline_tick"],
                    is_divisible=tx.get("is_divisible", True),
                )
            )

    def create_samples(
        self,
        agent_id: str,
        num_samples: int,
        max_tick: int | None = None,
        method: str = "bootstrap",
    ) -> list[list[HistoricalTransaction]]:
        """Create Monte Carlo transaction samples.

        Args:
            agent_id: Filter to transactions involving this agent.
            num_samples: Number of samples to create.
            max_tick: Only include transactions arriving before this tick.
            method: Sampling method (bootstrap, permutation, stratified).

        Returns:
            List of transaction lists (one per sample).

        Raises:
            ValueError: If method is unknown.
        """
        # Filter transactions
        filtered = self._filter_transactions(agent_id, max_tick)

        if not filtered:
            return [[] for _ in range(num_samples)]

        if method == "bootstrap":
            return self._bootstrap_sample(filtered, num_samples)
        elif method == "permutation":
            return self._permutation_sample(filtered, num_samples)
        elif method == "stratified":
            return self._stratified_sample(filtered, num_samples)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

    def _filter_transactions(
        self,
        agent_id: str,
        max_tick: int | None,
    ) -> list[HistoricalTransaction]:
        """Filter transactions by agent and tick.

        Args:
            agent_id: Filter to this agent (as sender or receiver).
            max_tick: Maximum arrival tick (inclusive).

        Returns:
            Filtered transaction list.
        """
        result = []
        for tx in self._transactions:
            # Include if agent is sender or receiver
            if tx.sender_id != agent_id and tx.receiver_id != agent_id:
                continue
            # Include if within tick bound
            if max_tick is not None and tx.arrival_tick > max_tick:
                continue
            result.append(tx)
        return result

    def _bootstrap_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Bootstrap resampling (with replacement).

        Args:
            transactions: Source transactions.
            num_samples: Number of samples to generate.

        Returns:
            List of sampled transaction lists.
        """
        n = len(transactions)
        samples = []
        for _ in range(num_samples):
            indices = self._rng.integers(0, n, size=n)
            samples.append([transactions[i] for i in indices])
        return samples

    def _permutation_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Permutation sampling (shuffle arrival order).

        Args:
            transactions: Source transactions.
            num_samples: Number of samples to generate.

        Returns:
            List of shuffled transaction lists.
        """
        samples = []
        n = len(transactions)
        for _ in range(num_samples):
            # Use permutation on indices instead of shuffling list directly
            indices = self._rng.permutation(n)
            shuffled = [transactions[i] for i in indices]
            samples.append(shuffled)
        return samples

    def _stratified_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Stratified sampling by transaction size buckets.

        Divides transactions into quartiles by amount and samples
        from each bucket to maintain the amount distribution.

        Args:
            transactions: Source transactions.
            num_samples: Number of samples to generate.

        Returns:
            List of stratified-sampled transaction lists.
        """
        # Sort by amount and divide into quartiles
        sorted_txs = sorted(transactions, key=lambda tx: tx.amount)
        n = len(sorted_txs)
        quartile_size = n // 4

        # Create buckets (may be uneven)
        buckets: list[list[HistoricalTransaction]] = [
            sorted_txs[: quartile_size],
            sorted_txs[quartile_size : 2 * quartile_size],
            sorted_txs[2 * quartile_size : 3 * quartile_size],
            sorted_txs[3 * quartile_size :],
        ]
        # Filter out empty buckets
        buckets = [b for b in buckets if b]

        samples = []
        for _ in range(num_samples):
            sample = []
            for bucket in buckets:
                if bucket:
                    bucket_n = len(bucket)
                    indices = self._rng.integers(0, bucket_n, size=bucket_n)
                    sample.extend([bucket[i] for i in indices])
            samples.append(sample)
        return samples

    def derive_subseed(self, iteration: int, agent_id: str) -> int:
        """Derive deterministic subseed for a specific optimization.

        Ensures same master_seed + iteration + agent produces same samples.

        Args:
            iteration: Optimization iteration number.
            agent_id: Agent being optimized.

        Returns:
            Derived seed value.
        """
        key = f"{self._seed}:{iteration}:{agent_id}"
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big")
