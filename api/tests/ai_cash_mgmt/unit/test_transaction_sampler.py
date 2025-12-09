"""Unit tests for TransactionSampler - Monte Carlo transaction sampling.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestHistoricalTransaction:
    """Test historical transaction dataclass."""

    def test_historical_transaction_creation(self) -> None:
        """HistoricalTransaction should be creatable with required fields."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            HistoricalTransaction,
        )

        tx = HistoricalTransaction(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=10,
            deadline_tick=20,
            is_divisible=True,
        )

        assert tx.tx_id == "TX001"
        assert tx.sender_id == "BANK_A"
        assert tx.receiver_id == "BANK_B"
        assert tx.amount == 100000
        assert tx.priority == 5
        assert tx.arrival_tick == 10
        assert tx.deadline_tick == 20
        assert tx.is_divisible is True

    def test_historical_transaction_is_immutable(self) -> None:
        """HistoricalTransaction should be frozen (immutable)."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            HistoricalTransaction,
        )

        tx = HistoricalTransaction(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=10,
            deadline_tick=20,
            is_divisible=True,
        )

        with pytest.raises(AttributeError):
            tx.amount = 200000  # type: ignore[misc]

    def test_historical_transaction_to_dict(self) -> None:
        """HistoricalTransaction should convert to dict for simulation injection."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            HistoricalTransaction,
        )

        tx = HistoricalTransaction(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=10,
            deadline_tick=20,
            is_divisible=True,
        )

        data = tx.to_dict()

        assert data["sender_id"] == "BANK_A"
        assert data["receiver_id"] == "BANK_B"
        assert data["amount"] == 100000
        assert data["priority"] == 5
        assert data["deadline_ticks"] == 10  # deadline_tick - arrival_tick
        assert data["is_divisible"] is True


class TestTransactionSamplerCollection:
    """Test transaction collection functionality."""

    def test_sampler_collects_transactions(self) -> None:
        """TransactionSampler should collect transactions from simulation data."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)

        transactions = [
            {
                "tx_id": "TX001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "arrival_tick": 10,
                "deadline_tick": 20,
                "is_divisible": True,
            },
            {
                "tx_id": "TX002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_C",
                "amount": 200000,
                "priority": 7,
                "arrival_tick": 15,
                "deadline_tick": 25,
                "is_divisible": False,
            },
        ]

        sampler.collect_transactions(transactions)

        assert sampler.transaction_count == 2

    def test_sampler_handles_optional_fields(self) -> None:
        """TransactionSampler should handle missing optional fields with defaults."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)

        # Missing priority and is_divisible
        transactions = [
            {
                "tx_id": "TX001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "arrival_tick": 10,
                "deadline_tick": 20,
            },
        ]

        sampler.collect_transactions(transactions)

        # Should use defaults
        assert sampler.transaction_count == 1


class TestBootstrapSampling:
    """Test bootstrap resampling (with replacement)."""

    def test_bootstrap_sample_returns_correct_count(self) -> None:
        """Bootstrap should return requested number of samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(_create_test_transactions(10))

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="bootstrap",
        )

        assert len(samples) == 5

    def test_bootstrap_sample_with_replacement(self) -> None:
        """Bootstrap sampling should sample with replacement (duplicates possible)."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        # Create small set to ensure duplicates
        sampler.collect_transactions(_create_test_transactions(5, agent="BANK_A"))

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=10,
            method="bootstrap",
        )

        # Each sample should have same size as original (5 transactions)
        for sample in samples:
            assert len(sample) == 5

    def test_same_seed_produces_identical_bootstrap_samples(self) -> None:
        """Same seed should produce identical bootstrap samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_test_transactions(20, agent="BANK_A")

        sampler1 = TransactionSampler(seed=12345)
        sampler1.collect_transactions(transactions)
        samples1 = sampler1.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="bootstrap",
        )

        sampler2 = TransactionSampler(seed=12345)
        sampler2.collect_transactions(transactions)
        samples2 = sampler2.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="bootstrap",
        )

        # Convert to comparable format
        for i in range(5):
            ids1 = [tx.tx_id for tx in samples1[i]]
            ids2 = [tx.tx_id for tx in samples2[i]]
            assert ids1 == ids2, f"Sample {i} differs"


class TestPermutationSampling:
    """Test permutation sampling (shuffle order)."""

    def test_permutation_sample_preserves_all_transactions(self) -> None:
        """Permutation should keep all transactions, just reorder them."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = _create_test_transactions(10, agent="BANK_A")
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=3,
            method="permutation",
        )

        original_ids = {f"TX{i:03d}" for i in range(10)}

        for sample in samples:
            sample_ids = {tx.tx_id for tx in sample}
            assert sample_ids == original_ids, "Permutation should preserve all transactions"

    def test_permutation_produces_different_orders(self) -> None:
        """Permutation should produce different orderings."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = _create_test_transactions(20, agent="BANK_A")
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="permutation",
        )

        # At least some samples should have different orders
        orders = [tuple(tx.tx_id for tx in sample) for sample in samples]
        assert len(set(orders)) > 1, "Should produce different orderings"


class TestStratifiedSampling:
    """Test stratified sampling by amount buckets."""

    def test_stratified_sample_maintains_distribution(self) -> None:
        """Stratified sampling should maintain amount distribution."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        # Create transactions with varying amounts
        transactions = _create_test_transactions_varied_amounts(30, agent="BANK_A")
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="stratified",
        )

        # All samples should have transactions
        for sample in samples:
            assert len(sample) > 0


class TestAgentFiltering:
    """Test transaction filtering by agent."""

    def test_filter_by_agent_includes_sender_transactions(self) -> None:
        """Filter should include transactions where agent is sender."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = [
            _tx("TX001", "BANK_A", "BANK_B"),  # BANK_A is sender
            _tx("TX002", "BANK_B", "BANK_C"),  # Not involving BANK_A
            _tx("TX003", "BANK_A", "BANK_C"),  # BANK_A is sender
        ]
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=1,
            method="bootstrap",
        )

        # Should only include TX001 and TX003
        tx_ids = {tx.tx_id for tx in samples[0]}
        assert "TX001" in tx_ids or "TX003" in tx_ids
        assert "TX002" not in tx_ids

    def test_filter_by_agent_includes_receiver_transactions(self) -> None:
        """Filter should include transactions where agent is receiver."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = [
            _tx("TX001", "BANK_B", "BANK_A"),  # BANK_A is receiver
            _tx("TX002", "BANK_B", "BANK_C"),  # Not involving BANK_A
            _tx("TX003", "BANK_C", "BANK_A"),  # BANK_A is receiver
        ]
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=1,
            method="bootstrap",
        )

        # Should only include TX001 and TX003
        tx_ids = {tx.tx_id for tx in samples[0]}
        assert "TX001" in tx_ids or "TX003" in tx_ids
        assert "TX002" not in tx_ids


class TestTickFiltering:
    """Test transaction filtering by tick."""

    def test_filter_by_max_tick_excludes_future_transactions(self) -> None:
        """Filter should exclude transactions arriving after max_tick."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = [
            _tx("TX001", "BANK_A", "BANK_B", arrival_tick=5),
            _tx("TX002", "BANK_A", "BANK_B", arrival_tick=10),
            _tx("TX003", "BANK_A", "BANK_B", arrival_tick=15),
            _tx("TX004", "BANK_A", "BANK_B", arrival_tick=20),
        ]
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=1,
            max_tick=12,
            method="bootstrap",
        )

        # Should only include TX001, TX002 (arrival_tick <= 12)
        all_tx_ids = {tx.tx_id for sample in samples for tx in sample}
        assert "TX003" not in all_tx_ids
        assert "TX004" not in all_tx_ids


class TestEmptySamples:
    """Test handling of empty samples."""

    def test_empty_transactions_returns_empty_samples(self) -> None:
        """Empty transaction list should return empty samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        # Don't collect any transactions

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=5,
            method="bootstrap",
        )

        assert len(samples) == 5
        for sample in samples:
            assert len(sample) == 0

    def test_no_matching_agent_returns_empty_samples(self) -> None:
        """No transactions for agent should return empty samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        transactions = [
            _tx("TX001", "BANK_B", "BANK_C"),
            _tx("TX002", "BANK_C", "BANK_D"),
        ]
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",  # Not in any transaction
            num_samples=3,
            method="bootstrap",
        )

        for sample in samples:
            assert len(sample) == 0


class TestSubseedDerivation:
    """Test deterministic subseed derivation."""

    def test_derive_subseed_is_deterministic(self) -> None:
        """Derived subseed should be deterministic."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler1 = TransactionSampler(seed=42)
        sampler2 = TransactionSampler(seed=42)

        subseed1 = sampler1.derive_subseed(iteration=5, agent_id="BANK_A")
        subseed2 = sampler2.derive_subseed(iteration=5, agent_id="BANK_A")

        assert subseed1 == subseed2

    def test_derive_subseed_differs_by_iteration(self) -> None:
        """Different iterations should produce different subseeds."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)

        subseed1 = sampler.derive_subseed(iteration=0, agent_id="BANK_A")
        subseed2 = sampler.derive_subseed(iteration=1, agent_id="BANK_A")

        assert subseed1 != subseed2

    def test_derive_subseed_differs_by_agent(self) -> None:
        """Different agents should produce different subseeds."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)

        subseed1 = sampler.derive_subseed(iteration=0, agent_id="BANK_A")
        subseed2 = sampler.derive_subseed(iteration=0, agent_id="BANK_B")

        assert subseed1 != subseed2


class TestUnknownSamplingMethod:
    """Test error handling for unknown methods."""

    def test_unknown_method_raises_error(self) -> None:
        """Unknown sampling method should raise ValueError."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(_create_test_transactions(5))

        with pytest.raises(ValueError, match="Unknown sampling method"):
            sampler.create_samples(
                agent_id="BANK_A",
                num_samples=1,
                method="invalid_method",
            )


# Helper functions for creating test data


def _create_test_transactions(
    count: int, agent: str = "BANK_A"
) -> list[dict[str, object]]:
    """Create test transactions involving a specific agent."""
    return [
        {
            "tx_id": f"TX{i:03d}",
            "sender_id": agent if i % 2 == 0 else "OTHER",
            "receiver_id": "OTHER" if i % 2 == 0 else agent,
            "amount": 100000 + i * 1000,
            "priority": 5,
            "arrival_tick": i,
            "deadline_tick": i + 10,
            "is_divisible": True,
        }
        for i in range(count)
    ]


def _create_test_transactions_varied_amounts(
    count: int, agent: str = "BANK_A"
) -> list[dict[str, object]]:
    """Create test transactions with varied amounts for stratified testing."""
    return [
        {
            "tx_id": f"TX{i:03d}",
            "sender_id": agent if i % 2 == 0 else "OTHER",
            "receiver_id": "OTHER" if i % 2 == 0 else agent,
            "amount": (i % 10 + 1) * 100000,  # Amounts from 100k to 1M
            "priority": 5,
            "arrival_tick": i,
            "deadline_tick": i + 10,
            "is_divisible": True,
        }
        for i in range(count)
    ]


def _tx(
    tx_id: str,
    sender: str,
    receiver: str,
    arrival_tick: int = 10,
) -> dict[str, object]:
    """Create a minimal test transaction."""
    return {
        "tx_id": tx_id,
        "sender_id": sender,
        "receiver_id": receiver,
        "amount": 100000,
        "priority": 5,
        "arrival_tick": arrival_tick,
        "deadline_tick": arrival_tick + 10,
        "is_divisible": True,
    }
