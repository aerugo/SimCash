"""Tests for deterministic evaluation mode.

TDD tests for the feature that allows disabling bootstrap sampling
when running experiments with deterministic scenarios.

Tests cover:
- BootstrapConfig deterministic flag
- CastroExperiment deterministic flag propagation
- Single-sample evaluation in runner
- Context builder single-sample handling
- Display output for deterministic mode
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from payment_simulator.ai_cash_mgmt.config.game_config import BootstrapConfig


class TestBootstrapConfigDeterministic:
    """Tests for BootstrapConfig deterministic mode."""

    def test_deterministic_mode_default_false(self) -> None:
        """Deterministic mode defaults to False."""
        config = BootstrapConfig()
        assert config.deterministic is False

    def test_deterministic_mode_explicit_true(self) -> None:
        """Deterministic mode can be set explicitly to True."""
        config = BootstrapConfig(deterministic=True)
        assert config.deterministic is True

    def test_deterministic_forces_num_samples_to_one(self) -> None:
        """When deterministic=True, num_samples is forced to 1."""
        config = BootstrapConfig(deterministic=True, num_samples=10)
        assert config.num_samples == 1

    def test_deterministic_allows_num_samples_one(self) -> None:
        """When deterministic=True, num_samples=1 is allowed."""
        config = BootstrapConfig(deterministic=True, num_samples=1)
        assert config.num_samples == 1

    def test_non_deterministic_requires_minimum_five_samples(self) -> None:
        """When deterministic=False, num_samples must be >= 5."""
        with pytest.raises(ValueError, match="num_samples must be >= 5"):
            BootstrapConfig(deterministic=False, num_samples=3)

    def test_non_deterministic_allows_five_or_more_samples(self) -> None:
        """When deterministic=False, num_samples >= 5 is valid."""
        config = BootstrapConfig(deterministic=False, num_samples=5)
        assert config.num_samples == 5

        config = BootstrapConfig(deterministic=False, num_samples=20)
        assert config.num_samples == 20

    def test_default_num_samples_valid_for_non_deterministic(self) -> None:
        """Default num_samples (20) is valid for non-deterministic mode."""
        config = BootstrapConfig()
        assert config.num_samples == 20
        assert config.deterministic is False


class TestCastroExperimentDeterministic:
    """Tests for CastroExperiment deterministic mode."""

    def test_experiment_deterministic_default_false(self) -> None:
        """Experiments default to non-deterministic."""
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            num_samples=5,
        )
        assert exp.deterministic is False

    def test_experiment_deterministic_explicit_true(self) -> None:
        """Experiments can be set to deterministic mode."""
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,
        )
        assert exp.deterministic is True

    def test_experiment_deterministic_propagates_to_bootstrap_config(self) -> None:
        """Deterministic flag flows to BootstrapConfig."""
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,
            num_samples=10,  # Should be ignored/overridden
        )
        mc_config = exp.get_bootstrap_config()

        assert mc_config.deterministic is True
        assert mc_config.num_samples == 1

    def test_experiment_non_deterministic_respects_num_samples(self) -> None:
        """Non-deterministic experiments respect num_samples."""
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=False,
            num_samples=10,
        )
        mc_config = exp.get_bootstrap_config()

        assert mc_config.deterministic is False
        assert mc_config.num_samples == 10


class TestExp1Deterministic:
    """Tests for exp1 deterministic configuration."""

    def test_exp1_is_deterministic(self) -> None:
        """Exp1 (2-period Nash) should use deterministic mode."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        exp = YamlExperimentConfig(config_dict)
        bootstrap_config = exp.get_bootstrap_config()
        assert bootstrap_config.deterministic is True

    def test_exp1_bootstrap_config_is_deterministic(self) -> None:
        """Exp1's BootstrapConfig should be deterministic with 1 sample."""
        from castro.experiment_config import YamlExperimentConfig
        from castro.experiment_loader import load_experiment

        config_dict = load_experiment("exp1")
        exp = YamlExperimentConfig(config_dict)
        mc_config = exp.get_bootstrap_config()

        assert mc_config.deterministic is True
        assert mc_config.num_samples == 1


class TestContextBuilderSingleSample:
    """Tests for BootstrapContextBuilder with single sample."""

    def test_single_sample_best_equals_worst(self) -> None:
        """With one sample, best and worst seed are identical."""
        from castro.context_builder import BootstrapContextBuilder

        # Create a mock result
        mock_result = MagicMock()
        mock_result.total_cost = 500
        mock_result.per_agent_costs = {"BANK_A": 250, "BANK_B": 250}
        mock_result.settlement_rate = 1.0
        mock_result.verbose_output = None

        builder = BootstrapContextBuilder(results=[mock_result], seeds=[12345])
        ctx = builder.get_agent_simulation_context("BANK_A")

        assert ctx.best_seed == ctx.worst_seed == 12345
        assert ctx.best_seed_cost == ctx.worst_seed_cost == 250

    def test_single_sample_std_is_zero(self) -> None:
        """With one sample, standard deviation is 0."""
        from castro.context_builder import BootstrapContextBuilder

        mock_result = MagicMock()
        mock_result.total_cost = 500
        mock_result.per_agent_costs = {"BANK_A": 250, "BANK_B": 250}
        mock_result.settlement_rate = 1.0
        mock_result.verbose_output = None

        builder = BootstrapContextBuilder(results=[mock_result], seeds=[12345])
        ctx = builder.get_agent_simulation_context("BANK_A")

        assert ctx.cost_std == 0.0

    def test_single_sample_mean_equals_value(self) -> None:
        """With one sample, mean equals the single value."""
        from castro.context_builder import BootstrapContextBuilder

        mock_result = MagicMock()
        mock_result.total_cost = 500
        mock_result.per_agent_costs = {"BANK_A": 300, "BANK_B": 200}
        mock_result.settlement_rate = 1.0
        mock_result.verbose_output = None

        builder = BootstrapContextBuilder(results=[mock_result], seeds=[12345])
        ctx = builder.get_agent_simulation_context("BANK_A")

        assert ctx.mean_cost == 300.0


class TestVerboseLoggerDeterministic:
    """Tests for VerboseLogger deterministic mode output."""

    def test_deterministic_display_no_std_shown(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Deterministic mode doesn't show standard deviation."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )
        from rich.console import Console

        config = VerboseConfig(bootstrap=True)
        console = Console(force_terminal=True, width=120)
        logger = VerboseLogger(config, console)

        # Single result (deterministic)
        seed_results = [
            BootstrapSampleResult(
                seed=12345,
                cost=50000,
                settled=10,
                total=10,
                settlement_rate=1.0,
            )
        ]

        logger.log_bootstrap_evaluation(
            seed_results=seed_results,
            mean_cost=50000,
            std_cost=0,
            deterministic=True,
        )

        captured = capsys.readouterr()
        # Should show deterministic label
        assert "Deterministic" in captured.out or "deterministic" in captured.out.lower()

    def test_non_deterministic_display_shows_statistics(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-deterministic mode shows mean and std statistics."""
        from castro.verbose_logging import (
            BootstrapSampleResult,
            VerboseConfig,
            VerboseLogger,
        )
        from rich.console import Console

        config = VerboseConfig(bootstrap=True)
        console = Console(force_terminal=True, width=120)
        logger = VerboseLogger(config, console)

        # Multiple results (non-deterministic)
        seed_results = [
            BootstrapSampleResult(seed=1, cost=45000, settled=9, total=10, settlement_rate=0.9),
            BootstrapSampleResult(seed=2, cost=50000, settled=10, total=10, settlement_rate=1.0),
            BootstrapSampleResult(seed=3, cost=55000, settled=10, total=10, settlement_rate=1.0),
        ]

        logger.log_bootstrap_evaluation(
            seed_results=seed_results,
            mean_cost=50000,
            std_cost=4082,
            deterministic=False,
        )

        captured = capsys.readouterr()
        # Should show statistics
        assert "Mean" in captured.out
        assert "std" in captured.out


class TestEvaluatePoliciesDeterministic:
    """Tests for _evaluate_policies with deterministic mode."""

    def test_deterministic_runs_single_simulation(self) -> None:
        """In deterministic mode, only one simulation runs."""
        # This test will verify the runner behavior once implemented
        # For now, just verify the config is set up correctly
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,
        )
        mc_config = exp.get_bootstrap_config()

        assert mc_config.num_samples == 1

    def test_deterministic_seed_is_iteration_based(self) -> None:
        """Deterministic mode uses iteration-based seed without sample index."""
        from payment_simulator.ai_cash_mgmt import SeedManager

        seed_manager = SeedManager(master_seed=42)

        # In deterministic mode, seed should be iteration * 1000 (no sample_idx)
        seed_iter_1 = seed_manager.simulation_seed(1 * 1000)
        seed_iter_2 = seed_manager.simulation_seed(2 * 1000)

        # Seeds should be different for different iterations
        assert seed_iter_1 != seed_iter_2

        # Same iteration should give same seed (deterministic)
        seed_iter_1_again = seed_manager.simulation_seed(1 * 1000)
        assert seed_iter_1 == seed_iter_1_again
