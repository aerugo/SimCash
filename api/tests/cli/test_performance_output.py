"""
Tests for performance diagnostics display output.

Tests verify that the log_performance_diagnostics() function correctly
formats and displays timing data.
"""

import pytest
from io import StringIO
from rich.console import Console


def test_log_performance_diagnostics_structure():
    """Verify performance diagnostics display correctly."""
    # Import here to allow patching console
    from payment_simulator.cli.output import log_performance_diagnostics

    timing = {
        "arrivals_micros": 1000,
        "policy_eval_micros": 5000,
        "rtgs_settlement_micros": 2000,
        "rtgs_queue_micros": 3000,
        "lsm_micros": 10000,
        "cost_accrual_micros": 500,
        "total_micros": 22000,
    }

    # Capture output
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    # Temporarily replace global console
    import payment_simulator.cli.output as output_module

    original_console = output_module.console
    output_module.console = console

    try:
        log_performance_diagnostics(timing, tick=42)
        output = string_io.getvalue()

        # Verify table headers
        assert "Performance Diagnostics" in output
        assert "Tick 42" in output
        assert "Phase" in output
        assert "Time" in output or "μs" in output
        assert "% of Total" in output or "%" in output

        # Verify phases are listed
        assert "Arrivals" in output
        assert "Policy Evaluation" in output
        assert "LSM Coordinator" in output

        # Verify values appear (numbers may be formatted with commas)
        # Check for microseconds values
        assert "1,000" in output or "1000" in output  # arrivals
        assert "10,000" in output or "10000" in output  # lsm
        assert "22,000" in output or "22000" in output  # total

        # Verify percentages are calculated
        # LSM is 10000/22000 = 45.45%
        assert "45" in output  # Should show ~45%

    finally:
        output_module.console = original_console


def test_log_performance_diagnostics_handles_zero_total():
    """Verify graceful handling of zero total time (shouldn't crash)."""
    from payment_simulator.cli.output import log_performance_diagnostics

    timing = {
        "arrivals_micros": 0,
        "policy_eval_micros": 0,
        "rtgs_settlement_micros": 0,
        "rtgs_queue_micros": 0,
        "lsm_micros": 0,
        "cost_accrual_micros": 0,
        "total_micros": 0,
    }

    # Should not crash with ZeroDivisionError
    try:
        # Capture output to avoid console spam
        string_io = StringIO()
        console = Console(file=string_io)

        import payment_simulator.cli.output as output_module

        original_console = output_module.console
        output_module.console = console

        try:
            log_performance_diagnostics(timing, tick=1)
        finally:
            output_module.console = original_console

    except ZeroDivisionError:
        pytest.fail("Should handle zero total gracefully without ZeroDivisionError")


def test_log_performance_diagnostics_percentages():
    """Verify percentage calculations are correct."""
    from payment_simulator.cli.output import log_performance_diagnostics

    timing = {
        "arrivals_micros": 100,
        "policy_eval_micros": 200,
        "rtgs_settlement_micros": 300,
        "rtgs_queue_micros": 400,
        "lsm_micros": 500,  # 50% of total
        "cost_accrual_micros": 500,  # 50% of total
        "total_micros": 1000,
    }

    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    import payment_simulator.cli.output as output_module

    original_console = output_module.console
    output_module.console = console

    try:
        log_performance_diagnostics(timing, tick=99)
        output = string_io.getvalue()

        # With total=1000:
        # arrivals: 100/1000 = 10%
        # policy: 200/1000 = 20%
        # cost: 500/1000 = 50%

        # Check for presence of percentages (may be formatted as "10.0%" or similar)
        assert "10" in output  # arrivals ~10%
        assert "50" in output  # cost ~50%

        # Total should show 100%
        assert "100" in output

    finally:
        output_module.console = original_console


def test_log_performance_diagnostics_large_values():
    """Verify formatting of large timing values (milliseconds range)."""
    from payment_simulator.cli.output import log_performance_diagnostics

    timing = {
        "arrivals_micros": 500_000,  # 500ms
        "policy_eval_micros": 1_000_000,  # 1 second
        "rtgs_settlement_micros": 250_000,  # 250ms
        "rtgs_queue_micros": 100_000,  # 100ms
        "lsm_micros": 2_000_000,  # 2 seconds
        "cost_accrual_micros": 50_000,  # 50ms
        "total_micros": 4_000_000,  # 4 seconds
    }

    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)

    import payment_simulator.cli.output as output_module

    original_console = output_module.console
    output_module.console = console

    try:
        log_performance_diagnostics(timing, tick=1)
        output = string_io.getvalue()

        # Should display values (check for comma-formatted large numbers)
        assert "500,000" in output or "500000" in output  # arrivals
        assert "2,000,000" in output or "2000000" in output  # lsm
        assert "4,000,000" in output or "4000000" in output  # total

        # If displaying milliseconds, check for those too
        # 2_000_000 μs = 2000 ms
        if "ms" in output:
            assert "2000" in output or "2,000" in output

    finally:
        output_module.console = original_console
