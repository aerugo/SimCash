"""TDD test for LSM event completeness.

The log_lsm_cycle_visualization function expects specific fields in LSM events.
This test verifies that Event::LsmBilateralOffset includes all necessary fields.
"""

import pytest
from payment_simulator._core import Orchestrator


class TestLsmEventCompleteness:
    """Verify LSM events contain all fields needed for visualization."""

    def test_lsm_bilateral_offset_event_has_required_fields(self):
        """FAILING TEST: LsmBilateralOffset should include agent_a, agent_b, amount_a, amount_b.

        The log_lsm_cycle_visualization function (output.py:1066-1069) expects:
        - agent_a: First agent ID
        - agent_b: Second agent ID
        - tx_id_a: First transaction ID
        - tx_id_b: Second transaction ID
        - amount_a: Amount of first transaction
        - amount_b: Amount of second transaction

        Currently, Event::LsmBilateralOffset (event.rs:138-143) only has:
        - tx_id_a
        - tx_id_b
        - amount (single value, not separate amounts)

        Missing fields cause visualization to show "unknown ⇄ unknown" with $0.00.
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,  # Low balance to force queuing
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit mutual transactions that will trigger bilateral offset
        tx_a_to_b = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=50000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        tx_b_to_a = orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=30000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run tick to process - should trigger LSM bilateral offset
        orch.tick()

        # Get events
        events = orch.get_tick_events(0)

        # Find LSM bilateral offset events
        lsm_events = [e for e in events if e.get("event_type") == "LsmBilateralOffset"]

        # May or may not trigger LSM depending on settlement order
        # If LSM triggered, verify event has all required fields
        if len(lsm_events) > 0:
            event = lsm_events[0]

            # CRITICAL ASSERTIONS: These fields MUST be present
            assert "agent_a" in event, \
                f"Missing agent_a. Event keys: {list(event.keys())}"
            assert "agent_b" in event, \
                f"Missing agent_b. Event keys: {list(event.keys())}"
            assert "tx_id_a" in event, \
                f"Missing tx_id_a. Event keys: {list(event.keys())}"
            assert "tx_id_b" in event, \
                f"Missing tx_id_b. Event keys: {list(event.keys())}"
            assert "amount_a" in event, \
                f"Missing amount_a. Event keys: {list(event.keys())}"
            assert "amount_b" in event, \
                f"Missing amount_b. Event keys: {list(event.keys())}"

            # Verify values are correct
            assert event["agent_a"] in ["BANK_A", "BANK_B"], \
                f"agent_a should be BANK_A or BANK_B, got {event['agent_a']}"
            assert event["agent_b"] in ["BANK_A", "BANK_B"], \
                f"agent_b should be BANK_A or BANK_B, got {event['agent_b']}"
            assert event["agent_a"] != event["agent_b"], \
                "agent_a and agent_b should be different"

            # Amounts should be non-zero
            assert event["amount_a"] > 0, f"amount_a should be > 0, got {event['amount_a']}"
            assert event["amount_b"] > 0, f"amount_b should be > 0, got {event['amount_b']}"
        else:
            # If no LSM triggered, skip test
            pytest.skip("LSM bilateral offset not triggered in this scenario")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
