"""Tests for metrics aggregation module.

Tests for computing aggregated metrics from simulation results.
"""

from __future__ import annotations

import pytest


class TestComputeMetrics:
    """Tests for compute_metrics function."""

    def test_returns_mean_cost(self) -> None:
        """Mean cost is computed correctly."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 1.0, "seed": 2, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["total_cost_mean"] == 1500

    def test_returns_std_cost(self) -> None:
        """Standard deviation is computed correctly."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 1.0, "seed": 2, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        # stdev of [1000, 2000] = 707.1...
        assert metrics["total_cost_std"] > 700
        assert metrics["total_cost_std"] < 710

    def test_identifies_best_worst_seed(self) -> None:
        """Best and worst seeds are identified."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 42, "agent_cost": 500},
            {"total_cost": 3000, "settlement_rate": 1.0, "seed": 17, "agent_cost": 1500},
            {"total_cost": 2000, "settlement_rate": 1.0, "seed": 99, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["best_seed"] == 42
        assert metrics["worst_seed"] == 17
        assert metrics["best_seed_cost"] == 1000
        assert metrics["worst_seed_cost"] == 3000

    def test_computes_risk_adjusted_cost(self) -> None:
        """Risk-adjusted cost = mean + std."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 1.0, "seed": 2, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        expected = metrics["total_cost_mean"] + metrics["total_cost_std"]
        assert abs(metrics["risk_adjusted_cost"] - expected) < 0.01

    def test_handles_single_result(self) -> None:
        """Single result has std=0."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500}
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["total_cost_std"] == 0.0
        assert metrics["total_cost_mean"] == 1000
        assert metrics["best_seed"] == 1
        assert metrics["worst_seed"] == 1

    def test_returns_none_for_empty(self) -> None:
        """Returns None for empty results."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        metrics = compute_metrics([], agent_id="BANK_A")

        assert metrics is None

    def test_filters_error_results(self) -> None:
        """Error results are filtered out."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"error": "Simulation failed"},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["total_cost_mean"] == 1000

    def test_returns_none_when_all_errors(self) -> None:
        """Returns None when all results are errors."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"error": "Simulation failed"},
            {"error": "Another failure"},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is None

    def test_computes_settlement_rate_mean(self) -> None:
        """Settlement rate mean is computed correctly."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 0.9, "seed": 2, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["settlement_rate_mean"] == 0.95

    def test_computes_failure_rate(self) -> None:
        """Failure rate is computed correctly."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 0.9, "seed": 2, "agent_cost": 1000},
            {"total_cost": 1500, "settlement_rate": 1.0, "seed": 3, "agent_cost": 750},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        # 1 out of 3 has settlement_rate < 1.0
        assert abs(metrics["failure_rate"] - (1 / 3)) < 0.01

    def test_computes_agent_cost_mean(self) -> None:
        """Per-agent cost mean is computed correctly."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import compute_metrics

        results = [
            {"total_cost": 1000, "settlement_rate": 1.0, "seed": 1, "agent_cost": 500},
            {"total_cost": 2000, "settlement_rate": 1.0, "seed": 2, "agent_cost": 1000},
        ]

        metrics = compute_metrics(results, agent_id="BANK_A")

        assert metrics is not None
        assert metrics["agent_cost_mean"] == 750


class TestAggregatedMetricsType:
    """Tests for AggregatedMetrics TypedDict."""

    def test_has_required_fields(self) -> None:
        """AggregatedMetrics has all required fields."""
        from payment_simulator.ai_cash_mgmt.metrics.aggregation import AggregatedMetrics

        # TypedDict should define these fields
        expected_fields = {
            "total_cost_mean",
            "total_cost_std",
            "risk_adjusted_cost",
            "settlement_rate_mean",
            "failure_rate",
            "best_seed",
            "worst_seed",
            "best_seed_cost",
            "worst_seed_cost",
            "agent_cost_mean",
        }

        # Get annotations from TypedDict
        annotations = getattr(AggregatedMetrics, "__annotations__", {})

        assert expected_fields == set(annotations.keys())
