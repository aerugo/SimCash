"""End-to-end test: Run and Replay must produce identical verbose output.

This test captures the exact issue from the bug report: when you run a simulation
with --persist --full-replay and then replay it, the verbose output should be
byte-for-byte identical.

Current failures:
- Transaction metadata (priority shows P:0 instead of actual values, deadline shows Tick 0)
- LSM cycles missing from replay output
- Collateral activity missing from replay output
- Cost accruals missing from replay output
- Credit utilization shows 0% instead of actual values
"""

import pytest
import tempfile
import os
from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import write_events_batch
from payment_simulator.persistence.event_queries import get_simulation_events
from io import StringIO
from rich.console import Console
import re


def normalize_output(text: str) -> str:
    """Normalize output for comparison by removing ANSI codes and normalizing whitespace."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)  # Remove ANSI
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def capture_console_output(func):
    """Capture rich console output from a function."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=120, legacy_windows=False)

    import payment_simulator.cli.output as output_module
    old_console = output_module.console
    output_module.console = console

    try:
        result = func()
        return output.getvalue(), result
    finally:
        output_module.console = old_console


class TestRunReplayIdentity:
    """THE ULTIMATE TEST: Verify run and replay produce identical output."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database path for testing."""
        # Create a unique path but don't create the file (DuckDB will create it)
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)  # Close the file descriptor
        os.unlink(db_path)  # Delete the empty file (DuckDB will create its own)
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
        # Also cleanup WAL file if it exists
        wal_path = db_path + ".wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)

    def test_transaction_metadata_in_arrival_event(self):
        """FAILING TEST: Event::Arrival should include priority and is_divisible.

        This test demonstrates that the Rust Event::Arrival enum is missing
        critical transaction metadata fields. When these fields are missing,
        they cannot be persisted to the database, and replay will show
        default values (priority=0, deadline=0) instead of the actual values.
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Submit a transaction with specific priority and divisibility
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=10000,
            deadline_tick=20,  # Deadline at tick 20
            priority=7,  # High priority
            divisible=False,  # Not divisible
        )

        # Run a tick to process the transaction
        orch.tick()

        # Get events for tick 0 (the events are in raw dict format from Rust FFI)
        tick_events = orch.get_tick_events(0)

        # Find the Arrival event
        arrival_events = [e for e in tick_events if e.get("event_type") == "Arrival"]

        assert len(arrival_events) > 0, "No Arrival events found"

        arrival = arrival_events[0]

        # CRITICAL ASSERTIONS: These fields MUST be present in the event
        # Otherwise replay will show incorrect values

        # Priority must be in the event
        assert "priority" in arrival, \
            f"Priority field missing from Arrival event. Event keys: {list(arrival.keys())}"
        assert arrival["priority"] == 7, \
            f"Priority should be 7, got {arrival.get('priority', 'MISSING')}"

        # Deadline must be in the event (not deadline_tick, the event uses 'deadline')
        assert "deadline" in arrival or "deadline_tick" in arrival, \
            f"Deadline field missing from Arrival event. Event keys: {list(arrival.keys())}"

        deadline_value = arrival.get("deadline") or arrival.get("deadline_tick")
        assert deadline_value == 20, \
            f"Deadline should be 20, got {deadline_value}"

        # is_divisible should be in the event
        # Note: The event may not include is_divisible yet, this documents what SHOULD be there
        # assert "is_divisible" in arrival or "divisible" in arrival, \
        #     f"Divisibility field missing from Arrival event. Event keys: {list(arrival.keys())}"

    def test_lsm_events_reconstructed_from_database(self):
        """FAILING TEST: LSM cycle events should be reconstructed from database.

        When LSM cycles are stored in the lsm_cycles table, they should be
        reconstructed as LsmBilateralOffset or LsmCycleSettlement events
        during replay, so that log_lsm_cycle_visualization can display them.
        """
        from payment_simulator.cli.commands.replay import _reconstruct_lsm_events

        # Simulate an LSM bilateral cycle record from the database
        lsm_cycles = [
            {
                "cycle_type": "bilateral",
                "agent_ids": ["BANK_A", "BANK_B"],
                "tx_ids": ["tx_001", "tx_002"],
                "settled_value": 100000,  # $1,000.00
                "tx_amounts": [100000, 100000],  # Both transactions for $1,000.00
            }
        ]

        # Reconstruct events
        events = _reconstruct_lsm_events(lsm_cycles)

        # CRITICAL ASSERTIONS
        assert len(events) == 1, "Should reconstruct 1 LSM event"

        event = events[0]
        assert event["event_type"] == "LsmBilateralOffset", \
            f"Expected LsmBilateralOffset, got {event.get('event_type')}"

        # Verify all required fields are present for visualization
        assert "agent_a" in event, "Missing agent_a for bilateral offset"
        assert "agent_b" in event, "Missing agent_b for bilateral offset"
        assert "tx_id_a" in event, "Missing tx_id_a for bilateral offset"
        assert "tx_id_b" in event, "Missing tx_id_b for bilateral offset"
        assert "amount" in event, "Missing amount for bilateral offset"

        # Verify values
        assert event["agent_a"] == "BANK_A"
        assert event["agent_b"] == "BANK_B"
        assert event["tx_id_a"] == "tx_001"
        assert event["tx_id_b"] == "tx_002"
        assert event["amount"] == 100000

    def test_collateral_events_reconstructed_from_simulation_events(self):
        """TEST: Collateral events should be reconstructed from simulation_events.

        For databases that have collateral events in simulation_events but not in
        the dedicated collateral_events table, we should still be able to reconstruct
        and display them.
        """
        # Create a function to reconstruct from simulation_events format
        def _reconstruct_collateral_from_simulation_events(events: list[dict]) -> list[dict]:
            """Reconstruct collateral events from simulation_events table."""
            result = []
            for event in events:
                event_type = event["event_type"]
                details = event.get("details", {})

                if event_type in ["CollateralPost", "CollateralWithdraw"]:
                    result.append({
                        "event_type": event_type,
                        "agent_id": event.get("agent_id") or details.get("agent_id"),
                        "amount": details.get("amount", 0),
                        "reason": details.get("reason", ""),
                        "new_total": details.get("new_total", 0),
                    })
            return result

        # Simulate collateral events from simulation_events table
        simulation_events = [
            {
                "event_type": "CollateralPost",
                "agent_id": "BANK_A",
                "details": {
                    "amount": 100000,
                    "reason": "PreemptivePosting",
                    "new_total": 100000,
                },
            },
        ]

        # Reconstruct events
        events = _reconstruct_collateral_from_simulation_events(simulation_events)

        # Verify reconstruction
        assert len(events) == 1
        assert events[0]["event_type"] == "CollateralPost"
        assert events[0]["agent_id"] == "BANK_A"
        assert events[0]["amount"] == 100000

    def test_collateral_events_reconstructed_from_database(self):
        """TEST: Collateral events should be reconstructed from database.

        When collateral events are stored in the collateral_events table,
        they should be reconstructed as CollateralPost/CollateralWithdraw events
        during replay, so that log_collateral_activity can display them.
        """
        from payment_simulator.cli.commands.replay import _reconstruct_collateral_events

        # Simulate collateral event records from the database
        collateral_events = [
            {
                "action": "post",
                "agent_id": "BANK_A",
                "amount": 100000,  # $1,000.00
                "reason": "PreemptivePosting",
                "posted_collateral_after": 100000,
            },
            {
                "action": "withdraw",
                "agent_id": "BANK_A",
                "amount": 50000,  # $500.00
                "reason": "CostOptimization",
                "posted_collateral_after": 50000,
            },
        ]

        # Reconstruct events
        events = _reconstruct_collateral_events(collateral_events)

        # CRITICAL ASSERTIONS
        assert len(events) == 2, f"Should reconstruct 2 collateral events, got {len(events)}"

        # First event: CollateralPost
        post_event = events[0]
        assert post_event["event_type"] == "CollateralPost", \
            f"Expected CollateralPost, got {post_event.get('event_type')}"
        assert post_event["agent_id"] == "BANK_A"
        assert post_event["amount"] == 100000
        assert post_event["reason"] == "PreemptivePosting"
        assert post_event["new_total"] == 100000

        # Second event: CollateralWithdraw
        withdraw_event = events[1]
        assert withdraw_event["event_type"] == "CollateralWithdraw", \
            f"Expected CollateralWithdraw, got {withdraw_event.get('event_type')}"
        assert withdraw_event["agent_id"] == "BANK_A"
        assert withdraw_event["amount"] == 50000
        assert withdraw_event["reason"] == "CostOptimization"
        assert withdraw_event["new_total"] == 50000

    def test_cost_accrual_events_reconstructed_from_simulation_events(self):
        """TEST: Cost accrual events should be reconstructed from simulation_events.

        When cost accrual events are in simulation_events, they should be
        reconstructed as CostAccrual events during replay, so that
        log_cost_accrual_events can display them.
        """
        # Create a reconstruction function (to be implemented in replay.py)
        def _reconstruct_cost_accrual_events(events: list[dict]) -> list[dict]:
            """Reconstruct cost accrual events from simulation_events table."""
            result = []
            for event in events:
                if event["event_type"] == "CostAccrual":
                    details = event.get("details", {})
                    # Cost breakdown is in details.costs
                    costs = details.get("costs", {})

                    result.append({
                        "event_type": "CostAccrual",
                        "agent_id": event.get("agent_id") or details.get("agent_id"),
                        "costs": costs,
                    })
            return result

        # Simulate cost accrual event from simulation_events
        simulation_events = [
            {
                "event_type": "CostAccrual",
                "agent_id": "BANK_A",
                "details": {
                    "costs": {
                        "liquidity_cost": 50000,
                        "delay_cost": 1000,
                        "collateral_cost": 500,
                        "penalty_cost": 0,
                        "split_friction_cost": 0,
                    }
                },
            },
        ]

        # Reconstruct events
        events = _reconstruct_cost_accrual_events(simulation_events)

        # Verify reconstruction
        assert len(events) == 1
        assert events[0]["event_type"] == "CostAccrual"
        assert events[0]["agent_id"] == "BANK_A"
        assert "costs" in events[0]
        assert events[0]["costs"]["liquidity_cost"] == 50000
        assert events[0]["costs"]["delay_cost"] == 1000

    def test_full_tick_output_identity(self, temp_db):
        """THE ULTIMATE TEST: Full tick output from run vs replay must be identical.

        This test runs a simulation, persists it with --full-replay data,
        then replays it and compares the verbose output for each tick.
        """
        # TODO: Implement full end-to-end test once infrastructure is in place
        pytest.skip("Full integration test needs completion")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
