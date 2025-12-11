"""Tests for unified display functions.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from typing import Any

import pytest
from rich.console import Console


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestDisplayExperimentOutput:
    """Test display_experiment_output function."""

    def test_display_with_live_provider(self) -> None:
        """display_experiment_output works with LiveExperimentProvider."""
        from castro.display import display_experiment_output
        from castro.events import (
            create_experiment_end_event,
            create_experiment_start_event,
            create_iteration_start_event,
        )
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test experiment",
            model="anthropic:claude-sonnet-4-5",
            max_iterations=25,
            num_samples=5,
        )

        # Add some events
        provider.capture_event(create_experiment_start_event(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test experiment",
            model="anthropic:claude-sonnet-4-5",
            max_iterations=25,
            num_samples=5,
        ))
        provider.capture_event(create_iteration_start_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            total_cost=15000,
        ))
        provider.capture_event(create_experiment_end_event(
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            final_cost=12000,
            best_cost=12000,
            converged=True,
            convergence_reason="stability_reached",
            duration_seconds=10.5,
        ))

        provider.set_final_result(
            final_cost=12000,
            best_cost=12000,
            converged=True,
            convergence_reason="stability_reached",
            num_iterations=1,
            duration_seconds=10.5,
        )

        # Capture output
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_experiment_output(provider, console)

        text = strip_ansi(output.getvalue())

        # Should contain run ID
        assert "exp1-20251209-143022-a1b2c3" in text
        # Should contain experiment name
        assert "exp1" in text

    def test_display_with_database_provider(self) -> None:
        """display_experiment_output works with DatabaseExperimentProvider."""
        import duckdb

        from castro.display import display_experiment_output
        from castro.events import ExperimentEvent
        from castro.persistence import ExperimentEventRepository, ExperimentRunRecord
        from castro.state_provider import DatabaseExperimentProvider

        # Set up database with test data
        conn = duckdb.connect(":memory:")
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        # Save run record
        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 14, 30, 22),
            status="completed",
            final_cost=12000,
            best_cost=12000,
            num_iterations=1,
            converged=True,
            convergence_reason="stability_reached",
            model="anthropic:claude-sonnet-4-5",
        )
        repo.save_run_record(record)

        # Save events
        events = [
            ExperimentEvent(
                event_type="experiment_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=0,
                timestamp=datetime(2025, 12, 9, 14, 30, 22),
                details={
                    "experiment_name": "exp1",
                    "description": "Test experiment",
                    "model": "anthropic:claude-sonnet-4-5",
                    "max_iterations": 25,
                    "num_samples": 5,
                },
            ),
            ExperimentEvent(
                event_type="iteration_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=1,
                timestamp=datetime(2025, 12, 9, 14, 30, 23),
                details={"total_cost": 15000},
            ),
        ]
        for event in events:
            repo.save_event(event)

        # Create provider
        provider = DatabaseExperimentProvider(conn=conn, run_id="exp1-20251209-143022-a1b2c3")

        # Capture output
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_experiment_output(provider, console)

        text = strip_ansi(output.getvalue())

        # Should contain run ID
        assert "exp1-20251209-143022-a1b2c3" in text


class TestDisplayEventHandlers:
    """Test individual event display handlers."""

    def test_display_iteration_start_event(self) -> None:
        """display_iteration_start formats correctly."""
        from castro.display import display_iteration_start
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={"total_cost": 15000},
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_iteration_start(event, console)

        text = strip_ansi(output.getvalue())
        assert "Iteration 1" in text
        assert "$150.00" in text  # 15000 cents = $150.00

    def test_display_bootstrap_evaluation_event(self) -> None:
        """display_bootstrap_evaluation formats correctly."""
        from castro.display import display_bootstrap_evaluation
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="bootstrap_evaluation",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={
                "seed_results": [
                    {"seed": 42, "cost": 15000, "settled": 10, "total": 10, "settlement_rate": 1.0},
                    {"seed": 43, "cost": 16000, "settled": 9, "total": 10, "settlement_rate": 0.9},
                ],
                "mean_cost": 15500,
                "std_cost": 500,
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_bootstrap_evaluation(event, console)

        text = strip_ansi(output.getvalue())
        assert "Bootstrap" in text
        # Should show mean cost
        assert "$155.00" in text or "15500" in text

    def test_display_llm_call_event(self) -> None:
        """display_llm_call formats correctly."""
        from castro.display import display_llm_call
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="llm_call",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={
                "agent_id": "BANK_A",
                "model": "openai:gpt-5.1",
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "latency_seconds": 2.5,
                "context_summary": {"current_cost": 7500},
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_llm_call(event, console)

        text = strip_ansi(output.getvalue())
        assert "LLM" in text or "BANK_A" in text
        assert "gpt-5.1" in text or "openai" in text

    def test_display_policy_change_event(self) -> None:
        """display_policy_change formats correctly."""
        from castro.display import display_policy_change
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="policy_change",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={
                "agent_id": "BANK_A",
                "old_policy": {"parameters": {"threshold": 3.0}},
                "new_policy": {"parameters": {"threshold": 2.0}},
                "old_cost": 8000,
                "new_cost": 7000,
                "accepted": True,
            },
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        display_policy_change(event, console)

        text = strip_ansi(output.getvalue())
        assert "BANK_A" in text
        # Should show cost change
        assert "$80.00" in text or "$70.00" in text or "8000" in text


class TestVerboseConfig:
    """Test VerboseConfig for controlling display."""

    def test_verbose_config_all_disabled(self) -> None:
        """VerboseConfig with all disabled."""
        from castro.display import VerboseConfig

        config = VerboseConfig()

        assert config.iterations is False
        assert config.bootstrap is False
        assert config.llm is False
        assert config.policy is False

    def test_verbose_config_all_enabled(self) -> None:
        """VerboseConfig with all enabled."""
        from castro.display import VerboseConfig

        config = VerboseConfig.all_enabled()

        assert config.iterations is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is True

    def test_verbose_config_from_flags(self) -> None:
        """VerboseConfig.from_flags creates config from CLI flags."""
        from castro.display import VerboseConfig

        # --verbose enables all
        config = VerboseConfig.from_flags(verbose=True)
        assert config.iterations is True
        assert config.bootstrap is True

        # Individual flags
        config = VerboseConfig.from_flags(
            verbose=False,
            verbose_bootstrap=True,
        )
        assert config.bootstrap is True
        assert config.iterations is False
