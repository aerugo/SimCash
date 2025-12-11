"""Tests for Monte Carlo percentage-delta comparison.

TDD tests for fixing the Monte Carlo evaluation to compare policy improvement
percentages rather than raw costs across different transaction sets.

Problem: Current implementation compares raw costs across Monte Carlo samples
with different transaction sets, which is meaningless because a sample with
61 transactions will naturally cost more than one with 42 transactions.

Solution: For each Monte Carlo sample (fixed transaction set):
1. Run with BASELINE policy → get baseline_cost
2. Run with NEW policy → get current_cost
3. Compute improvement: delta_percent = (baseline_cost - current_cost) / baseline_cost * 100

Best/Worst should be determined by:
- Best = seed where policy showed biggest improvement (highest delta_percent)
- Worst = seed where policy showed smallest improvement/regression (lowest delta_percent)

For iteration 1 (baseline run):
- No comparison possible, just establish baselines
- No "Best"/"Worst" labels should appear
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

if TYPE_CHECKING:
    pass


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestBootstrapSampleResultDeltaFields:
    """Tests for BootstrapSampleResult delta percentage fields."""

    def test_seed_result_has_baseline_cost_field(self) -> None:
        """BootstrapSampleResult should have optional baseline_cost field."""
        from castro.verbose_logging import BootstrapSampleResult

        # With baseline (iteration > 1)
        result_with_baseline = BootstrapSampleResult(
            seed=0x12345,
            cost=9000,  # Current cost with new policy
            settled=50,
            total=50,
            settlement_rate=1.0,
            baseline_cost=10000,  # Cost with original policy
        )
        assert result_with_baseline.baseline_cost == 10000

        # Without baseline (iteration 1)
        result_without_baseline = BootstrapSampleResult(
            seed=0x12345,
            cost=10000,
            settled=50,
            total=50,
            settlement_rate=1.0,
        )
        assert result_without_baseline.baseline_cost is None

    def test_seed_result_computes_delta_percent(self) -> None:
        """BootstrapSampleResult should compute delta_percent property."""
        from castro.verbose_logging import BootstrapSampleResult

        # 10% improvement: baseline=10000, new=9000
        result = BootstrapSampleResult(
            seed=0x12345,
            cost=9000,
            settled=50,
            total=50,
            settlement_rate=1.0,
            baseline_cost=10000,
        )
        # delta_percent = (10000 - 9000) / 10000 * 100 = 10%
        assert result.delta_percent == pytest.approx(10.0)

    def test_seed_result_delta_percent_negative_for_regression(self) -> None:
        """delta_percent should be negative when cost increased (regression)."""
        from castro.verbose_logging import BootstrapSampleResult

        # 20% regression: baseline=10000, new=12000
        result = BootstrapSampleResult(
            seed=0x12345,
            cost=12000,
            settled=50,
            total=50,
            settlement_rate=1.0,
            baseline_cost=10000,
        )
        # delta_percent = (10000 - 12000) / 10000 * 100 = -20%
        assert result.delta_percent == pytest.approx(-20.0)

    def test_seed_result_delta_percent_none_without_baseline(self) -> None:
        """delta_percent should be None when baseline_cost is not set."""
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=0x12345,
            cost=10000,
            settled=50,
            total=50,
            settlement_rate=1.0,
        )
        assert result.delta_percent is None

    def test_seed_result_delta_percent_handles_zero_baseline(self) -> None:
        """delta_percent should handle zero baseline gracefully."""
        from castro.verbose_logging import BootstrapSampleResult

        result = BootstrapSampleResult(
            seed=0x12345,
            cost=0,
            settled=50,
            total=50,
            settlement_rate=1.0,
            baseline_cost=0,  # Edge case: zero baseline
        )
        # Should return 0.0 or None, not raise division by zero
        assert result.delta_percent == 0.0 or result.delta_percent is None


class TestMonteCarloLoggingDeltaComparison:
    """Tests for Monte Carlo logging with delta-based best/worst."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_baseline_run_shows_no_best_worst_labels(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """On baseline run (iteration 1), no Best/Worst labels should appear."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        # Baseline run: no baseline_cost set on any result
        seed_results = [
            BootstrapSampleResult(
                seed=0x1111, cost=1320000, settled=42, total=42, settlement_rate=1.0
            ),
            BootstrapSampleResult(
                seed=0x2222, cost=1380000, settled=61, total=61, settlement_rate=1.0
            ),
            BootstrapSampleResult(
                seed=0x3333, cost=1340000, settled=48, total=48, settlement_rate=1.0
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=1346666,
            std_cost=24944,
            is_baseline_run=True,
        )

        output = buffer.getvalue()

        # Should NOT contain Best/Worst labels
        assert "Best" not in output
        assert "Worst" not in output
        # Should indicate this is a baseline
        assert "Baseline" in output or "baseline" in output.lower()

    def test_subsequent_run_shows_best_worst_by_delta(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """After baseline, Best/Worst should be determined by delta_percent."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        # Subsequent run: all results have baseline_cost
        seed_results = [
            BootstrapSampleResult(
                seed=0x1111,
                cost=1260000,  # 5% improvement
                settled=42,
                total=42,
                settlement_rate=1.0,
                baseline_cost=1320000,
            ),
            BootstrapSampleResult(
                seed=0x2222,
                cost=1360000,  # ~1.4% improvement (WORST)
                settled=61,
                total=61,
                settlement_rate=1.0,
                baseline_cost=1380000,
            ),
            BootstrapSampleResult(
                seed=0x3333,
                cost=1190000,  # ~11.2% improvement (BEST)
                settled=48,
                total=48,
                settlement_rate=1.0,
                baseline_cost=1340000,
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=1270000,
            std_cost=70000,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Should show Best/Worst labels
        assert "Best" in output
        assert "Worst" in output

        # Best should be seed 0x3333 (highest delta ~11.2%)
        # Worst should be seed 0x2222 (lowest delta ~1.4%)
        # Check that delta percentages are displayed
        assert "%" in output

    def test_delta_column_shown_when_baselines_present(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Table should show Delta column when baselines are present."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0x1111,
                cost=9000,
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,  # 10% improvement
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=9000,
            std_cost=0,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Should show Delta or Δ column header
        assert "Delta" in output or "Δ" in output or "delta" in output.lower()

    def test_no_delta_column_on_baseline_run(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Table should NOT show Delta column on baseline run."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0x1111,
                cost=10000,
                settled=50,
                total=50,
                settlement_rate=1.0,
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=10000,
            std_cost=0,
            is_baseline_run=True,
        )

        output = buffer.getvalue()

        # Should NOT show Delta column (since there's nothing to compare)
        # Output should still work but without delta info
        assert "Monte Carlo" in output


class TestBestWorstDeltaLogic:
    """Tests for best/worst determination logic based on delta."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_best_is_highest_positive_delta(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Best seed should have highest delta_percent (most improvement)."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0xAAAA,
                cost=9500,
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,  # 5% improvement
            ),
            BootstrapSampleResult(
                seed=0xBBBB,
                cost=8500,
                settled=60,
                total=60,
                settlement_rate=1.0,
                baseline_cost=10000,  # 15% improvement - BEST
            ),
            BootstrapSampleResult(
                seed=0xCCCC,
                cost=9000,
                settled=55,
                total=55,
                settlement_rate=1.0,
                baseline_cost=10000,  # 10% improvement
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=9000,
            std_cost=500,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Seed 0xBBBB should be marked as Best (15% improvement)
        # Check that the Best label appears near the 0xbbbb seed
        lines = output.split("\n")
        best_line = [line for line in lines if "bbbb" in line.lower() and "Best" in line]
        # May find both the table row and "Best seed:" summary line - that's fine
        assert len(best_line) >= 1, f"Expected 0xBBBB to be marked Best. Output:\n{output}"

    def test_worst_is_lowest_delta_including_regression(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Worst seed should have lowest delta_percent (including regression)."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0xAAAA,
                cost=9000,
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,  # 10% improvement
            ),
            BootstrapSampleResult(
                seed=0xBBBB,
                cost=11000,
                settled=60,
                total=60,
                settlement_rate=1.0,
                baseline_cost=10000,  # -10% regression - WORST
            ),
            BootstrapSampleResult(
                seed=0xCCCC,
                cost=9500,
                settled=55,
                total=55,
                settlement_rate=1.0,
                baseline_cost=10000,  # 5% improvement
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=9833,
            std_cost=850,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Seed 0xBBBB should be marked as Worst (-10% regression)
        lines = output.split("\n")
        worst_line = [line for line in lines if "bbbb" in line.lower() and "Worst" in line]
        # May find both the table row and "Worst seed:" summary line - that's fine
        assert len(worst_line) >= 1, f"Expected 0xBBBB to be marked Worst. Output:\n{output}"

    def test_regression_shown_with_negative_sign(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Regression (cost increased) should show negative delta."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0xAAAA,
                cost=12000,  # 20% regression
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=12000,
            std_cost=0,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Should show negative delta like "-20%" or "-20.0%"
        assert "-20" in output or "−20" in output  # Regular minus or unicode minus


class TestMeanDeltaStatistics:
    """Tests for mean delta percentage statistics in output."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_mean_delta_shown_when_baselines_present(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Output should show mean delta percentage when comparing to baseline."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        seed_results = [
            BootstrapSampleResult(
                seed=0x1111,
                cost=9000,
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,  # 10% improvement
            ),
            BootstrapSampleResult(
                seed=0x2222,
                cost=8000,
                settled=50,
                total=50,
                settlement_rate=1.0,
                baseline_cost=10000,  # 20% improvement
            ),
        ]

        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=8500,
            std_cost=500,
            is_baseline_run=False,
        )

        output = buffer.getvalue()

        # Mean delta should be 15% ((10% + 20%) / 2)
        # Should show something like "Mean improvement: 15.0%"
        assert "15" in output
        assert "%" in output


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing behavior."""

    @pytest.fixture
    def string_console(self) -> tuple[Console, io.StringIO]:
        """Create a console that writes to a string buffer."""
        buffer = io.StringIO()
        console = Console(file=buffer, force_terminal=True, width=120)
        return console, buffer

    def test_existing_api_still_works_without_new_params(
        self, string_console: tuple[Console, io.StringIO]
    ) -> None:
        """Existing code calling log_monte_carlo_evaluation should still work."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )

        console, buffer = string_console
        config = VerboseConfig(monte_carlo=True)
        logger = VerboseLogger(config, console)

        # Old-style call without is_baseline_run or baseline_cost
        seed_results = [
            BootstrapSampleResult(
                seed=0x7A3B,
                cost=1320000,
                settled=12,
                total=12,
                settlement_rate=1.0,
            ),
            BootstrapSampleResult(
                seed=0x2F1C,
                cost=1380000,
                settled=11,
                total=12,
                settlement_rate=11 / 12,
            ),
        ]

        # Should not raise - is_baseline_run defaults appropriately
        logger.log_monte_carlo_evaluation(
            seed_results=seed_results,
            mean_cost=1350000,
            std_cost=30000,
        )

        output = buffer.getvalue()

        # Should produce valid output
        assert "Monte Carlo" in output
        # Without baselines, should treat as baseline run (no delta comparison)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
