"""Tests for evaluation mode parsing in EvaluationConfig.

Phase 2 of deterministic-evaluation-modes implementation.

Tests validation and helper properties for evaluation modes:
- bootstrap
- deterministic (alias for deterministic-pairwise)
- deterministic-pairwise
- deterministic-temporal
"""

from __future__ import annotations

import pytest

from payment_simulator.experiments.config.experiment_config import EvaluationConfig


class TestEvaluationModeValidation:
    """Tests for evaluation mode validation."""

    def test_bootstrap_mode_accepted(self) -> None:
        """Bootstrap mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="bootstrap", num_samples=20)
        assert config.mode == "bootstrap"

    def test_deterministic_pairwise_mode_accepted(self) -> None:
        """deterministic-pairwise mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="deterministic-pairwise")
        assert config.mode == "deterministic-pairwise"

    def test_deterministic_temporal_mode_accepted(self) -> None:
        """deterministic-temporal mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        assert config.mode == "deterministic-temporal"

    def test_plain_deterministic_accepted_for_backward_compat(self) -> None:
        """Plain 'deterministic' should be accepted for backward compatibility."""
        config = EvaluationConfig(ticks=10, mode="deterministic")
        assert config.mode == "deterministic"

    def test_invalid_mode_raises_error(self) -> None:
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid evaluation mode"):
            EvaluationConfig(ticks=10, mode="invalid")

    def test_empty_mode_raises_error(self) -> None:
        """Empty mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid evaluation mode"):
            EvaluationConfig(ticks=10, mode="")


class TestEvaluationModeHelperProperties:
    """Tests for helper properties on EvaluationConfig."""

    def test_is_bootstrap_true_for_bootstrap_mode(self) -> None:
        """is_bootstrap should be True for bootstrap mode."""
        config = EvaluationConfig(ticks=10, mode="bootstrap")
        assert config.is_bootstrap is True

    def test_is_bootstrap_false_for_deterministic_modes(self) -> None:
        """is_bootstrap should be False for deterministic modes."""
        for mode in ["deterministic", "deterministic-pairwise", "deterministic-temporal"]:
            config = EvaluationConfig(ticks=10, mode=mode)
            assert config.is_bootstrap is False, f"is_bootstrap should be False for {mode}"

    def test_is_deterministic_true_for_all_deterministic_modes(self) -> None:
        """is_deterministic should be True for all deterministic modes."""
        for mode in ["deterministic", "deterministic-pairwise", "deterministic-temporal"]:
            config = EvaluationConfig(ticks=10, mode=mode)
            assert config.is_deterministic is True, f"is_deterministic should be True for {mode}"

    def test_is_deterministic_false_for_bootstrap(self) -> None:
        """is_deterministic should be False for bootstrap mode."""
        config = EvaluationConfig(ticks=10, mode="bootstrap")
        assert config.is_deterministic is False

    def test_is_deterministic_pairwise_true_for_pairwise_and_plain(self) -> None:
        """is_deterministic_pairwise should be True for pairwise and plain deterministic."""
        for mode in ["deterministic", "deterministic-pairwise"]:
            config = EvaluationConfig(ticks=10, mode=mode)
            assert config.is_deterministic_pairwise is True, (
                f"is_deterministic_pairwise should be True for {mode}"
            )

    def test_is_deterministic_pairwise_false_for_temporal(self) -> None:
        """is_deterministic_pairwise should be False for temporal mode."""
        config = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        assert config.is_deterministic_pairwise is False

    def test_is_deterministic_pairwise_false_for_bootstrap(self) -> None:
        """is_deterministic_pairwise should be False for bootstrap mode."""
        config = EvaluationConfig(ticks=10, mode="bootstrap")
        assert config.is_deterministic_pairwise is False

    def test_is_deterministic_temporal_true_for_temporal_mode(self) -> None:
        """is_deterministic_temporal should be True for temporal mode."""
        config = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        assert config.is_deterministic_temporal is True

    def test_is_deterministic_temporal_false_for_other_modes(self) -> None:
        """is_deterministic_temporal should be False for non-temporal modes."""
        for mode in ["bootstrap", "deterministic", "deterministic-pairwise"]:
            config = EvaluationConfig(ticks=10, mode=mode)
            assert config.is_deterministic_temporal is False, (
                f"is_deterministic_temporal should be False for {mode}"
            )


class TestEvaluationModeSemantics:
    """Tests documenting the semantics of each evaluation mode."""

    def test_bootstrap_mode_semantics(self) -> None:
        """Document bootstrap mode: N samples, paired comparison."""
        config = EvaluationConfig(ticks=10, mode="bootstrap", num_samples=20)
        assert config.is_bootstrap is True
        assert config.num_samples == 20
        # Bootstrap mode runs N simulations and compares delta_sum

    def test_deterministic_pairwise_semantics(self) -> None:
        """Document deterministic-pairwise: same seed, old vs new in same iteration."""
        config = EvaluationConfig(ticks=10, mode="deterministic-pairwise")
        assert config.is_deterministic_pairwise is True
        assert config.is_deterministic_temporal is False
        # Pairwise compares old_cost vs new_cost on same seed

    def test_deterministic_temporal_semantics(self) -> None:
        """Document deterministic-temporal: compare cost across iterations."""
        config = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        assert config.is_deterministic_temporal is True
        assert config.is_deterministic_pairwise is False
        # Temporal compares cost_N vs cost_{N-1}
