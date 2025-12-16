"""Tests for experiment charting module.

Tests chart data extraction and rendering functionality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from payment_simulator.experiments.analysis.charting import (
    ChartData,
    ChartDataPoint,
    ExperimentChartService,
    render_convergence_chart,
    _build_accepted_trajectory,
)
from payment_simulator.experiments.persistence.repository import (
    ExperimentRecord,
    IterationRecord,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_repo() -> MagicMock:
    """Create a mock ExperimentRepository."""
    return MagicMock()


@pytest.fixture
def sample_experiment() -> ExperimentRecord:
    """Create a sample experiment record."""
    return ExperimentRecord(
        run_id="exp1-20251215-084901-866d63",
        experiment_name="exp1",
        experiment_type="castro",
        config={"evaluation": {"mode": "deterministic"}},
        created_at="2025-12-15T08:49:01",
        completed_at="2025-12-15T09:00:00",
        num_iterations=5,
        converged=True,
        convergence_reason="stability",
    )


@pytest.fixture
def sample_iterations() -> list[IterationRecord]:
    """Create sample iteration records."""
    return [
        IterationRecord(
            run_id="exp1-20251215-084901-866d63",
            iteration=0,
            costs_per_agent={"BANK_A": 8000, "BANK_B": 7000},
            accepted_changes={"BANK_A": True, "BANK_B": True},
            policies={
                "BANK_A": {"parameters": {"initial_liquidity_fraction": 0.5}},
                "BANK_B": {"parameters": {"initial_liquidity_fraction": 0.5}},
            },
            timestamp="2025-12-15T08:49:02",
        ),
        IterationRecord(
            run_id="exp1-20251215-084901-866d63",
            iteration=1,
            costs_per_agent={"BANK_A": 7500, "BANK_B": 6500},
            accepted_changes={"BANK_A": True, "BANK_B": False},
            policies={
                "BANK_A": {"parameters": {"initial_liquidity_fraction": 0.4}},
                "BANK_B": {"parameters": {"initial_liquidity_fraction": 0.45}},
            },
            timestamp="2025-12-15T08:49:10",
        ),
        IterationRecord(
            run_id="exp1-20251215-084901-866d63",
            iteration=2,
            costs_per_agent={"BANK_A": 7000, "BANK_B": 6000},
            accepted_changes={"BANK_A": True, "BANK_B": True},
            policies={
                "BANK_A": {"parameters": {"initial_liquidity_fraction": 0.3}},
                "BANK_B": {"parameters": {"initial_liquidity_fraction": 0.35}},
            },
            timestamp="2025-12-15T08:49:20",
        ),
    ]


# =============================================================================
# Data Extraction Tests
# =============================================================================


class TestExperimentChartService:
    """Tests for ExperimentChartService."""

    def test_extract_chart_data_basic(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
        sample_iterations: list[IterationRecord],
    ) -> None:
        """Extract costs for all iterations."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = sample_iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data("exp1-20251215-084901-866d63")

        assert data.run_id == "exp1-20251215-084901-866d63"
        assert data.experiment_name == "exp1"
        assert data.evaluation_mode == "deterministic"
        assert len(data.data_points) == 3

        # Check iteration numbers are 0-indexed (iteration 0 = baseline)
        assert data.data_points[0].iteration == 0
        assert data.data_points[1].iteration == 1
        assert data.data_points[2].iteration == 2

        # Check costs converted to dollars (system total)
        assert data.data_points[0].cost_dollars == 150.0  # (8000 + 7000) / 100
        assert data.data_points[1].cost_dollars == 140.0  # (7500 + 6500) / 100
        assert data.data_points[2].cost_dollars == 130.0  # (7000 + 6000) / 100

    def test_extract_chart_data_separates_accepted(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
        sample_iterations: list[IterationRecord],
    ) -> None:
        """Accepted vs all policies are distinguished."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = sample_iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data("exp1-20251215-084901-866d63")

        # Iteration 0: both accepted -> True
        # Iteration 1: BANK_A accepted, BANK_B not -> True (any accepted)
        # Iteration 2: both accepted -> True
        assert data.data_points[0].accepted is True
        assert data.data_points[1].accepted is True  # any agent accepted
        assert data.data_points[2].accepted is True

    def test_extract_chart_data_agent_filter(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
        sample_iterations: list[IterationRecord],
    ) -> None:
        """Filter to single agent's costs."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = sample_iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data(
            "exp1-20251215-084901-866d63",
            agent_filter="BANK_A",
        )

        assert data.agent_id == "BANK_A"
        # Only BANK_A costs
        assert data.data_points[0].cost_dollars == 80.0  # 8000 / 100
        assert data.data_points[1].cost_dollars == 75.0  # 7500 / 100
        assert data.data_points[2].cost_dollars == 70.0  # 7000 / 100

        # Check acceptance is agent-specific
        assert data.data_points[0].accepted is True
        assert data.data_points[1].accepted is True
        assert data.data_points[2].accepted is True

    def test_extract_chart_data_agent_filter_bank_b(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
        sample_iterations: list[IterationRecord],
    ) -> None:
        """Filter to BANK_B which has rejection in iteration 1."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = sample_iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data(
            "exp1-20251215-084901-866d63",
            agent_filter="BANK_B",
        )

        assert data.agent_id == "BANK_B"
        # BANK_B costs
        assert data.data_points[0].cost_dollars == 70.0  # 7000 / 100
        assert data.data_points[1].cost_dollars == 65.0  # 6500 / 100
        assert data.data_points[2].cost_dollars == 60.0  # 6000 / 100

        # Acceptance is inferred from cost improvement (not accepted_changes field)
        # All costs decrease, so all are accepted
        assert data.data_points[0].accepted is True  # First iteration
        assert data.data_points[1].accepted is True  # 65.0 < 70.0 (improved)
        assert data.data_points[2].accepted is True  # 60.0 < 65.0 (improved)

    def test_extract_chart_data_parameter_extraction(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
        sample_iterations: list[IterationRecord],
    ) -> None:
        """Extract parameter values from policies."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = sample_iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data(
            "exp1-20251215-084901-866d63",
            agent_filter="BANK_A",
            parameter_name="initial_liquidity_fraction",
        )

        assert data.parameter_name == "initial_liquidity_fraction"
        assert data.data_points[0].parameter_value == 0.5
        assert data.data_points[1].parameter_value == 0.4
        assert data.data_points[2].parameter_value == 0.3

    def test_extract_chart_data_empty_run(
        self,
        mock_repo: MagicMock,
        sample_experiment: ExperimentRecord,
    ) -> None:
        """Handle run with no iterations gracefully."""
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False  # Use iterations table
        mock_repo.get_iterations.return_value = []

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data("exp1-20251215-084901-866d63")

        assert data.data_points == []
        assert data.run_id == "exp1-20251215-084901-866d63"

    def test_extract_chart_data_run_not_found(
        self,
        mock_repo: MagicMock,
    ) -> None:
        """Error on invalid run_id."""
        mock_repo.load_experiment.return_value = None

        service = ExperimentChartService(mock_repo)

        with pytest.raises(ValueError, match="Experiment run not found"):
            service.extract_chart_data("nonexistent-run")


# =============================================================================
# Accepted Trajectory Tests
# =============================================================================


class TestBuildAcceptedTrajectory:
    """Tests for _build_accepted_trajectory helper."""

    def test_all_accepted(self) -> None:
        """All iterations accepted - costs flow through."""
        points = [
            ChartDataPoint(1, 100.0, True),
            ChartDataPoint(2, 90.0, True),
            ChartDataPoint(3, 80.0, True),
        ]
        trajectory = _build_accepted_trajectory(points)
        assert trajectory == [100.0, 90.0, 80.0]

    def test_some_rejected(self) -> None:
        """Rejected iterations carry forward previous accepted cost."""
        points = [
            ChartDataPoint(1, 100.0, True),
            ChartDataPoint(2, 110.0, False),  # Rejected
            ChartDataPoint(3, 80.0, True),
        ]
        trajectory = _build_accepted_trajectory(points)
        assert trajectory == [100.0, 100.0, 80.0]  # Iteration 2 carries forward

    def test_first_rejected(self) -> None:
        """First iteration rejected uses its own cost."""
        points = [
            ChartDataPoint(1, 100.0, False),  # Rejected
            ChartDataPoint(2, 90.0, True),
            ChartDataPoint(3, 80.0, True),
        ]
        trajectory = _build_accepted_trajectory(points)
        # First iteration has no prior accepted, uses its own
        assert trajectory == [100.0, 90.0, 80.0]

    def test_consecutive_rejections(self) -> None:
        """Multiple consecutive rejections carry same accepted cost."""
        points = [
            ChartDataPoint(1, 100.0, True),
            ChartDataPoint(2, 110.0, False),  # Rejected
            ChartDataPoint(3, 120.0, False),  # Rejected
            ChartDataPoint(4, 70.0, True),
        ]
        trajectory = _build_accepted_trajectory(points)
        assert trajectory == [100.0, 100.0, 100.0, 70.0]


# =============================================================================
# Chart Rendering Tests
# =============================================================================


class TestRenderConvergenceChart:
    """Tests for render_convergence_chart."""

    def test_render_chart_creates_file(self, tmp_path: Path) -> None:
        """Chart file is created at specified path."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id=None,
            parameter_name=None,
            data_points=[
                ChartDataPoint(1, 100.0, True),
                ChartDataPoint(2, 90.0, True),
                ChartDataPoint(3, 80.0, True),
            ],
        )

        output_path = tmp_path / "chart.png"
        render_convergence_chart(data, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_chart_with_agent(self, tmp_path: Path) -> None:
        """Chart with agent ID in title."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id="BANK_A",
            parameter_name=None,
            data_points=[
                ChartDataPoint(1, 100.0, True),
                ChartDataPoint(2, 90.0, True),
            ],
        )

        output_path = tmp_path / "chart.png"
        render_convergence_chart(data, output_path)

        assert output_path.exists()

    def test_render_chart_with_parameter_annotations(self, tmp_path: Path) -> None:
        """Chart with parameter annotations."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id="BANK_A",
            parameter_name="initial_liquidity_fraction",
            data_points=[
                ChartDataPoint(1, 100.0, True, 0.5),
                ChartDataPoint(2, 90.0, True, 0.4),
                ChartDataPoint(3, 80.0, True, 0.3),
            ],
        )

        output_path = tmp_path / "chart.png"
        render_convergence_chart(data, output_path)

        assert output_path.exists()

    def test_render_chart_pdf_format(self, tmp_path: Path) -> None:
        """Chart can be saved as PDF."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id=None,
            parameter_name=None,
            data_points=[
                ChartDataPoint(1, 100.0, True),
                ChartDataPoint(2, 90.0, True),
            ],
        )

        output_path = tmp_path / "chart.pdf"
        render_convergence_chart(data, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_render_chart_empty_data_raises(self, tmp_path: Path) -> None:
        """Empty data raises ValueError."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id=None,
            parameter_name=None,
            data_points=[],
        )

        output_path = tmp_path / "chart.png"

        with pytest.raises(ValueError, match="Cannot render chart with no data points"):
            render_convergence_chart(data, output_path)

    def test_render_chart_dual_lines(self, tmp_path: Path) -> None:
        """Chart with mix of accepted/rejected shows both lines."""
        data = ChartData(
            run_id="test-run",
            experiment_name="test",
            evaluation_mode="deterministic",
            agent_id=None,
            parameter_name=None,
            data_points=[
                ChartDataPoint(1, 100.0, True),
                ChartDataPoint(2, 110.0, False),  # Rejected
                ChartDataPoint(3, 90.0, True),
                ChartDataPoint(4, 80.0, True),
            ],
        )

        output_path = tmp_path / "chart.png"
        render_convergence_chart(data, output_path)

        assert output_path.exists()
