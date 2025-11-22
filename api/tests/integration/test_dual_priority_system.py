"""TDD Tests for Dual Priority System (Internal vs RTGS Priority).

Phase 0 of TARGET2 LSM Alignment.

This separates the bank's internal prioritization (Queue 1) from the
RTGS declared priority (Queue 2).

Internal Priority (0-10): Bank's internal view of payment importance
RTGS Priority (Urgent/Normal): Declared to RTGS at submission time
"""

import pytest
from payment_simulator._core import Orchestrator


# =============================================================================
# TDD Step 0.1: RtgsPriority Enum
# =============================================================================


class TestRtgsPriorityEnum:
    """TDD Step 0.1: RtgsPriority enum exists and has correct values."""

    def test_rtgs_priority_values_exist(self):
        """RtgsPriority enum should have HighlyUrgent=0, Urgent=1, Normal=2.

        TARGET2 uses these priority levels:
        - HighlyUrgent (0): Restricted to central bank/CLS
        - Urgent (1): Time-critical, higher fees
        - Normal (2): Standard (default)
        """
        # This test will FAIL until we implement the enum
        from payment_simulator._core import RtgsPriority

        # Verify enum values match TARGET2 specification
        assert hasattr(RtgsPriority, "HighlyUrgent")
        assert hasattr(RtgsPriority, "Urgent")
        assert hasattr(RtgsPriority, "Normal")


# =============================================================================
# TDD Step 0.2: Transaction RTGS Priority Fields
# =============================================================================


class TestTransactionRtgsPriorityFields:
    """TDD Step 0.2: Transaction has rtgs_priority and rtgs_submission_tick."""

    def test_transaction_has_rtgs_priority_field(self):
        """Transaction details should include rtgs_priority field."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
        tx_id = orch.submit_transaction(
            "BANK_A", "BANK_B", 100_000, deadline_tick=50, priority=5, divisible=False
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert "rtgs_priority" in details
        # Default should be Normal when submitted through standard path
        assert details["rtgs_priority"] == "Normal"

    def test_transaction_has_rtgs_submission_tick_field(self):
        """Transaction details should include rtgs_submission_tick."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
        tx_id = orch.submit_transaction(
            "BANK_A", "BANK_B", 100_000, deadline_tick=50, priority=5, divisible=False
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert "rtgs_submission_tick" in details
        # Should be tick 0 (when it was processed and entered Queue 2)
        assert details["rtgs_submission_tick"] == 0

    def test_rtgs_priority_none_before_tick(self):
        """rtgs_priority should be None before first tick processes the transaction.

        When a transaction is submitted but not yet processed by a tick,
        it has not yet been submitted to RTGS, so rtgs_priority should be None.
        """
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
        tx_id = orch.submit_transaction(
            "BANK_A", "BANK_B", 100_000, deadline_tick=50, priority=5, divisible=False
        )
        # Don't tick yet - transaction hasn't been processed

        details = orch.get_transaction_details(tx_id)
        # Before RTGS submission (before tick), these should be None
        assert details.get("rtgs_priority") is None
        assert details.get("rtgs_submission_tick") is None


# =============================================================================
# TDD Step 0.3: Submit with RTGS Priority
# =============================================================================


class TestSubmitWithRtgsPriority:
    """TDD Step 0.3: Submit action can specify RTGS priority."""

    def test_submit_transaction_with_rtgs_priority_ffi(self):
        """FFI method to submit with explicit RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # New FFI method with rtgs_priority parameter
        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,  # Internal priority
            divisible=False,
            rtgs_priority="Urgent",  # NEW: RTGS priority
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["priority"] == 5  # Internal priority unchanged
        assert details["rtgs_priority"] == "Urgent"  # RTGS priority set

    def test_submit_with_normal_rtgs_priority(self):
        """Submit with Normal RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            amount=100_000,
            deadline_tick=50,
            priority=9,  # High internal priority
            divisible=False,
            rtgs_priority="Normal",  # Normal RTGS (save fees)
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["priority"] == 9  # High internal
        assert details["rtgs_priority"] == "Normal"  # But Normal RTGS

    def test_internal_and_rtgs_priority_are_independent(self):
        """Internal and RTGS priorities should be completely independent."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # High internal (9), Normal RTGS
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9,
            divisible=False, rtgs_priority="Normal"
        )
        # Low internal (2), Urgent RTGS
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=2,
            divisible=False, rtgs_priority="Urgent"
        )

        orch.tick()

        details1 = orch.get_transaction_details(tx1)
        details2 = orch.get_transaction_details(tx2)

        # Verify independence
        assert details1["priority"] == 9
        assert details1["rtgs_priority"] == "Normal"
        assert details2["priority"] == 2
        assert details2["rtgs_priority"] == "Urgent"


# =============================================================================
# TDD Step 0.4: RtgsSubmission Event
# =============================================================================


class TestRtgsSubmissionEvent:
    """TDD Step 0.4: RtgsSubmission event emitted and persisted."""

    def test_rtgs_submission_event_emitted(self):
        """RtgsSubmission event should be emitted when tx enters Queue 2."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 100_000, deadline_tick=50, priority=7,
            divisible=False, rtgs_priority="Urgent"
        )
        orch.tick()

        events = orch.get_tick_events(0)
        submission_events = [e for e in events if e.get("event_type") == "RtgsSubmission"]

        assert len(submission_events) >= 1
        event = submission_events[0]

        # Verify ALL required fields for replay identity
        assert event["tick"] == 0
        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["receiver"] == "BANK_B"
        assert event["amount"] == 100_000
        assert event["internal_priority"] == 7
        assert event["rtgs_priority"] == "Urgent"

    def test_rtgs_submission_event_for_normal_priority(self):
        """RtgsSubmission event for Normal priority transaction."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 50_000, deadline_tick=50, priority=3,
            divisible=False, rtgs_priority="Normal"
        )
        orch.tick()

        events = orch.get_tick_events(0)
        submission_events = [e for e in events if e.get("event_type") == "RtgsSubmission"]

        assert len(submission_events) >= 1
        event = submission_events[0]
        assert event["rtgs_priority"] == "Normal"
        assert event["internal_priority"] == 3


# =============================================================================
# TDD Step 0.7: Withdrawal from RTGS
# =============================================================================


class TestWithdrawFromRtgs:
    """TDD Step 0.7: Withdrawal from RTGS Queue 2."""

    def test_withdraw_removes_from_queue2(self):
        """Withdrawal should remove transaction from Queue 2."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        tx_id = orch.submit_transaction(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False
        )
        orch.tick()

        assert orch.queue_size() == 1

        # Withdraw
        result = orch.withdraw_from_rtgs(tx_id)

        assert result["success"] is True
        assert orch.queue_size() == 0

    def test_withdraw_clears_rtgs_priority(self):
        """Withdrawal should clear rtgs_priority and rtgs_submission_tick."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Forces Queue 2
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Urgent"
        )
        orch.tick()

        details_before = orch.get_transaction_details(tx_id)
        assert details_before["rtgs_priority"] == "Urgent"
        assert details_before["rtgs_submission_tick"] == 0

        orch.withdraw_from_rtgs(tx_id)

        details_after = orch.get_transaction_details(tx_id)
        assert details_after["rtgs_priority"] is None
        assert details_after["rtgs_submission_tick"] is None

    def test_withdraw_emits_event(self):
        """Withdrawal should emit RtgsWithdrawal event."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Urgent"
        )
        orch.tick()  # Tick 0: submission

        orch.withdraw_from_rtgs(tx_id)

        # Get events after withdrawal
        events = orch.get_all_events()
        withdrawal_events = [e for e in events if e.get("event_type") == "RtgsWithdrawal"]

        assert len(withdrawal_events) == 1
        event = withdrawal_events[0]

        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["original_rtgs_priority"] == "Urgent"


# =============================================================================
# TDD Step 0.8: Resubmission with New Priority
# =============================================================================


class TestResubmitToRtgs:
    """TDD Step 0.8: Resubmission to RTGS with new priority."""

    def test_resubmit_changes_rtgs_priority(self):
        """Resubmission should change RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )
        orch.tick()

        # Withdraw and resubmit as Urgent
        orch.withdraw_from_rtgs(tx_id)
        orch.resubmit_to_rtgs(tx_id, rtgs_priority="Urgent")
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "Urgent"

    def test_resubmit_loses_fifo_position(self):
        """Resubmission should move transaction to back of priority band."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # Submit three Normal transactions
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )
        tx3 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )
        orch.tick()  # Tick 0

        # Queue should be FIFO: tx1, tx2, tx3
        queue = orch.get_queue2_contents()
        assert queue == [tx1, tx2, tx3]

        # Withdraw tx1 and resubmit (same priority)
        orch.withdraw_from_rtgs(tx1)
        orch.resubmit_to_rtgs(tx1, rtgs_priority="Normal")
        orch.tick()  # Tick 1

        # tx1 should now be LAST (lost FIFO position)
        queue = orch.get_queue2_contents()
        assert queue == [tx2, tx3, tx1]

    def test_resubmit_emits_event(self):
        """Resubmission should emit RtgsResubmission event."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )
        orch.tick()

        orch.withdraw_from_rtgs(tx_id)
        orch.resubmit_to_rtgs(tx_id, rtgs_priority="Urgent")
        orch.tick()

        events = orch.get_all_events()
        resubmit_events = [e for e in events if e.get("event_type") == "RtgsResubmission"]

        assert len(resubmit_events) == 1
        event = resubmit_events[0]

        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["old_rtgs_priority"] == "Normal"
        assert event["new_rtgs_priority"] == "Urgent"


# =============================================================================
# TDD Step 0.9: Queue 2 Ordering by RTGS Priority
# =============================================================================


class TestQueue2RtgsPriorityOrdering:
    """TDD Step 0.9: Queue 2 ordered by rtgs_priority, then submission tick."""

    def test_queue2_orders_by_rtgs_priority_not_internal(self):
        """Queue 2 should order by RTGS priority, not internal priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # High internal (9), Normal RTGS
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9,
            divisible=False, rtgs_priority="Normal"
        )
        # Low internal (2), Urgent RTGS
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=2,
            divisible=False, rtgs_priority="Urgent"
        )

        orch.tick()

        queue = orch.get_queue2_contents()

        # Urgent (tx2) should be BEFORE Normal (tx1), despite lower internal priority
        assert queue[0] == tx2  # Urgent first
        assert queue[1] == tx1  # Normal second

    def test_queue2_fifo_within_same_rtgs_priority(self):
        """Within same RTGS priority band, FIFO by submission tick."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # All Normal RTGS, different internal priorities
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=3,
            divisible=False, rtgs_priority="Normal"
        )
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9,
            divisible=False, rtgs_priority="Normal"
        )
        tx3 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5,
            divisible=False, rtgs_priority="Normal"
        )

        orch.tick()

        queue = orch.get_queue2_contents()

        # All Normal, so FIFO order preserved
        assert queue == [tx1, tx2, tx3]


# =============================================================================
# TDD Step 0.10: Backward Compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with existing configs."""

    def test_existing_submit_transaction_defaults_to_normal_rtgs(self):
        """Existing submit_transaction should default to Normal RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # Use existing submit_transaction (no rtgs_priority parameter)
        tx_id = orch.submit_transaction(
            "BANK_A", "BANK_B", 100_000, deadline_tick=50, priority=9, divisible=False
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "Normal"  # Default

    def test_existing_priority_mode_still_works(self):
        """priority_mode=true should still work (uses rtgs_priority for ordering)."""
        config = {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
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

        # All default to Normal RTGS priority (via existing submit_transaction)
        tx1 = orch.submit_transaction(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=9, divisible=False
        )
        tx2 = orch.submit_transaction(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=3, divisible=False
        )
        tx3 = orch.submit_transaction(
            "BANK_A", "BANK_B", 1000, deadline_tick=50, priority=5, divisible=False
        )

        orch.tick()

        # All Normal RTGS priority -> FIFO order preserved
        queue = orch.get_queue2_contents()

        # Should be FIFO since all are Normal RTGS band
        assert queue == [tx1, tx2, tx3]
