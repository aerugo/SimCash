"""Tests for LaTeX formatting utilities - TDD RED phase.

These tests define the expected behavior of LaTeX formatting functions.
"""

from __future__ import annotations


# =============================================================================
# Phase 2.1: Money Formatting Tests (RED)
# =============================================================================


class TestFormatMoney:
    """Test money formatting: cents (int) -> LaTeX dollars string."""

    def test_format_zero_cents(self) -> None:
        """0 cents should format as $0.00."""
        from src.latex.formatting import format_money

        assert format_money(0) == r"\$0.00"

    def test_format_positive_cents(self) -> None:
        """Positive cents should format correctly."""
        from src.latex.formatting import format_money

        assert format_money(100) == r"\$1.00"
        assert format_money(2500) == r"\$25.00"
        assert format_money(12345) == r"\$123.45"

    def test_format_cents_with_decimals(self) -> None:
        """Non-round cents should show decimal places."""
        from src.latex.formatting import format_money

        assert format_money(199) == r"\$1.99"
        assert format_money(1) == r"\$0.01"
        assert format_money(99) == r"\$0.99"

    def test_format_large_amounts(self) -> None:
        """Large amounts should format with commas."""
        from src.latex.formatting import format_money

        # 100,000 cents = $1,000.00
        assert format_money(100000) == r"\$1,000.00"
        # 1,000,000 cents = $10,000.00
        assert format_money(1000000) == r"\$10,000.00"

    def test_format_money_returns_string(self) -> None:
        """format_money must return str type."""
        from src.latex.formatting import format_money

        result = format_money(100)
        assert isinstance(result, str)


# =============================================================================
# Phase 2.2: Percent Formatting Tests (RED)
# =============================================================================


class TestFormatPercent:
    """Test percent formatting: fraction (float) -> LaTeX percent string."""

    def test_format_zero_percent(self) -> None:
        """0.0 should format as 0.0%."""
        from src.latex.formatting import format_percent

        assert format_percent(0.0) == r"0.0\%"

    def test_format_whole_percents(self) -> None:
        """Whole number fractions should format correctly."""
        from src.latex.formatting import format_percent

        assert format_percent(0.10) == r"10.0\%"
        assert format_percent(0.20) == r"20.0\%"
        assert format_percent(0.50) == r"50.0\%"
        assert format_percent(1.0) == r"100.0\%"

    def test_format_decimal_percents(self) -> None:
        """Fractional percents should show one decimal place."""
        from src.latex.formatting import format_percent

        assert format_percent(0.165) == r"16.5\%"
        assert format_percent(0.115) == r"11.5\%"
        assert format_percent(0.151) == r"15.1\%"

    def test_format_percent_returns_string(self) -> None:
        """format_percent must return str type."""
        from src.latex.formatting import format_percent

        result = format_percent(0.5)
        assert isinstance(result, str)


# =============================================================================
# Phase 2.3: CI Formatting Tests (RED)
# =============================================================================


class TestFormatCI:
    """Test confidence interval formatting."""

    def test_format_ci_basic(self) -> None:
        """CI should format as [lower, upper] in dollars."""
        from src.latex.formatting import format_ci

        # 10000 and 15000 cents -> [$100.00, $150.00]
        result = format_ci(10000, 15000)
        assert result == r"[\$100.00, \$150.00]"

    def test_format_ci_same_bounds(self) -> None:
        """Equal bounds (deterministic) should still show both."""
        from src.latex.formatting import format_ci

        result = format_ci(5000, 5000)
        assert result == r"[\$50.00, \$50.00]"

    def test_format_ci_returns_string(self) -> None:
        """format_ci must return str type."""
        from src.latex.formatting import format_ci

        result = format_ci(100, 200)
        assert isinstance(result, str)


# =============================================================================
# Phase 2.4: Table Row Formatting Tests (RED)
# =============================================================================


class TestTableRow:
    """Test LaTeX table row formatting."""

    def test_format_table_row_basic(self) -> None:
        """Table row should join cells with & and end with \\\\."""
        from src.latex.formatting import format_table_row

        result = format_table_row(["A", "B", "C"])
        assert result == r"A & B & C \\"

    def test_format_table_row_single_cell(self) -> None:
        """Single cell row."""
        from src.latex.formatting import format_table_row

        result = format_table_row(["Single"])
        assert result == r"Single \\"

    def test_format_table_row_with_numbers(self) -> None:
        """Row with mixed types should convert to strings."""
        from src.latex.formatting import format_table_row

        result = format_table_row(["Name", 100, 0.5])
        assert result == r"Name & 100 & 0.5 \\"


# =============================================================================
# Phase 2.5: Full Table Generation Tests (RED)
# =============================================================================


class TestGenerateIterationTable:
    """Test iteration results table generation."""

    def test_generates_valid_latex_table(self) -> None:
        """Should generate complete LaTeX tabular environment."""
        from src.latex.tables import generate_iteration_table
        from src.data_provider import AgentIterationResult

        results: list[AgentIterationResult] = [
            AgentIterationResult(
                iteration=1,
                agent_id="BANK_A",
                cost=5000,
                liquidity_fraction=0.5,
                accepted=True,
            ),
            AgentIterationResult(
                iteration=1,
                agent_id="BANK_B",
                cost=5000,
                liquidity_fraction=0.5,
                accepted=True,
            ),
        ]

        table = generate_iteration_table(
            results,
            caption="Test Table",
            label="tab:test",
        )

        # Should contain LaTeX table elements
        assert r"\begin{table}" in table
        assert r"\end{table}" in table
        assert r"\begin{tabular}" in table
        assert r"\end{tabular}" in table
        assert r"\caption{Test Table}" in table
        assert r"\label{tab:test}" in table

    def test_table_contains_formatted_values(self) -> None:
        """Table should contain properly formatted money and percent values."""
        from src.latex.tables import generate_iteration_table
        from src.data_provider import AgentIterationResult

        results: list[AgentIterationResult] = [
            AgentIterationResult(
                iteration=1,
                agent_id="BANK_A",
                cost=2500,
                liquidity_fraction=0.25,
                accepted=True,
            ),
        ]

        table = generate_iteration_table(results, caption="Test", label="tab:test")

        # Should contain formatted values
        assert r"\$25.00" in table  # 2500 cents = $25.00
        assert r"25.0\%" in table  # 0.25 = 25.0%

    def test_table_returns_string(self) -> None:
        """generate_iteration_table must return str type."""
        from src.latex.tables import generate_iteration_table
        from src.data_provider import AgentIterationResult

        results: list[AgentIterationResult] = [
            AgentIterationResult(
                iteration=1,
                agent_id="BANK_A",
                cost=0,
                liquidity_fraction=0.0,
                accepted=True,
            ),
        ]

        result = generate_iteration_table(results, caption="Test", label="tab:test")
        assert isinstance(result, str)


class TestGenerateBootstrapTable:
    """Test bootstrap statistics table generation."""

    def test_generates_valid_latex_table(self) -> None:
        """Should generate complete LaTeX tabular environment."""
        from src.latex.tables import generate_bootstrap_table
        from src.data_provider import BootstrapStats

        stats: dict[str, BootstrapStats] = {
            "BANK_A": BootstrapStats(
                mean_cost=10000,
                std_dev=500,
                ci_lower=9000,
                ci_upper=11000,
                num_samples=50,
            ),
            "BANK_B": BootstrapStats(
                mean_cost=8000,
                std_dev=1000,
                ci_lower=6000,
                ci_upper=10000,
                num_samples=50,
            ),
        }

        table = generate_bootstrap_table(
            stats,
            caption="Bootstrap Statistics",
            label="tab:bootstrap",
        )

        assert r"\begin{table}" in table
        assert r"\end{table}" in table
        assert r"\caption{Bootstrap Statistics}" in table
        assert r"\label{tab:bootstrap}" in table

    def test_table_contains_bootstrap_values(self) -> None:
        """Table should contain mean, std dev, and CI values."""
        from src.latex.tables import generate_bootstrap_table
        from src.data_provider import BootstrapStats

        stats: dict[str, BootstrapStats] = {
            "BANK_A": BootstrapStats(
                mean_cost=16440,
                std_dev=0,
                ci_lower=16440,
                ci_upper=16440,
                num_samples=50,
            ),
        }

        table = generate_bootstrap_table(stats, caption="Test", label="tab:test")

        # Should contain formatted values
        assert r"\$164.40" in table  # mean cost
        assert r"BANK\_A" in table  # escaped underscore
