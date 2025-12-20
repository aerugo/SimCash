"""Tests for figure inclusion and chart paths - TDD RED phase."""

from __future__ import annotations

from pathlib import Path

import pytest


# =============================================================================
# Phase 5.1: Figure Inclusion Tests (RED)
# =============================================================================


class TestIncludeFigure:
    """Test figure inclusion helper."""

    def test_include_figure_basic(self) -> None:
        """Should generate LaTeX figure environment."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="charts/exp1_convergence.png",
            caption="Experiment 1 Convergence",
            label="fig:exp1_conv",
        )

        assert r"\begin{figure}" in result
        assert r"\end{figure}" in result
        assert r"\includegraphics" in result
        assert "charts/exp1_convergence.png" in result
        assert r"\caption{Experiment 1 Convergence}" in result
        assert r"\label{fig:exp1_conv}" in result

    def test_include_figure_with_width(self) -> None:
        """Should support width parameter."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="chart.png",
            caption="Test",
            label="fig:test",
            width=0.8,
        )

        assert r"width=0.8\textwidth" in result

    def test_include_figure_default_width(self) -> None:
        """Default width should be 1.0 (full textwidth)."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="chart.png",
            caption="Test",
            label="fig:test",
        )

        assert r"width=1.0\textwidth" in result

    def test_include_figure_centering(self) -> None:
        """Figure should be centered."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="chart.png",
            caption="Test",
            label="fig:test",
        )

        assert r"\centering" in result

    def test_include_figure_returns_string(self) -> None:
        """include_figure must return str type."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="chart.png",
            caption="Test",
            label="fig:test",
        )

        assert isinstance(result, str)


# =============================================================================
# Phase 5.2: Chart Path Tests (RED)
# =============================================================================


class TestChartPaths:
    """Test chart path resolution."""

    def test_get_convergence_chart_path(self) -> None:
        """Should return path to convergence chart."""
        from src.charts import get_convergence_chart_path

        path = get_convergence_chart_path("exp1", pass_num=1)

        assert isinstance(path, Path)
        assert "exp1" in str(path)
        assert "pass1" in str(path) or "1" in str(path)

    def test_chart_paths_are_in_output_charts(self) -> None:
        """Chart paths should be in output/charts directory."""
        from src.charts import get_convergence_chart_path

        path = get_convergence_chart_path("exp1", pass_num=1)

        assert "charts" in str(path)


# =============================================================================
# Phase 5.2b: Module Exports Tests (RED)
# =============================================================================


class TestFiguresModuleExports:
    """Test that figures module exports correctly."""

    def test_latex_figures_module_exists(self) -> None:
        """latex.figures module should be importable."""
        from src.latex import figures

        assert hasattr(figures, "include_figure")

    def test_charts_module_exists(self) -> None:
        """charts module should be importable."""
        from src import charts

        assert hasattr(charts, "get_convergence_chart_path")
