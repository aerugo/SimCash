"""Tests for policy-evolution CLI command.

TDD tests for the policy-evolution subcommand.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from payment_simulator.experiments.cli.commands import experiment_app
from payment_simulator.experiments.persistence import (
    EventRecord,
    ExperimentRecord,
    ExperimentRepository,
    IterationRecord,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_db_path(tmp_path: Path) -> Path:
    """Create a sample database with test data."""
    db_path = tmp_path / "test.db"
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

    # Create iterations (0-indexed internally)
    for i in range(3):
        repo.save_iteration(
            IterationRecord(
                run_id="test-run-123",
                iteration=i,
                costs_per_agent={
                    "BANK_A": 10000 - i * 1000,
                    "BANK_B": 8000 - i * 500,
                },
                accepted_changes={"BANK_A": True, "BANK_B": i > 0},
                policies={
                    "BANK_A": {
                        "version": "2.0",
                        "parameters": {"threshold": 100 + i * 10},
                    },
                    "BANK_B": {
                        "version": "2.0",
                        "parameters": {"threshold": 200 + i * 5},
                    },
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    # Create LLM events
    for i in range(3):
        for agent in ["BANK_A", "BANK_B"]:
            repo.save_event(
                EventRecord(
                    run_id="test-run-123",
                    iteration=i,
                    event_type="llm_interaction",
                    event_data={
                        "agent_id": agent,
                        "system_prompt": f"System prompt for {agent} iteration {i}",
                        "user_prompt": f"User prompt for {agent} iteration {i}",
                        "raw_response": f'{{"threshold": {100 + i * 10}}}',
                    },
                    timestamp=datetime.now().isoformat(),
                )
            )

    repo.close()
    return db_path


class TestPolicyEvolutionCommand:
    """Tests for policy-evolution CLI command."""

    def test_command_outputs_json(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify command outputs valid JSON."""
        result = cli_runner.invoke(
            experiment_app,
            ["policy-evolution", "test-run-123", "--db", str(sample_db_path)],
        )

        assert result.exit_code == 0
        # Should be valid JSON
        output = json.loads(result.stdout)
        assert isinstance(output, dict)
        assert "BANK_A" in output
        assert "BANK_B" in output

    def test_command_filters_by_agent(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify --agent filter works."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--agent",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "BANK_A" in output
        assert "BANK_B" not in output

    def test_command_filters_by_iteration_range(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify --start and --end filters work."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--start",
                "2",
                "--end",
                "3",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)

        # Should have only iteration_2 and iteration_3
        for agent_id, agent_data in output.items():
            assert "iteration_1" not in agent_data
            assert "iteration_2" in agent_data or "iteration_3" in agent_data

    def test_command_includes_llm_with_flag(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify --llm flag includes LLM data."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--llm",
                "--agent",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)

        # Check that LLM data is present
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" in iteration_1
        assert "system_prompt" in iteration_1["llm"]
        assert "user_prompt" in iteration_1["llm"]
        assert "raw_response" in iteration_1["llm"]

    def test_command_excludes_llm_by_default(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify LLM data is excluded by default."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--agent",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)

        # Check that LLM data is NOT present
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" not in iteration_1

    def test_command_handles_invalid_run_id(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify error handling for invalid run ID."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "nonexistent-run",
                "--db",
                str(sample_db_path),
            ],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower() if result.stderr else "not found" in result.stdout.lower()

    def test_command_handles_missing_database(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Verify error handling for missing database."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(tmp_path / "nonexistent.db"),
            ],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "database" in result.stdout.lower()

    def test_command_compact_output(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify --compact flag removes indentation."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--compact",
                "--agent",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        # Compact JSON has no newlines (except at the end)
        output_lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(output_lines) == 1  # Single line of JSON

    def test_command_includes_policy_and_cost(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify output includes policy, cost, and accepted fields."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--agent",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)

        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "policy" in iteration_1
        assert "cost" in iteration_1
        assert "accepted" in iteration_1
        assert iteration_1["cost"] == 10000  # First iteration cost
        assert iteration_1["accepted"] is True

    def test_command_invalid_iteration_range(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify error when start > end."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--start",
                "5",
                "--end",
                "2",
            ],
        )

        assert result.exit_code == 1
        assert "start" in result.stdout.lower() or "end" in result.stdout.lower()


class TestPolicyEvolutionCommandEdgeCases:
    """Edge case tests for policy-evolution command."""

    def test_empty_experiment(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Verify handling of experiment with no iterations."""
        db_path = tmp_path / "empty.db"
        repo = ExperimentRepository(db_path)
        repo.save_experiment(
            ExperimentRecord(
                run_id="empty-run",
                experiment_name="empty_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
        )
        repo.close()

        result = cli_runner.invoke(
            experiment_app,
            ["policy-evolution", "empty-run", "--db", str(db_path)],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output == {}  # Empty dict for no iterations

    def test_agent_not_found(
        self, cli_runner: CliRunner, sample_db_path: Path
    ) -> None:
        """Verify handling of nonexistent agent filter."""
        result = cli_runner.invoke(
            experiment_app,
            [
                "policy-evolution",
                "test-run-123",
                "--db",
                str(sample_db_path),
                "--agent",
                "NONEXISTENT",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output == {}  # Empty dict when agent not found
