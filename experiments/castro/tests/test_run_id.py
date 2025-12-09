"""Tests for run ID generation.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest


class TestRunIdGeneration:
    """Test run ID generation."""

    def test_run_id_format(self) -> None:
        """Run ID follows expected format: {exp}-{YYYYMMDD}-{HHMMSS}-{hex}."""
        from castro.run_id import generate_run_id

        run_id = generate_run_id("exp1")

        # Should match pattern: exp1-20251209-143022-a1b2c3
        pattern = r"^exp1-\d{8}-\d{6}-[a-f0-9]{6}$"
        assert re.match(pattern, run_id), f"Run ID '{run_id}' doesn't match expected format"

    def test_run_id_contains_experiment_name(self) -> None:
        """Run ID starts with experiment name."""
        from castro.run_id import generate_run_id

        for exp_name in ["exp1", "exp2", "exp3", "custom_experiment"]:
            run_id = generate_run_id(exp_name)
            assert run_id.startswith(f"{exp_name}-"), f"Run ID should start with '{exp_name}-'"

    def test_run_id_contains_valid_date(self) -> None:
        """Run ID contains a valid date component."""
        from castro.run_id import generate_run_id

        run_id = generate_run_id("exp1")

        # Extract date component (YYYYMMDD)
        parts = run_id.split("-")
        assert len(parts) >= 3, "Run ID should have at least 3 parts"

        date_str = parts[1]
        assert len(date_str) == 8, "Date component should be 8 digits"

        # Should be parseable as a date
        parsed_date = datetime.strptime(date_str, "%Y%m%d")
        assert parsed_date.year >= 2024, "Year should be reasonable"

    def test_run_id_contains_valid_time(self) -> None:
        """Run ID contains a valid time component."""
        from castro.run_id import generate_run_id

        run_id = generate_run_id("exp1")

        # Extract time component (HHMMSS)
        parts = run_id.split("-")
        assert len(parts) >= 4, "Run ID should have at least 4 parts"

        time_str = parts[2]
        assert len(time_str) == 6, "Time component should be 6 digits"

        # Should be parseable as a time
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])

        assert 0 <= hour <= 23, "Hour should be 0-23"
        assert 0 <= minute <= 59, "Minute should be 0-59"
        assert 0 <= second <= 59, "Second should be 0-59"

    def test_run_id_uniqueness(self) -> None:
        """Multiple calls generate unique run IDs."""
        from castro.run_id import generate_run_id

        # Generate many run IDs
        run_ids = [generate_run_id("exp1") for _ in range(100)]

        # All should be unique
        assert len(run_ids) == len(set(run_ids)), "Run IDs should be unique"

    def test_run_id_random_suffix_is_hex(self) -> None:
        """Random suffix is valid hexadecimal."""
        from castro.run_id import generate_run_id

        run_id = generate_run_id("exp1")

        # Extract random suffix (last component)
        parts = run_id.split("-")
        random_suffix = parts[-1]

        # Should be 6 hex characters
        assert len(random_suffix) == 6, "Random suffix should be 6 characters"
        assert all(c in "0123456789abcdef" for c in random_suffix), (
            "Random suffix should be hexadecimal"
        )

    def test_run_id_with_special_characters_in_name(self) -> None:
        """Experiment names with underscores work correctly."""
        from castro.run_id import generate_run_id

        run_id = generate_run_id("my_experiment")

        # Should start with experiment name
        assert run_id.startswith("my_experiment-")

        # Should still have correct structure
        parts = run_id.split("-")
        assert len(parts) == 4, "Should have 4 parts separated by -"


class TestParseRunId:
    """Test run ID parsing."""

    def test_parse_run_id_extracts_experiment_name(self) -> None:
        """parse_run_id extracts experiment name correctly."""
        from castro.run_id import parse_run_id

        result = parse_run_id("exp1-20251209-143022-a1b2c3")

        assert result["experiment_name"] == "exp1"

    def test_parse_run_id_extracts_timestamp(self) -> None:
        """parse_run_id extracts timestamp correctly."""
        from castro.run_id import parse_run_id

        result = parse_run_id("exp1-20251209-143022-a1b2c3")

        assert result["date"] == "20251209"
        assert result["time"] == "143022"

    def test_parse_run_id_extracts_random_suffix(self) -> None:
        """parse_run_id extracts random suffix correctly."""
        from castro.run_id import parse_run_id

        result = parse_run_id("exp1-20251209-143022-a1b2c3")

        assert result["random_suffix"] == "a1b2c3"

    def test_parse_run_id_handles_underscore_in_name(self) -> None:
        """parse_run_id handles experiment names with underscores."""
        from castro.run_id import parse_run_id

        result = parse_run_id("my_experiment-20251209-143022-a1b2c3")

        assert result["experiment_name"] == "my_experiment"

    def test_parse_run_id_invalid_format_returns_none(self) -> None:
        """parse_run_id returns None for invalid format."""
        from castro.run_id import parse_run_id

        assert parse_run_id("invalid") is None
        assert parse_run_id("exp1-20251209") is None
        assert parse_run_id("") is None
