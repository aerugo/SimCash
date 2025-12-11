"""Integration tests for replay audit functionality.

Tests the full flow from CLI to database to display.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import duckdb
import pytest
from rich.console import Console
from typer.testing import CliRunner

from payment_simulator.ai_cash_mgmt.events import (
    EVENT_BOOTSTRAP_EVALUATION,
    EVENT_LLM_INTERACTION,
    EVENT_POLICY_CHANGE,
    EVENT_POLICY_REJECTED,
    create_llm_interaction_event,
)

from castro.event_compat import CastroEvent as ExperimentEvent
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


@pytest.fixture
def runner() -> CliRunner:
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def comprehensive_test_db(tmp_path: Path) -> Path:
    """Create a comprehensive test database with all event types."""
    db_path = tmp_path / "comprehensive_castro.db"
    conn = duckdb.connect(str(db_path))
    repo = ExperimentEventRepository(conn)
    repo.initialize_schema()

    # Create run record
    run_record = ExperimentRunRecord(
        run_id="integration-test-run",
        experiment_name="exp1",
        started_at=datetime(2025, 12, 9, 10, 0, 0),
        status="completed",
        model="anthropic:claude-sonnet-4-5",
        master_seed=42,
        final_cost=8000,
        best_cost=7500,
        num_iterations=3,
        converged=True,
        convergence_reason="stability_reached",
    )
    repo.save_run_record(run_record)

    # Add comprehensive events for each iteration
    for iteration in range(1, 4):
        # For each agent in this iteration
        for agent_id in ["BANK_A", "BANK_B"]:
            # LLM interaction event
            llm_event = create_llm_interaction_event(
                run_id="integration-test-run",
                iteration=iteration,
                agent_id=agent_id,
                system_prompt="You are a payment optimization expert. Your task is to improve bank payment policies.",
                user_prompt=f"""
Current iteration: {iteration}
Agent: {agent_id}
Current cost: ${iteration * 1000}

Please optimize the policy to reduce costs.
                """.strip(),
                raw_response=f'''{{
  "version": "2.0",
  "policy_id": "optimized_{agent_id}_iter{iteration}",
  "parameters": {{
    "initial_liquidity_fraction": 0.{20 + iteration * 5},
    "urgency_threshold": {3.0 - iteration * 0.3:.1f},
    "liquidity_buffer_factor": {1.0 + iteration * 0.1:.1f}
  }}
}}''',
                parsed_policy={
                    "version": "2.0",
                    "policy_id": f"optimized_{agent_id}_iter{iteration}",
                    "parameters": {
                        "initial_liquidity_fraction": 0.20 + iteration * 0.05,
                        "urgency_threshold": 3.0 - iteration * 0.3,
                        "liquidity_buffer_factor": 1.0 + iteration * 0.1,
                    },
                },
                parsing_error=None,
                model="anthropic:claude-sonnet-4-5",
                prompt_tokens=500 + iteration * 100,
                completion_tokens=200 + iteration * 50,
                latency_seconds=1.5 + iteration * 0.2,
            )
            repo.save_event(llm_event)

            # Bootstrap evaluation event
            mc_event = ExperimentEvent(
                event_type=EVENT_BOOTSTRAP_EVALUATION,
                run_id="integration-test-run",
                iteration=iteration,
                timestamp=datetime.now(),
                details={
                    "agent_id": agent_id,
                    "seed_results": [
                        {
                            "seed": 42 + i,
                            "cost": 10000 - iteration * 1000 - i * 100,
                            "settled": 95 + i,
                            "total": 100,
                            "settlement_rate": 0.95 + i * 0.01,
                        }
                        for i in range(5)
                    ],
                    "mean_cost": 10000 - iteration * 1000,
                    "std_cost": 200,
                },
            )
            repo.save_event(mc_event)

            # Policy change event (accepted on even iterations)
            accepted = iteration % 2 == 0
            if accepted:
                policy_event = ExperimentEvent(
                    event_type=EVENT_POLICY_CHANGE,
                    run_id="integration-test-run",
                    iteration=iteration,
                    timestamp=datetime.now(),
                    details={
                        "agent_id": agent_id,
                        "old_policy": {"parameters": {"urgency_threshold": 3.0}},
                        "new_policy": {
                            "parameters": {"urgency_threshold": 3.0 - iteration * 0.3}
                        },
                        "old_cost": 10000,
                        "new_cost": 10000 - iteration * 500,
                        "accepted": True,
                    },
                )
            else:
                policy_event = ExperimentEvent(
                    event_type=EVENT_POLICY_REJECTED,
                    run_id="integration-test-run",
                    iteration=iteration,
                    timestamp=datetime.now(),
                    details={
                        "agent_id": agent_id,
                        "proposed_policy": {"parameters": {"urgency_threshold": -1.0}},
                        "validation_errors": ["urgency_threshold must be non-negative"],
                        "rejection_reason": "validation_failed",
                    },
                )
            repo.save_event(policy_event)

    conn.close()
    return db_path


@pytest.fixture
def db_with_parsing_errors(tmp_path: Path) -> Path:
    """Create a database with LLM interaction that has parsing errors."""
    db_path = tmp_path / "parsing_errors_castro.db"
    conn = duckdb.connect(str(db_path))
    repo = ExperimentEventRepository(conn)
    repo.initialize_schema()

    # Create run record
    run_record = ExperimentRunRecord(
        run_id="parsing-error-run",
        experiment_name="exp1",
        started_at=datetime(2025, 12, 9, 10, 0, 0),
        status="completed",
        model="anthropic:claude-sonnet-4-5",
        master_seed=42,
    )
    repo.save_run_record(run_record)

    # Add LLM interaction with parsing error
    error_event = create_llm_interaction_event(
        run_id="parsing-error-run",
        iteration=1,
        agent_id="BANK_A",
        system_prompt="System prompt",
        user_prompt="User prompt requesting policy",
        raw_response="I think we should... {invalid json here",
        parsed_policy=None,
        parsing_error="Failed to parse policy JSON: JSONDecodeError at position 25",
        model="anthropic:claude-sonnet-4-5",
        prompt_tokens=500,
        completion_tokens=200,
        latency_seconds=1.5,
    )
    repo.save_event(error_event)

    conn.close()
    return db_path


class TestAuditReplayIntegration:
    """Integration tests for audit replay."""

    def test_audit_replay_full_flow(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test full audit replay flow through CLI."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
            ],
        )

        assert result.exit_code == 0

        # Should contain all 3 iterations
        output = strip_ansi(result.output)
        assert "Iteration 1" in output or "iteration 1" in output.lower()
        assert "Iteration 2" in output or "iteration 2" in output.lower()
        assert "Iteration 3" in output or "iteration 3" in output.lower()

    def test_audit_replay_with_range(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test audit replay with iteration range."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
                "--start",
                "2",
                "--end",
                "3",
            ],
        )

        assert result.exit_code == 0

        output = strip_ansi(result.output)
        # Should contain iterations 2 and 3
        assert "Iteration 2" in output or "iteration 2" in output.lower()
        assert "Iteration 3" in output or "iteration 3" in output.lower()

    def test_audit_shows_both_agents(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test that audit shows data for both agents."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )

        assert result.exit_code == 0

        output = strip_ansi(result.output)
        assert "BANK_A" in output
        assert "BANK_B" in output

    def test_audit_shows_prompts_and_responses(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test that audit shows prompts and responses."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )

        assert result.exit_code == 0

        output = strip_ansi(result.output)
        # Should contain prompt indicators
        assert "System Prompt" in output or "system prompt" in output.lower()
        assert "User Prompt" in output or "user prompt" in output.lower()
        # Should contain policy content
        assert "policy_id" in output or "version" in output

    def test_audit_shows_model_info(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test that audit shows model information."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )

        assert result.exit_code == 0

        output = strip_ansi(result.output)
        # Should show model info
        assert "claude" in output.lower() or "anthropic" in output.lower()

    def test_audit_with_parsing_errors(
        self, runner: CliRunner, db_with_parsing_errors: Path
    ) -> None:
        """Test audit display with parsing errors."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "parsing-error-run",
                "--db",
                str(db_with_parsing_errors),
                "--audit",
            ],
        )

        assert result.exit_code == 0

        output = strip_ansi(result.output)
        # Should show error indication
        assert (
            "error" in output.lower()
            or "invalid" in output.lower()
            or "failed" in output.lower()
        )


class TestAuditReplayEdgeCases:
    """Edge case tests for audit replay."""

    def test_audit_nonexistent_run(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test audit with nonexistent run ID."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "nonexistent-run-id",
                "--db",
                str(comprehensive_test_db),
                "--audit",
            ],
        )

        # Should fail with appropriate error
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_audit_start_beyond_iterations(
        self, runner: CliRunner, comprehensive_test_db: Path
    ) -> None:
        """Test audit with start beyond available iterations."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "integration-test-run",
                "--db",
                str(comprehensive_test_db),
                "--audit",
                "--start",
                "100",  # Way beyond actual iterations
            ],
        )

        # Should succeed but show no iterations or appropriate message
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "no iterations" in output.lower() or len(output.strip()) < 500

    def test_audit_empty_db(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test audit with empty database (schema only)."""
        from cli import app

        # Create empty database
        db_path = tmp_path / "empty_castro.db"
        conn = duckdb.connect(str(db_path))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()
        conn.close()

        result = runner.invoke(
            app,
            ["replay", "any-run-id", "--db", str(db_path), "--audit"],
        )

        # Should fail gracefully
        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestAuditDisplayFunctions:
    """Test audit display functions directly."""

    def test_display_audit_output_direct(
        self, comprehensive_test_db: Path
    ) -> None:
        """Test display_audit_output function directly."""
        from castro.audit_display import display_audit_output
        from castro.state_provider import DatabaseExperimentProvider

        conn = duckdb.connect(str(comprehensive_test_db), read_only=True)
        provider = DatabaseExperimentProvider(conn=conn, run_id="integration-test-run")

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)

        # Should not raise
        display_audit_output(
            provider=provider,
            console=console,
            start_iteration=1,
            end_iteration=2,
        )

        conn.close()

        text = strip_ansi(output.getvalue())
        assert "BANK_A" in text
        assert "BANK_B" in text

    def test_format_helpers(self) -> None:
        """Test format helper functions."""
        from castro.audit_display import (
            format_agent_section_header,
            format_iteration_header,
        )

        iter_header = format_iteration_header(5)
        assert "5" in iter_header
        assert "Iteration" in iter_header or "ITERATION" in iter_header

        agent_header = format_agent_section_header("BANK_A")
        assert "BANK_A" in agent_header
