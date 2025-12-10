"""Bootstrap sampler for Monte Carlo transaction resampling.

This module implements deterministic bootstrap resampling of transaction
histories for policy evaluation.

Key features:
- Deterministic sampling using seeded xorshift64* RNG
- Resampling with replacement (bootstrap methodology)
- Uniform remapping of arrival ticks
- Preservation of transaction offsets (deadline, settlement)
"""

from __future__ import annotations

import hashlib

from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
    TransactionRecord,
)


class BootstrapSampler:
    """Generates bootstrap samples from transaction history.

    Uses deterministic xorshift64* RNG to ensure reproducibility.
    Same seed + same inputs = same outputs (project invariant).

    The sampling process:
    1. Derive a sample-specific seed from base seed + sample_idx
    2. Resample records with replacement (bootstrap)
    3. For each sampled record, assign uniform random arrival tick
    4. Remap to RemappedTransaction with absolute ticks

    Example:
        ```python
        sampler = BootstrapSampler(seed=12345)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=outgoing,
            incoming_records=incoming,
            total_ticks=100,
        )
        ```
    """

    def __init__(self, seed: int) -> None:
        """Initialize the sampler with a base seed.

        Args:
            seed: Base seed for deterministic RNG.
        """
        self._base_seed = seed

    def generate_sample(
        self,
        agent_id: str,
        sample_idx: int,
        outgoing_records: tuple[TransactionRecord, ...],
        incoming_records: tuple[TransactionRecord, ...],
        total_ticks: int,
    ) -> BootstrapSample:
        """Generate a single bootstrap sample.

        Args:
            agent_id: ID of the agent being evaluated.
            sample_idx: Index of this sample (for seed derivation).
            outgoing_records: Historical outgoing transactions.
            incoming_records: Historical incoming transactions.
            total_ticks: Number of ticks in the simulated day.

        Returns:
            BootstrapSample with remapped transactions.
        """
        # Derive sample-specific seed
        sample_seed = self._derive_sample_seed(sample_idx)
        rng = _Xorshift64Star(sample_seed)

        # Sample outgoing transactions
        outgoing_txns = self._sample_and_remap(
            records=outgoing_records,
            rng=rng,
            total_ticks=total_ticks,
            prefix="out",
        )

        # Filter incoming to only settled transactions
        settled_incoming = tuple(r for r in incoming_records if r.was_settled)

        # Sample incoming transactions (liquidity beats)
        incoming_txns = self._sample_and_remap(
            records=settled_incoming,
            rng=rng,
            total_ticks=total_ticks,
            prefix="in",
        )

        return BootstrapSample(
            agent_id=agent_id,
            sample_idx=sample_idx,
            seed=sample_seed,
            outgoing_txns=outgoing_txns,
            incoming_settlements=incoming_txns,
            total_ticks=total_ticks,
        )

    def generate_samples(
        self,
        agent_id: str,
        n_samples: int,
        outgoing_records: tuple[TransactionRecord, ...],
        incoming_records: tuple[TransactionRecord, ...],
        total_ticks: int,
    ) -> list[BootstrapSample]:
        """Generate multiple bootstrap samples.

        Args:
            agent_id: ID of the agent being evaluated.
            n_samples: Number of samples to generate.
            outgoing_records: Historical outgoing transactions.
            incoming_records: Historical incoming transactions.
            total_ticks: Number of ticks in the simulated day.

        Returns:
            List of BootstrapSample instances.
        """
        return [
            self.generate_sample(
                agent_id=agent_id,
                sample_idx=i,
                outgoing_records=outgoing_records,
                incoming_records=incoming_records,
                total_ticks=total_ticks,
            )
            for i in range(n_samples)
        ]

    def _derive_sample_seed(self, sample_idx: int) -> int:
        """Derive a sample-specific seed from base seed and index.

        Uses SHA-256 for deterministic derivation.

        Args:
            sample_idx: Sample index.

        Returns:
            Derived seed for this sample.
        """
        key = f"{self._base_seed}:sample:{sample_idx}"
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)

    def _sample_and_remap(
        self,
        records: tuple[TransactionRecord, ...],
        rng: _Xorshift64Star,
        total_ticks: int,
        prefix: str,
    ) -> tuple[RemappedTransaction, ...]:
        """Resample records with replacement and remap to new arrival ticks.

        Args:
            records: Source records to sample from.
            rng: Random number generator.
            total_ticks: Total ticks for uniform arrival distribution.
            prefix: Prefix for unique tx_ids.

        Returns:
            Tuple of remapped transactions.
        """
        if not records:
            return ()

        n = len(records)
        result: list[RemappedTransaction] = []

        for i in range(n):
            # Sample with replacement: pick random record
            idx = rng.next_int(n)
            record = records[idx]

            # Uniform random arrival tick in [0, total_ticks)
            arrival_tick = rng.next_int(total_ticks)

            # Remap with unique tx_id
            remapped = record.remap_to_tick(arrival_tick, total_ticks)

            # Make tx_id unique
            unique_remapped = RemappedTransaction(
                tx_id=f"{record.tx_id}:{prefix}:{i}",
                sender_id=remapped.sender_id,
                receiver_id=remapped.receiver_id,
                amount=remapped.amount,
                priority=remapped.priority,
                arrival_tick=remapped.arrival_tick,
                deadline_tick=remapped.deadline_tick,
                settlement_tick=remapped.settlement_tick,
            )

            result.append(unique_remapped)

        return tuple(result)


class _Xorshift64Star:
    """Deterministic xorshift64* random number generator.

    This is the same algorithm used in the Rust simulation core,
    ensuring identical behavior across languages.
    """

    def __init__(self, seed: int) -> None:
        """Initialize with seed.

        Args:
            seed: Initial state (must be non-zero).
        """
        # Ensure non-zero state
        self._state = seed if seed != 0 else 1

    def next_u64(self) -> int:
        """Generate next 64-bit random value.

        Returns:
            Random 64-bit unsigned integer.
        """
        # xorshift64*
        x = self._state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self._state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def next_int(self, max_val: int) -> int:
        """Generate random integer in [0, max_val).

        Args:
            max_val: Exclusive upper bound.

        Returns:
            Random integer in range [0, max_val).
        """
        if max_val <= 0:
            return 0
        return self.next_u64() % max_val
