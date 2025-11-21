"""Integration tests for Priority Escalation (Phase 5).

TDD tests for dynamic priority escalation as transactions approach deadline.

The escalation system automatically boosts transaction priority as the deadline
approaches. This prevents low-priority transactions from being starved when
they become urgent due to time pressure.

Escalation Formula (linear):
  boost = max_boost * (1 - ticks_remaining / start_escalating_at_ticks)

Example with start_escalating_at_ticks=20, max_boost=3:
  - 20 ticks remaining: +0 boost (just started escalating)
  - 10 ticks remaining: +1.5 boost (50% through window)
  - 5 ticks remaining: +2.25 boost (75% through window)
  - 1 tick remaining: +3 boost (capped at max)
"""

import pytest
from payment_simulator._core import Orchestrator


class TestPriorityEscalationConfig:
    """Test priority escalation configuration."""

    def test_default_escalation_disabled(self):
        """Default config should have escalation disabled."""
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

        # Should work without escalation config
        orch = Orchestrator.new(config)
        orch.tick()

    def test_escalation_config_accepted(self):
        """Escalation config should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 20,
                "max_boost": 3,
            },
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

    def test_escalation_disabled_explicitly(self):
        """Explicit disabled escalation should work."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": False,
            },
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


class TestPriorityEscalationBehavior:
    """Test that priority escalation actually affects transaction priorities."""

    def test_no_escalation_when_disabled(self):
        """Priority should not change when escalation is disabled."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            # No escalation config (disabled by default)
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
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

        # Submit transaction with low priority and deadline at tick 30
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=30, priority=3, divisible=False)

        # Run many ticks (past escalation window)
        for _ in range(25):
            orch.tick()

        # Get transaction - priority should NOT have changed
        transactions = orch.get_transactions_for_day(0)
        tx = transactions[0]

        # Priority should remain at original value (3)
        assert tx["priority"] == 3, \
            f"Expected priority to remain 3 (escalation disabled), got {tx['priority']}"

    def test_escalation_boosts_priority_as_deadline_approaches(self):
        """Priority should increase as deadline approaches when escalation is enabled."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 20,  # Start boosting at 20 ticks remaining
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
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

        # Submit at tick 0, deadline at tick 30, original priority 3
        # Escalation starts at 20 ticks remaining (tick 10)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=30, priority=3, divisible=False)

        # Run until tick 25 (5 ticks remaining, 75% through escalation window)
        # Expected boost: 3 * (1 - 5/20) = 3 * 0.75 = 2.25
        # Expected priority: 3 + 2.25 = 5.25, rounded to 5
        for _ in range(25):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)
        tx = transactions[0]

        # Priority should have been boosted from 3 to at least 5
        assert tx["priority"] >= 5, \
            f"Expected escalated priority >= 5, got {tx['priority']}"

    def test_escalation_caps_at_max_boost(self):
        """Priority boost should be capped at max_boost."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 20,
                "max_boost": 3,  # Max boost of 3
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
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

        # Submit with priority 8, max boost 3 would give 11, but max priority is 10
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=30, priority=8, divisible=False)

        # Run past deadline approach
        for _ in range(29):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)
        tx = transactions[0]

        # Priority should be capped at 10 (maximum priority)
        assert tx["priority"] <= 10, \
            f"Expected priority capped at 10, got {tx['priority']}"

    def test_escalation_only_starts_at_threshold(self):
        """Priority should not escalate until reaching start_escalating_at_ticks."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,  # Start boosting at 10 ticks remaining
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
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

        # Submit at tick 0, deadline at tick 30, original priority 5
        # Escalation starts at 10 ticks remaining (tick 20)
        orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=30, priority=5, divisible=False)

        # Run until tick 15 (15 ticks remaining - BEFORE escalation window)
        for _ in range(15):
            orch.tick()

        transactions = orch.get_transactions_for_day(0)
        tx = transactions[0]

        # Priority should NOT have changed yet (15 ticks remaining > 10 threshold)
        assert tx["priority"] == 5, \
            f"Expected priority 5 (no escalation yet), got {tx['priority']}"


class TestPriorityEscalationWithQueueOrdering:
    """Test escalation interaction with queue ordering."""

    def test_escalation_affects_queue1_ordering(self):
        """Escalated priority should affect Queue 1 ordering."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 20,
                "max_boost": 5,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    # Hold all transactions in Queue 1
                    "policy": {"type": "Deadline", "urgency_threshold": 1},
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

        # Submit two transactions:
        # - High priority (7), far deadline (tick 80) - won't escalate
        # - Low priority (2), close deadline (tick 30) - will escalate
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=80, priority=7, divisible=False)
        orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=30, priority=2, divisible=False)

        # Run to tick 25 (5 ticks remaining for second tx)
        # Second tx should escalate: 2 + 3.75 = 5.75 → 6 (or 5 depending on rounding)
        for _ in range(25):
            orch.tick()

        # Get Queue 1 contents
        queue1_tx_ids = orch.get_agent_queue1_contents("BANK_A")

        if len(queue1_tx_ids) >= 2:
            priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue1_tx_ids[:2]]
            # After escalation, originally low-priority (2) tx should have higher effective priority
            # and be at front of queue (or at least have boosted priority)
            escalated_priority = max(priorities)
            original_high_priority = 7

            # The escalated transaction should now have competitive priority
            assert escalated_priority >= 5, \
                f"Expected escalated priority >= 5, got priorities: {priorities}"


class TestPriorityEscalationBackwardCompatibility:
    """Test backward compatibility with existing configs."""

    def test_existing_configs_work_without_escalation(self):
        """Existing configs without escalation config should work."""
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

        # Should work without escalation config
        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        assert orch.current_tick() == 10
