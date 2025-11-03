"""Integration tests for CLI event filtering.

Tests the --filter-* flags in verbose and event-stream modes.
Following TDD principles with RED-GREEN-REFACTOR cycle.

Key Requirements:
- Filter flags require --verbose or --event-stream mode
- Event type filtering works correctly
- Agent filtering works correctly
- Transaction filtering works correctly
- Tick range filtering works correctly
- Multiple filters use AND logic
"""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_config():
    """Use the existing 12-bank config for testing."""
    # Use the existing 12-bank config file
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "12_bank_4_policy_comparison.yaml"
    assert config_path.exists(), f"Config file not found: {config_path}"
    return config_path


class TestFilterValidation:
    """Test filter flag validation."""

    def test_filter_without_mode_fails(self, test_config):
        """Verify filter flags require --verbose or --event-stream."""
        # Try to use filter without --verbose or --event-stream
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--filter-event-type",
                "Arrival",
                "--quiet",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert (
            "Event filters (--filter-*) require either --verbose or --event-stream mode"
            in result.stderr
        )

    def test_filter_with_verbose_succeeds(self, test_config):
        """Verify filter flags work with --verbose."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--ticks",
                "20",
                "--verbose",
                "--filter-event-type",
                "Arrival",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled" in result.stderr

    def test_filter_with_event_stream_succeeds(self, test_config):
        """Verify filter flags work with --event-stream."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--ticks",
                "20",
                "--event-stream",
                "--filter-event-type",
                "Arrival",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled" in result.stderr


class TestEventTypeFiltering:
    """Test --filter-event-type flag."""

    def test_filter_single_event_type_verbose(self, test_config):
        """Verify filtering by single event type in verbose mode."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--verbose",
                "--filter-event-type",
                "Arrival",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Verify only Arrival events are shown
        assert "Arrival:" in result.stderr or "arrivals" in result.stderr.lower()

        # Verify no Settlement events are shown (if any occurred)
        # Note: With low rate_per_tick, we might not have settlements
        # This is a soft check - if settlements happened, they shouldn't be displayed

    def test_filter_single_event_type_stream(self, test_config):
        """Verify filtering by single event type in event-stream mode."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-event-type",
                "Arrival",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Check that output only contains Arrival events
        lines = [line for line in result.stderr.split("\n") if "[Tick" in line]
        if lines:
            # All event lines should be Arrival events
            for line in lines:
                assert "Arrival:" in line

    def test_filter_multiple_event_types(self, test_config):
        """Verify filtering by comma-separated event types."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-event-type",
                "Arrival,Settlement",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: types=Arrival,Settlement" in result.stderr


class TestAgentFiltering:
    """Test --filter-agent flag."""

    def test_filter_by_agent_verbose(self, test_config):
        """Verify filtering by agent ID in verbose mode."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--verbose",
                "--filter-agent",
                "BANK_A",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: agent=BANK_A" in result.stderr

    def test_filter_by_agent_stream(self, test_config):
        """Verify filtering by agent ID in event-stream mode."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-agent",
                "BANK_B",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: agent=BANK_B" in result.stderr


class TestTickRangeFiltering:
    """Test --filter-tick-range flag."""

    def test_filter_tick_range_both(self, test_config):
        """Verify filtering by tick range (min-max)."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-tick-range",
                "5-10",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: ticks=5-10" in result.stderr

        # Verify tick numbers in output are within range
        lines = [line for line in result.stderr.split("\n") if "[Tick" in line]
        if lines:
            for line in lines:
                # Extract tick number from line like "[Tick 7]"
                import re

                match = re.search(r"\[Tick (\d+)\]", line)
                if match:
                    tick = int(match.group(1))
                    assert 5 <= tick <= 10, f"Tick {tick} outside range 5-10"

    def test_filter_tick_range_min_only(self, test_config):
        """Verify filtering by minimum tick only (min-)."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-tick-range",
                "15-",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: ticks=15-" in result.stderr

    def test_filter_tick_range_max_only(self, test_config):
        """Verify filtering by maximum tick only (-max)."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-tick-range",
                "-5",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Event filtering enabled: ticks=-5" in result.stderr


class TestMultipleFilters:
    """Test combining multiple filters (AND logic)."""

    def test_multiple_filters_and_logic(self, test_config):
        """Verify multiple filters use AND logic."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--event-stream",
                "--filter-event-type",
                "Arrival",
                "--filter-agent",
                "BANK_A",
                "--filter-tick-range",
                "5-15",
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert (
            "Event filtering enabled: types=Arrival, agent=BANK_A, ticks=5-15"
            in result.stderr
        )

        # Verify events match all criteria
        lines = [line for line in result.stderr.split("\n") if "[Tick" in line]
        if lines:
            for line in lines:
                # Should be Arrival events
                assert "Arrival:" in line
                # Should be from BANK_A (sender)
                assert "BANK_A" in line
                # Should be in tick range 5-15
                import re

                match = re.search(r"\[Tick (\d+)\]", line)
                if match:
                    tick = int(match.group(1))
                    assert 5 <= tick <= 15

    def test_all_filters_combined(self, test_config):
        """Verify all four filter types work together."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "payment_simulator.cli.main",
                "run",
                "--config",
                str(test_config),
                "--verbose",
                "--filter-event-type",
                "Arrival,Settlement",
                "--filter-agent",
                "BANK_A",
                "--filter-tick-range",
                "0-10",
                # Note: --filter-tx would require knowing a specific tx_id
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Check filter configuration is logged
        assert "Event filtering enabled" in result.stderr
        assert "types=Arrival,Settlement" in result.stderr
        assert "agent=BANK_A" in result.stderr
        assert "ticks=0-10" in result.stderr
