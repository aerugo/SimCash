"""Unit tests for policy-evolution CLI command."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from payment_simulator.cli.main import app
from payment_simulator.experiments.persistence import (
    EventRecord,
    ExperimentRecord,
    ExperimentRepository,
    IterationRecord,
)


runner = CliRunner()


@pytest.fixture
def experiment_db(tmp_path: Path) -> Path:
    """Create a test experiment database with sample data."""
    db_path = tmp_path / "test_experiments.db"
    repo = ExperimentRepository(db_path)

    # Create experiment
    repo.save_experiment(
        ExperimentRecord(
            run_id="test-run-123",
            experiment_name="test_exp",
            experiment_type="generic",
            config={},
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            num_iterations=3,
            converged=True,
            convergence_reason="stability_reached",
        )
    )

    # Create iterations with policies
    for i in range(3):
        repo.save_iteration(
            IterationRecord(
                run_id="test-run-123",
                iteration=i,
                costs_per_agent={"BANK_A": 10000 - i * 1000, "BANK_B": 8000 - i * 500},
                accepted_changes={"BANK_A": True, "BANK_B": i > 0},
                policies={
                    "BANK_A": {"version": "2.0", "threshold": 100 + i * 10},
                    "BANK_B": {"version": "2.0", "threshold": 200 + i * 5},
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    # Create LLM events
    for i in range(3):
        repo.save_event(
            EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_call_complete",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": f"System prompt for iteration {i}",
                    "user_prompt": f"User prompt for iteration {i}",
                    "raw_response": f'{{"threshold": {100 + i * 10}}}',
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    repo.close()
    return db_path


class TestPolicyEvolutionCommand:
    """Tests for policy-evolution CLI command."""

    def test_command_exists(self) -> None:
        """Verify command is registered."""
        result = runner.invoke(app, ["experiment", "policy-evolution", "--help"])
        assert result.exit_code == 0
        assert "policy-evolution" in result.output or "Extract policy evolution" in result.output

    def test_requires_run_id(self) -> None:
        """Verify run_id is required."""
        result = runner.invoke(app, ["experiment", "policy-evolution"])
        assert result.exit_code != 0

    def test_validates_iteration_range(self, experiment_db: Path) -> None:
        """Verify start <= end validation."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--start",
                "5",
                "--end",
                "2",
            ],
        )
        assert result.exit_code != 0
        assert "start" in result.output.lower()

    def test_validates_start_positive(self, experiment_db: Path) -> None:
        """Verify start must be >= 1."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--start",
                "0",
            ],
        )
        assert result.exit_code != 0
        assert "start" in result.output.lower()

    def test_outputs_valid_json(self, experiment_db: Path) -> None:
        """Verify output is valid JSON."""
        import json

        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
            ],
        )
        assert result.exit_code == 0

        # Should parse as valid JSON
        output = json.loads(result.output)
        assert isinstance(output, dict)

    def test_pretty_flag_formats_output(self, experiment_db: Path) -> None:
        """Verify --pretty flag indents JSON."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--pretty",
            ],
        )
        assert result.exit_code == 0

        # Pretty output should have newlines and indentation
        assert "\n  " in result.output or "\n    " in result.output

    def test_database_not_found_error(self, tmp_path: Path) -> None:
        """Verify error for non-existent database."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "some-run",
                "--db",
                str(tmp_path / "nonexistent.db"),
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_run_not_found_error(self, experiment_db: Path) -> None:
        """Verify error for non-existent run ID."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "nonexistent-run",
                "--db",
                str(experiment_db),
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_agent_filter_works(self, experiment_db: Path) -> None:
        """Verify --agent filter works."""
        import json

        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--agent",
                "BANK_A",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.output)
        assert "BANK_A" in output
        assert "BANK_B" not in output

    def test_llm_flag_includes_prompts(self, experiment_db: Path) -> None:
        """Verify --llm flag includes LLM data."""
        import json

        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--llm",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.output)
        # BANK_A has LLM events
        iteration_1 = output.get("BANK_A", {}).get("iteration_1", {})
        assert "llm" in iteration_1
        assert "system_prompt" in iteration_1["llm"]

    def test_iteration_range_filter(self, experiment_db: Path) -> None:
        """Verify --start and --end filter iterations."""
        import json

        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--start",
                "2",
                "--end",
                "2",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.output)
        bank_a = output.get("BANK_A", {})

        # Should only have iteration_2
        assert "iteration_1" not in bank_a
        assert "iteration_2" in bank_a
        assert "iteration_3" not in bank_a
