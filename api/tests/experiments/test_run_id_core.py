"""TDD tests for core run_id module.

Tests for run ID generation moved to core experiments module.
Write these tests FIRST, then implement the module.
"""

from __future__ import annotations

import re
import time

import pytest


class TestRunIdImport:
    """Tests for importing from new core location."""

    def test_importable_from_experiments(self) -> None:
        """generate_run_id should be importable from experiments."""
        from payment_simulator.experiments import generate_run_id

        assert callable(generate_run_id)

    def test_parse_run_id_importable_from_experiments(self) -> None:
        """parse_run_id should be importable from experiments."""
        from payment_simulator.experiments import parse_run_id

        assert callable(parse_run_id)

    def test_importable_from_run_id_module(self) -> None:
        """Direct import from run_id module should work."""
        from payment_simulator.experiments.run_id import (
            ParsedRunId,
            generate_run_id,
            parse_run_id,
        )

        assert callable(generate_run_id)
        assert callable(parse_run_id)
        assert ParsedRunId is not None


class TestGenerateRunId:
    """Tests for run ID generation."""

    def test_returns_string(self) -> None:
        """generate_run_id should return a string."""
        from payment_simulator.experiments import generate_run_id

        run_id = generate_run_id("test_experiment")
        assert isinstance(run_id, str)

    def test_unique_ids(self) -> None:
        """Each call should generate a unique ID."""
        from payment_simulator.experiments import generate_run_id

        ids = [generate_run_id("exp") for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_valid_format(self) -> None:
        """Run ID should have valid format for filenames/paths."""
        from payment_simulator.experiments import generate_run_id

        run_id = generate_run_id("exp1")
        # Should be alphanumeric with dashes
        assert re.match(r"^[a-zA-Z0-9_-]+$", run_id)

    def test_includes_experiment_name(self) -> None:
        """Run ID should include experiment name."""
        from payment_simulator.experiments import generate_run_id

        run_id = generate_run_id("my_experiment")
        assert run_id.startswith("my_experiment-")

    def test_includes_timestamp_date(self) -> None:
        """Run ID should include date component."""
        from payment_simulator.experiments import generate_run_id

        run_id = generate_run_id("exp1")
        today = time.strftime("%Y%m%d")
        assert today in run_id

    def test_format_matches_pattern(self) -> None:
        """Run ID should match expected pattern: name-YYYYMMDD-HHMMSS-hex6."""
        from payment_simulator.experiments import generate_run_id

        run_id = generate_run_id("exp1")
        # Pattern: {name}-{YYYYMMDD}-{HHMMSS}-{hex6}
        pattern = r"^exp1-\d{8}-\d{6}-[a-f0-9]{6}$"
        assert re.match(pattern, run_id), f"Run ID {run_id} doesn't match pattern"


class TestParseRunId:
    """Tests for run ID parsing."""

    def test_parses_valid_id(self) -> None:
        """parse_run_id should correctly parse a valid run ID."""
        from payment_simulator.experiments import parse_run_id

        result = parse_run_id("exp1-20251210-143022-a1b2c3")

        assert result is not None
        assert result["experiment_name"] == "exp1"
        assert result["date"] == "20251210"
        assert result["time"] == "143022"
        assert result["random_suffix"] == "a1b2c3"

    def test_parses_name_with_underscore(self) -> None:
        """parse_run_id should handle experiment names with underscores."""
        from payment_simulator.experiments import parse_run_id

        result = parse_run_id("my_experiment-20251210-143022-aabbcc")

        assert result is not None
        assert result["experiment_name"] == "my_experiment"

    def test_returns_none_for_invalid_format(self) -> None:
        """parse_run_id should return None for invalid format."""
        from payment_simulator.experiments import parse_run_id

        assert parse_run_id("invalid") is None
        assert parse_run_id("") is None
        assert parse_run_id("no-timestamp-here") is None

    def test_returns_none_for_empty_string(self) -> None:
        """parse_run_id should return None for empty string."""
        from payment_simulator.experiments import parse_run_id

        assert parse_run_id("") is None

    def test_round_trip(self) -> None:
        """generate_run_id followed by parse_run_id should work."""
        from payment_simulator.experiments import generate_run_id, parse_run_id

        run_id = generate_run_id("exp2")
        parsed = parse_run_id(run_id)

        assert parsed is not None
        assert parsed["experiment_name"] == "exp2"
        assert len(parsed["date"]) == 8
        assert len(parsed["time"]) == 6
        assert len(parsed["random_suffix"]) == 6


def _castro_available() -> bool:
    """Check if castro module is available."""
    try:
        import castro  # noqa: F401

        return True
    except ImportError:
        return False


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can still use run_id.

    These tests should be run from Castro's environment to verify
    backward compatibility. They're skipped in the API environment
    where Castro is not installed.
    """

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_import_works(self) -> None:
        """Castro should be able to import from its location."""
        from castro.run_id import generate_run_id

        assert callable(generate_run_id)

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_uses_same_function(self) -> None:
        """Castro's function should be the same as core."""
        from castro.run_id import generate_run_id as castro_func
        from payment_simulator.experiments import generate_run_id as core_func

        # Should be the same function (re-exported)
        assert castro_func is core_func
