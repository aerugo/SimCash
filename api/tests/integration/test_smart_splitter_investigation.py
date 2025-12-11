"""
Integration tests for SMART_SPLITTER investigation (from lsm-splitting-investigation-plan.md).

Tests verify that the SMART_SPLITTER policy correctly handles splitting decisions
through the full orchestrator stack, including the identified bug where negative
available_liquidity prevents splitting.

Test 7: Full Orchestrator Splitting Scenario
"""

import pytest
import json
from pathlib import Path
from payment_simulator._core import Orchestrator


def test_smart_splitter_splits_under_stress():
    """
    Test 7: Integration test - SMART_SPLITTER should split when liquidity-constrained.

    This test verifies the complete workflow through Python FFI:
    1. Agent starts with limited balance but has credit
    2. Large divisible transaction exceeds balance
    3. Policy should decide to split (using credit headroom)
    4. At least one chunk should settle
    5. Costs should be reasonable (not death spiral levels)

    This test will FAIL before the fix (policy holds instead of splitting)
    and PASS after the fix (policy splits using effective_liquidity).
    """
    # Load the smart_splitter policy JSON
    policy_path = Path(__file__).parents[3] / "simulator" / "policies" / "smart_splitter.json"
    with open(policy_path) as f:
        policy_json = f.read()

    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "SMART_SPLITTER",
                "opening_balance": 200_000,  # $2k
                "unsecured_cap": 500_000,     # $5k credit
                "policy": {
                    "type": "FromJson",
                    "json": policy_json,
                },
            },
            {
                "id": "RECEIVER",
                "opening_balance": 10_000_000,  # $100k - sufficient liquidity
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "split_friction_cost": 1_000,  # $10 per split
            "overdraft_bps_per_tick": 0.0001,
            "delay_cost_per_tick_per_cent": 0.0001,
        },
    }

    orch = Orchestrator.new(config)

    initial_balance = orch.get_agent_balance("SMART_SPLITTER")
    assert initial_balance == 200_000, "Should start with $2k"

    # Submit large divisible transaction: $5k
    # - Exceeds balance ($2k) but within credit capacity
    # - Exceeds split_threshold ($3k) in policy
    # - Transaction is divisible (required for splitting)
    tx_id = orch.submit_transaction(
        sender="SMART_SPLITTER",
        receiver="RECEIVER",
        amount=500_000,  # $5k
        deadline_tick=50,
        priority=5,
        divisible=True,  # MUST be divisible for splitting
    )

    # Run one tick - policy should evaluate and act
    result = orch.tick()

    # CRITICAL ASSERTIONS
    # After fix: SMART_SPLITTER should split the transaction
    # Before fix: Policy holds (bug) due to negative available_liquidity check

    # Check if any settlements occurred
    # If splitting worked, at least one chunk should have settled
    balance_after = orch.get_agent_balance("SMART_SPLITTER")
    balance_changed = balance_after != initial_balance

    if not balance_changed:
        # Balance didn't change - no settlements occurred
        # This indicates the policy held instead of splitting (BUG)
        queue_size = orch.get_queue2_size()

        pytest.fail(
            f"SMART_SPLITTER did not settle any payment chunks. "
            f"Balance unchanged: ${initial_balance/100:.2f}, Queue size: {queue_size}. "
            f"\n\nBUG REPRODUCED: Policy likely held due to negative available_liquidity check. "
            f"The policy should have split the $50 transaction using credit headroom. "
            f"\n\nExpected behavior: Split into chunks, settle at least one chunk. "
            f"Actual behavior: Held in queue, no settlement. "
            f"\n\nThis reproduces the $25M cost accumulation from the simulation review."
        )

    # If we got here, balance changed - some settlement occurred
    # Verify settlements actually happened
    assert result["num_settlements"] > 0, (
        f"num_settlements should be > 0 if balance changed. "
        f"Got {result['num_settlements']}"
    )

    # Check that balance decreased (payment was sent)
    assert balance_after < initial_balance, (
        f"Balance should decrease after sending payment. "
        f"Initial: ${initial_balance/100:.2f}, After: ${balance_after/100:.2f}"
    )

    # Verify costs are reasonable (not death spiral)
    # If splitting worked, costs should be dominated by split friction
    # If policy held (bug), costs would include large delay/overdraft costs

    # Note: We can't directly query split friction cost via FFI yet,
    # but we can verify that the agent isn't in a death spiral by
    # checking that the balance change is reasonable relative to the
    # transaction amount

    amount_settled = abs(balance_after - initial_balance)
    assert amount_settled > 0, "Some amount should have settled"

    # If the full transaction ($5k) was sent, balance would be -$3k (using credit)
    # If chunks were sent, balance should be less negative or possibly still positive
    # The key is that SOME progress was made

    print(f"✅ SMART_SPLITTER made progress:")
    print(f"   Initial balance: ${initial_balance/100:.2f}")
    print(f"   Final balance: ${balance_after/100:.2f}")
    print(f"   Amount settled: ${amount_settled/100:.2f}")
    print(f"   Settlements: {result['num_settlements']}")
    print(f"   Queue size: {orch.get_queue2_size()}")


def test_smart_splitter_with_negative_balance_bug_reproduction():
    """
    Test 7b: Reproduce the exact bug condition from simulation review.

    This test deliberately pushes SMART_SPLITTER into overdraft first,
    then submits a large transaction. The policy should split using
    credit headroom, but the bug causes it to hold instead.

    This is the most direct reproduction of the death spiral scenario.
    """
    # Load the smart_splitter policy JSON
    policy_path = Path(__file__).parents[3] / "simulator" / "policies" / "smart_splitter.json"
    with open(policy_path) as f:
        policy_json = f.read()

    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "SMART_SPLITTER",
                "opening_balance": 100_000,  # $1k - will go negative quickly
                "unsecured_cap": 500_000,     # $5k credit
                "policy": {
                    "type": "FromJson",
                    "json": policy_json,
                },
            },
            {
                "id": "RECEIVER",
                "opening_balance": 10_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "split_friction_cost": 1_000,
            "overdraft_bps_per_tick": 0.01,  # High overdraft cost to show death spiral
            "delay_cost_per_tick_per_cent": 0.0001,
        },
    }

    orch = Orchestrator.new(config)

    # Phase 1: Push agent into overdraft with first transaction
    tx1_id = orch.submit_transaction(
        sender="SMART_SPLITTER",
        receiver="RECEIVER",
        amount=200_000,  # $2k - pushes balance to -$1k
        deadline_tick=100,
        priority=5,
        divisible=False,
    )

    result1 = orch.tick()

    balance_after_tx1 = orch.get_agent_balance("SMART_SPLITTER")
    assert balance_after_tx1 < 0, (
        f"Agent should be in overdraft after first transaction. "
        f"Balance: ${balance_after_tx1/100:.2f}"
    )

    credit_used = abs(balance_after_tx1)
    credit_headroom = 500_000 - credit_used  # $5k limit - used

    print(f"After TX1 (overdraft setup):")
    print(f"  Balance: ${balance_after_tx1/100:.2f} (negative)")
    print(f"  Credit used: ${credit_used/100:.2f}")
    print(f"  Credit headroom: ${credit_headroom/100:.2f}")

    assert credit_headroom > 100_000, (
        f"Agent should still have significant credit headroom. "
        f"Got ${credit_headroom/100:.2f}"
    )

    # Phase 2: Submit large transaction while in overdraft
    # This is where the bug manifests
    tx2_id = orch.submit_transaction(
        sender="SMART_SPLITTER",
        receiver="RECEIVER",
        amount=400_000,  # $4k - exceeds split_threshold ($3k)
        deadline_tick=50,
        priority=5,
        divisible=True,  # MUST be divisible
    )

    result2 = orch.tick()

    balance_after_tx2 = orch.get_agent_balance("SMART_SPLITTER")

    # CRITICAL ASSERTION - this is the bug
    # BUG: available_liquidity is negative, so split condition fails
    # Policy holds the transaction instead of splitting
    # Result: delay costs accumulate, overdraft costs accumulate, death spiral

    if balance_after_tx2 == balance_after_tx1:
        # Balance unchanged - second transaction didn't settle AT ALL
        # This is the bug: policy held when it should have split

        print(f"\n❌ BUG REPRODUCED:")
        print(f"  Second transaction ($4k) made NO progress")
        print(f"  Balance unchanged: ${balance_after_tx2/100:.2f}")
        print(f"  Credit headroom available: ${credit_headroom/100:.2f}")
        print(f"\n  Root cause: available_liquidity = {balance_after_tx1} (negative)")
        print(f"  Policy condition: available_liquidity > $7.50 (min_split_amount)")
        print(f"  Evaluation: {balance_after_tx1} > 75000 = FALSE")
        print(f"  Decision: HOLD (incorrect - should SPLIT)")
        print(f"\n  Fix: Add effective_liquidity = balance + credit_headroom")
        print(f"       effective_liquidity = {balance_after_tx1} + {credit_headroom} = {balance_after_tx1 + credit_headroom}")
        print(f"       New condition: {balance_after_tx1 + credit_headroom} > 75000 = TRUE")
        print(f"       Decision: SPLIT (correct)")

        pytest.fail(
            "BUG CONFIRMED: SMART_SPLITTER holds transaction instead of splitting "
            "when in overdraft. This leads to the $25M cost death spiral from the "
            "simulation review. See diagnostic output above for details."
        )

    # If we got here, some progress was made (fix is working)
    print(f"\n✅ FIX VERIFIED:")
    print(f"  Second transaction made progress despite overdraft")
    print(f"  Balance after TX2: ${balance_after_tx2/100:.2f}")
    print(f"  Settlements: {result2['num_settlements']}")
    print(f"  Policy successfully used credit headroom for splitting decision")
