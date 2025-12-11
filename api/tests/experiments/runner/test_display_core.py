"""Tests for core experiment display functions.

Task 14.2: TDD tests for display_experiment_output and related functions.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

import pytest
from io import StringIO
from rich.console import Console


class TestDisplayImport:
    """Tests for display function importability."""

    def test_import_from_experiments_runner(self) -> None:
        """display_experiment_output importable from experiments.runner."""
        from payment_simulator.experiments.runner import display_experiment_output
        assert display_experiment_output is not None

    def test_import_from_display_module(self) -> None:
        """display_experiment_output importable from display module."""
        from payment_simulator.experiments.runner.display import display_experiment_output
        assert display_experiment_output is not None


class TestDisplayExperimentOutput:
    """Tests for display_experiment_output function."""

    def test_displays_header_with_run_id(self) -> None:
        """Display includes run ID in header."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_output(provider, console)

        assert "exp1-123" in output.getvalue()

    def test_displays_experiment_name(self) -> None:
        """Display includes experiment name in header."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="my_experiment",
            experiment_type="castro",
            config={},
            run_id="run-123",
        )
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_output(provider, console)

        assert "my_experiment" in output.getvalue()

    def test_displays_final_results(self) -> None:
        """Display shows final results from provider."""
        from payment_simulator.experiments.runner import (
            LiveStateProvider,
            display_experiment_output,
        )

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        provider.set_final_result(
            final_cost=15000,
            best_cost=14000,
            converged=True,
            convergence_reason="stability",
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_output(provider, console)

        result = output.getvalue()
        assert "Complete" in result or "Final" in result


class TestEventDisplayFunctions:
    """Tests for individual event display functions."""

    def test_display_iteration_start(self) -> None:
        """display_iteration_start shows iteration info."""
        from payment_simulator.experiments.runner.display import display_iteration_start

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_iteration_start(
            {"iteration": 5, "total_cost": 25000},
            console,
        )

        result = output.getvalue()
        assert "5" in result
        assert "$250.00" in result

    def test_display_policy_change(self) -> None:
        """display_policy_change shows policy comparison."""
        from payment_simulator.experiments.runner.display import display_policy_change

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_policy_change(
            {
                "agent_id": "BANK_A",
                "old_cost": 10000,
                "new_cost": 8000,
                "accepted": True,
                "old_policy": {"parameters": {"threshold": 3}},
                "new_policy": {"parameters": {"threshold": 2}},
            },
            console,
        )

        result = output.getvalue()
        assert "BANK_A" in result
        assert "$100.00" in result  # old_cost
        assert "$80.00" in result   # new_cost


class TestFormatCost:
    """Tests for cost formatting helper."""

    def test_format_cost_integer_cents(self) -> None:
        """_format_cost formats integer cents correctly."""
        from payment_simulator.experiments.runner.display import _format_cost

        assert _format_cost(10000) == "$100.00"
        assert _format_cost(12345) == "$123.45"
        assert _format_cost(0) == "$0.00"

    def test_format_cost_large_amounts(self) -> None:
        """_format_cost handles large amounts with commas."""
        from payment_simulator.experiments.runner.display import _format_cost

        assert _format_cost(100000000) == "$1,000,000.00"


class TestDisplayExperimentStart:
    """Tests for display_experiment_start function."""

    def test_display_experiment_start_shows_name(self) -> None:
        """display_experiment_start shows experiment name."""
        from payment_simulator.experiments.runner.display import display_experiment_start

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_start(
            {"experiment_name": "my_exp", "description": "Test experiment"},
            console,
        )

        result = output.getvalue()
        assert "my_exp" in result


class TestDisplayBootstrapEvaluation:
    """Tests for display_bootstrap_evaluation function."""

    def test_display_bootstrap_evaluation_shows_samples(self) -> None:
        """display_bootstrap_evaluation shows sample count."""
        from payment_simulator.experiments.runner.display import display_bootstrap_evaluation

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_bootstrap_evaluation(
            {
                "seed_results": [
                    {"seed": 12345, "cost": 10000, "settled": 80, "total": 100, "settlement_rate": 0.8},
                    {"seed": 67890, "cost": 12000, "settled": 70, "total": 100, "settlement_rate": 0.7},
                ],
                "mean_cost": 11000,
                "std_cost": 1000,
            },
            console,
        )

        result = output.getvalue()
        assert "2 samples" in result


class TestDisplayLLMCall:
    """Tests for display_llm_call function."""

    def test_display_llm_call_shows_model(self) -> None:
        """display_llm_call shows model name."""
        from payment_simulator.experiments.runner.display import display_llm_call

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_llm_call(
            {
                "agent_id": "BANK_A",
                "model": "anthropic:claude-sonnet-4-5",
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "latency_seconds": 2.5,
            },
            console,
        )

        result = output.getvalue()
        assert "anthropic:claude-sonnet-4-5" in result
        assert "BANK_A" in result
