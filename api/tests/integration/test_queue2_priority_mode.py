"""Integration tests for Queue 2 Priority Mode (T2-style).

TDD tests for Phase 4 of priority system redesign.
Tests that Queue 2 can optionally process transactions by priority bands.

Priority Bands (T2-style):
- Urgent: priority 8-10
- Normal: priority 4-7
- Low: priority 0-3

When priority_mode is enabled, Queue 2 processes all urgent transactions
before normal, and all normal before low. Within each band, FIFO is preserved.
"""

import pytest
from payment_simulator._core import Orchestrator


class TestQueue2PriorityModeConfig:
    """Test Queue 2 priority mode configuration."""

    def test_default_priority_mode_is_disabled(self):
        """Default priority_mode should be False (backward compatible FIFO)."""
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

        # Should work without priority_mode specified
        orch = Orchestrator.new(config)
        orch.tick()

    def test_explicit_priority_mode_false_works(self):
        """Explicit priority_mode: false should work."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": False,  # Explicit disable
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

    def test_priority_mode_true_works(self):
        """Priority mode enabled should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,  # Enable T2-style priority
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


class TestQueue2PriorityModeBehavior:
    """Test that priority mode actually affects Queue 2 processing order."""

    def test_fifo_mode_processes_queue2_by_arrival_order(self):
        """With priority_mode disabled, Queue 2 should process by arrival (FIFO)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": False,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - will need Queue 2
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
        # Low priority first, then high priority
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=1, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)

        # Run tick - all should go to Queue 2 due to insufficient liquidity
        orch.tick()

        # Check Queue 2 contents - should be in arrival order (FIFO)
        queue2_tx_ids = orch.get_queue2_contents()

        assert len(queue2_tx_ids) >= 3, f"Expected 3 transactions in Queue 2, got {len(queue2_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_tx_ids[:3]]
        assert priorities == [1, 9, 5], f"Expected FIFO order [1, 9, 5], got {priorities}"

    def test_priority_mode_reorders_queue2_by_priority_bands(self):
        """With priority_mode enabled, Queue 2 should reorder by priority bands.

        This is the KEY test for priority mode - Queue 2 should be reordered so that:
        - Urgent (8-10) transactions come first
        - Normal (4-7) transactions come second
        - Low (0-3) transactions come last
        Within each band, FIFO is preserved.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - all go to Queue 2
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

        # Submit in reverse priority band order: low, normal, urgent
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=2, divisible=False)   # Low (first submitted)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)   # Normal (second)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9, divisible=False)   # Urgent (third)

        # Run tick to process into Queue 2 - priority_mode should reorder
        orch.tick()

        # Check Queue 2 contents - should be reordered by priority bands
        queue2_tx_ids = orch.get_queue2_contents()

        assert len(queue2_tx_ids) >= 3, f"Expected 3 transactions in Queue 2, got {len(queue2_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_tx_ids[:3]]

        # With priority_mode=True, should be reordered: urgent(9) first, then normal(5), then low(2)
        assert priorities == [9, 5, 2], \
            f"Expected priority-band order [9, 5, 2] (urgent, normal, low), got {priorities}"

    def test_priority_mode_preserves_fifo_within_same_band(self):
        """Within the same priority band, FIFO should be preserved."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - all go to Queue 2
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

        # Submit multiple normal-band transactions in specific order
        # All are priority 4-7 (normal band), should preserve submission order within band
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=6, divisible=False)  # First normal
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=4, divisible=False)  # Second normal
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=7, divisible=False)  # Third normal

        # Run tick
        orch.tick()

        queue2_tx_ids = orch.get_queue2_contents()

        assert len(queue2_tx_ids) >= 3, f"Expected 3 transactions in Queue 2, got {len(queue2_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_tx_ids[:3]]

        # All in same band (normal), so FIFO order preserved: [6, 4, 7] (submission order)
        assert priorities == [6, 4, 7], \
            f"Expected FIFO within band [6, 4, 7], got {priorities}"

    def test_priority_mode_complex_ordering(self):
        """Test complex scenario with multiple transactions in each band."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - all go to Queue 2
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

        # Submit in mixed order
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=3, divisible=False)   # Low (first)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=8, divisible=False)   # Urgent (second)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)   # Normal (third)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=1, divisible=False)   # Low (fourth)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9, divisible=False)   # Urgent (fifth)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=6, divisible=False)   # Normal (sixth)

        # Run tick
        orch.tick()

        queue2_tx_ids = orch.get_queue2_contents()

        assert len(queue2_tx_ids) >= 6, f"Expected 6 transactions in Queue 2, got {len(queue2_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_tx_ids[:6]]

        # Expected order:
        # - Urgent band (8-10), FIFO: [8, 9] (8 was submitted before 9)
        # - Normal band (4-7), FIFO: [5, 6] (5 was submitted before 6)
        # - Low band (0-3), FIFO: [3, 1] (3 was submitted before 1)
        expected = [8, 9, 5, 6, 3, 1]
        assert priorities == expected, \
            f"Expected priority-band order {expected}, got {priorities}"


class TestQueue2PriorityModeWithQueue1Ordering:
    """Test interaction between Queue 1 ordering and Queue 2 priority mode."""

    def test_queue1_priority_and_queue2_priority_mode_together(self):
        """Both Queue 1 priority ordering and Queue 2 priority mode should work together."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "priority_mode": True,
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

        # Should work with both enabled
        orch = Orchestrator.new(config)
        for _ in range(5):
            orch.tick()

    def test_queue1_priority_affects_queue2_entry_order(self):
        """Transactions should enter Queue 2 in Queue 1's priority order."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "priority_mode": False,  # Disable Queue 2 priority to see entry order
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions go to Queue 2
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

        # Submit in reverse priority order
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=1, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)

        # Run tick to process through Queue 1 (with priority ordering) to Queue 2
        orch.tick()

        # Queue 2 should have transactions in the order they came from Queue 1
        # (which was priority-ordered: 9, 5, 1)
        queue2_tx_ids = orch.get_queue2_contents()

        assert len(queue2_tx_ids) >= 3, f"Expected 3 transactions in Queue 2, got {len(queue2_tx_ids)}"
        priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_tx_ids[:3]]
        # With Queue 1 priority ordering, high priority should have been released first
        # and thus entered Queue 2 first
        assert priorities == [9, 5, 1], \
            f"Expected Queue 2 order [9, 5, 1] from Queue 1 priority, got {priorities}"


class TestQueue2PriorityModeBackwardCompatibility:
    """Test backward compatibility with existing configs."""

    def test_existing_configs_work_without_priority_mode(self):
        """Existing configs without priority_mode should work (default to False)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            # No priority_mode specified
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

        # Should work without priority_mode
        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        # Simulation should complete successfully
        assert orch.current_tick() == 10
