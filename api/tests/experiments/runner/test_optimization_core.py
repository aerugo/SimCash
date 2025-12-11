"""TDD tests for generic optimization loop.

Phase 16.2: Tests for OptimizationLoop in core.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOptimizationLoopImport:
    """Tests for OptimizationLoop import and creation."""

    def test_import_from_experiments_runner(self) -> None:
        """OptimizationLoop can be imported from experiments.runner."""
        from payment_simulator.experiments.runner import OptimizationLoop

        assert OptimizationLoop is not None

    def test_creates_with_config(self) -> None:
        """OptimizationLoop created with ExperimentConfig."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.llm import LLMConfig

        # Use mock config
        mock_config = MagicMock(spec=ExperimentConfig)
        mock_config.name = "test_experiment"
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)
        assert loop is not None


class TestOptimizationLoopResult:
    """Tests for OptimizationResult dataclass."""

    def test_optimization_result_importable(self) -> None:
        """OptimizationResult can be imported."""
        from payment_simulator.experiments.runner import OptimizationResult

        assert OptimizationResult is not None

    def test_optimization_result_has_required_fields(self) -> None:
        """OptimizationResult has all required fields."""
        from payment_simulator.experiments.runner import OptimizationResult

        result = OptimizationResult(
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
            final_cost=15000,  # Integer cents (INV-1)
            best_cost=14500,
            per_agent_costs={"BANK_A": 7500, "BANK_B": 7000},
            final_policies={"BANK_A": {}, "BANK_B": {}},
            iteration_history=[],
        )

        assert result.num_iterations == 10
        assert result.converged is True
        assert result.convergence_reason == "stability_reached"
        assert result.final_cost == 15000
        assert result.best_cost == 14500
        assert result.per_agent_costs == {"BANK_A": 7500, "BANK_B": 7000}

    def test_optimization_result_costs_are_integers(self) -> None:
        """OptimizationResult costs are integer cents (INV-1)."""
        from payment_simulator.experiments.runner import OptimizationResult

        result = OptimizationResult(
            num_iterations=5,
            converged=True,
            convergence_reason="max_iterations",
            final_cost=10000,
            best_cost=9500,
            per_agent_costs={"BANK_A": 5000},
            final_policies={},
            iteration_history=[],
        )

        # INV-1: All costs must be integers (cents)
        assert isinstance(result.final_cost, int)
        assert isinstance(result.best_cost, int)
        for cost in result.per_agent_costs.values():
            assert isinstance(cost, int)


class TestOptimizationLoopConvergence:
    """Tests for convergence behavior."""

    def test_loop_uses_convergence_config(self) -> None:
        """OptimizationLoop uses convergence criteria from config."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 25
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 5
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        # Should have convergence detector with config values
        assert loop.max_iterations == 25
        assert loop.stability_threshold == 0.05

    def test_loop_has_is_converged_property(self) -> None:
        """OptimizationLoop has is_converged property."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "is_converged")
        assert loop.is_converged is False  # Initially not converged


class TestOptimizationLoopRunMethod:
    """Tests for the run() method."""

    def test_has_async_run_method(self) -> None:
        """OptimizationLoop has async run() method."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "run")
        import inspect
        assert inspect.iscoroutinefunction(loop.run)

    def test_run_returns_optimization_result(self) -> None:
        """run() returns OptimizationResult."""
        from payment_simulator.experiments.runner import (
            OptimizationLoop,
            OptimizationResult,
        )
        from payment_simulator.llm import LLMConfig

        # This test verifies the return type signature
        # Actual running requires mocked evaluator/optimizer
        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        # Check return type annotation
        import typing
        hints = typing.get_type_hints(loop.run)
        assert hints.get("return") is OptimizationResult


class TestOptimizationLoopAgentOptimization:
    """Tests for per-agent optimization."""

    def test_loop_has_optimized_agents_property(self) -> None:
        """OptimizationLoop exposes optimized_agents from config."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A", "BANK_B")
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        assert loop.optimized_agents == ("BANK_A", "BANK_B")

    def test_loop_has_current_policies_property(self) -> None:
        """OptimizationLoop tracks current policies per agent."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "current_policies")
        # Initially empty or default
        assert isinstance(loop.current_policies, dict)


class TestOptimizationLoopConstraints:
    """Tests for constraint handling."""

    def test_loop_uses_constraints_from_config(self) -> None:
        """OptimizationLoop gets constraints from config.get_constraints()."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig
        from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints

        mock_constraints = MagicMock(spec=ScenarioConstraints)

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = mock_constraints
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        # Should have called get_constraints
        mock_config.get_constraints.assert_called()


class TestOptimizationLoopSeedManagement:
    """Tests for RNG seed management."""

    def test_loop_uses_master_seed_from_config(self) -> None:
        """OptimizationLoop uses master_seed from config for determinism."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 12345

        loop = OptimizationLoop(config=mock_config)

        assert loop.master_seed == 12345


class TestOptimizationIterationRecord:
    """Tests for IterationData tracking."""

    def test_loop_has_current_iteration_property(self) -> None:
        """OptimizationLoop tracks current iteration."""
        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.master_seed = 42

        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "current_iteration")
        assert loop.current_iteration == 0  # Initially 0


class TestBackwardCompatibility:
    """Tests for Castro backward compatibility (skipped in API env)."""

    @pytest.mark.skip(reason="Castro not available in API test environment")
    def test_castro_can_use_core_optimization_loop(self) -> None:
        """Castro can import and use OptimizationLoop from core."""
        pass
