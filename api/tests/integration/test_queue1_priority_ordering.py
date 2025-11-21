"""Integration tests for Queue 1 priority ordering.

TDD tests for Phase 2 of priority system redesign.
Tests that Queue 1 can optionally order transactions by priority.
"""

import pytest
from payment_simulator._core import Orchestrator


class TestQueue1PriorityOrderingConfig:
    """Test Queue 1 ordering configuration."""

    def test_default_queue1_ordering_is_fifo(self):
        """Default Queue 1 ordering should be FIFO (backward compatible)."""
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
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Should work without queue1_ordering specified
        orch = Orchestrator.new(config)
        orch.tick()

    def test_explicit_fifo_ordering_works(self):
        """Explicit FIFO ordering should work."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "fifo",  # Explicit FIFO
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
        orch.tick()

    def test_priority_deadline_ordering_works(self):
        """Priority-deadline ordering should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",  # Priority ordering
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
        orch.tick()


class TestQueue1PriorityOrderingBehavior:
    """Test that priority ordering actually affects queue iteration order."""

    def test_fifo_ordering_processes_by_arrival_order(self):
        """FIFO ordering should process transactions in arrival order."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "fifo",
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - can't settle anything
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # Submit transactions with different priorities
        # Submit high priority first
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=9, divisible=False)
        # Then low priority
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=1, divisible=False)
        # Then medium priority
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=5, divisible=False)

        # Get queue contents - returns tx_ids, need to fetch details
        queue_tx_ids = orch.get_agent_queue1_contents("BANK_A")

        # In FIFO mode, order should match submission order
        # First submitted (priority 9) should be first in queue
        assert len(queue_tx_ids) >= 3
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue_tx_ids[:3]]
        assert priorities == [9, 1, 5], f"Expected FIFO order [9, 1, 5], got {priorities}"

    def test_priority_deadline_ordering_sorts_by_priority(self):
        """Priority-deadline ordering should sort high priority first."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    # DeadlinePolicy holds non-urgent transactions (deadline > urgency_threshold)
                    "policy": {"type": "Deadline", "urgency_threshold": 1},  # Very low - holds most
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

        # Submit transactions with different priorities (in "wrong" order)
        # All have deadline=50, urgency_threshold=1 means ticks_remaining=50 > 1, so held
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=3, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=9, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=1, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=7, divisible=False)

        # Run tick to apply queue sorting (sorting happens before policy evaluation)
        orch.tick()

        # Get queue contents - should be sorted by priority (descending)
        queue_tx_ids = orch.get_agent_queue1_contents("BANK_A")

        assert len(queue_tx_ids) >= 4, f"Expected 4 transactions in queue, got {len(queue_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue_tx_ids[:4]]

        # Priority-deadline ordering: high priority first
        # Expected: [9, 7, 3, 1]
        assert priorities == [9, 7, 3, 1], \
            f"Expected priority order [9, 7, 3, 1], got {priorities}"

    def test_priority_deadline_ordering_uses_deadline_as_tiebreaker(self):
        """Same priority should be ordered by deadline (soonest first)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    # DeadlinePolicy holds non-urgent transactions (deadline > urgency_threshold)
                    "policy": {"type": "Deadline", "urgency_threshold": 1},  # Very low - holds most
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

        # All same priority, different deadlines
        # With urgency_threshold=1, these will be held since ticks_remaining > 1
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=5, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=20, priority=5, divisible=False)  # Soonest
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=35, priority=5, divisible=False)

        # Run tick to apply queue sorting (sorting happens before policy evaluation)
        orch.tick()

        queue_tx_ids = orch.get_agent_queue1_contents("BANK_A")

        assert len(queue_tx_ids) >= 3, f"Expected 3 transactions in queue, got {len(queue_tx_ids)}"
        deadlines = [orch.get_transaction_details(tx_id)["deadline_tick"] for tx_id in queue_tx_ids[:3]]

        # Same priority, order by deadline (soonest first)
        assert deadlines == [20, 35, 50], \
            f"Expected deadline order [20, 35, 50], got {deadlines}"

    def test_priority_ordering_affects_policy_evaluation_order(self):
        """High-priority transactions should be evaluated first by policy."""
        # This test verifies that when a policy processes Queue 1,
        # high-priority transactions are considered first.

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 15000,  # Can only settle ONE transaction
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},  # FIFO policy releases in queue order
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

        # Submit low priority first, then high priority
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=1, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=50, priority=9, divisible=False)

        # Run one tick - with limited liquidity, only one can settle
        orch.tick()

        # Get transactions to see which settled
        transactions = orch.get_transactions_for_day(0)

        # Find settled and pending transactions
        settled = [tx for tx in transactions if tx["status"] == "settled"]

        # With priority ordering, the high-priority transaction (p=9) should settle first
        if len(settled) == 1:
            assert settled[0]["priority"] == 9, \
                f"Expected high-priority (9) to settle first, but got priority {settled[0]['priority']}"


class TestQueue1OrderingBackwardCompatibility:
    """Test backward compatibility with existing configs."""

    def test_existing_configs_work_without_queue1_ordering(self):
        """Existing configs without queue1_ordering should work (default to FIFO)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            # No queue1_ordering specified
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

        # Should work without queue1_ordering
        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        # Simulation should complete successfully
        assert orch.current_tick() == 10
