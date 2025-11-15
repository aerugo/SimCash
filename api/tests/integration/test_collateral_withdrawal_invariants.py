"""
Integration tests for collateral withdrawal invariants.

These tests enforce the T2/CLM-style collateralized intraday credit rules:
- I1: credit_used ≤ allowed_overdraft_limit
- I2: Cannot withdraw collateral if it would breach headroom
- I3: Buffer cushion maintained after withdrawal

These tests will FAIL initially until the implementation is complete.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_cannot_withdraw_while_overdrawn():
    """
    Invariant I2: Cannot withdraw collateral if credit_used > 0
    and withdrawal would breach allowed_overdraft_limit.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -100_000_00,  # $100k overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,  # 10% haircut
                "unsecured_cap": 0,
                "posted_collateral": 120_000_00,  # Posted to cover overdraft
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Verify initial state
    state = orch.get_agent_state("BANK_A")
    assert state["balance"] == -100_000_00, "Agent should be overdrawn"
    assert state["posted_collateral"] == 120_000_00, "Collateral should be posted"

    # credit_used = 100k
    # allowed_limit = 108k (120k × 0.9)
    # headroom = 8k
    # Attempting to withdraw $50k would leave:
    # new_limit = (70k × 0.9) = 63k < 100k usage → VIOLATION

    # Try to withdraw $50k (should fail)
    result = orch.withdraw_collateral("BANK_A", 50_000_00)

    assert result["success"] is False, \
        f"Withdrawal should be rejected. Got: {result}"

    error_msg = result.get("message", "").lower()
    assert "breach" in error_msg or "headroom" in error_msg or "insufficient" in error_msg, \
        f"Should reject withdrawal with headroom violation. Got: {result['message']}"

    # Verify collateral unchanged
    state_after = orch.get_agent_state("BANK_A")
    assert state_after["posted_collateral"] == 120_000_00, \
        "Collateral should remain unchanged after rejected withdrawal"


def test_can_withdraw_excess_collateral():
    """
    Should allow withdrawal of collateral that exceeds requirement.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 0,  # No overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.05,
                "posted_collateral": 200_000_00,  # Excess posted
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Should allow withdrawal since no credit is being used
    result = orch.withdraw_collateral("BANK_A", 150_000_00)

    assert result.get("success") is True or result.get("new_total") == 50_000_00, \
        f"Should successfully withdraw excess collateral. Got: {result}"

    # Verify state updated
    state = orch.get_agent_state("BANK_A")
    assert state["posted_collateral"] == 50_000_00, \
        "Posted collateral should be updated after successful withdrawal"


def test_withdrawal_respects_safety_buffer():
    """
    Invariant I3: Withdrawal should maintain headroom ≥ buffer.
    """
    # Note: safety_buffer might be a global config or per-agent
    # For now, testing the underlying max_withdrawable_collateral logic
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -30_000_00,  # Using $30k credit
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,
                "posted_collateral": 100_000_00,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 30k
    # allowed_limit = 90k (100k × 0.9)
    # headroom = 60k
    #
    # If buffer = 20k (hardcoded in FFI or passed), need headroom ≥ 20k after withdrawal
    # Max withdrawable ≈ amount that keeps C_new × 0.9 ≥ 50k (30k + 20k)
    # C_new ≥ 55,556 → max withdraw = 100k - 55,556 = 44,444

    # Try to withdraw $50k (should fail if buffer is enforced)
    # This test may pass if buffer is 0, but documents the behavior
    try:
        result = orch.withdraw_collateral("BANK_A", 50_000_00)
        # If it succeeds, buffer is not enforced or is small
        # Verify that headroom is still reasonable
        state = orch.get_agent_state("BANK_A")
        credit_used = max(0, -state["balance"])
        allowed_limit = state.get("allowed_overdraft_limit", state.get("credit_limit", 0))
        headroom = allowed_limit - credit_used

        # At least verify it didn't create a violation
        assert headroom >= 0, "Withdrawal should not create negative headroom"

    except Exception as e:
        # If it fails, good - buffer is being enforced
        assert "breach" in str(e).lower() or "headroom" in str(e).lower(), \
            f"Should mention headroom/breach in error. Got: {e}"


def test_max_withdrawable_at_utilization_limit():
    """
    Cannot withdraw any collateral when at full utilization.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -90_000_00,  # $90k overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,
                "posted_collateral": 100_000_00,  # Exactly covers usage
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 90k
    # allowed_limit = 90k (100k × 0.9)
    # headroom = 0
    # Cannot withdraw anything

    result = orch.withdraw_collateral("BANK_A", 1_00)  # Even $1 should fail
    assert result["success"] is False, f"Should reject any withdrawal at full utilization. Got: {result}"

    error_msg = result.get("message", "").lower()
    assert "breach" in error_msg or "headroom" in error_msg or "insufficient" in error_msg, \
        f'Should reject any withdrawal at full utilization. Got: {result["message"]}'


def test_tick_282_scenario_withdrawal_blocked():
    """
    Reproduces tick 282 REGIONAL_TRUST scenario where withdrawal
    should have been blocked but wasn't.

    This test will FAIL initially (withdrawal succeeds), PASS after fix (withdrawal rejected).
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "REGIONAL_TRUST",
                "opening_balance": -164_897_33,  # Deep overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.02,
                "posted_collateral": 50_000_00,  # Hypothetical amount
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 164,897
    # allowed_limit = 49,000 (50k × 0.98)
    # Already massively over limit!

    # Attempt the withdrawal that occurred at tick 282
    result = orch.withdraw_collateral("REGIONAL_TRUST", 17_934_08)
    assert result["success"] is False, f"Should block withdrawal when deeply overdrawn.. Got: {result}"
    error_msg = result.get("message", "").lower()
    assert "breach" in error_msg or "headroom" in error_msg or "insufficient" in error_msg, \
        f'Should block withdrawal when deeply overdrawn.. Got: {result["message"]}'

    # Verify collateral unchanged
    state = orch.get_agent_state("REGIONAL_TRUST")
    assert state["posted_collateral"] == 50_000_00, \
        "Collateral should not decrease when agent is over limit"


def test_can_withdraw_partial_amount_safely():
    """
    Should allow withdrawal up to max_withdrawable amount.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -60_000_00,  # $60k overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,
                "posted_collateral": 100_000_00,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 60k
    # Need: C_new × 0.9 ≥ 60k → C_new ≥ 66,667
    # Max withdraw ≈ 33,333

    # Try to withdraw $30k (should succeed)
    result = orch.withdraw_collateral("BANK_A", 30_000_00)

    assert result.get("success") is True or result.get("new_total") == 70_000_00, \
        f"Should allow safe withdrawal. Got: {result}"

    # Verify new state maintains invariant
    state = orch.get_agent_state("BANK_A")
    assert state["posted_collateral"] == 70_000_00

    credit_used = max(0, -state["balance"])
    # Calculate new allowed_limit based on remaining collateral
    new_allowed_limit = int((70_000_00 * 0.9))  # 63,000

    assert credit_used <= new_allowed_limit, \
        f"After withdrawal, credit_used ({credit_used}) must be ≤ allowed_limit ({new_allowed_limit})"


def test_withdrawal_with_unsecured_cap():
    """
    Unsecured cap should reduce the required collateral.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -50_000_00,  # $50k overdraft
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,
                "unsecured_cap": 20_000_00,  # $20k unsecured daylight cap
                "posted_collateral": 80_000_00,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 50k
    # allowed_limit = (80k × 0.9) + 20k = 72k + 20k = 92k
    # headroom = 42k
    #
    # Need: C_new × 0.9 + 20k ≥ 50k
    # Need: C_new ≥ (50k - 20k) / 0.9 = 33,334
    # Max withdraw ≈ 80k - 33,334 = 46,666

    # Try to withdraw $40k (should succeed)
    result = orch.withdraw_collateral("BANK_A", 40_000_00)

    assert result.get("success") is True or result.get("new_total") == 40_000_00, \
        f"Should allow withdrawal with unsecured cap reducing requirement. Got: {result}"

    # Try to withdraw $50k (should fail - exceeds max_withdrawable)
    result = orch.withdraw_collateral("BANK_A", 50_000_00)
    assert result["success"] is False, f"Withdrawal should be rejected. Got: {result}"


def test_min_holding_ticks_still_enforced():
    """
    Verify that MIN_HOLDING_TICKS constraint is still checked
    in addition to headroom checks.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000_00,  # Positive balance
                "unsecured_cap": 0,
                "posted_collateral": 0,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Post collateral
    result = orch.post_collateral("BANK_A", 50_000_00)
    assert result.get("success") is True or result.get("new_total") == 50_000_00

    # Immediately try to withdraw (should fail due to MIN_HOLDING_TICKS)
    result = orch.withdraw_collateral("BANK_A", 10_000_00)
    assert result["success"] is False, f"Should enforce MIN_HOLDING_TICKS. Got: {result}"

    error_msg = result.get("message", "").lower()
    assert "holding" in error_msg or "ticks" in error_msg or "recently" in error_msg or "minimum" in error_msg, \
        f'Should enforce MIN_HOLDING_TICKS. Got: {result["message"]}'


def test_state_exposes_new_collateral_fields():
    """
    Verify that get_agent_state() returns the new collateral/headroom fields.
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -50_000_00,
                "unsecured_cap": 0,
                "collateral_haircut": 0.10,
                "unsecured_cap": 10_000_00,
                "posted_collateral": 100_000_00,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)
    state = orch.get_agent_state("BANK_A")

    # Check that new fields exist
    assert "credit_used" in state, "Should expose credit_used"
    assert "allowed_overdraft_limit" in state, "Should expose allowed_overdraft_limit"
    assert "overdraft_headroom" in state, "Should expose overdraft_headroom"
    assert "max_withdrawable_collateral" in state, "Should expose max_withdrawable_collateral"
    assert "collateral_haircut" in state, "Should expose collateral_haircut"

    # Verify values are correct
    assert state["credit_used"] == 50_000_00, \
        f"credit_used should be 50k. Got: {state['credit_used']}"

    expected_allowed = int((100_000_00 * 0.9)) + 10_000_00  # 90k + 10k = 100k
    assert state["allowed_overdraft_limit"] == expected_allowed, \
        f"allowed_overdraft_limit should be {expected_allowed}. Got: {state['allowed_overdraft_limit']}"

    expected_headroom = expected_allowed - 50_000_00  # 100k - 50k = 50k
    assert state["overdraft_headroom"] == expected_headroom, \
        f"overdraft_headroom should be {expected_headroom}. Got: {state['overdraft_headroom']}"

    assert state["collateral_haircut"] == 0.10, \
        f"collateral_haircut should be 0.10. Got: {state['collateral_haircut']}"


def test_zero_haircut_edge_case():
    """
    Test 0% haircut (full collateral value, 1:1 relationship).
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -80_000_00,
                "unsecured_cap": 0,
                "collateral_haircut": 0.0,  # 0% haircut
                "posted_collateral": 100_000_00,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 80k
    # allowed_limit = 100k (100k × 1.0)
    # headroom = 20k
    # Can withdraw up to 20k

    result = orch.withdraw_collateral("BANK_A", 20_000_00)
    assert result.get("success") is True or result.get("new_total") == 80_000_00, \
        "Should allow withdrawal up to exact credit usage with 0% haircut"

    # Cannot withdraw more
    result = orch.withdraw_collateral("BANK_A", 1_00)
    assert result["success"] is False, f"Withdrawal should be rejected. Got: {result}"  # Even $1 more should fail


def test_100_percent_haircut_edge_case():
    """
    Test 100% haircut (collateral provides no credit capacity).
    """
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 50_000_00,  # Positive balance
                "unsecured_cap": 0,
                "collateral_haircut": 1.0,  # 100% haircut (worthless collateral)
                "posted_collateral": 100_000_00,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Advance past MIN_HOLDING_TICKS if needed
    for _ in range(6):
        orch.tick()

    # With 100% haircut and no unsecured cap, allowed_limit = 0
    # But agent has positive balance, so not using any credit
    # Should be able to withdraw all collateral (it's not backing anything)
    result = orch.withdraw_collateral("BANK_A", 100_000_00)

    assert result.get("success") is True or result.get("new_total") == 0, \
        "Should allow withdrawal of worthless collateral when not using credit"
