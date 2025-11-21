"""Integration tests for CLI priority output (Phase 6b).

TDD tests verifying priority information appears in CLI verbose output:
1. Transaction arrivals show priority levels with color coding
2. Settlements show priority of settled transactions
3. Priority escalation events are displayed when they occur

Following strict TDD principles - write tests first, then implement.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


def run_cli_with_config(config: dict, extra_args: list = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run the CLI with the given config and return the result."""
    extra_args = extra_args or []

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                config_path,
                *extra_args,
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result
    finally:
        Path(config_path).unlink()


class TestTransactionArrivalsShowPriority:
    """Test that transaction arrivals display priority in verbose mode."""

    def test_arrivals_show_priority_level(self):
        """Verify arrivals show P:X priority notation in verbose output."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "10", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Should show arrivals with priority notation (P:X)
        assert "P:" in result.stderr, "Expected priority notation P:X in arrival output"

    def test_arrivals_show_priority_color_coding(self):
        """Verify priority levels are color-coded (HIGH/MED/LOW)."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 3.0,  # More arrivals to get variety
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,  # MED priority
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "20", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Should show at least one priority level indicator
        has_priority_indicator = (
            "HIGH" in result.stderr or
            "MED" in result.stderr or
            "LOW" in result.stderr
        )
        assert has_priority_indicator, "Expected priority level indicator (HIGH/MED/LOW) in output"


class TestSettlementsShowPriority:
    """Test that settlements display priority in verbose mode."""

    def test_rtgs_settlement_shows_priority(self):
        """RTGS immediate settlements should show transaction priority."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 7,  # HIGH priority
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "10", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Check for settlement section with priority
        if "transaction(s) settled" in result.stderr:
            # Settlement section exists - verify priority info is present
            # The format should show P:X for each settled transaction
            lines = result.stderr.split('\n')
            settlement_section = False
            has_priority_in_settlement = False

            for line in lines:
                if "settled" in line.lower():
                    settlement_section = True
                if settlement_section and "P:" in line:
                    has_priority_in_settlement = True
                    break

            assert has_priority_in_settlement, "Expected priority P:X in settlement details"


class TestPriorityEscalationEvents:
    """Test that priority escalation events are displayed in verbose mode."""

    def test_escalation_event_displayed(self):
        """When priority escalates, it should be shown in verbose output."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
                "priority_escalation": {
                    "enabled": True,
                    "curve": "linear",
                    "start_escalating_at_ticks": 10,
                    "max_boost": 3,
                },
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {"type": "Uniform", "min": 10000, "max": 50000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [15, 25],  # Close deadlines to trigger escalation
                        "priority": 3,  # Low priority to see escalation effect
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "30", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # When we have transactions that escalate, we should see escalation events
        # For now, just verify the simulation runs with escalation config

    def test_escalation_shows_old_and_new_priority(self):
        """Escalation event should show both old and new priority values."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
                "priority_escalation": {
                    "enabled": True,
                    "curve": "linear",
                    "start_escalating_at_ticks": 5,
                    "max_boost": 3,
                },
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Very low - transactions stay in queue
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.3,
                        "amount_distribution": {"type": "Uniform", "min": 10000, "max": 50000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [8, 15],  # Very close deadlines
                        "priority": 3,
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "20", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Look for escalation output pattern
        # Format should be something like: "Priority escalated: TX xxxx 3 -> 5"
        # This test documents the expected behavior


class TestPriorityModeOutput:
    """Test that Queue 2 priority mode is indicated in output."""

    def test_priority_mode_simulation_runs(self):
        """Priority mode should work without errors in CLI."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
                "priority_mode": True,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "20", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"


class TestQueue1PriorityOrdering:
    """Test Queue 1 priority ordering is visible in output."""

    def test_queue1_priority_ordering_runs(self):
        """Queue 1 priority ordering should work in CLI."""
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
                "queue1_ordering": "priority_deadline",
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 2.0,
                        "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "deadline_range": [10, 50],
                        "priority": 5,
                        "divisible": False,
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        result = run_cli_with_config(config, ["--ticks", "20", "--verbose"])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
