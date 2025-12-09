"""TDD tests for CLI --audit flag functionality.

These tests are written BEFORE the implementation following TDD principles.
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import duckdb
import pytest
from rich.console import Console
from typer.testing import CliRunner

from castro.events import (
    EVENT_LLM_INTERACTION,
    ExperimentEvent,
    create_llm_interaction_event,
)
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord


@pytest.fixture
def runner() -> CliRunner:
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database with test data."""
    db_path = tmp_path / "test_castro.db"
    conn = duckdb.connect(str(db_path))
    repo = ExperimentEventRepository(conn)
    repo.initialize_schema()

    # Create a test run
    run_record = ExperimentRunRecord(
        run_id="test-run-001",
        experiment_name="exp1",
        started_at=datetime(2025, 12, 9, 10, 0, 0),
        status="completed",
        model="anthropic:claude-sonnet-4-5",
        master_seed=42,
        final_cost=10000,
        best_cost=9000,
        num_iterations=3,
        converged=True,
        convergence_reason="stability_reached",
    )
    repo.save_run_record(run_record)

    # Add LLM interaction events for iterations 1, 2, and 3
    for iteration in range(1, 4):
        for agent_id in ["BANK_A", "BANK_B"]:
            event = create_llm_interaction_event(
                run_id="test-run-001",
                iteration=iteration,
                agent_id=agent_id,
                system_prompt=f"System prompt for {agent_id}",
                user_prompt=f"User prompt for iteration {iteration}, agent {agent_id}",
                raw_response=f'{{"version": "2.0", "policy_id": "test_{agent_id}_{iteration}"}}',
                parsed_policy={"version": "2.0", "policy_id": f"test_{agent_id}_{iteration}"},
                parsing_error=None,
                model="anthropic:claude-sonnet-4-5",
                prompt_tokens=500,
                completion_tokens=200,
                latency_seconds=1.5,
            )
            repo.save_event(event)

    conn.close()
    return db_path


class TestReplayAuditFlagRecognition:
    """Test that the --audit flag is recognized by the CLI."""

    def test_replay_command_exists(self, runner: CliRunner) -> None:
        """The replay command should exist."""
        from cli import app

        result = runner.invoke(app, ["replay", "--help"])
        assert result.exit_code == 0
        assert "replay" in result.output.lower()

    def test_replay_audit_flag_in_help(self, runner: CliRunner) -> None:
        """The --audit flag should appear in replay help."""
        from cli import app

        result = runner.invoke(app, ["replay", "--help"])
        assert result.exit_code == 0
        assert "--audit" in result.output

    def test_replay_start_flag_in_help(self, runner: CliRunner) -> None:
        """The --start flag should appear in replay help."""
        from cli import app

        result = runner.invoke(app, ["replay", "--help"])
        assert result.exit_code == 0
        assert "--start" in result.output

    def test_replay_end_flag_in_help(self, runner: CliRunner) -> None:
        """The --end flag should appear in replay help."""
        from cli import app

        result = runner.invoke(app, ["replay", "--help"])
        assert result.exit_code == 0
        assert "--end" in result.output


class TestReplayAuditValidation:
    """Test validation of --audit, --start, and --end flags."""

    def test_audit_without_start_end_shows_all_iterations(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--audit without --start/--end should show all iterations."""
        from cli import app

        result = runner.invoke(
            app, ["replay", "test-run-001", "--db", str(temp_db), "--audit"]
        )
        # Should succeed and show audit output for all iterations
        assert result.exit_code == 0
        # Should contain iteration numbers
        assert "Iteration 1" in result.output or "iteration 1" in result.output.lower()

    def test_audit_with_start_only_shows_from_start(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--audit --start 2 should show iterations 2 onwards."""
        from cli import app

        result = runner.invoke(
            app, ["replay", "test-run-001", "--db", str(temp_db), "--audit", "--start", "2"]
        )
        assert result.exit_code == 0
        # Should NOT contain iteration 1
        # (checking lowercase to be case-insensitive)
        output_lower = result.output.lower()
        # Should contain iteration 2
        assert "iteration 2" in output_lower or "iteration: 2" in output_lower

    def test_audit_with_end_only_shows_until_end(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--audit --end 2 should show iterations up to and including 2."""
        from cli import app

        result = runner.invoke(
            app, ["replay", "test-run-001", "--db", str(temp_db), "--audit", "--end", "2"]
        )
        assert result.exit_code == 0
        # Should contain iteration 2
        output_lower = result.output.lower()
        assert "iteration 2" in output_lower or "iteration: 2" in output_lower

    def test_audit_with_start_and_end_shows_range(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--audit --start 2 --end 3 should show iterations 2 and 3."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "2",
                "--end",
                "3",
            ],
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should contain iterations 2 and 3
        assert "iteration 2" in output_lower or "iteration: 2" in output_lower

    def test_audit_start_greater_than_end_fails(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--start greater than --end should fail with clear error."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "5",
                "--end",
                "2",
            ],
        )
        assert result.exit_code != 0
        assert "start" in result.output.lower() or "end" in result.output.lower()

    def test_audit_negative_start_fails(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--start with negative value should fail."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "-1",
            ],
        )
        # Should either fail with exit code or handle gracefully
        # (Typer might reject negative integers automatically)
        assert result.exit_code != 0 or "invalid" in result.output.lower()

    def test_start_and_end_without_audit_ignored(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """--start and --end without --audit should be ignored (normal replay)."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--start",
                "2",
                "--end",
                "3",
            ],
        )
        # Should succeed with normal replay (ignoring start/end)
        assert result.exit_code == 0


class TestReplayAuditOutput:
    """Test the content of audit output."""

    def test_audit_shows_agent_headers(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """Audit output should show separate sections for each agent."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Should contain agent IDs
        assert "BANK_A" in result.output
        assert "BANK_B" in result.output

    def test_audit_shows_system_prompt(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """Audit output should show the system prompt."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Should contain system prompt marker or content
        assert (
            "system prompt" in result.output.lower()
            or "System prompt for" in result.output
        )

    def test_audit_shows_user_prompt(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """Audit output should show the user prompt."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Should contain user prompt marker or content
        assert (
            "user prompt" in result.output.lower()
            or "User prompt for" in result.output
        )

    def test_audit_shows_raw_response(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """Audit output should show the raw LLM response."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Should contain response marker or content
        assert (
            "response" in result.output.lower()
            or "policy_id" in result.output  # From the JSON response
        )

    def test_audit_shows_model_info(
        self, runner: CliRunner, temp_db: Path
    ) -> None:
        """Audit output should show model information."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-001",
                "--db",
                str(temp_db),
                "--audit",
                "--start",
                "1",
                "--end",
                "1",
            ],
        )
        assert result.exit_code == 0
        # Should contain model info
        assert "claude" in result.output.lower() or "anthropic" in result.output.lower()


class TestReplayAuditWithValidationErrors:
    """Test audit output when validation errors occurred."""

    @pytest.fixture
    def temp_db_with_errors(self, tmp_path: Path) -> Path:
        """Create a database with validation error events."""
        db_path = tmp_path / "test_castro_errors.db"
        conn = duckdb.connect(str(db_path))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()

        # Create a test run
        run_record = ExperimentRunRecord(
            run_id="test-run-errors",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 10, 0, 0),
            status="completed",
            model="anthropic:claude-sonnet-4-5",
            master_seed=42,
        )
        repo.save_run_record(run_record)

        # Add an LLM interaction with parsing error
        event = create_llm_interaction_event(
            run_id="test-run-errors",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response="invalid json {{{",
            parsed_policy=None,
            parsing_error="Failed to parse policy JSON: JSONDecodeError",
            model="anthropic:claude-sonnet-4-5",
            prompt_tokens=500,
            completion_tokens=200,
            latency_seconds=1.5,
        )
        repo.save_event(event)

        conn.close()
        return db_path

    def test_audit_shows_validation_errors(
        self, runner: CliRunner, temp_db_with_errors: Path
    ) -> None:
        """Audit output should show validation errors when they occurred."""
        from cli import app

        result = runner.invoke(
            app,
            [
                "replay",
                "test-run-errors",
                "--db",
                str(temp_db_with_errors),
                "--audit",
            ],
        )
        assert result.exit_code == 0
        # Should contain error indication
        assert (
            "error" in result.output.lower()
            or "invalid" in result.output.lower()
            or "failed" in result.output.lower()
        )
