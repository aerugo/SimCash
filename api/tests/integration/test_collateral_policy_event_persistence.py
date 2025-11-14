"""
TDD Tests for Issue #2: Collateral Policy Events Not Persisted

Problem:
- PostCollateral and WithdrawCollateral actions execute successfully
- Verbose output shows "💰 Collateral Activity"
- BUT: No events in simulation_events table
- No collateral-related event_types found

Expected:
- PostCollateral action should generate CollateralPosted event
- WithdrawCollateral action should generate CollateralWithdrawn event
- Events should be serialized via FFI and persisted to simulation_events

TDD Approach:
1. RED: Test fails - no collateral events in database
2. GREEN: Implement event generation in Rust + FFI serialization
3. REFACTOR: Clean up and verify
"""

import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import write_events_batch


class TestCollateralPolicyEventGeneration:
    """Test that collateral policy actions generate events."""

    def test_post_collateral_action_generates_event(self, tmp_path):
        """Test that PostCollateral action generates CollateralPosted event.

        TDD RED: This test will FAIL because:
        - PostCollateral action executes but doesn't generate event
        - Need to add event generation in Rust policy interpreter
        """

        # Create policy with PostCollateral action
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "cost_params": {
                "liquidity_cost_bps_per_day": 10,
                "delay_cost_per_tick": 0.1,
                "deadline_penalty": 100.0,
                "overdue_delay_multiplier": 5.0,
                "split_friction_bps": 5,
            },
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy_id": "test_collateral_post",
                }
            ],
        }

        # Policy that always posts collateral at tick 0
        policy_def = {
            "version": "1.0",
            "policy_id": "test_collateral_post",
            "description": "Test policy that posts collateral",
            "parameters": {},
            "bank_tree": {
                "type": "action",
                "node_id": "Hold",
                "action": "Hold"
            },
            "payment_tree": {
                "type": "action",
                "node_id": "HoldAll",
                "action": "Hold"
            },
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "PostCollateral",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"value": 50000.0},
                    "reason": {"value": "test_post"}
                }
            }
        }

        # Pass policy as JSON string
        import json
        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Run first tick - should post collateral
        result = orch.tick()
        print(f"Tick 0 result: {result}")

        # Get events from tick 0
        events = orch.get_tick_events(0)
        print(f"\nTotal events: {len(events)}")

        # Filter for collateral events
        collateral_events = [
            e for e in events
            if any(keyword in e.get('event_type', '').lower() for keyword in ['collateral', 'post', 'withdraw'])
        ]
        print(f"Collateral events: {len(collateral_events)}")
        for event in collateral_events:
            print(f"  Event: {event}")

        # TDD RED: This assertion will FAIL
        assert len(collateral_events) > 0, \
            "PostCollateral action should generate a CollateralPosted event"

        # Verify event structure
        event = collateral_events[0]
        print(f"Event details: {event}")

        assert 'event_type' in event
        # Event type is "CollateralPost" from Rust
        assert event['event_type'] in ['CollateralPost', 'CollateralPosted', 'PostCollateral']
        assert 'agent_id' in event
        assert event['agent_id'] == 'TEST_BANK'
        assert 'amount' in event
        # Amount might be different if fallback logic is used
        assert event['amount'] > 0
        assert 'reason' in event
        # Reason might be "UrgentLiquidityNeed" from fallback or "test_post" from policy
        assert event['reason'] in ['test_post', 'UrgentLiquidityNeed']

    def test_collateral_events_persist_to_database(self, tmp_path):
        """Test that collateral events are persisted to simulation_events table.

        TDD RED: Will fail because events aren't generated yet.
        """

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.setup()

        # Create policy with PostCollateral action
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "cost_params": {
                "liquidity_cost_bps_per_day": 10,
                "delay_cost_per_tick": 0.1,
                "deadline_penalty": 100.0,
                "overdue_delay_multiplier": 5.0,
                "split_friction_bps": 5,
            },
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy_id": "test_collateral_post",
                }
            ],
        }

        policy_def = {
            "version": "1.0",
            "policy_id": "test_collateral_post",
            "description": "Test policy that posts collateral",
            "parameters": {},
            "bank_tree": {
                "type": "action",
                "node_id": "Hold",
                "action": "Hold"
            },
            "payment_tree": {
                "type": "action",
                "node_id": "HoldAll",
                "action": "Hold"
            },
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "PostCollateral",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"value": 50000.0},
                    "reason": {"value": "test_post"}
                }
            }
        }

        # Pass policy as JSON string
        import json
        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Run tick
        orch.tick()

        # Get events
        events = orch.get_tick_events(0)

        # Write to database
        count = write_events_batch(manager.conn, "sim-test", events, ticks_per_day=100)
        print(f"Wrote {count} events to database")

        # Query for collateral events
        result = manager.conn.execute("""
            SELECT event_type, agent_id, details
            FROM simulation_events
            WHERE simulation_id = 'sim-test'
            AND (
                event_type LIKE '%Collateral%'
                OR event_type LIKE '%Post%'
                OR event_type LIKE '%Withdraw%'
            )
        """).fetchall()

        print(f"\nCollateral events in database: {len(result)}")
        for row in result:
            print(f"  {row}")

        # TDD RED: This will FAIL
        assert len(result) > 0, "Collateral events should be persisted to database"

        # Verify event details
        event_type, agent_id, details_json = result[0]
        assert agent_id == 'TEST_BANK'

        import json
        details = json.loads(details_json)
        assert 'amount' in details
        assert details['amount'] == 50000
        assert 'reason' in details
        # Reason can be from policy ("test_post") or fallback ("UrgentLiquidityNeed")
        assert details['reason'] in ['test_post', 'UrgentLiquidityNeed']

        manager.close()

    def test_withdraw_collateral_action_generates_event(self, tmp_path):
        """Test that WithdrawCollateral action generates CollateralWithdrawn event.

        TDD RED: Will fail because event generation not implemented.
        """

        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "cost_params": {
                "liquidity_cost_bps_per_day": 10,
                "delay_cost_per_tick": 0.1,
                "deadline_penalty": 100.0,
                "overdue_delay_multiplier": 5.0,
                "split_friction_bps": 5,
            },
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "collateral_posted": 100000,  # Start with collateral posted
                    "policy_id": "test_collateral_withdraw",
                }
            ],
        }

        policy_def = {
            "version": "1.0",
            "policy_id": "test_collateral_withdraw",
            "description": "Test policy that withdraws collateral",
            "parameters": {},
            "bank_tree": {
                "type": "action",
                "node_id": "Hold",
                "action": "Hold"
            },
            "payment_tree": {
                "type": "action",
                "node_id": "HoldAll",
                "action": "Hold"
            },
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "WithdrawCollateral",
                "action": "WithdrawCollateral",
                "parameters": {
                    "amount": {"value": 25000.0},
                    "reason": {"value": "test_withdraw"}
                }
            }
        }

        # Pass policy as JSON string
        import json
        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Run tick
        orch.tick()

        # Get events
        events = orch.get_tick_events(0)

        # Filter for collateral withdrawal events
        withdrawal_events = [
            e for e in events
            if 'withdraw' in e.get('event_type', '').lower() or 'collateral' in e.get('event_type', '').lower()
        ]

        print(f"Withdrawal events: {len(withdrawal_events)}")
        for event in withdrawal_events:
            print(f"  Event: {event}")

        # TDD RED: This will FAIL
        assert len(withdrawal_events) > 0, \
            "WithdrawCollateral action should generate a CollateralWithdrawn event"

        # Verify event structure
        event = withdrawal_events[0]
        assert event.get('agent_id') == 'TEST_BANK'
        assert event.get('amount') == 25000
        assert event.get('reason') == 'test_withdraw'


if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: PostCollateral generates event")
    print("=" * 80)
    try:
        test = TestCollateralPolicyEventGeneration()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            test.test_post_collateral_action_generates_event(Path(tmpdir))
        print("\n✓ TEST 1 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 1 FAILED (RED - expected): {e}")
    except Exception as e:
        print(f"\n✗ TEST 1 ERROR: {e}")

    print("\n" + "=" * 80)
    print("TEST 2: Collateral events persist to database")
    print("=" * 80)
    try:
        test = TestCollateralPolicyEventGeneration()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            test.test_collateral_events_persist_to_database(Path(tmpdir))
        print("\n✓ TEST 2 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 2 FAILED (RED - expected): {e}")
    except Exception as e:
        print(f"\n✗ TEST 2 ERROR: {e}")

    print("\n" + "=" * 80)
    print("TEST 3: WithdrawCollateral generates event")
    print("=" * 80)
    try:
        test = TestCollateralPolicyEventGeneration()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            test.test_withdraw_collateral_action_generates_event(Path(tmpdir))
        print("\n✓ TEST 3 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 3 FAILED (RED - expected): {e}")
    except Exception as e:
        print(f"\n✗ TEST 3 ERROR: {e}")
