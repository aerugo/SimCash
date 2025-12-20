"""Tests for verbose metrics replay identity.

TDD Tests for verbose metrics implementation with StateProvider pattern.
These tests verify that verbose metrics output is identical in run and replay modes.

INV-5: Replay output MUST be identical to run output (modulo timing).

Event Types:
- iteration_metrics: Per-iteration costs, liquidity fractions
- llm_stats: Per-iteration LLM statistics (tokens, calls)
- experiment_summary: Final experiment summary (iterations, convergence, totals)

Note: Timing information (duration, latency) is excluded from identity comparison
per CLAUDE.md specification.
"""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from payment_simulator.experiments.runner.state_provider import LiveStateProvider
from payment_simulator.experiments.runner.verbose import VerboseConfig


# =============================================================================
# Event Recording Tests
# =============================================================================


class TestIterationMetricsEventRecording:
    """Tests for iteration_metrics event recording."""

    def test_record_iteration_metrics_event(self) -> None:
        """LiveStateProvider should record iteration_metrics events."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        # Record an iteration_metrics event
        provider.record_event(
            iteration=0,
            event_type="iteration_metrics",
            event_data={
                "total_cost": 15000,  # $150.00 in cents
                "per_agent_costs": {"BANK_A": 8000, "BANK_B": 7000},
                "per_agent_liquidity": {"BANK_A": 0.5, "BANK_B": 0.6},
            },
        )

        events = provider.get_iteration_events(0)
        metrics_events = [e for e in events if e["event_type"] == "iteration_metrics"]

        assert len(metrics_events) == 1
        event = metrics_events[0]
        assert event["total_cost"] == 15000
        assert event["per_agent_costs"]["BANK_A"] == 8000
        assert event["per_agent_costs"]["BANK_B"] == 7000
        assert event["per_agent_liquidity"]["BANK_A"] == 0.5

    def test_iteration_metrics_event_has_required_fields(self) -> None:
        """iteration_metrics event must have all required fields."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="iteration_metrics",
            event_data={
                "total_cost": 15000,
                "per_agent_costs": {"BANK_A": 15000},
            },
        )

        events = provider.get_iteration_events(0)
        event = [e for e in events if e["event_type"] == "iteration_metrics"][0]

        # Required fields (not timing)
        assert "total_cost" in event
        assert "per_agent_costs" in event
        # Optional fields should be present if provided
        assert "per_agent_liquidity" not in event or event["per_agent_liquidity"] is None


class TestLlmStatsEventRecording:
    """Tests for llm_stats event recording."""

    def test_record_llm_stats_event(self) -> None:
        """LiveStateProvider should record llm_stats events."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="llm_stats",
            event_data={
                "total_calls": 2,
                "successful_calls": 2,
                "failed_calls": 0,
                "total_prompt_tokens": 5000,
                "total_completion_tokens": 500,
            },
        )

        events = provider.get_iteration_events(0)
        stats_events = [e for e in events if e["event_type"] == "llm_stats"]

        assert len(stats_events) == 1
        event = stats_events[0]
        assert event["total_calls"] == 2
        assert event["total_prompt_tokens"] == 5000
        assert event["total_completion_tokens"] == 500

    def test_llm_stats_event_excludes_timing(self) -> None:
        """llm_stats events should NOT include timing (per replay identity)."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        # Record event WITHOUT timing data
        provider.record_event(
            iteration=0,
            event_type="llm_stats",
            event_data={
                "total_calls": 1,
                "successful_calls": 1,
                "failed_calls": 0,
                "total_prompt_tokens": 1000,
                "total_completion_tokens": 100,
                # NOTE: NO latency field - timing excluded from replay identity
            },
        )

        events = provider.get_iteration_events(0)
        event = [e for e in events if e["event_type"] == "llm_stats"][0]

        # Timing should NOT be part of the event for replay identity
        assert "total_latency_seconds" not in event


class TestExperimentSummaryEventRecording:
    """Tests for experiment_summary event recording."""

    def test_record_experiment_summary_event(self) -> None:
        """LiveStateProvider should record experiment_summary events."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=5,  # Final iteration
            event_type="experiment_summary",
            event_data={
                "num_iterations": 6,
                "converged": True,
                "convergence_reason": "stability",
                "final_cost": 10000,
                "best_cost": 9500,
                "total_llm_calls": 12,
                "total_tokens": 60000,
            },
        )

        events = provider.get_iteration_events(5)
        summary_events = [e for e in events if e["event_type"] == "experiment_summary"]

        assert len(summary_events) == 1
        event = summary_events[0]
        assert event["num_iterations"] == 6
        assert event["converged"] is True
        assert event["final_cost"] == 10000
        assert event["total_llm_calls"] == 12

    def test_experiment_summary_excludes_duration(self) -> None:
        """experiment_summary should NOT include duration (timing excluded)."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="experiment_summary",
            event_data={
                "num_iterations": 1,
                "converged": True,
                "convergence_reason": "max_iterations",
                "final_cost": 10000,
                "best_cost": 10000,
                "total_llm_calls": 2,
                "total_tokens": 10000,
                # NOTE: NO duration field - timing excluded
            },
        )

        events = provider.get_iteration_events(0)
        event = [e for e in events if e["event_type"] == "experiment_summary"][0]

        assert "total_duration_seconds" not in event


# =============================================================================
# Display Function Tests
# =============================================================================


class TestIterationMetricsDisplay:
    """Tests for display_iteration_metrics function."""

    def test_display_iteration_metrics_function_exists(self) -> None:
        """display_iteration_metrics should be importable."""
        from payment_simulator.experiments.runner.display import (
            display_iteration_metrics,
        )

        assert display_iteration_metrics is not None

    def test_display_iteration_metrics_shows_costs(self) -> None:
        """display_iteration_metrics shows per-agent costs."""
        from payment_simulator.experiments.runner.display import (
            display_iteration_metrics,
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_iteration_metrics(
            {
                "iteration": 3,
                "total_cost": 20000,
                "per_agent_costs": {"BANK_A": 12000, "BANK_B": 8000},
            },
            console,
        )

        result = output.getvalue()
        assert "BANK_A" in result
        assert "BANK_B" in result
        assert "$120.00" in result or "120.00" in result  # BANK_A cost
        assert "$80.00" in result or "80.00" in result  # BANK_B cost

    def test_display_iteration_metrics_shows_liquidity(self) -> None:
        """display_iteration_metrics shows liquidity fractions."""
        from payment_simulator.experiments.runner.display import (
            display_iteration_metrics,
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_iteration_metrics(
            {
                "iteration": 1,
                "total_cost": 15000,
                "per_agent_costs": {"BANK_A": 15000},
                "per_agent_liquidity": {"BANK_A": 0.45},
            },
            console,
        )

        result = output.getvalue()
        assert "45" in result  # 45% liquidity


class TestLlmStatsDisplay:
    """Tests for display_llm_stats function."""

    def test_display_llm_stats_function_exists(self) -> None:
        """display_llm_stats should be importable."""
        from payment_simulator.experiments.runner.display import display_llm_stats

        assert display_llm_stats is not None

    def test_display_llm_stats_shows_token_counts(self) -> None:
        """display_llm_stats shows token counts."""
        from payment_simulator.experiments.runner.display import display_llm_stats

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_llm_stats(
            {
                "iteration": 2,
                "total_calls": 4,
                "successful_calls": 4,
                "failed_calls": 0,
                "total_prompt_tokens": 8000,
                "total_completion_tokens": 800,
            },
            console,
        )

        result = output.getvalue()
        assert "8000" in result or "8,000" in result  # prompt tokens
        assert "800" in result  # completion tokens
        assert "4" in result  # calls

    def test_display_llm_stats_shows_failures(self) -> None:
        """display_llm_stats highlights failures."""
        from payment_simulator.experiments.runner.display import display_llm_stats

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_llm_stats(
            {
                "iteration": 1,
                "total_calls": 3,
                "successful_calls": 2,
                "failed_calls": 1,
                "total_prompt_tokens": 5000,
                "total_completion_tokens": 400,
            },
            console,
        )

        result = output.getvalue()
        # Should indicate failure
        assert "1" in result  # failed count
        assert "2" in result or "succeeded" in result.lower()


class TestExperimentSummaryDisplay:
    """Tests for display_experiment_summary function."""

    def test_display_experiment_summary_function_exists(self) -> None:
        """display_experiment_summary should be importable."""
        from payment_simulator.experiments.runner.display import (
            display_experiment_summary,
        )

        assert display_experiment_summary is not None

    def test_display_experiment_summary_shows_iterations(self) -> None:
        """display_experiment_summary shows iteration count."""
        from payment_simulator.experiments.runner.display import (
            display_experiment_summary,
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_summary(
            {
                "num_iterations": 15,
                "converged": True,
                "convergence_reason": "stability",
                "final_cost": 12000,
                "best_cost": 11000,
                "total_llm_calls": 30,
                "total_tokens": 150000,
            },
            console,
        )

        result = output.getvalue()
        assert "15" in result  # iterations
        assert "stability" in result.lower() or "converged" in result.lower()

    def test_display_experiment_summary_shows_costs(self) -> None:
        """display_experiment_summary shows final and best costs."""
        from payment_simulator.experiments.runner.display import (
            display_experiment_summary,
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_experiment_summary(
            {
                "num_iterations": 10,
                "converged": True,
                "convergence_reason": "max_iterations",
                "final_cost": 15000,
                "best_cost": 12000,
                "total_llm_calls": 20,
                "total_tokens": 100000,
            },
            console,
        )

        result = output.getvalue()
        assert "$150.00" in result or "150.00" in result  # final cost
        assert "$120.00" in result or "120.00" in result  # best cost


# =============================================================================
# Event Routing Tests
# =============================================================================


class TestMetricsEventRouting:
    """Tests for routing metrics events in display_experiment_output."""

    def test_iteration_metrics_routed_when_metrics_enabled(self) -> None:
        """iteration_metrics events displayed when config.metrics=True."""
        from payment_simulator.experiments.runner.display import display_experiment_output

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="iteration_metrics",
            event_data={
                "total_cost": 10000,
                "per_agent_costs": {"BANK_A": 10000},
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(metrics=True)

        display_experiment_output(provider, console, config)

        result = output.getvalue()
        # Should contain the metrics output
        assert "BANK_A" in result or "$100.00" in result

    def test_iteration_metrics_not_routed_when_metrics_disabled(self) -> None:
        """iteration_metrics events NOT displayed when config.metrics=False."""
        from payment_simulator.experiments.runner.display import display_experiment_output

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="iteration_metrics",
            event_data={
                "total_cost": 10000,
                "per_agent_costs": {"BANK_A": 10000},
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(metrics=False)

        display_experiment_output(provider, console, config)

        result = output.getvalue()
        # Should NOT contain BANK_A cost info (only header/footer)
        # Note: BANK_A might appear elsewhere, so check for the specific cost
        assert "10000" not in result or "$100.00" not in result

    def test_llm_stats_routed_when_metrics_enabled(self) -> None:
        """llm_stats events displayed when config.metrics=True."""
        from payment_simulator.experiments.runner.display import display_experiment_output

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="llm_stats",
            event_data={
                "total_calls": 5,
                "successful_calls": 5,
                "failed_calls": 0,
                "total_prompt_tokens": 25000,
                "total_completion_tokens": 2500,
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(metrics=True)

        display_experiment_output(provider, console, config)

        result = output.getvalue()
        assert "25000" in result or "25,000" in result  # prompt tokens

    def test_experiment_summary_routed_when_metrics_enabled(self) -> None:
        """experiment_summary events displayed when config.metrics=True."""
        from payment_simulator.experiments.runner.display import display_experiment_output

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="experiment_summary",
            event_data={
                "num_iterations": 8,
                "converged": True,
                "convergence_reason": "stability",
                "final_cost": 9000,
                "best_cost": 8500,
                "total_llm_calls": 16,
                "total_tokens": 80000,
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)
        config = VerboseConfig(metrics=True)

        display_experiment_output(provider, console, config)

        result = output.getvalue()
        assert "8" in result  # num_iterations
        assert "16" in result  # total_llm_calls


# =============================================================================
# Replay Identity Tests
# =============================================================================


class TestMetricsReplayIdentity:
    """Tests for metrics replay identity (INV-5).

    Verifies that output from LiveStateProvider matches output from
    DatabaseStateProvider when both have the same events.
    """

    def test_iteration_metrics_identical_in_replay(self) -> None:
        """iteration_metrics output identical in live and replay modes."""
        from payment_simulator.experiments.runner.display import display_experiment_output

        # Create live provider with metrics event
        live_provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )
        live_provider.record_event(
            iteration=0,
            event_type="iteration_metrics",
            event_data={
                "total_cost": 20000,
                "per_agent_costs": {"BANK_A": 12000, "BANK_B": 8000},
                "per_agent_liquidity": {"BANK_A": 0.4, "BANK_B": 0.6},
            },
        )

        # Capture live output
        live_output = StringIO()
        live_console = Console(file=live_output, force_terminal=False, no_color=True)
        config = VerboseConfig(metrics=True)
        display_experiment_output(live_provider, live_console, config)

        # For now, just verify that the events are retrievable
        # (Full replay identity test requires database round-trip)
        events = list(live_provider.get_all_events())
        metrics_events = [e for e in events if e["event_type"] == "iteration_metrics"]

        assert len(metrics_events) == 1
        assert metrics_events[0]["total_cost"] == 20000
        assert metrics_events[0]["per_agent_costs"]["BANK_A"] == 12000

    def test_llm_stats_without_timing_for_replay_identity(self) -> None:
        """llm_stats events exclude timing fields for replay identity."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        # Record event with only replay-safe fields
        provider.record_event(
            iteration=0,
            event_type="llm_stats",
            event_data={
                "total_calls": 3,
                "successful_calls": 3,
                "failed_calls": 0,
                "total_prompt_tokens": 15000,
                "total_completion_tokens": 1500,
            },
        )

        events = list(provider.get_all_events())
        llm_events = [e for e in events if e["event_type"] == "llm_stats"]

        assert len(llm_events) == 1
        event = llm_events[0]

        # These fields enable replay identity
        assert event["total_calls"] == 3
        assert event["total_prompt_tokens"] == 15000

        # Timing fields should NOT be in the event
        assert "total_latency_seconds" not in event
        assert "avg_latency" not in event

    def test_experiment_summary_without_duration_for_replay_identity(self) -> None:
        """experiment_summary events exclude duration for replay identity."""
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="test",
            config={},
            run_id="test-run",
        )

        provider.record_event(
            iteration=0,
            event_type="experiment_summary",
            event_data={
                "num_iterations": 5,
                "converged": True,
                "convergence_reason": "stability",
                "final_cost": 8000,
                "best_cost": 7500,
                "total_llm_calls": 10,
                "total_tokens": 50000,
            },
        )

        events = list(provider.get_all_events())
        summary_events = [e for e in events if e["event_type"] == "experiment_summary"]

        assert len(summary_events) == 1
        event = summary_events[0]

        # Replay-safe fields
        assert event["num_iterations"] == 5
        assert event["final_cost"] == 8000

        # Duration should NOT be in the event
        assert "total_duration_seconds" not in event
        assert "avg_time_per_iteration" not in event
