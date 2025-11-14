"""
Scenario tests for collateral/headroom invariants using advanced_policy_crisis.yaml.

These tests run realistic crisis simulations and verify that invariants hold throughout.
"""

import json
import pytest
import yaml
from pathlib import Path
from payment_simulator.backends.rust import Orchestrator


@pytest.fixture
def crisis_config():
    """Load the advanced_policy_crisis.yaml configuration."""
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"

    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def test_advanced_crisis_maintains_invariants(crisis_config):
    """
    Run advanced_policy_crisis.yaml and verify invariants hold throughout.

    Invariant I1: credit_used ≤ allowed_overdraft_limit for all agents at all ticks.
    """
    orch = Orchestrator.new(crisis_config)

    # Run simulation for 300 ticks (3 days)
    max_ticks = 300
    violations = []

    agent_ids = [agent["id"] for agent in crisis_config["agent_configs"]]

    for tick in range(max_ticks):
        orch.tick()

        # Check invariants for all agents
        for agent_id in agent_ids:
            state = orch.get_agent_state(agent_id)

            credit_used = state.get("credit_used")
            allowed_limit = state.get("allowed_overdraft_limit")

            # Skip if new fields not yet implemented
            if credit_used is None or allowed_limit is None:
                pytest.skip("New collateral fields not yet implemented in FFI")

            # Invariant I1: credit_used ≤ allowed_limit
            if credit_used > allowed_limit:
                violations.append({
                    "tick": tick,
                    "agent": agent_id,
                    "credit_used": credit_used,
                    "allowed_limit": allowed_limit,
                    "violation_amount": credit_used - allowed_limit,
                    "balance": state["balance"],
                    "posted_collateral": state.get("posted_collateral", 0),
                    "violation_type": "I1: credit_used > allowed_limit"
                })

    if violations:
        print("\n=== INVARIANT VIOLATIONS DETECTED ===")
        for v in violations[:10]:  # Print first 10
            print(json.dumps(v, indent=2))

    assert len(violations) == 0, \
        f"Found {len(violations)} invariant violations. First: {violations[0] if violations else 'None'}"


def test_tick_282_no_unsafe_withdrawal(crisis_config):
    """
    Load advanced_crisis to tick 281, execute tick 282,
    verify REGIONAL_TRUST does NOT withdraw collateral unsafely.

    This is the specific scenario documented in the user's bug report.
    """
    orch = Orchestrator.new(crisis_config)

    # Fast-forward to tick 281
    for _ in range(281):
        orch.tick()

    # Capture REGIONAL_TRUST state before tick 282
    rt_before = orch.get_agent_state("REGIONAL_TRUST")
    collateral_before = rt_before["posted_collateral"]
    balance_before = rt_before["balance"]

    print(f"\n=== TICK 281 STATE ===")
    print(f"Balance: ${balance_before / 100:.2f}")
    print(f"Posted Collateral: ${collateral_before / 100:.2f}")

    # Execute tick 282
    orch.tick()

    # Capture state after
    rt_after = orch.get_agent_state("REGIONAL_TRUST")
    collateral_after = rt_after["posted_collateral"]
    balance_after = rt_after["balance"]

    print(f"\n=== TICK 282 STATE ===")
    print(f"Balance: ${balance_after / 100:.2f}")
    print(f"Posted Collateral: ${collateral_after / 100:.2f}")

    credit_used = max(0, -balance_after)

    # Get new fields if available
    allowed_limit = rt_after.get("allowed_overdraft_limit")
    if allowed_limit is None:
        # Fallback to old credit_limit if new fields not implemented
        allowed_limit = rt_after.get("credit_limit", 0)

    print(f"Credit Used: ${credit_used / 100:.2f}")
    print(f"Allowed Limit: ${allowed_limit / 100:.2f}")

    # If agent is over limit AND collateral decreased, that's a violation
    if credit_used > allowed_limit:
        if collateral_after < collateral_before:
            withdrawal_amount = collateral_before - collateral_after
            pytest.fail(
                f"UNSAFE WITHDRAWAL at tick 282:\n"
                f"  Agent was over limit: credit_used ({credit_used}) > allowed_limit ({allowed_limit})\n"
                f"  Yet collateral was withdrawn: ${withdrawal_amount / 100:.2f}\n"
                f"  This violates Invariant I2"
            )

    # Better: verify that if withdrawal occurred, it was safe
    if collateral_after < collateral_before:
        withdrawal_amount = collateral_before - collateral_after
        print(f"Collateral withdrawal occurred: ${withdrawal_amount / 100:.2f}")

        # Calculate what allowed_limit would be after this withdrawal
        haircut = rt_after.get("collateral_haircut", 0.0)
        allowed_limit_after = int(collateral_after * (1 - haircut))

        assert credit_used <= allowed_limit_after, \
            f"UNSAFE WITHDRAWAL: After withdrawing ${withdrawal_amount / 100:.2f}, " \
            f"credit_used ({credit_used}) exceeds allowed_limit ({allowed_limit_after})"
    else:
        print("No collateral withdrawal occurred (correct behavior if over limit)")


def test_no_agent_exceeds_limit_during_crisis():
    """
    Simplified crisis scenario that ensures no agent ever exceeds their limit.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000_00,
                "collateral_haircut": 0.05,
                "unsecured_cap": 0,
                "policy": "simple_queue_flush",
                "arrival_config": {
                    "poisson_lambda": 2.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 5000.0,
                        "std_dev": 1000.0
                    },
                    "counterparty_weights": {"BANK_B": 1.0}
                }
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000_00,
                "collateral_haircut": 0.05,
                "unsecured_cap": 0,
                "policy": "simple_queue_flush",
                "arrival_config": {
                    "poisson_lambda": 2.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 5000.0,
                        "std_dev": 1000.0
                    },
                    "counterparty_weights": {"BANK_A": 1.0}
                }
            }
        ],
        "global_config": {
            "enable_lsm": True,
            "lsm_frequency_ticks": 5
        }
    }

    orch = Orchestrator.new(config)

    for tick in range(200):
        orch.tick()

        for agent_id in ["BANK_A", "BANK_B"]:
            state = orch.get_agent_state(agent_id)

            credit_used = state.get("credit_used")
            allowed_limit = state.get("allowed_overdraft_limit")

            if credit_used is not None and allowed_limit is not None:
                assert credit_used <= allowed_limit, \
                    f"Tick {tick}, Agent {agent_id}: " \
                    f"credit_used ({credit_used}) > allowed_limit ({allowed_limit})"


def test_auto_withdraw_deferred_when_unsafe(crisis_config):
    """
    Verify that auto-withdraw timer does NOT execute when agent is overdrawn.

    This tests that the auto-withdraw logic in the policy tree is state-safe.
    """
    # Modify config to ensure agents post collateral
    config = crisis_config.copy()

    # Reduce opening balances to create liquidity pressure
    for agent_cfg in config["agent_configs"]:
        agent_cfg["opening_balance"] = 50_000_00  # Low balance

    orch = Orchestrator.new(config)

    # Track collateral events
    collateral_withdrawal_attempts = []
    agent_ids = [agent["id"] for agent in config["agent_configs"]]

    # Run for enough ticks to trigger auto-withdraw timers
    for tick in range(50):
        orch.tick()

        # Check events for collateral withdrawals
        events = orch.get_tick_events(tick)

        for event in events:
            if event.get("event_type") in ["collateral_withdrawn", "collateral_release_deferred"]:
                agent_id = event.get("agent_id")

                if agent_id:
                    state = orch.get_agent_state(agent_id)
                    credit_used = max(0, -state["balance"])
                    allowed_limit = state.get("allowed_overdraft_limit", state.get("credit_limit", 0))

                    collateral_withdrawal_attempts.append({
                        "tick": tick,
                        "agent": agent_id,
                        "event_type": event["event_type"],
                        "amount": event.get("amount", 0),
                        "credit_used": credit_used,
                        "allowed_limit": allowed_limit,
                        "was_deferred": event["event_type"] == "collateral_release_deferred"
                    })

    # Verify that any withdrawal that occurred was safe
    unsafe_withdrawals = []
    for attempt in collateral_withdrawal_attempts:
        if attempt["event_type"] == "collateral_withdrawn":
            # Withdrawal happened - verify it was safe
            if attempt["credit_used"] > attempt["allowed_limit"]:
                unsafe_withdrawals.append(attempt)

    if unsafe_withdrawals:
        print("\n=== UNSAFE WITHDRAWALS DETECTED ===")
        for w in unsafe_withdrawals:
            print(json.dumps(w, indent=2))

    assert len(unsafe_withdrawals) == 0, \
        f"Found {len(unsafe_withdrawals)} unsafe auto-withdrawals"


def test_collateral_posting_increases_headroom():
    """
    Verify that posting collateral increases allowed_overdraft_limit.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 200_000_00,
                "collateral_haircut": 0.10,
                "max_collateral_capacity": 500_000_00,
                "policy": "simple_queue_flush",
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial state
    state_before = orch.get_agent_state("BANK_A")
    limit_before = state_before.get("allowed_overdraft_limit", 0)

    print(f"Before: allowed_limit = ${limit_before / 100:.2f}")

    # Post $100k collateral
    result = orch.post_collateral("BANK_A", 100_000_00, "test_posting")
    assert result.get("success") is True or result.get("new_total") == 100_000_00

    # Check new state
    state_after = orch.get_agent_state("BANK_A")
    limit_after = state_after.get("allowed_overdraft_limit")

    if limit_after is None:
        pytest.skip("New collateral fields not yet implemented")

    print(f"After: allowed_limit = ${limit_after / 100:.2f}")

    # Expected increase: $100k × 0.9 = $90k
    expected_increase = int(100_000_00 * 0.9)

    assert limit_after >= limit_before + expected_increase, \
        f"Posting collateral should increase allowed_limit by at least ${expected_increase / 100:.2f}"


def test_headroom_display_in_verbose_output(crisis_config):
    """
    Verify that verbose output includes new headroom metrics.

    This test checks that the display logic is updated to show the new fields.
    """
    orch = Orchestrator.new(crisis_config)

    # Run a few ticks
    for _ in range(10):
        orch.tick()

    # Get state for one agent
    state = orch.get_agent_state("REGIONAL_TRUST")

    # Check that new fields are exposed
    required_fields = [
        "credit_used",
        "allowed_overdraft_limit",
        "overdraft_headroom",
        "collateral_haircut"
    ]

    missing_fields = [f for f in required_fields if f not in state]

    if missing_fields:
        pytest.skip(f"New fields not yet implemented: {missing_fields}")

    # Verify relationships
    credit_used = state["credit_used"]
    allowed_limit = state["allowed_overdraft_limit"]
    headroom = state["overdraft_headroom"]

    assert headroom == allowed_limit - credit_used, \
        f"Headroom calculation incorrect: {headroom} != {allowed_limit} - {credit_used}"


@pytest.mark.parametrize("haircut", [0.0, 0.02, 0.05, 0.10, 0.20, 0.50])
def test_various_haircut_levels(haircut):
    """
    Test that invariants hold across various haircut levels.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000_00,
                "collateral_haircut": haircut,
                "max_collateral_capacity": 500_000_00,
                "policy": "simple_queue_flush",
                "arrival_config": {
                    "poisson_lambda": 1.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 10000.0,
                        "std_dev": 2000.0
                    },
                    "counterparty_weights": {"BANK_B": 1.0}
                }
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000_00,
                "collateral_haircut": haircut,
                "max_collateral_capacity": 500_000_00,
                "policy": "simple_queue_flush",
                "arrival_config": {
                    "poisson_lambda": 1.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 10000.0,
                        "std_dev": 2000.0
                    },
                    "counterparty_weights": {"BANK_A": 1.0}
                }
            }
        ],
    }

    orch = Orchestrator.new(config)

    for tick in range(100):
        orch.tick()

        for agent_id in ["BANK_A", "BANK_B"]:
            state = orch.get_agent_state(agent_id)

            credit_used = state.get("credit_used")
            allowed_limit = state.get("allowed_overdraft_limit")

            if credit_used is not None and allowed_limit is not None:
                assert credit_used <= allowed_limit, \
                    f"Haircut {haircut}, Tick {tick}, Agent {agent_id}: " \
                    f"credit_used ({credit_used}) > allowed_limit ({allowed_limit})"
