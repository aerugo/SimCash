"""Test unified output functions work identically with both StateProvider implementations.

This test suite verifies that output functions produce byte-for-byte identical
results whether using OrchestratorStateProvider (live) or DatabaseStateProvider (replay).
"""
import pytest
from io import StringIO
import sys
import re
from rich.console import Console
from payment_simulator.cli.execution.state_provider import (
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator.cli.output import log_agent_state
from payment_simulator._core import Orchestrator


def normalize_output(text: str) -> str:
    """Normalize output for comparison.

    Removes ANSI color codes and normalizes whitespace.
    """
    # Remove ANSI color codes
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # Normalize whitespace while preserving structure
    lines = [line.rstrip() for line in text.splitlines()]
    # Remove empty lines at start/end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


class TestUnifiedLogAgentState:
    """Test that log_agent_state() works identically with both providers."""

    @pytest.fixture
    def orchestrator_provider(self):
        """Create provider from live orchestrator."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2000000,
                    "credit_limit": 1000000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }
        orch = Orchestrator.new(config)
        return OrchestratorStateProvider(orch)

    @pytest.fixture
    def database_provider(self):
        """Create provider from database state (matching orchestrator_provider initial state)."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": 1000000,
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        return DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

    def capture_stderr(self, func):
        """Capture stderr output from a function."""
        # Create a console that writes to StringIO
        output = StringIO()
        console = Console(file=output, stderr=True, force_terminal=False, width=120)

        # Temporarily replace the global console
        import payment_simulator.cli.output as output_module
        old_console = output_module.console
        output_module.console = console

        try:
            func()
            return output.getvalue()
        finally:
            output_module.console = old_console

    def test_log_agent_state_exists(self):
        """log_agent_state() function should exist."""
        from payment_simulator.cli.output import log_agent_state
        assert callable(log_agent_state)

    def test_log_agent_state_with_orchestrator_provider(self, orchestrator_provider):
        """Should display agent state using orchestrator provider."""
        def output_func():
            log_agent_state(orchestrator_provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)

        # Check output contains expected elements
        assert "BANK_A" in output
        assert "10,000.00" in output  # 1000000 cents = $10,000.00

    def test_log_agent_state_with_database_provider(self, database_provider):
        """Should display agent state using database provider."""
        def output_func():
            log_agent_state(database_provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)

        # Check output contains expected elements
        assert "BANK_A" in output
        assert "10,000.00" in output

    def test_both_providers_produce_identical_output(
        self, orchestrator_provider, database_provider
    ):
        """CRITICAL: Both providers must produce identical output."""
        def orch_output():
            log_agent_state(orchestrator_provider, "BANK_A", balance_change=0, quiet=False)

        def db_output():
            log_agent_state(database_provider, "BANK_A", balance_change=0, quiet=False)

        output_orch = self.capture_stderr(orch_output)
        output_db = self.capture_stderr(db_output)

        # Normalize for comparison
        output_orch_normalized = normalize_output(output_orch)
        output_db_normalized = normalize_output(output_db)

        assert output_orch_normalized == output_db_normalized, \
            f"Outputs differ:\nOrch:\n{output_orch_normalized}\n\nDB:\n{output_db_normalized}"

    def test_log_agent_state_with_positive_balance_change(self, orchestrator_provider):
        """Should show positive balance change indicator."""
        def output_func():
            log_agent_state(orchestrator_provider, "BANK_A", balance_change=50000, quiet=False)

        output = self.capture_stderr(output_func)
        assert "+500.00" in output or "+$500.00" in output

    def test_log_agent_state_with_negative_balance_change(self, orchestrator_provider):
        """Should show negative balance change indicator."""
        def output_func():
            log_agent_state(orchestrator_provider, "BANK_A", balance_change=-50000, quiet=False)

        output = self.capture_stderr(output_func)
        assert "-500.00" in output or "-$500.00" in output

    def test_log_agent_state_with_negative_balance(self):
        """Should show overdraft indicator for negative balance."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": -100000,  # Negative balance (overdraft)
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        def output_func():
            log_agent_state(provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)
        assert "overdraft" in output.lower()

    def test_log_agent_state_with_credit_utilization(self):
        """Should display credit utilization percentage."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": 200000,  # Used 300K of 500K credit
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        def output_func():
            log_agent_state(provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)
        assert "Credit:" in output
        assert "60%" in output  # (500000-200000)/500000 = 60%

    def test_log_agent_state_with_queue_contents(self):
        """Should display queue contents with transaction details."""
        mock_data = {
            "tx_cache": {
                "tx_001": {
                    "tx_id": "tx_001",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "amount_settled": 0,
                    "priority": 7,
                    "deadline_tick": 50,
                    "status": "pending",
                    "is_divisible": False,
                }
            },
            "agent_states": {
                "BANK_A": {
                    "balance": 1000000,
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": ["tx_001"], "rtgs": []},
            },
        }
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        def output_func():
            log_agent_state(provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)
        assert "Queue 1" in output
        assert "tx_001" in output
        assert "BANK_B" in output
        assert "1,000.00" in output  # Amount

    def test_log_agent_state_with_collateral(self):
        """Should display collateral posted."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": 1000000,
                    "credit_limit": 500000,
                    "collateral_posted": 250000,  # $2,500 collateral
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        def output_func():
            log_agent_state(provider, "BANK_A", balance_change=0, quiet=False)

        output = self.capture_stderr(output_func)
        assert "Collateral Posted" in output
        assert "2,500.00" in output

    def test_log_agent_state_quiet_mode(self, orchestrator_provider):
        """Should produce no output when quiet=True."""
        def output_func():
            log_agent_state(orchestrator_provider, "BANK_A", balance_change=0, quiet=True)

        output = self.capture_stderr(output_func)
        assert output == ""
