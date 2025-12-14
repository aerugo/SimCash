"""Integration tests for policy-evolution command.

Tests the full flow from CLI to database to JSON output.
Uses a real experiment database fixture.
"""

from __future__ import annotations

import json
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

    # Create iterations with policies that have meaningful changes
    policies_bank_a = [
        {"version": "2.0", "policy_id": "p1", "threshold": 100, "rate": 0.5},
        {"version": "2.0", "policy_id": "p2", "threshold": 110, "rate": 0.5},
        {"version": "2.0", "policy_id": "p3", "threshold": 120, "rate": 0.6},
    ]
    policies_bank_b = [
        {"version": "2.0", "policy_id": "q1", "threshold": 200},
        {"version": "2.0", "policy_id": "q2", "threshold": 205},
        {"version": "2.0", "policy_id": "q3", "threshold": 210},
    ]

    for i in range(3):
        repo.save_iteration(
            IterationRecord(
                run_id="test-run-123",
                iteration=i,
                costs_per_agent={"BANK_A": 10000 - i * 1000, "BANK_B": 8000 - i * 500},
                accepted_changes={"BANK_A": True, "BANK_B": i > 0},
                policies={
                    "BANK_A": policies_bank_a[i],
                    "BANK_B": policies_bank_b[i],
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    # Create LLM events for BANK_A
    for i in range(3):
        repo.save_event(
            EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_call_complete",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": f"You are optimizing BANK_A policy. Iteration {i}.",
                    "user_prompt": f"Current policy: {json.dumps(policies_bank_a[i])}",
                    "raw_response": json.dumps(policies_bank_a[min(i + 1, 2)]),
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    repo.close()
    return db_path


class TestPolicyEvolutionIntegration:
    """Integration tests for policy-evolution command."""

    def test_basic_output_structure(self, experiment_db: Path) -> None:
        """Verify basic JSON output structure."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Check structure
        assert "BANK_A" in output
        assert "BANK_B" in output
        assert "iteration_1" in output["BANK_A"]
        assert "policy" in output["BANK_A"]["iteration_1"]

    def test_agent_filter(self, experiment_db: Path) -> None:
        """Verify --agent filter works."""
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

    def test_iteration_range_filter(self, experiment_db: Path) -> None:
        """Verify --start and --end filters work."""
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

        # Should only have iteration_2
        assert "iteration_1" not in output.get("BANK_A", {})
        assert "iteration_2" in output.get("BANK_A", {})
        assert "iteration_3" not in output.get("BANK_A", {})

    def test_llm_flag_includes_prompts(self, experiment_db: Path) -> None:
        """Verify --llm flag includes LLM data."""
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

        # Check LLM data is present for BANK_A
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" in iteration_1
        assert "system_prompt" in iteration_1["llm"]
        assert "user_prompt" in iteration_1["llm"]
        assert "raw_response" in iteration_1["llm"]
        assert "optimizing BANK_A" in iteration_1["llm"]["system_prompt"]

    def test_llm_flag_absent_excludes_prompts(self, experiment_db: Path) -> None:
        """Verify LLM data is excluded without --llm flag."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # LLM data should NOT be present
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "llm" not in iteration_1

    def test_diff_computed_between_iterations(self, experiment_db: Path) -> None:
        """Verify diff is computed between consecutive iterations."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # First iteration should have no diff
        iteration_1 = output["BANK_A"]["iteration_1"]
        assert iteration_1.get("diff") is None

        # Second iteration should have diff (threshold changed 100 -> 110)
        iteration_2 = output["BANK_A"]["iteration_2"]
        assert iteration_2.get("diff") is not None
        assert "threshold" in iteration_2["diff"]
        assert "100" in iteration_2["diff"]
        assert "110" in iteration_2["diff"]

    def test_invalid_run_id_returns_error(self, experiment_db: Path) -> None:
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

    def test_invalid_iteration_range_returns_error(self, experiment_db: Path) -> None:
        """Verify error when start > end."""
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

    def test_cost_included_in_output(self, experiment_db: Path) -> None:
        """Verify cost is included in iteration output."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "cost" in iteration_1
        assert iteration_1["cost"] == 10000  # First iteration cost

    def test_accepted_included_in_output(self, experiment_db: Path) -> None:
        """Verify accepted status is included in iteration output."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        iteration_1 = output["BANK_A"]["iteration_1"]
        assert "accepted" in iteration_1
        assert iteration_1["accepted"] is True

    def test_combined_filters(self, experiment_db: Path) -> None:
        """Verify combined filters work together."""
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
                "--start",
                "1",
                "--end",
                "2",
                "--llm",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Only BANK_A
        assert "BANK_A" in output
        assert "BANK_B" not in output

        # Only iterations 1 and 2
        bank_a = output["BANK_A"]
        assert "iteration_1" in bank_a
        assert "iteration_2" in bank_a
        assert "iteration_3" not in bank_a

        # LLM data included
        assert "llm" in bank_a["iteration_1"]

    def test_policy_content_preserved(self, experiment_db: Path) -> None:
        """Verify policy content is fully preserved in output."""
        result = runner.invoke(
            app,
            ["experiment", "policy-evolution", "test-run-123", "--db", str(experiment_db)],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)

        # Check first iteration policy
        policy = output["BANK_A"]["iteration_1"]["policy"]
        assert policy["version"] == "2.0"
        assert policy["threshold"] == 100
        assert policy["rate"] == 0.5

        # Check third iteration policy (values changed)
        policy_3 = output["BANK_A"]["iteration_3"]["policy"]
        assert policy_3["threshold"] == 120
        assert policy_3["rate"] == 0.6

    def test_empty_agent_filter_returns_empty(self, experiment_db: Path) -> None:
        """Verify filtering by non-existent agent returns empty."""
        result = runner.invoke(
            app,
            [
                "experiment",
                "policy-evolution",
                "test-run-123",
                "--db",
                str(experiment_db),
                "--agent",
                "NONEXISTENT_BANK",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == {}
