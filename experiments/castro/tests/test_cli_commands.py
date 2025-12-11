"""Tests for CLI replay and results commands.

TDD: These tests are written BEFORE the implementation.
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

from castro.event_compat import CastroEvent as ExperimentEvent
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_castro.db"


@pytest.fixture
def populated_db(db_path: Path) -> Path:
    """Create a database with test data."""
    conn = duckdb.connect(str(db_path))
    repo = ExperimentEventRepository(conn)
    repo.initialize_schema()

    # Create run record
    record = ExperimentRunRecord(
        run_id="exp1-20251209-143022-a1b2c3",
        experiment_name="exp1",
        started_at=datetime(2025, 12, 9, 14, 30, 22),
        status="completed",
        final_cost=12000,
        best_cost=12000,
        num_iterations=3,
        converged=True,
        convergence_reason="stability_reached",
        model="anthropic:claude-sonnet-4-5",
    )
    repo.save_run_record(record)

    # Create events
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
        ExperimentEvent(
            event_type="experiment_end",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=3,
            timestamp=datetime(2025, 12, 9, 14, 30, 35),
            details={
                "final_cost": 12000,
                "best_cost": 12000,
                "converged": True,
                "convergence_reason": "stability_reached",
                "duration_seconds": 13.0,
            },
        ),
    ]
    repo.save_events_batch(events)

    # Create a second run for testing results listing
    record2 = ExperimentRunRecord(
        run_id="exp2-20251209-150000-b2c3d4",
        experiment_name="exp2",
        started_at=datetime(2025, 12, 9, 15, 0, 0),
        status="completed",
        final_cost=25000,
        best_cost=22000,
        num_iterations=5,
        converged=True,
        convergence_reason="max_iterations",
        model="openai:gpt-5.1",
    )
    repo.save_run_record(record2)

    conn.close()
    return db_path


class TestReplayCommand:
    """Test castro replay command."""

    def test_replay_command_exists(self) -> None:
        """castro replay command is available."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["replay", "--help"])

        assert result.exit_code == 0
        assert "replay" in result.output.lower() or "RUN_ID" in result.output

    def test_replay_requires_run_id(self) -> None:
        """castro replay requires a run_id argument."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["replay"])

        # Should fail with missing argument
        assert result.exit_code != 0

    def test_replay_requires_database(self) -> None:
        """castro replay requires --db option or default database."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["replay", "nonexistent-run-id"])

        # Should fail if database doesn't exist
        assert result.exit_code != 0

    def test_replay_shows_run_id(self, populated_db: Path) -> None:
        """castro replay displays run ID in output."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["replay", "exp1-20251209-143022-a1b2c3", "--db", str(populated_db)]
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "exp1-20251209-143022-a1b2c3" in output

    def test_replay_shows_experiment_name(self, populated_db: Path) -> None:
        """castro replay displays experiment name."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["replay", "exp1-20251209-143022-a1b2c3", "--db", str(populated_db)]
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "exp1" in output

    def test_replay_shows_final_results(self, populated_db: Path) -> None:
        """castro replay displays final results."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["replay", "exp1-20251209-143022-a1b2c3", "--db", str(populated_db)]
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Should show final cost ($120.00 = 12000 cents)
        assert "$120.00" in output or "12000" in output

    def test_replay_run_not_found(self, populated_db: Path) -> None:
        """castro replay handles nonexistent run gracefully."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["replay", "nonexistent-run-id", "--db", str(populated_db)]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_replay_supports_verbose_flag(self, populated_db: Path) -> None:
        """castro replay supports --verbose flag."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "replay",
                "exp1-20251209-143022-a1b2c3",
                "--db",
                str(populated_db),
                "--verbose",
            ],
        )

        assert result.exit_code == 0


class TestResultsCommand:
    """Test castro results command."""

    def test_results_command_exists(self) -> None:
        """castro results command is available."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--help"])

        assert result.exit_code == 0
        assert "results" in result.output.lower() or "list" in result.output.lower()

    def test_results_lists_runs(self, populated_db: Path) -> None:
        """castro results lists experiment runs."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(populated_db)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Should show both runs (may be truncated in table)
        assert "exp1" in output
        assert "exp2" in output
        # Should show count
        assert "2 run" in output

    def test_results_shows_experiment_names(self, populated_db: Path) -> None:
        """castro results shows experiment names."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(populated_db)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "exp1" in output
        assert "exp2" in output

    def test_results_shows_status(self, populated_db: Path) -> None:
        """castro results shows run status."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(populated_db)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Status column shows "compl…" when truncated
        assert "compl" in output.lower()

    def test_results_shows_costs(self, populated_db: Path) -> None:
        """castro results shows final/best costs."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(populated_db)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Check for cost values (may be truncated, e.g., "$120.…" or "$250.…")
        assert "$120" in output or "$250" in output or "$220" in output

    def test_results_filter_by_experiment(self, populated_db: Path) -> None:
        """castro results --experiment filters by experiment name."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["results", "--db", str(populated_db), "--experiment", "exp1"]
        )

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Should show only 1 run
        assert "1 run" in output
        # Should show exp1 experiment name
        assert "exp1" in output

    def test_results_empty_database(self, db_path: Path) -> None:
        """castro results handles empty database gracefully."""
        from cli import app

        # Create empty database with schema
        conn = duckdb.connect(str(db_path))
        repo = ExperimentEventRepository(conn)
        repo.initialize_schema()
        conn.close()

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(db_path)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "no" in output.lower() or "empty" in output.lower() or output.strip() == ""

    def test_results_shows_model(self, populated_db: Path) -> None:
        """castro results shows model used."""
        from cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["results", "--db", str(populated_db)])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        # Should show model info (truncated, e.g., "anth…" or "open…")
        assert "anth" in output.lower() or "open" in output.lower()
