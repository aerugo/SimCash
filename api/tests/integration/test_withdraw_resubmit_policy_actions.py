"""
TDD Tests for WithdrawFromRtgs and ResubmitToRtgs Policy Actions

Phase 0.8: Allow policies to withdraw transactions from RTGS Queue 2
and resubmit them with different RTGS priorities.

Following strict TDD principles:
1. RED: Write failing tests first
2. GREEN: Implement minimum code to pass
3. REFACTOR: Clean up while keeping tests passing
"""

import json
import pytest
from payment_simulator._core import Orchestrator


def make_policy_config(policy_json: dict) -> dict:
    """Convert policy dict to FromJson config format."""
    return {"type": "FromJson", "json": json.dumps(policy_json)}


# =============================================================================
# TDD Step 0.8.1: WithdrawFromRtgs Action Type Exists
# =============================================================================


class TestWithdrawFromRtgsActionType:
    """TDD Step 0.8.1: WithdrawFromRtgs action type is recognized."""

    def test_withdraw_from_rtgs_action_type_in_policy_json(self):
        """Policy JSON can use WithdrawFromRtgs action type."""
        # Policy that withdraws from RTGS when priority is low and deadline is far
        policy_json = {
            "version": "1.0",
            "policy_id": "withdraw_test_v1",
            "description": "Test policy that withdraws from RTGS",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Should we withdraw from RTGS?",
                "condition": {
                    "op": "and",
                    "conditions": [
                        {
                            "op": "<",
                            "left": {"field": "priority"},
                            "right": {"value": 5},
                        },
                        {
                            "op": ">",
                            "left": {"field": "ticks_to_deadline"},
                            "right": {"value": 30},
                        },
                    ],
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "WithdrawFromRtgs",
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Should not raise - action type should be recognized
        orch = Orchestrator.new(config)
        assert orch is not None


class TestWithdrawFromRtgsPolicyExecution:
    """TDD Step 0.8.2: WithdrawFromRtgs action executes correctly."""

    def test_policy_can_withdraw_transaction_from_queue2(self):
        """Policy decision to withdraw removes transaction from Queue 2."""
        # Policy that always withdraws when in Queue 2
        policy_json = {
            "version": "1.0",
            "policy_id": "always_withdraw_v1",
            "description": "Always withdraw from RTGS (for testing)",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Is this in Queue 2?",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "WithdrawFromRtgs",
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",  # Submit to Queue 2 initially
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Create transaction that will go to Queue 2
        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,  # More than balance
            deadline_tick=80,
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        # Tick 0: Transaction submitted to Queue 2
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "Normal"

        # Tick 1: Policy should see it in Queue 2 and withdraw it
        orch.tick()

        # After withdrawal, RTGS priority should be cleared
        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] is None, "Transaction should be withdrawn from RTGS"

    def test_withdraw_emits_rtgs_withdrawal_event(self):
        """WithdrawFromRtgs action should emit RtgsWithdrawal event."""
        policy_json = {
            "version": "1.0",
            "policy_id": "withdraw_test_v1",
            "description": "Withdraw when in Queue 2",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "WithdrawFromRtgs",
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=80,
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        orch.tick()  # Submit to Queue 2
        orch.tick()  # Policy withdraws

        events = orch.get_tick_events(1)
        withdrawal_events = [e for e in events if e.get("event_type") == "RtgsWithdrawal"]

        assert len(withdrawal_events) >= 1, "RtgsWithdrawal event should be emitted"
        event = withdrawal_events[0]
        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["original_rtgs_priority"] == "Normal"


# =============================================================================
# TDD Step 0.8.3: ResubmitToRtgs Action Type
# =============================================================================


class TestResubmitToRtgsActionType:
    """TDD Step 0.8.3: ResubmitToRtgs action type is recognized."""

    def test_resubmit_to_rtgs_action_type_in_policy_json(self):
        """Policy JSON can use ResubmitToRtgs action type."""
        policy_json = {
            "version": "1.0",
            "policy_id": "resubmit_test_v1",
            "description": "Test policy that resubmits with higher priority",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Is deadline approaching?",
                "condition": {
                    "op": "<",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"value": 10},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "ResubmitToRtgs",
                    "parameters": {
                        "rtgs_priority": {"value": "HighlyUrgent"},
                    },
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Hold",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)
        assert orch is not None


class TestResubmitToRtgsPolicyExecution:
    """TDD Step 0.8.4: ResubmitToRtgs action executes correctly."""

    def test_policy_can_resubmit_with_higher_priority(self):
        """Policy decision to resubmit changes RTGS priority."""
        # Policy that resubmits with HighlyUrgent when deadline < 20 ticks
        policy_json = {
            "version": "1.0",
            "policy_id": "escalate_priority_v1",
            "description": "Escalate RTGS priority as deadline approaches",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "description": "Is this in Queue 2?",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "condition",
                    "node_id": "N2",
                    "description": "Is deadline approaching?",
                    "condition": {
                        "op": "<",
                        "left": {"field": "ticks_to_deadline"},
                        "right": {"value": 20},
                    },
                    "on_true": {
                        "type": "action",
                        "node_id": "A1",
                        "action": "ResubmitToRtgs",
                        "parameters": {
                            "rtgs_priority": {"value": "HighlyUrgent"},
                        },
                    },
                    "on_false": {
                        "type": "action",
                        "node_id": "A2",
                        "action": "Hold",
                    },
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A3",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Create transaction with short deadline
        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=15,  # Short deadline - within threshold
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        # Tick 0: Submit to Queue 2 with Normal priority
        orch.tick()
        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "Normal"

        # Tick 1: Queue 2 policy sees deadline < 20, withdraws and resubmits
        # After this tick, transaction is back in Queue 1 with declared_rtgs_priority=HighlyUrgent
        orch.tick()
        details = orch.get_transaction_details(tx_id)
        # Transaction should be withdrawn (rtgs_priority=None) and declared as HighlyUrgent
        assert details["rtgs_priority"] is None, "Should be withdrawn from Queue 2"
        assert details["declared_rtgs_priority"] == "HighlyUrgent", "Should have declared HighlyUrgent"

        # Tick 2: Queue 1 policy releases to Queue 2 with new HighlyUrgent priority
        orch.tick()
        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "HighlyUrgent", "Should be in Queue 2 with HighlyUrgent priority"

    def test_resubmit_emits_rtgs_resubmission_event(self):
        """ResubmitToRtgs action should emit RtgsResubmission event."""
        policy_json = {
            "version": "1.0",
            "policy_id": "resubmit_test_v1",
            "description": "Resubmit when in Queue 2",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "ResubmitToRtgs",
                    "parameters": {
                        "rtgs_priority": {"value": "Urgent"},
                    },
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=80,
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        orch.tick()  # Submit to Queue 2
        orch.tick()  # Policy resubmits

        events = orch.get_tick_events(1)
        resubmit_events = [e for e in events if e.get("event_type") == "RtgsResubmission"]

        assert len(resubmit_events) >= 1, "RtgsResubmission event should be emitted"
        event = resubmit_events[0]
        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["old_rtgs_priority"] == "Normal"
        assert event["new_rtgs_priority"] == "Urgent"


# =============================================================================
# TDD Step 0.8.5: Context Field for Queue 2 Status
# =============================================================================


class TestIsInQueue2ContextField:
    """TDD Step 0.8.5: is_in_queue2 context field exists."""

    def test_is_in_queue2_field_available_in_policy_context(self):
        """Policies can check if transaction is in Queue 2."""
        # Simple policy that uses is_in_queue2 field
        policy_json = {
            "version": "1.0",
            "policy_id": "queue2_check_v1",
            "description": "Check Queue 2 status",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "Hold",
                    "parameters": {"reason": {"value": "InQueue2"}},
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Should not raise - field should be recognized
        orch = Orchestrator.new(config)
        assert orch is not None


# =============================================================================
# TDD Step 0.8.6: Replay Identity
# =============================================================================


class TestWithdrawResubmitReplayIdentity:
    """TDD Step 0.8.6: Events have all fields for replay identity."""

    def test_rtgs_withdrawal_event_has_all_fields(self):
        """RtgsWithdrawal event must have all fields for replay."""
        policy_json = {
            "version": "1.0",
            "policy_id": "withdraw_test_v1",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "WithdrawFromRtgs",
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=80,
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        orch.tick()
        orch.tick()

        events = orch.get_tick_events(1)
        withdrawal_events = [e for e in events if e.get("event_type") == "RtgsWithdrawal"]

        assert len(withdrawal_events) >= 1
        event = withdrawal_events[0]

        # Required fields for replay identity
        assert "event_type" in event
        assert "tick" in event
        assert "tx_id" in event
        assert "sender" in event
        assert "original_rtgs_priority" in event

    def test_rtgs_resubmission_event_has_all_fields(self):
        """RtgsResubmission event must have all fields for replay."""
        policy_json = {
            "version": "1.0",
            "policy_id": "resubmit_test_v1",
            "parameters": {},
            "payment_tree": {
                "type": "condition",
                "node_id": "N1",
                "condition": {
                    "op": "==",
                    "left": {"field": "is_in_queue2"},
                    "right": {"value": 1},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "A1",
                    "action": "ResubmitToRtgs",
                    "parameters": {
                        "rtgs_priority": {"value": "Urgent"},
                    },
                },
                "on_false": {
                    "type": "action",
                    "node_id": "A2",
                    "action": "Release",
                },
            },
        }

        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": make_policy_config(policy_json),
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50_000,
            deadline_tick=80,
            priority=3,
            divisible=False,
            rtgs_priority="Normal",
        )

        orch.tick()
        orch.tick()

        events = orch.get_tick_events(1)
        resubmit_events = [e for e in events if e.get("event_type") == "RtgsResubmission"]

        assert len(resubmit_events) >= 1
        event = resubmit_events[0]

        # Required fields for replay identity
        assert "event_type" in event
        assert "tick" in event
        assert "tx_id" in event
        assert "sender" in event
        assert "old_rtgs_priority" in event
        assert "new_rtgs_priority" in event
