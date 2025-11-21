"""Integration tests for priority distribution FFI.

Tests that priority distributions are correctly passed to Rust
and sampled during transaction generation.
"""

import pytest
from collections import Counter

from payment_simulator._core import Orchestrator


class TestPriorityDistributionSampling:
    """Test that Rust correctly samples from priority distributions."""

    def test_fixed_priority_generates_same_value(self):
        """Fixed priority (legacy) generates all transactions with same priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 5.0,  # Generate many transactions
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 7,  # Legacy single value
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run a few ticks to generate transactions
        for _ in range(10):
            orch.tick()

        # Get all transactions
        transactions = orch.get_transactions_for_day(0)

        # All should have priority 7
        for tx in transactions:
            assert tx["priority"] == 7, f"Expected priority 7, got {tx['priority']}"

    def test_categorical_priority_distribution_samples_correctly(self):
        """Categorical distribution samples from specified values with weights."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 10.0,  # Generate many transactions
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority_distribution": {
                            "type": "Categorical",
                            "values": [3, 5, 7, 9],
                            "weights": [0.25, 0.50, 0.15, 0.10],
                        },
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run many ticks to generate sufficient transactions
        for _ in range(50):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)

        # Count priorities
        priority_counts = Counter(tx["priority"] for tx in transactions)

        # Should only see priorities 3, 5, 7, 9
        assert set(priority_counts.keys()).issubset({3, 5, 7, 9}), \
            f"Unexpected priorities: {set(priority_counts.keys()) - {3, 5, 7, 9}}"

        # With enough samples, priority 5 should be most common (50% weight)
        # This is probabilistic, so we use a loose check
        if len(transactions) > 50:
            assert priority_counts[5] > priority_counts[9], \
                f"Expected priority 5 to be more common than 9: {priority_counts}"

    def test_uniform_priority_distribution_samples_in_range(self):
        """Uniform distribution samples within specified range."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 10.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority_distribution": {
                            "type": "Uniform",
                            "min": 3,
                            "max": 8,
                        },
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run many ticks
        for _ in range(50):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)

        # All priorities should be in range [3, 8]
        for tx in transactions:
            assert 3 <= tx["priority"] <= 8, \
                f"Priority {tx['priority']} out of range [3, 8]"

        # Check we get some variation (not all the same)
        priorities = [tx["priority"] for tx in transactions]
        if len(priorities) > 10:
            assert len(set(priorities)) > 1, "Expected variation in priorities"

    def test_priority_distribution_determinism(self):
        """Same seed produces same priority distribution."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 5.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority_distribution": {
                            "type": "Categorical",
                            "values": [1, 5, 9],
                            "weights": [0.3, 0.4, 0.3],
                        },
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run twice with same seed
        orch1 = Orchestrator.new(config)
        for _ in range(20):
            orch1.tick()
        # Sort by deterministic keys (arrival_tick, sender_id, amount) since tx_id is UUID
        txs1 = sorted(
            orch1.get_transactions_for_day(0),
            key=lambda t: (t["arrival_tick"], t["sender_id"], t["amount"])
        )
        priorities1 = [tx["priority"] for tx in txs1]

        orch2 = Orchestrator.new(config)
        for _ in range(20):
            orch2.tick()
        txs2 = sorted(
            orch2.get_transactions_for_day(0),
            key=lambda t: (t["arrival_tick"], t["sender_id"], t["amount"])
        )
        priorities2 = [tx["priority"] for tx in txs2]

        # Should be identical when sorted by deterministic keys
        assert priorities1 == priorities2, "Determinism violated"

    def test_different_agents_can_have_different_distributions(self):
        """Different agents can have different priority distributions."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 5.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0, "BANK_C": 1.0},
                        "deadline_range": [10, 50],
                        # Low priority distribution
                        "priority_distribution": {
                            "type": "Categorical",
                            "values": [1, 2, 3],
                            "weights": [0.33, 0.34, 0.33],
                        },
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 5.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_A": 1.0, "BANK_C": 1.0},
                        "deadline_range": [10, 50],
                        # High priority distribution
                        "priority_distribution": {
                            "type": "Categorical",
                            "values": [8, 9, 10],
                            "weights": [0.33, 0.34, 0.33],
                        },
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(30):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)

        # Separate by sender
        bank_a_priorities = [tx["priority"] for tx in transactions if tx["sender_id"] == "BANK_A"]
        bank_b_priorities = [tx["priority"] for tx in transactions if tx["sender_id"] == "BANK_B"]

        # BANK_A should have low priorities (1, 2, 3)
        if bank_a_priorities:
            assert all(p in [1, 2, 3] for p in bank_a_priorities), \
                f"BANK_A unexpected priorities: {set(bank_a_priorities)}"

        # BANK_B should have high priorities (8, 9, 10)
        if bank_b_priorities:
            assert all(p in [8, 9, 10] for p in bank_b_priorities), \
                f"BANK_B unexpected priorities: {set(bank_b_priorities)}"


class TestPriorityDistributionBackwardCompatibility:
    """Test backward compatibility with existing configs."""

    def test_existing_config_format_works(self):
        """Existing config format with single priority should work."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,  # Old format
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Should not raise
        orch = Orchestrator.new(config)
        for _ in range(5):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)
        assert all(tx["priority"] == 5 for tx in transactions)

    def test_default_priority_when_omitted(self):
        """Default priority should be 5 when omitted entirely."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 10000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        # No priority specified
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)
        for _ in range(5):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)
        # Default priority is 5
        assert all(tx["priority"] == 5 for tx in transactions)
