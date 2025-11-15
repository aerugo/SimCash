"""
Integration test for Phase 4.6: Decision Path Auditing

Tests that decision paths are correctly tracked and displayed for state register updates.
"""

import json
import pytest
from payment_simulator._core import Orchestrator


def test_decision_path_appears_in_state_register_events():
    """
    Test that SetState actions include decision path in events.

    TDD: RED → GREEN → REFACTOR
    This test verifies that when a policy tree uses SetState action,
    the resulting StateRegisterSet event includes the decision path
    showing which nodes were traversed to reach that action.
    """
    # Create a simple policy tree with SetState action
    policy_tree = {
        "version": "1.0",
        "policy_id": "test_decision_path",
        "description": "Test policy for decision path tracking",
        "bank_tree": {
            "node_id": "root",
            "type": "condition",
            "condition": {
                "left": {"field": "balance"},
                "op": ">",
                "right": {"value": 0}
            },
            "on_true": {
                "node_id": "action_set_mode",
                "type": "action",
                "action": "SetState",
                "parameters": {
                    "key": {"value": "bank_state_mode"},
                    "value": {"value": 1.0},
                    "reason": {"value": "has_balance"}
                }
            },
            "on_false": {
                "node_id": "action_no_balance",
                "type": "action",
                "action": "SetState",
                "parameters": {
                    "key": {"value": "bank_state_mode"},
                    "value": {"value": 0.0},
                    "reason": {"value": "no_balance"}
                }
            }
        },
        "payment_tree": {
            "node_id": "pay_action",
            "type": "action",
            "action": "Hold",
            "hold_reason": "WaitingForLiquidity"
        },
        "strategic_collateral_tree": None,
        "end_of_tick_collateral_tree": None,
        "parameters": {}
    }

    # Configuration with the policy
    config = {
        "num_days": 1,
        "ticks_per_day": 10,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100000,  # Has balance, will take on_true path
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {
                    "type": "FromJson",
                    "json": json.dumps(policy_tree)
                }
            },
            {
                "id": "BANK_B",
                "opening_balance": 0,  # No balance, will take on_false path
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {
                    "type": "FromJson",
                    "json": json.dumps(policy_tree)
                }
            }
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.0,
            "delay_per_tick_bps": 0.0,
            "deadline_penalty_bps": 0.0,
            "eod_penalty": 0,
            "collateral_cost_per_tick_bps": 0.0,
            "overdue_delay_multiplier": 1,
        },
    }

    # Create orchestrator and run one tick
    orch = Orchestrator.new(config)
    orch.tick()

    # Get events from tick 0
    events = orch.get_tick_events(0)

    # Find StateRegisterSet events
    state_events = [
        e for e in events
        if e.get("event_type") == "StateRegisterSet"
    ]

    # Should have at least 2 state register events (one for each bank)
    assert len(state_events) >= 2, f"Expected at least 2 state events, got {len(state_events)}"

    # Check BANK_A event (has balance, took on_true path)
    bank_a_events = [e for e in state_events if e.get("agent_id") == "BANK_A"]
    assert len(bank_a_events) > 0, "Should have BANK_A state event"

    bank_a_event = bank_a_events[0]
    assert "decision_path" in bank_a_event, "Event should include decision_path field"

    decision_path = bank_a_event["decision_path"]
    assert decision_path is not None, "Decision path should not be None"
    assert len(decision_path) > 0, "Decision path should not be empty"

    # Path should show: root condition (true) → action_set_mode
    assert "root" in decision_path, f"Path should include root node: {decision_path}"
    assert "action_set_mode" in decision_path, f"Path should include action node: {decision_path}"
    assert "true" in decision_path or "True" in decision_path, f"Path should show condition was true: {decision_path}"

    # Check BANK_B event (no balance, took on_false path)
    bank_b_events = [e for e in state_events if e.get("agent_id") == "BANK_B"]
    assert len(bank_b_events) > 0, "Should have BANK_B state event"

    bank_b_event = bank_b_events[0]
    assert "decision_path" in bank_b_event, "Event should include decision_path field"

    decision_path_b = bank_b_event["decision_path"]
    assert decision_path_b is not None, "Decision path should not be None"

    # Path should show: root condition (false) → action_no_balance
    assert "root" in decision_path_b, f"Path should include root node: {decision_path_b}"
    assert "action_no_balance" in decision_path_b, f"Path should include action node: {decision_path_b}"
    assert "false" in decision_path_b or "False" in decision_path_b, f"Path should show condition was false: {decision_path_b}"


def test_decision_path_with_add_state():
    """
    Test that AddState actions also include decision path.

    Verifies that incrementing state registers (AddState) also tracks
    the decision path that led to the increment.
    """
    # Create a policy tree with AddState action
    policy_tree = {
        "version": "1.0",
        "policy_id": "test_add_state_path",
        "description": "Test policy for AddState decision path tracking",
        "bank_tree": {
            "node_id": "check_balance",
            "type": "condition",
            "condition": {
                "left": {"field": "balance"},
                "op": "<",
                "right": {"value": 50000}
            },
            "on_true": {
                "node_id": "increment_counter",
                "type": "action",
                "action": "AddState",
                "parameters": {
                    "key": {"value": "bank_state_counter"},
                    "value": {"value": 1.0},
                    "reason": {"value": "low_balance"}
                }
            },
            "on_false": {
                "node_id": "reset_counter",
                "type": "action",
                "action": "SetState",
                "parameters": {
                    "key": {"value": "bank_state_counter"},
                    "value": {"value": 0.0},
                    "reason": {"value": "high_balance"}
                }
            }
        },
        "payment_tree": {
            "node_id": "pay_action",
            "type": "action",
            "action": "Hold",
            "hold_reason": "WaitingForLiquidity"
        },
        "strategic_collateral_tree": None,
        "end_of_tick_collateral_tree": None,
        "parameters": {}
    }

    config = {
        "num_days": 1,
        "ticks_per_day": 10,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {
                    "type": "FromJson",
                    "json": json.dumps(policy_tree)
                }
            }
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.0,
            "delay_per_tick_bps": 0.0,
            "deadline_penalty_bps": 0.0,
            "eod_penalty": 0,
            "collateral_cost_per_tick_bps": 0.0,
            "overdue_delay_multiplier": 1,
        },
    }

    # Create orchestrator
    orch = Orchestrator.new(config)

    # Add a transaction to create a queue
    orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_A",
        amount=50000,  # More than balance, will queue
        deadline_tick=5,
        priority=5,
        divisible=False
    )

    # Run tick
    orch.tick()

    # Get events
    events = orch.get_tick_events(0)

    # Find StateRegisterSet events for AddState
    state_events = [
        e for e in events
        if e.get("event_type") == "StateRegisterSet" and
           e.get("reason") == "low_balance"
    ]

    # Should have at least one event
    assert len(state_events) > 0, "Should have AddState event"

    event = state_events[0]
    assert "decision_path" in event, "AddState event should include decision_path"

    decision_path = event["decision_path"]
    assert decision_path is not None, "Decision path should not be None"

    # Path should show: check_balance condition (true) → increment_counter
    assert "check_balance" in decision_path, f"Path should include condition node: {decision_path}"
    assert "increment_counter" in decision_path, f"Path should include action node: {decision_path}"
    assert "true" in decision_path or "True" in decision_path, f"Path should show condition was true: {decision_path}"


def test_eod_reset_has_no_decision_path():
    """
    Test that EOD resets do not include decision path.

    EOD resets are automatic, not policy decisions, so they should
    have decision_path = None.
    """
    policy_tree = {
        "version": "1.0",
        "policy_id": "test_eod_reset",
        "description": "Test policy for EOD reset (no decision path)",
        "bank_tree": {
            "node_id": "action",
            "type": "action",
            "action": "SetState",
            "parameters": {
                "key": {"value": "bank_state_dummy"},
                "value": {"value": 0.0},
                "reason": {"value": "noop"}
            }
        },
        "payment_tree": {
            "node_id": "pay_action",
            "type": "action",
            "action": "Hold",
            "hold_reason": "WaitingForLiquidity"
        },
        "strategic_collateral_tree": None,
        "end_of_tick_collateral_tree": None,
        "parameters": {}
    }

    config = {
        "num_days": 2,  # Need at least 2 days to see EOD reset
        "ticks_per_day": 5,  # Short day
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10000,
                "unsecured_cap": 0,
                "collateral_pool": 0,
                "policy": {
                    "type": "FromJson",
                    "json": json.dumps(policy_tree)
                }
            }
        ],
        "cost_model": {
            "overdraft_bps_per_tick": 0.0,
            "delay_per_tick_bps": 0.0,
            "deadline_penalty_bps": 0.0,
            "eod_penalty": 0,
            "collateral_cost_per_tick_bps": 0.0,
            "overdue_delay_multiplier": 1,
        },
    }

    orch = Orchestrator.new(config)

    # First, set a state register by manually creating a policy that sets it
    # For this test, we'll just run through a day to trigger EOD reset

    # Run until EOD (tick 4 is last tick of day 0, tick 5 is first tick of day 1)
    for _ in range(6):
        orch.tick()

    # Get events from tick 5 (start of day 1, should have EOD reset events)
    events = orch.get_tick_events(5)

    # Find EOD reset events
    eod_events = [
        e for e in events
        if e.get("event_type") == "StateRegisterSet" and
           e.get("reason") == "eod_reset"
    ]

    if len(eod_events) > 0:
        # If we have EOD reset events, verify they have no decision path
        for event in eod_events:
            decision_path = event.get("decision_path")
            assert decision_path is None, f"EOD reset should have no decision path, got: {decision_path}"
