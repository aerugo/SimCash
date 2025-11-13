"""
Tests for State Register Display (Phase 4.5)

Tests verbose output display of StateRegisterSet events.
"""

import pytest
from io import StringIO
from rich.console import Console
from payment_simulator.cli.output import log_state_register_events


class TestStateRegisterDisplay:
    """Test display of state register events in verbose output."""

    def test_log_state_register_events_displays_updates(self):
        """Verify StateRegisterSet events are displayed with proper formatting.

        RED: Function doesn't exist yet.
        """
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 42.0,
                "reason": "policy_action",
            }
        ]

        # Capture output using rich console
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)

        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=False)
            output = string_io.getvalue()

            # Verify output contains key information
            assert "Memory" in output
            assert "BANK_A" in output
            assert "cooldown" in output  # Note: bank_state_ prefix is removed
            assert "42.0" in output or "42" in output
        finally:
            output_module.console = original_console

    def test_log_state_register_events_shows_old_and_new_values(self):
        """Verify both old and new values are displayed.

        RED: Function doesn't exist yet.
        """
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_counter",
                "old_value": 5.0,
                "new_value": 6.0,
                "reason": "increment",
            }
        ]

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=False)
            output = string_io.getvalue()

            # Should show transition 5.0 → 6.0
            assert "5" in output
            assert "6" in output
            # Should have some arrow or indicator
            assert "→" in output or "->" in output or "to" in output.lower()
        finally:
            output_module.console = original_console

    def test_log_state_register_events_groups_by_agent(self):
        """Verify events are grouped by agent.

        RED: Function doesn't exist yet.
        """
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 10.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_counter",
                "old_value": 0.0,
                "new_value": 1.0,
                "reason": "policy_action",
            },
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_B",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 20.0,
                "reason": "policy_action",
            },
        ]

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=False)
            output = string_io.getvalue()

            # Should have both agents mentioned
            assert "BANK_A" in output
            assert "BANK_B" in output
            # Should show all registers (note: prefix removed)
            assert "cooldown" in output
            assert "counter" in output
        finally:
            output_module.console = original_console

    def test_log_state_register_events_shows_eod_reset(self):
        """Verify EOD reset events are displayed distinctly.

        RED: Function doesn't exist yet.
        """
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 100,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 42.0,
                "new_value": 0.0,
                "reason": "eod_reset",
            }
        ]

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=False)
            output = string_io.getvalue()

            # Should mention EOD or reset
            assert "EOD" in output or "reset" in output.lower()
        finally:
            output_module.console = original_console

    def test_log_state_register_events_quiet_mode(self):
        """Verify quiet mode suppresses output."""
        events = [
            {
                "event_type": "StateRegisterSet",
                "tick": 10,
                "agent_id": "BANK_A",
                "register_key": "bank_state_cooldown",
                "old_value": 0.0,
                "new_value": 42.0,
                "reason": "policy_action",
            }
        ]

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=True)
            output = string_io.getvalue()

            # Should produce no output
            assert output == ""
        finally:
            output_module.console = original_console

    def test_log_state_register_events_no_events(self):
        """Verify no output when no StateRegisterSet events."""
        events = [
            {
                "event_type": "Settlement",
                "tick": 10,
                "tx_id": "tx1",
            }
        ]

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        import payment_simulator.cli.output as output_module
        original_console = output_module.console
        output_module.console = console

        try:
            log_state_register_events(events, quiet=False)
            output = string_io.getvalue()

            # Should produce no output (no state register events)
            assert output == ""
        finally:
            output_module.console = original_console
