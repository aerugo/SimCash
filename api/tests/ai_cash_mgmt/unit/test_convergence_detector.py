"""Unit tests for ConvergenceDetector - stability and convergence detection.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestConvergenceDetector:
    """Test convergence detection logic."""

    def test_detector_not_converged_initially(self) -> None:
        """Detector should not be converged with no history."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        assert not detector.is_converged

    def test_detector_converges_after_stable_window(self) -> None:
        """Detector should converge after stability_window stable iterations."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        # Add 3 similar values (within threshold)
        detector.record_metric(100.0)
        assert not detector.is_converged

        detector.record_metric(99.0)  # 1% change
        assert not detector.is_converged

        detector.record_metric(98.5)  # <1% change
        assert not detector.is_converged

        detector.record_metric(98.2)  # <1% change - should converge
        assert detector.is_converged

    def test_detector_resets_on_large_change(self) -> None:
        """Large metric change should reset stability counter."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        # Build up some stability
        detector.record_metric(100.0)
        detector.record_metric(99.0)
        detector.record_metric(98.5)

        # Large change resets
        detector.record_metric(80.0)  # 20% drop
        assert not detector.is_converged

        # Need to rebuild stability window
        detector.record_metric(79.5)
        detector.record_metric(79.2)
        detector.record_metric(79.0)
        assert detector.is_converged

    def test_detector_max_iterations_triggers_convergence(self) -> None:
        """Should report converged after max_iterations regardless of stability."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.01,  # Very strict
            stability_window=3,
            max_iterations=5,  # Low max
            improvement_threshold=0.01,
        )

        # Keep changing significantly
        for i in range(6):
            detector.record_metric(100.0 - i * 10)  # 10% drops

        assert detector.is_converged  # max_iterations reached
        assert detector.current_iteration >= 5

    def test_detector_tracks_best_metric(self) -> None:
        """Detector should track best (lowest) metric seen."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        assert detector.best_metric == 100.0

        detector.record_metric(80.0)
        assert detector.best_metric == 80.0

        detector.record_metric(90.0)  # Worse
        assert detector.best_metric == 80.0  # Still 80

    def test_detector_improvement_check(self) -> None:
        """should_accept_improvement should use improvement_threshold."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.05,  # 5% improvement required
        )

        detector.record_metric(100.0)

        # 10% improvement - should accept
        assert detector.should_accept_improvement(90.0)

        # 2% improvement - below threshold
        assert not detector.should_accept_improvement(98.0)

        # No improvement
        assert not detector.should_accept_improvement(105.0)

    def test_detector_get_convergence_reason(self) -> None:
        """Should report why convergence was reached."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        # Stability convergence
        detector1 = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=2,
            max_iterations=100,
            improvement_threshold=0.01,
        )
        detector1.record_metric(100.0)
        detector1.record_metric(99.5)
        detector1.record_metric(99.3)

        assert "stability" in detector1.convergence_reason.lower()

        # Max iterations convergence
        detector2 = ConvergenceDetector(
            stability_threshold=0.01,
            stability_window=5,
            max_iterations=3,
            improvement_threshold=0.01,
        )
        for i in range(5):
            detector2.record_metric(100.0 - i * 10)

        assert "max" in detector2.convergence_reason.lower()


class TestConvergenceHistory:
    """Test convergence metric history tracking."""

    def test_history_records_all_metrics(self) -> None:
        """Should keep history of all recorded metrics."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        detector.record_metric(90.0)
        detector.record_metric(85.0)

        history = detector.metric_history
        assert len(history) == 3
        assert history[0] == 100.0
        assert history[1] == 90.0
        assert history[2] == 85.0

    def test_current_iteration_tracks_count(self) -> None:
        """current_iteration should return count of recorded metrics."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        assert detector.current_iteration == 0

        detector.record_metric(100.0)
        assert detector.current_iteration == 1

        detector.record_metric(90.0)
        assert detector.current_iteration == 2


class TestConvergenceEdgeCases:
    """Test edge cases in convergence detection."""

    def test_single_value_not_converged(self) -> None:
        """Single value should not trigger convergence."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=1,  # Even with window=1
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        # Need at least 2 values to compare
        assert not detector.is_converged

    def test_zero_metric_handled(self) -> None:
        """Zero metric values should be handled correctly."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(0.0)
        detector.record_metric(0.0)
        detector.record_metric(0.0)
        detector.record_metric(0.0)

        # Should converge (zero change)
        assert detector.is_converged

    def test_negative_metrics_handled(self) -> None:
        """Negative metric values should work (for metrics where lower is better)."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=3,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(-100.0)
        detector.record_metric(-99.0)
        detector.record_metric(-98.5)
        detector.record_metric(-98.2)

        assert detector.is_converged

    def test_reset_clears_state(self) -> None:
        """reset() should clear all state."""
        from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
            ConvergenceDetector,
        )

        detector = ConvergenceDetector(
            stability_threshold=0.05,
            stability_window=2,
            max_iterations=50,
            improvement_threshold=0.01,
        )

        detector.record_metric(100.0)
        detector.record_metric(99.5)
        detector.record_metric(99.3)
        assert detector.is_converged

        detector.reset()

        assert not detector.is_converged
        assert detector.current_iteration == 0
        assert len(detector.metric_history) == 0
        assert detector.best_metric is None
