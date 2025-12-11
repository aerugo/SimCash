"""Integration tests for verbose logging in experiment framework.

TDD tests for wiring up VerboseConfig/VerboseLogger to OptimizationLoop.
These tests MUST FAIL before implementation (RED phase).

The problem: VerboseConfig is passed to GenericExperimentRunner but never used.
When users run experiments with --verbose, they see no output.

Solution: Wire up verbose logging so OptimizationLoop produces output.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner import (
    OptimizationLoop,
    VerboseConfig,
    VerboseLogger,
)
from payment_simulator.experiments.runner.experiment_runner import (
    GenericExperimentRunner,
)
from payment_simulator.llm import LLMConfig


def _create_mock_experiment_config(
    max_iterations: int = 2,
    evaluation_mode: str = "deterministic",
    num_samples: int = 1,
    ticks: int = 2,
    system_prompt: str | None = None,
) -> MagicMock:
    """Create a mock ExperimentConfig for testing.

    Args:
        max_iterations: Maximum optimization iterations.
        evaluation_mode: "deterministic" or "bootstrap".
        num_samples: Number of bootstrap samples.
        ticks: Number of ticks per simulation.
        system_prompt: Optional system prompt for LLM.

    Returns:
        Mock ExperimentConfig.
    """
    mock_config = MagicMock(spec=ExperimentConfig)

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = evaluation_mode
    mock_config.evaluation.num_samples = num_samples
    mock_config.evaluation.ticks = ticks

    # Other required fields
    mock_config.optimized_agents = ("BANK_A",)
    mock_config.get_constraints.return_value = None
    mock_config.llm = LLMConfig(
        model="anthropic:claude-sonnet-4-5",
        system_prompt=system_prompt,
    )
    mock_config.master_seed = 42
    mock_config.name = "test_experiment"
    mock_config.scenario_path = Path("test_scenario.yaml")

    return mock_config


class TestOptimizationLoopVerboseLoggerCreation:
    """Task 1: VerboseLogger receives events from OptimizationLoop."""

    def test_optimization_loop_accepts_verbose_config_parameter(self) -> None:
        """OptimizationLoop.__init__ accepts verbose_config parameter."""
        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig.all_enabled()

        # This should not raise - loop accepts verbose_config
        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        assert loop is not None

    def test_optimization_loop_creates_verbose_logger_when_enabled(self) -> None:
        """OptimizationLoop creates VerboseLogger when VerboseConfig has any flag enabled."""
        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig.all_enabled()

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        # Loop should have created a VerboseLogger
        assert loop._verbose_logger is not None
        assert isinstance(loop._verbose_logger, VerboseLogger)

    def test_optimization_loop_no_logger_when_disabled(self) -> None:
        """OptimizationLoop does not create VerboseLogger when all flags disabled."""
        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig()  # All disabled

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        # No logger when verbose is disabled
        assert loop._verbose_logger is None

    def test_optimization_loop_stores_verbose_config(self) -> None:
        """OptimizationLoop stores verbose_config for later use."""
        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig(iterations=True, bootstrap=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        # Should store the config
        assert loop._verbose_config is not None
        assert loop._verbose_config.iterations is True
        assert loop._verbose_config.bootstrap is True


class TestIterationLogging:
    """Task 2: Iteration start/end logging."""

    @pytest.mark.asyncio
    async def test_logs_iteration_start(self, capsys: pytest.CaptureFixture) -> None:
        """OptimizationLoop logs iteration start when verbose_iterations enabled."""
        config = _create_mock_experiment_config(max_iterations=2)
        verbose_config = VerboseConfig(iterations=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        # Mock _run_single_simulation to avoid needing real scenario
        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})  # cost in cents

            await loop.run()

        captured = capsys.readouterr()
        # Should log iteration numbers
        assert "Iteration 1" in captured.out
        assert "Iteration 2" in captured.out

    @pytest.mark.asyncio
    async def test_logs_iteration_costs(self, capsys: pytest.CaptureFixture) -> None:
        """OptimizationLoop logs costs after each iteration."""
        config = _create_mock_experiment_config(max_iterations=1)
        verbose_config = VerboseConfig(iterations=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})

            await loop.run()

        captured = capsys.readouterr()
        # Should show cost in dollars (10000 cents = $100.00)
        assert "$" in captured.out or "cost" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_no_logs_when_iterations_disabled(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """No iteration logs when iterations flag is disabled."""
        config = _create_mock_experiment_config(max_iterations=1)
        verbose_config = VerboseConfig(iterations=False)  # Disabled

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})

            await loop.run()

        captured = capsys.readouterr()
        # Should NOT mention iterations
        assert "Iteration" not in captured.out


class TestBootstrapLogging:
    """Task 3: Bootstrap sample logging."""

    @pytest.mark.asyncio
    async def test_logs_bootstrap_samples(self, capsys: pytest.CaptureFixture) -> None:
        """OptimizationLoop logs bootstrap sample results when verbose_bootstrap enabled."""
        config = _create_mock_experiment_config(
            evaluation_mode="bootstrap",
            num_samples=3,
            max_iterations=1,
        )
        verbose_config = VerboseConfig(bootstrap=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        with patch.object(loop, "_run_single_simulation") as mock_run:
            # Return different costs for each sample
            mock_run.side_effect = [
                (10000, {"BANK_A": 10000}),
                (11000, {"BANK_A": 11000}),
                (9000, {"BANK_A": 9000}),
            ]

            await loop.run()

        captured = capsys.readouterr()
        # Should mention samples or bootstrap
        assert "Sample" in captured.out or "sample" in captured.out or "Bootstrap" in captured.out

    @pytest.mark.asyncio
    async def test_no_bootstrap_logs_in_deterministic_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """No bootstrap logs in deterministic mode even if flag enabled."""
        config = _create_mock_experiment_config(
            evaluation_mode="deterministic",
            max_iterations=1,
        )
        verbose_config = VerboseConfig(bootstrap=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
        )

        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})

            await loop.run()

        captured = capsys.readouterr()
        # Should not mention sample numbers in deterministic mode
        assert "Sample 1" not in captured.out
        assert "Sample 2" not in captured.out


class TestLLMCallLogging:
    """Task 4: LLM call logging."""

    @pytest.mark.asyncio
    async def test_logs_llm_calls(self) -> None:
        """OptimizationLoop logs LLM interactions when verbose_llm enabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        # Use max_iterations=2 so the loop runs optimization at least once
        # (with max_iterations=1, convergence triggers before optimization)
        config = _create_mock_experiment_config(
            max_iterations=2,
            system_prompt="You are an optimizer.",
        )
        verbose_config = VerboseConfig(llm=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
            console=console,
        )

        # Mock simulation and LLM client
        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})

            # Make generate_policy async
            async def mock_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
                return {"version": "2.0", "parameters": {}}

            mock_llm_client = MagicMock()
            mock_llm_client.generate_policy = mock_generate

            # Inject mock LLM client
            loop._llm_client = mock_llm_client

            await loop.run()

        result = output.getvalue()
        # Should log LLM or policy-related info
        assert "LLM" in result or "model" in result.lower() or "BANK_A" in result


class TestRejectionLogging:
    """Task 5: Policy acceptance/rejection logging."""

    @pytest.mark.asyncio
    async def test_logs_policy_rejections(self) -> None:
        """OptimizationLoop logs when policy is rejected."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        # Use max_iterations=2 so the loop runs optimization at least once
        # (with max_iterations=1, convergence triggers before optimization)
        config = _create_mock_experiment_config(
            max_iterations=2,
            system_prompt="You are an optimizer.",
        )
        verbose_config = VerboseConfig(rejections=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
            console=console,
        )

        with patch.object(loop, "_run_single_simulation") as mock_run:
            mock_run.return_value = (10000, {"BANK_A": 10000})

            # Mock LLM client to return a policy
            async def mock_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
                return {"version": "2.0", "parameters": {"threshold": -1}}

            mock_llm_client = MagicMock()
            mock_llm_client.generate_policy = mock_generate
            loop._llm_client = mock_llm_client

            # Set up constraints to trigger validation
            from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints

            mock_constraints = MagicMock(spec=ScenarioConstraints)
            loop._constraints = mock_constraints

            # Mock the ConstraintValidator class at import location
            with patch(
                "payment_simulator.ai_cash_mgmt.optimization.constraint_validator.ConstraintValidator"
            ) as mock_validator_cls:
                mock_result = MagicMock()
                mock_result.is_valid = False
                mock_result.violations = ["threshold must be positive"]
                mock_validator = MagicMock()
                mock_validator.validate.return_value = mock_result
                mock_validator_cls.return_value = mock_validator

                await loop.run()

        result = output.getvalue()
        # Should log rejection info
        assert (
            "Reject" in result
            or "BANK_A" in result
            or "violation" in result.lower()
        )


class TestGenericExperimentRunnerPassesVerboseConfig:
    """Task 6: GenericExperimentRunner passes verbose_config to OptimizationLoop."""

    def test_runner_stores_verbose_config(self) -> None:
        """GenericExperimentRunner stores verbose_config."""
        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig.all_enabled()

        runner = GenericExperimentRunner(
            config=config,
            verbose_config=verbose_config,
            config_dir=Path("."),
        )

        # Runner should store verbose_config
        assert runner._verbose_config == verbose_config

    @pytest.mark.asyncio
    async def test_runner_passes_verbose_config_to_loop(self) -> None:
        """GenericExperimentRunner passes verbose_config to OptimizationLoop."""
        config = _create_mock_experiment_config(max_iterations=1)
        verbose_config = VerboseConfig.all_enabled()

        runner = GenericExperimentRunner(
            config=config,
            verbose_config=verbose_config,
            config_dir=Path("."),
        )

        # Mock OptimizationLoop to capture what's passed
        # The import is inside the run() method, so we patch the module where it's imported
        with patch(
            "payment_simulator.experiments.runner.optimization.OptimizationLoop"
        ) as mock_loop_cls:
            mock_loop = MagicMock()

            # Make run async
            async def mock_run() -> Any:
                return MagicMock(
                    num_iterations=1,
                    converged=True,
                    convergence_reason="max_iterations",
                    per_agent_costs={"BANK_A": 10000},
                )

            mock_loop.run = mock_run
            mock_loop_cls.return_value = mock_loop

            await runner.run()

            # Check that OptimizationLoop was called with verbose_config
            mock_loop_cls.assert_called_once()
            call_kwargs = mock_loop_cls.call_args.kwargs
            assert "verbose_config" in call_kwargs
            assert call_kwargs["verbose_config"] == verbose_config


class TestVerboseLoggerIntegration:
    """Additional integration tests for VerboseLogger."""

    def test_verbose_logger_uses_custom_console(self) -> None:
        """VerboseLogger can use a custom console for testing."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        verbose_config = VerboseConfig(iterations=True)
        logger = VerboseLogger(verbose_config, console=console)

        logger.log_iteration_start(1, 10000)

        result = output.getvalue()
        assert "Iteration 1" in result
        assert "$100.00" in result

    def test_optimization_loop_can_use_custom_console(self) -> None:
        """OptimizationLoop can be configured with custom console for logger."""
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        config = _create_mock_experiment_config()
        verbose_config = VerboseConfig(iterations=True)

        loop = OptimizationLoop(
            config=config,
            config_dir=Path("."),
            verbose_config=verbose_config,
            console=console,  # Custom console for testing
        )

        # If verbose_logger was created, it should use the custom console
        if loop._verbose_logger is not None:
            loop._verbose_logger.log_iteration_start(1, 10000)
            result = output.getvalue()
            assert "Iteration 1" in result
