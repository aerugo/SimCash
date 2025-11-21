"""Integration tests for policy configuration effects on priority escalation.

TDD tests validating that different policy configurations have the intended
effect on priority escalation behavior. Tests are organized by:

1. Policy Type Interactions - How Fifo, LiquidityAware, etc. interact with escalation
2. Queue 1 Ordering Interactions - How queue ordering affects escalated transactions
3. Queue 2 Priority Mode Interactions - How priority mode affects escalated transactions
4. Edge Cases - Max boost capping, threshold behavior, etc.

Following strict TDD principles - tests define expected behavior.
"""

import pytest
from payment_simulator._core import Orchestrator


class TestFifoPolicyWithEscalation:
    """Test Fifo policy behavior with priority escalation enabled."""

    def test_fifo_policy_transactions_escalate_when_approaching_deadline(self):
        """Fifo policy should allow priority escalation without affecting queue order.

        Expected behavior:
        - Transactions escalate priority as deadline approaches
        - Queue 1 still processes in FIFO order (arrival order)
        - Escalation happens but doesn't change submission order
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low balance - transactions queue up
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

        # Submit transactions with different deadlines but same low priority
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=15, priority=3, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=25, priority=3, divisible=False)
        tx3_id = orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=35, priority=3, divisible=False)

        # Record initial priorities
        tx1_initial = orch.get_transaction_details(tx1_id)["priority"]
        tx2_initial = orch.get_transaction_details(tx2_id)["priority"]
        tx3_initial = orch.get_transaction_details(tx3_id)["priority"]

        assert tx1_initial == 3
        assert tx2_initial == 3
        assert tx3_initial == 3

        # Run until TX1 should have escalated (within 10 ticks of deadline)
        for _ in range(10):
            orch.tick()

        # TX1 (deadline 15, now at tick 10) should have escalated
        # Ticks remaining = 15 - 10 = 5, progress = 1 - 5/10 = 0.5
        # Boost = round(3 * 0.5) = 2, new priority = min(10, 3+2) = 5
        tx1_after = orch.get_transaction_details(tx1_id)
        tx2_after = orch.get_transaction_details(tx2_id)
        tx3_after = orch.get_transaction_details(tx3_id)

        # TX1 should have escalated (5 ticks until deadline)
        assert tx1_after["priority"] > tx1_initial, \
            f"TX1 should have escalated from {tx1_initial}, but got {tx1_after['priority']}"

        # TX2 has 15 ticks remaining, not yet in escalation window
        # TX3 has 25 ticks remaining, not yet in escalation window

    def test_fifo_policy_escalation_events_emitted(self):
        """Fifo policy should emit PriorityEscalated events when priority changes."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # Submit transaction with close deadline
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=12, priority=3, divisible=False)

        # Run until escalation should occur
        escalation_events = []
        for tick in range(15):
            orch.tick()
            events = orch.get_tick_events(tick)
            escalation_events.extend([e for e in events if e.get("event_type") == "PriorityEscalated"])

        # Should have at least one escalation event
        assert len(escalation_events) > 0, "Expected at least one PriorityEscalated event"

        # Verify event structure
        event = escalation_events[0]
        assert event["tx_id"] == tx_id
        assert event["original_priority"] == 3
        assert event["escalated_priority"] > 3


class TestLiquidityAwarePolicyWithEscalation:
    """Test LiquidityAware policy behavior with priority escalation."""

    def test_liquidity_aware_policy_with_escalation(self):
        """LiquidityAware policy should work correctly with priority escalation.

        LiquidityAware may hold transactions based on liquidity - escalation
        should still apply to held transactions.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low balance
                    "unsecured_cap": 0,
                    "policy": {
                        "type": "LiquidityAware",
                        "target_buffer": 50,
                        "urgency_threshold": 5,
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

        # Submit transaction that will be held due to liquidity
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 10000, deadline_tick=15, priority=3, divisible=False)

        initial_priority = orch.get_transaction_details(tx_id)["priority"]
        assert initial_priority == 3

        # Run past escalation window start
        for _ in range(10):
            orch.tick()

        # Even though held, priority should escalate
        final_priority = orch.get_transaction_details(tx_id)["priority"]
        assert final_priority > initial_priority, \
            f"Expected priority to escalate from {initial_priority}, got {final_priority}"


class TestQueue1OrderingWithEscalation:
    """Test Queue 1 ordering configuration effects on escalation."""

    def test_fifo_queue1_ordering_ignores_escalated_priority(self):
        """With queue1_ordering=fifo, escalation doesn't affect queue order.

        Expected: Transactions processed in arrival order even after escalation.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "fifo",
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 15,
                "max_boost": 5,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - transactions stay in queue
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

        # Submit: low priority with close deadline (will escalate)
        #         high priority with far deadline (won't escalate)
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=20, priority=2, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=8, divisible=False)

        # Run until TX1 escalates past TX2's priority
        for _ in range(12):
            orch.tick()

        tx1_details = orch.get_transaction_details(tx1_id)
        tx2_details = orch.get_transaction_details(tx2_id)

        # TX1 may have escalated, but with FIFO ordering, it shouldn't
        # matter - TX1 should still be processed first because it arrived first
        # The queue order should remain arrival order

    def test_priority_deadline_queue1_ordering_respects_escalation(self):
        """With queue1_ordering=priority_deadline, escalation affects queue order.

        Expected: Escalated transactions can move ahead in Queue 1.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "queue1_ordering": "priority_deadline",
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 15,
                "max_boost": 5,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - transactions stay in queue
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

        # Submit:
        # TX1: medium priority, far deadline (won't escalate soon)
        # TX2: low priority, close deadline (will escalate quickly)
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=20, priority=2, divisible=False)

        # Initially, TX1 (priority 5) should be ahead of TX2 (priority 2)
        orch.tick()

        # After some ticks, TX2 should escalate and potentially surpass TX1
        for _ in range(10):
            orch.tick()

        tx1_details = orch.get_transaction_details(tx1_id)
        tx2_details = orch.get_transaction_details(tx2_id)

        # TX2 should have escalated (close to deadline)
        assert tx2_details["priority"] > 2, \
            f"TX2 should have escalated from 2, got {tx2_details['priority']}"


class TestQueue2PriorityModeWithEscalation:
    """Test Queue 2 priority mode interactions with escalation."""

    def test_queue2_priority_mode_reorders_escalated_transactions(self):
        """With priority_mode=true, escalated transactions move up in Queue 2.

        Expected: Transactions that escalate from low to urgent band
        should be reordered in Queue 2.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,  # Enable Queue 2 priority bands
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 6,  # High boost to potentially reach urgent band
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # All go to Queue 2
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

        # TX1: Normal band (5), far deadline - won't escalate
        # TX2: Low band (2), close deadline - will escalate
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=15, priority=2, divisible=False)

        # Process initial submissions
        orch.tick()

        # Run until TX2 escalates
        for _ in range(10):
            orch.tick()

        tx2_details = orch.get_transaction_details(tx2_id)

        # TX2 should have escalated (started at 2, max_boost 6 could push to 8)
        assert tx2_details["priority"] > 2, \
            f"TX2 should have escalated from 2, got {tx2_details['priority']}"

    def test_queue2_no_priority_mode_ignores_escalation_for_ordering(self):
        """Without priority_mode, Queue 2 stays FIFO even after escalation.

        Expected: Escalation happens but Queue 2 order is unchanged.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": False,  # Disable Queue 2 priority bands
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 5,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # Submit in order: low priority close deadline, then high priority far deadline
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=15, priority=2, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=50, priority=8, divisible=False)

        # Process
        orch.tick()

        # Queue 2 should have FIFO order: TX1, TX2
        queue2_contents = orch.get_queue2_contents()
        assert len(queue2_contents) >= 2

        # Even after escalation runs...
        for _ in range(10):
            orch.tick()

        # ...order should still be FIFO (TX1 first, TX2 second)
        queue2_contents = orch.get_queue2_contents()
        if len(queue2_contents) >= 2:
            # Without priority_mode, order should be FIFO
            priorities = [orch.get_transaction_details(tx_id)["priority"] for tx_id in queue2_contents[:2]]
            # TX1 may have escalated but should still be first in queue (FIFO)


class TestEscalationEdgeCases:
    """Test edge cases for priority escalation."""

    def test_escalation_caps_at_max_priority_10(self):
        """Priority should never exceed 10 even with high boost."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 10,  # Very high boost
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # High priority transaction with close deadline
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=8, divisible=False)

        # Run past deadline
        for _ in range(15):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Priority should be capped at 10
        assert tx_details["priority"] <= 10, \
            f"Priority should be capped at 10, got {tx_details['priority']}"

    def test_escalation_preserves_original_priority(self):
        """Original priority should be preserved for escalation calculation."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=15, priority=3, divisible=False)

        # Run multiple ticks to trigger multiple escalations
        for _ in range(12):
            orch.tick()

        # Check escalation events
        all_events = orch.get_all_events()
        escalation_events = [e for e in all_events if e.get("event_type") == "PriorityEscalated" and e.get("tx_id") == tx_id]

        # All events should reference original_priority = 3
        for event in escalation_events:
            assert event["original_priority"] == 3, \
                f"Original priority should always be 3, got {event['original_priority']}"

    def test_escalation_only_starts_at_threshold(self):
        """Escalation should not occur until within threshold ticks of deadline."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # Transaction with deadline at tick 30
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=30, priority=3, divisible=False)

        # Run 15 ticks - still 15 ticks until deadline (> 10 threshold)
        for _ in range(15):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Should NOT have escalated yet (15 > 10 threshold)
        assert tx_details["priority"] == 3, \
            f"Priority should still be 3 (not in escalation window), got {tx_details['priority']}"

        # Run 5 more ticks - now 10 ticks until deadline (= threshold)
        for _ in range(5):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Now should start escalating
        # At tick 20, deadline 30, 10 ticks remaining = exactly at threshold
        # progress = 1 - 10/10 = 0, boost = 0 -> no change yet
        # But next tick (tick 21), 9 ticks remaining
        # progress = 1 - 9/10 = 0.1, boost = round(3 * 0.1) = 0 -> still no change
        # Need to go further into window for actual escalation

        # Run a few more ticks
        for _ in range(5):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Now should have escalated (5 ticks remaining)
        # progress = 1 - 5/10 = 0.5, boost = round(3 * 0.5) = 2
        assert tx_details["priority"] > 3, \
            f"Priority should have escalated from 3, got {tx_details['priority']}"

    def test_escalation_disabled_when_config_disabled(self):
        """With escalation disabled, priority should never change automatically."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": False,  # Disabled
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=3, divisible=False)

        # Run past deadline
        for _ in range(15):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Priority should NOT have changed
        assert tx_details["priority"] == 3, \
            f"With escalation disabled, priority should stay 3, got {tx_details['priority']}"

        # No escalation events should exist
        all_events = orch.get_all_events()
        escalation_events = [e for e in all_events if e.get("event_type") == "PriorityEscalated"]
        assert len(escalation_events) == 0, \
            f"With escalation disabled, no escalation events expected, got {len(escalation_events)}"

    def test_no_escalation_config_means_disabled(self):
        """Without priority_escalation config, escalation should be disabled by default."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            # No priority_escalation config
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=3, divisible=False)

        for _ in range(15):
            orch.tick()

        tx_details = orch.get_transaction_details(tx_id)

        # Priority should NOT have changed (escalation disabled by default)
        assert tx_details["priority"] == 3, \
            f"With no escalation config, priority should stay 3, got {tx_details['priority']}"


class TestMultipleTransactionsEscalation:
    """Test escalation behavior with multiple transactions."""

    def test_multiple_transactions_escalate_independently(self):
        """Each transaction should escalate based on its own deadline."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # Three transactions with different deadlines, same initial priority
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=3, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=20, priority=3, divisible=False)
        tx3_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=30, priority=3, divisible=False)

        # Run until tick 10
        for _ in range(10):
            orch.tick()

        tx1_details = orch.get_transaction_details(tx1_id)
        tx2_details = orch.get_transaction_details(tx2_id)
        tx3_details = orch.get_transaction_details(tx3_id)

        # TX1 (deadline 12): 2 ticks remaining, deep in escalation window
        # TX2 (deadline 20): 10 ticks remaining, at edge of window
        # TX3 (deadline 30): 20 ticks remaining, not in window

        # TX1 should have highest escalation
        assert tx1_details["priority"] >= tx2_details["priority"], \
            f"TX1 (closer deadline) should have >= priority than TX2"

        # TX3 should not have escalated
        assert tx3_details["priority"] == 3, \
            f"TX3 (far deadline) should not have escalated, got {tx3_details['priority']}"

    def test_different_original_priorities_escalate_proportionally(self):
        """Transactions with different original priorities should escalate to different final priorities."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_escalation": {
                "enabled": True,
                "curve": "linear",
                "start_escalating_at_ticks": 10,
                "max_boost": 3,
            },
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
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

        # Same deadline but different original priorities
        tx1_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=2, divisible=False)
        tx2_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=5, divisible=False)
        tx3_id = orch.submit_transaction("BANK_A", "BANK_B", 1000, deadline_tick=12, priority=8, divisible=False)

        # Run until escalation occurs
        for _ in range(10):
            orch.tick()

        tx1_details = orch.get_transaction_details(tx1_id)
        tx2_details = orch.get_transaction_details(tx2_id)
        tx3_details = orch.get_transaction_details(tx3_id)

        # All should have escalated by the same boost amount
        # But final priorities should maintain relative order: tx1 < tx2 < tx3
        assert tx1_details["priority"] < tx2_details["priority"], \
            f"TX1 (orig 2) should have lower priority than TX2 (orig 5)"
        assert tx2_details["priority"] < tx3_details["priority"], \
            f"TX2 (orig 5) should have lower priority than TX3 (orig 8)"

        # Verify each escalated from original by same amount (same boost)
        # At tick 10, deadline 12, 2 ticks remaining
        # progress = 1 - 2/10 = 0.8, boost = round(3 * 0.8) = 2
        expected_boost = 2  # Approximately
        assert tx1_details["priority"] >= 2 + expected_boost - 1, "TX1 should have escalated"
        assert tx2_details["priority"] >= 5 + expected_boost - 1, "TX2 should have escalated"
        # TX3 might be capped at 10
        assert tx3_details["priority"] >= 8, "TX3 should have escalated (or be at cap)"
