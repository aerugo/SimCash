"""Tests for chart generation - TDD RED phase.

These tests verify that charts can be generated from experiment databases.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def data_dir() -> Path:
    """Path to experiment databases."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def config() -> dict:
    """Load paper config."""
    from src.config import load_config

    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        pytest.skip("Config file not available")
    return load_config(config_path)


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Temporary directory for chart output."""
    charts_dir = tmp_path / "charts"
    charts_dir.mkdir()
    return charts_dir


# =============================================================================
# Phase: Convergence Chart Tests (RED)
# =============================================================================


class TestConvergenceChartGeneration:
    """Test convergence chart generation using existing SimCash infrastructure."""

    def test_generate_agent_convergence_chart(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate convergence chart for single agent."""
        from src.charts.generators import generate_convergence_chart

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "exp1_bankA.png"
        generate_convergence_chart(
            db_path=data_dir / "exp1.db",
            exp_id="exp1",
            pass_num=1,
            agent_id="BANK_A",
            output_path=output_path,
            config=config,
        )

        assert output_path.exists(), "Chart file should be created"
        assert output_path.stat().st_size > 1000, "Chart should have content"

    def test_generate_convergence_chart_bank_b(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate convergence chart for BANK_B."""
        from src.charts.generators import generate_convergence_chart

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "exp1_bankB.png"
        generate_convergence_chart(
            db_path=data_dir / "exp1.db",
            exp_id="exp1",
            pass_num=1,
            agent_id="BANK_B",
            output_path=output_path,
            config=config,
        )

        assert output_path.exists()

    def test_generate_combined_convergence_chart(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate combined chart showing both agents."""
        from src.charts.generators import generate_combined_convergence_chart

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "exp1_combined.png"
        generate_combined_convergence_chart(
            db_path=data_dir / "exp1.db",
            exp_id="exp1",
            pass_num=1,
            output_path=output_path,
            config=config,
        )

        assert output_path.exists()

    def test_generate_all_experiment_charts(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate all charts for an experiment pass."""
        from src.charts.generators import generate_experiment_charts

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        paths = generate_experiment_charts(
            db_path=data_dir / "exp1.db",
            exp_id="exp1",
            pass_num=1,
            output_dir=output_dir,
            config=config,
        )

        # Should return dict of chart paths
        assert "BANK_A" in paths
        assert "BANK_B" in paths
        assert "combined" in paths

        # All files should exist
        for path in paths.values():
            assert path.exists()


# =============================================================================
# Phase: Bootstrap Chart Tests (RED)
# =============================================================================


class TestBootstrapChartGeneration:
    """Test bootstrap analysis chart generation."""

    def test_generate_ci_width_chart(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate CI width comparison chart."""
        from src.charts.generators import generate_ci_width_chart

        if not (data_dir / "exp2.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "ci_width_comparison.png"
        generate_ci_width_chart(
            db_path=data_dir / "exp2.db",
            exp_id="exp2",
            pass_num=1,
            output_path=output_path,
            config=config,
        )

        assert output_path.exists()

    def test_generate_variance_evolution_chart(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate variance evolution over iterations."""
        from src.charts.generators import generate_variance_evolution_chart

        if not (data_dir / "exp2.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "variance_evolution.png"
        generate_variance_evolution_chart(
            db_path=data_dir / "exp2.db",
            exp_id="exp2",
            pass_num=1,
            output_path=output_path,
            config=config,
        )

        assert output_path.exists()

    def test_generate_sample_distribution_chart(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate sample distribution histogram."""
        from src.charts.generators import generate_sample_distribution_chart

        if not (data_dir / "exp2.db").exists():
            pytest.skip("Data not available")

        output_path = output_dir / "sample_distribution.png"
        generate_sample_distribution_chart(
            db_path=data_dir / "exp2.db",
            exp_id="exp2",
            pass_num=1,
            output_path=output_path,
            config=config,
        )

        assert output_path.exists()


# =============================================================================
# Phase: Batch Generation Tests (RED)
# =============================================================================


class TestBatchChartGeneration:
    """Test batch generation for all paper charts."""

    def test_generate_all_paper_charts(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Should generate all charts needed for the paper."""
        from src.charts.generators import generate_all_paper_charts

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        result = generate_all_paper_charts(
            data_dir=data_dir,
            output_dir=output_dir,
            config=config,
        )

        # Should return dict of all generated paths
        assert isinstance(result, dict)

        # Should have entries for all experiments and passes
        assert "exp1" in result
        assert "exp2" in result
        assert "exp3" in result

    def test_generate_charts_returns_paths(
        self, data_dir: Path, output_dir: Path, config: dict
    ) -> None:
        """Generated paths should all exist."""
        from src.charts.generators import generate_all_paper_charts

        if not (data_dir / "exp1.db").exists():
            pytest.skip("Data not available")

        result = generate_all_paper_charts(
            data_dir=data_dir,
            output_dir=output_dir,
            config=config,
        )

        # Flatten all paths and check existence
        for exp_charts in result.values():
            if isinstance(exp_charts, dict):
                for pass_charts in exp_charts.values():
                    if isinstance(pass_charts, dict):
                        for path in pass_charts.values():
                            if isinstance(path, Path):
                                assert path.exists(), f"Chart not created: {path}"


# =============================================================================
# Phase: Module Interface Tests (RED)
# =============================================================================


class TestChartGeneratorModule:
    """Test chart generator module exports."""

    def test_module_exports_convergence_functions(self) -> None:
        """Module should export convergence chart functions."""
        from src.charts import generators

        assert hasattr(generators, "generate_convergence_chart")
        assert hasattr(generators, "generate_combined_convergence_chart")
        assert hasattr(generators, "generate_experiment_charts")

    def test_module_exports_bootstrap_functions(self) -> None:
        """Module should export bootstrap chart functions."""
        from src.charts import generators

        assert hasattr(generators, "generate_ci_width_chart")
        assert hasattr(generators, "generate_variance_evolution_chart")
        assert hasattr(generators, "generate_sample_distribution_chart")

    def test_module_exports_batch_function(self) -> None:
        """Module should export batch generation function."""
        from src.charts import generators

        assert hasattr(generators, "generate_all_paper_charts")
