"""
TDD Tests for Bilateral and Multilateral Limits (Phase 1)

TARGET2 allows participants to set limits on payment flows:
- Bilateral limits: Maximum outflow to a specific counterparty
- Multilateral limits: Maximum total outflow to all participants

Test Strategy:
1. Write failing tests first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor while keeping tests green

This module follows the TDD plan in docs/plans/target2-lsm-tdd-implementation.md
"""

import pytest
from payment_simulator._core import Orchestrator


def make_agent(agent_id: str, balance: int, limits: dict = None, policy: str = "Fifo", unsecured_cap: int = 0) -> dict:
    """Helper to create agent config with sensible defaults."""
    agent = {
        "id": agent_id,
        "opening_balance": balance,
        "unsecured_cap": unsecured_cap,
        "policy": {"type": policy},
    }
    if limits:
        agent["limits"] = limits
    return agent


# ============================================================================
# TDD Step 1.1: AgentLimits Data Structure
# ============================================================================


class TestAgentLimitsConfig:
    """TDD Step 1.1: AgentLimits configuration accepted."""

    def test_bilateral_limits_config_accepted(self):
        """Config with bilateral_limits should be accepted without error."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_multilateral_limit_config_accepted(self):
        """Config with multilateral_limit should be accepted without error."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"multilateral_limit": 800_000}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_combined_limits_config_accepted(self):
        """Config with both bilateral and multilateral limits should be accepted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={
                    "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 300_000},
                    "multilateral_limit": 700_000
                }),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_get_agent_limits(self):
        """Should be able to query agent's limits via FFI."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={
                    "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 300_000},
                    "multilateral_limit": 700_000
                }),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        limits = orch.get_agent_limits("BANK_A")

        assert limits["bilateral_limits"]["BANK_B"] == 500_000
        assert limits["bilateral_limits"]["BANK_C"] == 300_000
        assert limits["multilateral_limit"] == 700_000

    def test_agent_without_limits_returns_none(self):
        """Agent without limits configured should return None/empty."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        limits = orch.get_agent_limits("BANK_A")

        # Should have empty bilateral_limits and no multilateral_limit
        assert limits["bilateral_limits"] == {} or limits["bilateral_limits"] is None
        assert limits["multilateral_limit"] is None


# ============================================================================
# TDD Step 1.2: Bilateral Limit Enforcement
# ============================================================================


class TestBilateralLimitEnforcement:
    """TDD Step 1.2: Bilateral limits block settlements."""

    def test_payment_within_bilateral_limit_settles(self):
        """Payment within bilateral limit should settle immediately."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Submit payment within limit (400k < 500k limit)
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=400_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Should settle (has liquidity AND within limit)
        details = orch.get_transaction_details(tx_id)
        assert details["status"] == "Settled"

    def test_payment_exceeding_bilateral_limit_queued(self):
        """Payment exceeding bilateral limit should be queued, not settled."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Submit payment exceeding limit (600k > 500k limit)
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Should be queued despite having sufficient liquidity
        assert orch.queue_size() == 1
        details = orch.get_transaction_details(tx_id)
        assert details["status"] != "Settled"

    def test_bilateral_limit_exceeded_event_emitted(self):
        """BilateralLimitExceeded event should be emitted when limit blocks payment."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "BilateralLimitExceeded"]

        assert len(limit_events) == 1
        event = limit_events[0]

        # All fields for replay identity
        assert event["sender"] == "BANK_A"
        assert event["receiver"] == "BANK_B"
        assert event["bilateral_limit"] == 500_000
        assert event["amount"] == 600_000
        assert event["current_bilateral_outflow"] == 0

    def test_bilateral_limit_per_counterparty(self):
        """Different counterparties should have independent bilateral limits."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 2_000_000, limits={
                    "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 300_000}
                }),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # 400k to B (within 500k limit) - should settle
        tx_b = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=400_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        # 400k to C (exceeds 300k limit) - should be queued
        tx_c = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_C",
            amount=400_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        # Only C payment should be queued
        assert orch.queue_size() == 1

        details_b = orch.get_transaction_details(tx_b)
        details_c = orch.get_transaction_details(tx_c)

        assert details_b["status"] == "Settled"
        assert details_c["status"] != "Settled"


# ============================================================================
# TDD Step 1.3: Cumulative Bilateral Tracking
# ============================================================================


class TestCumulativeBilateralTracking:
    """TDD Step 1.3: Bilateral limits track cumulative outflow."""

    def test_cumulative_bilateral_outflow_tracked(self):
        """Multiple payments should cumulatively track toward bilateral limit."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # First payment: 300k (within 500k limit)
        tx1 = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 0  # Settled

        # Second payment: 300k (cumulative 600k > 500k limit)
        tx2 = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1  # Queued due to limit

        # Verify event shows current outflow
        events = orch.get_tick_events(1)
        limit_events = [e for e in events if e.get("event_type") == "BilateralLimitExceeded"]
        assert len(limit_events) == 1
        assert limit_events[0]["current_bilateral_outflow"] == 300_000

    def test_bilateral_outflow_resets_at_day_boundary(self):
        """Bilateral outflow tracking should reset at start of new day."""
        config = {
            "ticks_per_day": 10,  # Short day for testing
            "num_days": 3,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 2_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Day 0: Use up limit
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=500_000,
            deadline_tick=5,
            priority=5,
            divisible=False,
        )
        for _ in range(10):
            orch.tick()

        # Now at Day 1
        assert orch.current_day() == 1

        # Day 1: Limit should reset - new 500k available
        tx = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=15,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Should settle (limit reset)
        details = orch.get_transaction_details(tx)
        assert details["status"] == "Settled"

    def test_get_agent_current_outflows(self):
        """Should be able to query agent's current bilateral outflows."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Make a payment
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        # Query outflows
        outflows = orch.get_agent_current_outflows("BANK_A")

        assert outflows["bilateral_outflows"]["BANK_B"] == 300_000
        assert outflows["total_outflow"] == 300_000


# ============================================================================
# TDD Step 1.4: Multilateral Limit Enforcement
# ============================================================================


class TestMultilateralLimitEnforcement:
    """TDD Step 1.4: Multilateral limits block settlements."""

    def test_payment_within_multilateral_limit_settles(self):
        """Payment within multilateral limit should settle immediately."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"multilateral_limit": 800_000}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=700_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["status"] == "Settled"

    def test_payment_exceeding_multilateral_limit_queued(self):
        """Payment exceeding multilateral limit should be queued."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"multilateral_limit": 500_000}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        assert orch.queue_size() == 1

    def test_multilateral_limit_tracks_total_outflow_across_counterparties(self):
        """Multilateral limit should track total outflow to all counterparties."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 2_000_000, limits={"multilateral_limit": 500_000}),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # 300k to B - settles (300k < 500k multilateral)
        tx_b = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 0

        # 300k to C - queued (cumulative 600k > 500k multilateral)
        tx_c = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_C",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1

        # Verify event
        events = orch.get_tick_events(1)
        limit_events = [e for e in events if e.get("event_type") == "MultilateralLimitExceeded"]
        assert len(limit_events) == 1

    def test_multilateral_limit_exceeded_event_emitted(self):
        """MultilateralLimitExceeded event should be emitted."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"multilateral_limit": 500_000}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "MultilateralLimitExceeded"]

        assert len(limit_events) == 1
        event = limit_events[0]

        assert event["sender"] == "BANK_A"
        assert event["multilateral_limit"] == 500_000
        assert event["amount"] == 600_000
        assert event["current_total_outflow"] == 0


# ============================================================================
# TDD Step 1.5: Combined Limits
# ============================================================================


class TestCombinedLimits:
    """Tests for bilateral AND multilateral limits together."""

    def test_both_limits_applied(self):
        """Both bilateral and multilateral limits should be checked."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 2_000_000, limits={
                    "bilateral_limits": {"BANK_B": 400_000},
                    "multilateral_limit": 600_000,
                }),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # 350k to B - settles (within both limits)
        tx1 = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=350_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 0

        # 100k to B - queued (bilateral: 350k + 100k = 450k > 400k limit)
        tx2 = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1

    def test_multilateral_blocks_before_bilateral_exhausted(self):
        """Multilateral limit can block payment even if bilateral allows it."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 2_000_000, limits={
                    "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 500_000},
                    "multilateral_limit": 400_000,  # Lower than bilateral
                }),
                make_agent("BANK_B", 1_000_000),
                make_agent("BANK_C", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        # 300k to B - settles
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 0

        # 200k to C - queued (within bilateral 500k, but multilateral 300+200=500 > 400)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_C",
            amount=200_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()
        assert orch.queue_size() == 1


# ============================================================================
# TDD Step 1.6: Limits in LSM
# ============================================================================


class TestLimitsInLsm:
    """TDD Step 1.6: LSM respects limits in cycle settlement."""

    def test_lsm_bilateral_offset_respects_limits(self):
        """LSM bilateral offset should check limits before settling."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": False},
            "agent_configs": [
                make_agent("BANK_A", 100, limits={"bilateral_limits": {"BANK_B": 200_000}}),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Create offsetting payments
        # A->B 300k (exceeds A's 200k bilateral limit to B)
        # B->A 300k
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        # Even though net is 0, A->B exceeds bilateral limit
        # Should NOT offset
        assert orch.queue_size() == 2

    def test_lsm_cycle_respects_limits(self):
        """LSM cycle settlement should check limits for each leg."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": True},
            "agent_configs": [
                make_agent("BANK_A", 50_000, limits={"bilateral_limits": {"BANK_B": 200_000}}),
                make_agent("BANK_B", 50_000),
                make_agent("BANK_C", 50_000),
            ]
        }
        orch = Orchestrator.new(config)

        # Cycle: A->B (300k, exceeds limit), B->C (300k), C->A (300k)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_C",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_C",
            receiver="BANK_A",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        # Cycle should NOT settle due to A's bilateral limit to B
        assert orch.queue_size() == 3

    def test_lsm_offset_within_limits_succeeds(self):
        """LSM offset should succeed when all payments are within limits."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": False},
            "agent_configs": [
                make_agent("BANK_A", 100, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 100),
            ]
        }
        orch = Orchestrator.new(config)

        # Offsetting payments within limits
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=300_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        orch.tick()

        # Should offset successfully
        assert orch.queue_size() == 0


# ============================================================================
# TDD Step 1.7: Limits Events Display (CLI)
# ============================================================================


class TestLimitsEventDisplay:
    """Tests for limits events in verbose output."""

    def test_bilateral_limit_exceeded_displayed(self):
        """BilateralLimitExceeded should appear in verbose output."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "BilateralLimitExceeded"]

        # Verify event has all fields needed for display
        assert len(limit_events) == 1
        event = limit_events[0]

        # Required fields for verbose display
        assert "tick" in event
        assert "sender" in event
        assert "receiver" in event
        assert "bilateral_limit" in event
        assert "amount" in event
        assert "current_bilateral_outflow" in event
        assert "tx_id" in event


# ============================================================================
# TDD Step 1.8: Limits E2E Replay Identity
# ============================================================================


class TestLimitsReplayIdentity:
    """TDD Step 1.8: Limits events replay correctly."""

    def test_bilateral_limit_exceeded_event_has_all_fields(self):
        """BilateralLimitExceeded event should have all fields for replay."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"bilateral_limits": {"BANK_B": 500_000}}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "BilateralLimitExceeded"]

        assert len(limit_events) == 1
        event = limit_events[0]

        # Full field list for replay identity
        required_fields = [
            "event_type", "tick", "tx_id", "sender", "receiver",
            "amount", "bilateral_limit", "current_bilateral_outflow"
        ]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"

    def test_multilateral_limit_exceeded_event_has_all_fields(self):
        """MultilateralLimitExceeded event should have all fields for replay."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                make_agent("BANK_A", 1_000_000, limits={"multilateral_limit": 500_000}),
                make_agent("BANK_B", 1_000_000),
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "MultilateralLimitExceeded"]

        assert len(limit_events) == 1
        event = limit_events[0]

        # Full field list for replay identity
        required_fields = [
            "event_type", "tick", "tx_id", "sender",
            "amount", "multilateral_limit", "current_total_outflow"
        ]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
