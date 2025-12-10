"""Unit tests for BootstrapSampler.

Phase 3: Bootstrap Sampler - TDD Tests

Tests for:
- Deterministic sampling with seeded RNG
- Resampling transactions with replacement
- Remapping arrival ticks uniformly
- Creating BootstrapSample instances
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
    TransactionRecord,
)
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler


class TestDeterministicSampling:
    """Test deterministic sampling with seeded RNG."""

    def test_same_seed_same_results(self) -> None:
        """Same seed produces identical samples."""
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=10,
                deadline_offset=5,
                settlement_offset=3,
            ),
            TransactionRecord(
                tx_id="tx-002",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=200000,
                priority=7,
                original_arrival_tick=20,
                deadline_offset=8,
                settlement_offset=5,
            ),
        )
        incoming_records = (
            TransactionRecord(
                tx_id="tx-003",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                original_arrival_tick=5,
                deadline_offset=10,
                settlement_offset=7,
            ),
        )

        sampler1 = BootstrapSampler(seed=12345)
        sampler2 = BootstrapSampler(seed=12345)

        sample1 = sampler1.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=incoming_records,
            total_ticks=100,
        )
        sample2 = sampler2.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=incoming_records,
            total_ticks=100,
        )

        # Both samples should have identical transactions
        assert len(sample1.outgoing_txns) == len(sample2.outgoing_txns)
        assert len(sample1.incoming_settlements) == len(sample2.incoming_settlements)

        for tx1, tx2 in zip(sample1.outgoing_txns, sample2.outgoing_txns, strict=True):
            assert tx1.tx_id == tx2.tx_id
            assert tx1.arrival_tick == tx2.arrival_tick
            assert tx1.deadline_tick == tx2.deadline_tick

    def test_different_seed_different_results(self) -> None:
        """Different seeds produce different samples."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(20)
        )

        sampler1 = BootstrapSampler(seed=12345)
        sampler2 = BootstrapSampler(seed=54321)

        sample1 = sampler1.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )
        sample2 = sampler2.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        # At least some arrival ticks should differ
        arrival_ticks_1 = [tx.arrival_tick for tx in sample1.outgoing_txns]
        arrival_ticks_2 = [tx.arrival_tick for tx in sample2.outgoing_txns]
        assert arrival_ticks_1 != arrival_ticks_2


class TestResamplingWithReplacement:
    """Test bootstrap resampling with replacement."""

    def test_resamples_same_count_as_input(self) -> None:
        """Resampling produces same count as input transactions."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 1000,
                priority=5,
                original_arrival_tick=i * 5,
                deadline_offset=10,
                settlement_offset=5,
            )
            for i in range(10)
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        # Should have same count as input
        assert len(sample.outgoing_txns) == len(records)

    def test_resampling_allows_duplicates(self) -> None:
        """Bootstrap resampling can select same record multiple times."""
        # With only 3 records and 3 samples, high chance of duplicates
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=10,
                settlement_offset=5,
            ),
            TransactionRecord(
                tx_id="tx-002",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=200000,
                priority=5,
                original_arrival_tick=10,
                deadline_offset=10,
                settlement_offset=5,
            ),
            TransactionRecord(
                tx_id="tx-003",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=300000,
                priority=5,
                original_arrival_tick=20,
                deadline_offset=10,
                settlement_offset=5,
            ),
        )

        # Generate many samples, at least one should have duplicate tx_ids
        sampler = BootstrapSampler(seed=12345)
        found_duplicate = False
        for sample_idx in range(100):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            # Note: tx_ids are made unique by suffix, but original tx_id is preserved
            # Check for repeated original amounts (proxy for same source record)
            amounts = [tx.amount for tx in sample.outgoing_txns]
            if len(amounts) != len(set(amounts)):
                found_duplicate = True
                break

        assert found_duplicate, "Expected at least one sample with duplicates"


class TestArrivalTickRemapping:
    """Test uniform remapping of arrival ticks."""

    def test_arrival_ticks_in_valid_range(self) -> None:
        """Remapped arrival ticks are within [0, total_ticks)."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=i * 100,  # Original ticks spread out
                deadline_offset=10,
                settlement_offset=5,
            )
            for i in range(20)
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=50,  # All arrivals should be in [0, 50)
        )

        for tx in sample.outgoing_txns:
            assert 0 <= tx.arrival_tick < 50
            # Deadline should be <= total_ticks (capped)
            assert tx.deadline_tick <= 50

    def test_deadline_capped_at_eod(self) -> None:
        """Deadline ticks are capped at end of day."""
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=100,  # Very long deadline
                settlement_offset=50,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=20,  # Short day
        )

        # Deadline should be capped at 20
        assert sample.outgoing_txns[0].deadline_tick <= 20


class TestBootstrapSampleCreation:
    """Test BootstrapSample output structure."""

    def test_sample_has_correct_metadata(self) -> None:
        """Generated sample has correct metadata."""
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=10,
                settlement_offset=5,
            ),
        )

        sampler = BootstrapSampler(seed=99999)
        sample = sampler.generate_sample(
            agent_id="BANK_X",
            sample_idx=42,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        assert sample.agent_id == "BANK_X"
        assert sample.sample_idx == 42
        assert sample.total_ticks == 100
        # Seed is derived from sampler seed + sample_idx
        assert sample.seed != 0  # Should have a valid seed

    def test_sample_contains_remapped_transactions(self) -> None:
        """Generated sample contains RemappedTransaction objects."""
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=10,
                settlement_offset=5,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        assert isinstance(sample, BootstrapSample)
        assert len(sample.outgoing_txns) > 0
        assert isinstance(sample.outgoing_txns[0], RemappedTransaction)


class TestIncomingTransactionSampling:
    """Test sampling of incoming transactions (liquidity beats)."""

    def test_incoming_transactions_sampled(self) -> None:
        """Incoming transactions are sampled and included."""
        incoming_records = (
            TransactionRecord(
                tx_id="tx-in-001",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                original_arrival_tick=5,
                deadline_offset=10,
                settlement_offset=7,  # Settled!
            ),
            TransactionRecord(
                tx_id="tx-in-002",
                sender_id="BANK_C",
                receiver_id="BANK_A",
                amount=75000,
                priority=5,
                original_arrival_tick=10,
                deadline_offset=10,
                settlement_offset=3,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=incoming_records,
            total_ticks=100,
        )

        # Should have sampled incoming transactions
        assert len(sample.incoming_settlements) == len(incoming_records)

    def test_unsettled_incoming_excluded(self) -> None:
        """Unsettled incoming transactions are excluded from liquidity beats."""
        incoming_records = (
            TransactionRecord(
                tx_id="tx-in-001",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                original_arrival_tick=5,
                deadline_offset=10,
                settlement_offset=7,  # Settled
            ),
            TransactionRecord(
                tx_id="tx-in-002",
                sender_id="BANK_C",
                receiver_id="BANK_A",
                amount=75000,
                priority=5,
                original_arrival_tick=10,
                deadline_offset=10,
                settlement_offset=None,  # NOT settled - should be excluded
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=incoming_records,
            total_ticks=100,
        )

        # Should only include the settled transaction
        # (sampled from filtered records)
        settled_records = tuple(r for r in incoming_records if r.was_settled)
        # Sample count should match settled count
        assert len(sample.incoming_settlements) == len(settled_records)


class TestEmptyInputHandling:
    """Test handling of empty transaction inputs."""

    def test_empty_outgoing_records(self) -> None:
        """Empty outgoing records produces empty outgoing in sample."""
        incoming_records = (
            TransactionRecord(
                tx_id="tx-in-001",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                original_arrival_tick=5,
                deadline_offset=10,
                settlement_offset=7,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=incoming_records,
            total_ticks=100,
        )

        assert len(sample.outgoing_txns) == 0
        assert len(sample.incoming_settlements) == 1

    def test_empty_incoming_records(self) -> None:
        """Empty incoming records produces empty incoming in sample."""
        outgoing_records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=10,
                settlement_offset=5,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=outgoing_records,
            incoming_records=(),
            total_ticks=100,
        )

        assert len(sample.outgoing_txns) == 1
        assert len(sample.incoming_settlements) == 0

    def test_all_empty_records(self) -> None:
        """All empty records produces empty sample."""
        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=(),
            total_ticks=100,
        )

        assert len(sample.outgoing_txns) == 0
        assert len(sample.incoming_settlements) == 0


class TestMultipleSamplesGeneration:
    """Test generating multiple samples."""

    def test_generate_multiple_samples(self) -> None:
        """generate_samples creates multiple independent samples."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=i * 5,
                deadline_offset=10,
                settlement_offset=5,
            )
            for i in range(10)
        )

        sampler = BootstrapSampler(seed=42)
        samples = sampler.generate_samples(
            agent_id="BANK_A",
            n_samples=5,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        assert len(samples) == 5

        # Each sample should have unique sample_idx
        indices = [s.sample_idx for s in samples]
        assert indices == [0, 1, 2, 3, 4]

        # Each sample should have different arrival patterns
        # (extremely unlikely to be identical)
        arrival_patterns = [tuple(tx.arrival_tick for tx in s.outgoing_txns) for s in samples]
        unique_patterns = set(arrival_patterns)
        assert len(unique_patterns) == 5, "Each sample should have unique arrival pattern"


class TestTxIdUniqueness:
    """Test that tx_ids are made unique within a sample."""

    def test_tx_ids_unique_in_sample(self) -> None:
        """All tx_ids in a sample are unique (even if same source record)."""
        # Single record that might be sampled multiple times
        records = (
            TransactionRecord(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=10,
                settlement_offset=5,
            ),
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=records,
            incoming_records=(),
            total_ticks=100,
        )

        tx_ids = [tx.tx_id for tx in sample.outgoing_txns]
        assert len(tx_ids) == len(set(tx_ids)), "tx_ids should be unique"
