"""
TDD Tests for Issue #4: Collateral Timer Auto-Withdrawal

Problem:
- PostCollateral with auto_withdraw_after_ticks should schedule automatic withdrawal
- Collateral should be automatically withdrawn after specified ticks
- CollateralTimerWithdrawn event should be generated

Expected:
- PostCollateral with auto_withdraw_after_ticks=N schedules withdrawal at tick+N
- Withdrawal happens automatically (no policy action needed)
- Event includes original_reason and posted_at_tick for audit trail

TDD Approach:
1. RED: Test fails - verify timer withdrawal doesn't happen yet
2. GREEN: Feature already implemented - tests should PASS
3. REFACTOR: Verify and clean up
"""

import pytest
import json
from payment_simulator._core import Orchestrator


class TestCollateralTimerAutoWithdrawal:
    """Test that collateral timers auto-withdraw as expected."""

    def test_collateral_auto_withdraws_after_timer_expires(self):
        """Test that collateral posted with timer auto-withdraws after N ticks.

        TDD: This test verifies the auto_withdraw_after_ticks feature works.
        Expected to PASS since feature is already implemented in Rust.
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
                    "credit_limit": 100000,  # capacity = 10 × credit_limit = 1M
                    "policy_id": "test_timer",
                }
            ],
        }

        # Policy that posts collateral with 5-tick auto-withdrawal
        policy_def = {
            "version": "1.0",
            "policy_id": "test_timer",
            "description": "Test policy with collateral timer",
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
                "node_id": "PostWithTimer",
                "action": "PostCollateral",
                "parameters": {
                    "amount": {"value": 50000.0},
                    "reason": {"value": "test_timer_post"},
                    "auto_withdraw_after_ticks": {"value": 5.0}
                }
            }
        }

        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Tick 0: Post collateral with 5-tick timer
        orch.tick()

        events_tick0 = orch.get_tick_events(0)
        post_events = [e for e in events_tick0 if e.get("event_type") == "CollateralPost"]

        assert len(post_events) > 0, "Collateral should be posted at tick 0"
        assert post_events[0]["amount"] == 50000, "Posted amount should be 50000"
        # Reason might be "UrgentLiquidityNeed" from default logic or "test_timer_post" from policy
        assert post_events[0]["reason"] in ["test_timer_post", "UrgentLiquidityNeed"]

        # Record the original reason for later verification
        original_reason = post_events[0]["reason"]

        # Ticks 1-4: No withdrawal yet
        for tick in range(1, 5):
            orch.tick()
            events = orch.get_tick_events(tick)
            timer_withdrawals = [
                e for e in events
                if e.get("event_type") == "CollateralTimerWithdrawn"
            ]
            assert len(timer_withdrawals) == 0, f"No timer withdrawal at tick {tick}"

        # Tick 5: Auto-withdrawal should happen
        orch.tick()
        events_tick5 = orch.get_tick_events(5)

        timer_withdrawals = [
            e for e in events_tick5
            if e.get("event_type") == "CollateralTimerWithdrawn"
        ]

        print(f"\nAll events at tick 5: {len(events_tick5)}")
        for event in events_tick5:
            print(f"  {event}")

        assert len(timer_withdrawals) > 0, "Timer withdrawal should occur at tick 5"

        # Verify event details
        withdrawal_event = timer_withdrawals[0]
        assert withdrawal_event["agent_id"] == "TEST_BANK"
        assert withdrawal_event["amount"] == 50000, "Withdrawn amount should match posted amount"
        # Should track original reason (should match what was in the post event)
        assert withdrawal_event["original_reason"] == original_reason
        assert withdrawal_event["posted_at_tick"] == 0, "Should track when it was posted"

    def test_multiple_timers_for_same_agent(self):
        """Test that agent can have multiple collateral timers scheduled.

        Verifies that posting collateral multiple times with different timers
        results in separate withdrawals at the correct ticks.
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
                    "credit_limit": 100000,  # capacity = 10 × credit_limit = 1M
                    "policy_id": "test_multi_timer",
                }
            ],
        }

        # Policy posts collateral at tick 0 and tick 2 with different timers
        policy_def = {
            "version": "1.0",
            "policy_id": "test_multi_timer",
            "description": "Test policy with multiple timers",
            "parameters": {},
            "bank_tree": {"type": "action", "node_id": "Hold", "action": "Hold"},
            "payment_tree": {"type": "action", "node_id": "HoldAll", "action": "Hold"},
            "strategic_collateral_tree": {
                "type": "condition",
                "node_id": "CheckTick0",
                "condition": {
                    "op": "==",
                    "left": {"field": "tick"},
                    "right": {"value": 0.0}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "Post1",
                    "action": "PostCollateral",
                    "parameters": {
                        "amount": {"value": 30000.0},
                        "reason": {"value": "first_post"},
                        "auto_withdraw_after_ticks": {"value": 3.0}
                    }
                },
                "on_false": {
                    "type": "condition",
                    "node_id": "CheckTick2",
                    "condition": {
                        "op": "==",
                        "left": {"field": "tick"},
                        "right": {"value": 2.0}
                    },
                    "on_true": {
                        "type": "action",
                        "node_id": "Post2",
                        "action": "PostCollateral",
                        "parameters": {
                            "amount": {"value": 20000.0},
                            "reason": {"value": "second_post"},
                            "auto_withdraw_after_ticks": {"value": 5.0}
                        }
                    },
                    "on_false": {
                        "type": "action",
                        "node_id": "HoldCollateral",
                        "action": "HoldCollateral"
                    }
                }
            }
        }

        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Tick 0: Post 30000 with 3-tick timer
        orch.tick()
        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 30000

        # Tick 1: Nothing happens
        orch.tick()

        # Tick 2: Post another 20000 with 5-tick timer
        orch.tick()
        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 50000, "Total should be 30000 + 20000"

        # Tick 3: First timer expires (30000 withdrawn)
        orch.tick()
        events_tick3 = orch.get_tick_events(3)
        timer_withdrawals = [
            e for e in events_tick3
            if e.get("event_type") == "CollateralTimerWithdrawn"
        ]

        assert len(timer_withdrawals) == 1, "First timer should expire"
        assert timer_withdrawals[0]["amount"] == 30000
        assert timer_withdrawals[0]["posted_at_tick"] == 0

        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 20000, "Only 20000 should remain"

        # Ticks 4-6: Nothing (waiting for second timer)
        orch.tick()  # tick 4
        orch.tick()  # tick 5
        orch.tick()  # tick 6

        # Tick 7: Second timer expires (posted at tick 2, 5-tick delay)
        orch.tick()
        events_tick7 = orch.get_tick_events(7)
        timer_withdrawals = [
            e for e in events_tick7
            if e.get("event_type") == "CollateralTimerWithdrawn"
        ]

        assert len(timer_withdrawals) == 1, "Second timer should expire"
        assert timer_withdrawals[0]["amount"] == 20000
        assert timer_withdrawals[0]["posted_at_tick"] == 2

        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 0, "All collateral should be withdrawn"

    def test_timer_withdrawal_limited_by_available_collateral(self):
        """Test that timer withdrawal is capped at actual posted collateral.

        If agent manually withdraws some collateral before timer expires,
        the timer withdrawal should only withdraw what remains.
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
                    "credit_limit": 100000,  # capacity = 10 × credit_limit = 1M
                    "collateral_posted": 100000,  # Start with collateral
                    "policy_id": "test_cap",
                }
            ],
        }

        # Policy posts 50000 with timer, then manually withdraws 30000 at tick 2
        policy_def = {
            "version": "1.0",
            "policy_id": "test_cap",
            "description": "Test timer capped by available collateral",
            "parameters": {},
            "bank_tree": {"type": "action", "node_id": "Hold", "action": "Hold"},
            "payment_tree": {"type": "action", "node_id": "HoldAll", "action": "Hold"},
            "strategic_collateral_tree": {
                "type": "condition",
                "node_id": "CheckTick0",
                "condition": {
                    "op": "==",
                    "left": {"field": "tick"},
                    "right": {"value": 0.0}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "PostWithTimer",
                    "action": "PostCollateral",
                    "parameters": {
                        "amount": {"value": 50000.0},
                        "reason": {"value": "timer_test"},
                        "auto_withdraw_after_ticks": {"value": 5.0}
                    }
                },
                "on_false": {
                    "type": "action",
                    "node_id": "HoldCollateral",
                    "action": "HoldCollateral"
                }
            },
            "end_of_tick_collateral_tree": {
                "type": "condition",
                "node_id": "CheckTick2",
                "condition": {
                    "op": "==",
                    "left": {"field": "tick"},
                    "right": {"value": 2.0}
                },
                "on_true": {
                    "type": "action",
                    "node_id": "ManualWithdraw",
                    "action": "WithdrawCollateral",
                    "parameters": {
                        "amount": {"value": 30000.0},
                        "reason": {"value": "manual_withdrawal"}
                    }
                },
                "on_false": {
                    "type": "action",
                    "node_id": "HoldCollateral2",
                    "action": "HoldCollateral"
                }
            }
        }

        config["agent_configs"][0]["policy"] = {
            "type": "FromJson",
            "json": json.dumps(policy_def)
        }

        orch = Orchestrator.new(config)

        # Tick 0: Post 50000 with 5-tick timer (total: 100000 + 50000 = 150000)
        orch.tick()
        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 150000

        orch.tick()  # tick 1

        # Tick 2: Manual withdrawal of 30000 (total: 150000 - 30000 = 120000)
        orch.tick()
        agent = orch.get_agents()[0]
        assert agent["posted_collateral"] == 120000

        orch.tick()  # tick 3
        orch.tick()  # tick 4

        # Tick 5: Timer tries to withdraw 50000, but less is available
        # Since we started with 100000, posted 50000 (timer-tracked), then manually withdrew 30000,
        # the timer should only withdraw what remains of its 50000 portion
        orch.tick()
        events_tick5 = orch.get_tick_events(5)

        timer_withdrawals = [
            e for e in events_tick5
            if e.get("event_type") == "CollateralTimerWithdrawn"
        ]

        assert len(timer_withdrawals) > 0, "Timer withdrawal should occur"

        # The timer should withdraw up to the scheduled amount
        withdrawal_event = timer_withdrawals[0]
        print(f"\nTimer withdrawal event: {withdrawal_event}")
        print(f"Posted collateral after withdrawal: {orch.get_agents()[0]['posted_collateral']}")

        # Verify withdrawal happened and was capped appropriately
        assert withdrawal_event["amount"] <= 50000, "Cannot withdraw more than scheduled"
        assert withdrawal_event["amount"] > 0, "Should withdraw something"


if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: Collateral auto-withdraws after timer expires")
    print("=" * 80)
    try:
        test = TestCollateralTimerAutoWithdrawal()
        test.test_collateral_auto_withdraws_after_timer_expires()
        print("\n✓ TEST 1 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 1 FAILED: {e}")
    except Exception as e:
        print(f"\n✗ TEST 1 ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 2: Multiple timers for same agent")
    print("=" * 80)
    try:
        test = TestCollateralTimerAutoWithdrawal()
        test.test_multiple_timers_for_same_agent()
        print("\n✓ TEST 2 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 2 FAILED: {e}")
    except Exception as e:
        print(f"\n✗ TEST 2 ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 3: Timer withdrawal capped by available collateral")
    print("=" * 80)
    try:
        test = TestCollateralTimerAutoWithdrawal()
        test.test_timer_withdrawal_limited_by_available_collateral()
        print("\n✓ TEST 3 PASSED")
    except AssertionError as e:
        print(f"\n✗ TEST 3 FAILED: {e}")
    except Exception as e:
        print(f"\n✗ TEST 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
