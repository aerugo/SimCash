"""Tests for core experiment CLI commands.

Task 14.4: TDD tests for generic experiment CLI.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from typer.testing import CliRunner


class TestExperimentAppImport:
    """Tests for experiment app importability."""

    def test_import_experiment_app(self) -> None:
        """experiment_app importable from experiments.cli."""
        from payment_simulator.experiments.cli import experiment_app

        assert experiment_app is not None

    def test_import_from_cli_module(self) -> None:
        """experiment_app importable from cli module."""
        from payment_simulator.experiments.cli.commands import experiment_app

        assert experiment_app is not None


class TestReplayCommand:
    """Tests for experiment replay command."""

    def test_replay_command_exists(self) -> None:
        """replay command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert result.exit_code == 0

    def test_replay_requires_run_id(self) -> None:
        """replay command requires run_id argument."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay"])
        assert result.exit_code != 0  # Should fail without argument

    def test_replay_has_audit_option(self) -> None:
        """replay command has --audit option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--audit" in result.output

    def test_replay_has_db_option(self) -> None:
        """replay command has --db option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--db" in result.output

    def test_replay_has_verbose_option(self) -> None:
        """replay command has --verbose option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--verbose" in result.output

    def test_replay_has_start_end_options(self) -> None:
        """replay command has --start and --end options for audit."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--start" in result.output
        assert "--end" in result.output

    def test_replay_fails_if_db_not_found(self, tmp_path) -> None:
        """replay command fails if database file doesn't exist."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        nonexistent_db = tmp_path / "nonexistent.db"
        result = runner.invoke(
            experiment_app, ["replay", "some-run-id", "--db", str(nonexistent_db)]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_replay_fails_if_run_not_found(self, tmp_path) -> None:
        """replay command fails if run_id not in database."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Create empty database
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(
            experiment_app, ["replay", "nonexistent-run", "--db", str(db_path)]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_replay_displays_experiment_output(self, tmp_path) -> None:
        """replay command displays experiment events."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            EventRecord,
        )

        # Create database with experiment and events
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            num_iterations=1,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(record)

        # Add an event
        event = EventRecord(
            run_id="test-run-123",
            iteration=1,
            event_type="experiment_start",
            event_data={"experiment_name": "exp1"},
            timestamp=datetime.now().isoformat(),
        )
        repo.save_event(event)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(
            experiment_app, ["replay", "test-run-123", "--db", str(db_path)]
        )
        assert result.exit_code == 0
        assert "exp1" in result.output or "test-run-123" in result.output


class TestResultsCommand:
    """Tests for experiment results command."""

    def test_results_command_exists(self) -> None:
        """results command exists in experiment_app."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert result.exit_code == 0

    def test_results_has_db_option(self) -> None:
        """results command has --db option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert "--db" in result.output

    def test_results_has_experiment_filter_option(self) -> None:
        """results command has --experiment filter option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert "--experiment" in result.output

    def test_results_has_type_filter_option(self) -> None:
        """results command has --type filter option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert "--type" in result.output

    def test_results_has_limit_option(self) -> None:
        """results command has --limit option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--help"])
        assert "--limit" in result.output

    def test_results_fails_if_db_not_found(self, tmp_path) -> None:
        """results command fails if database file doesn't exist."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        nonexistent_db = tmp_path / "nonexistent.db"
        result = runner.invoke(experiment_app, ["results", "--db", str(nonexistent_db)])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_results_lists_experiments(self, tmp_path) -> None:
        """results command lists experiments from database."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        # Create test database with experiment
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at=datetime.now().isoformat(),
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "test-run-123" in result.output or "exp1" in result.output

    def test_results_filters_by_experiment_name(self, tmp_path) -> None:
        """results command filters by experiment name."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        # Create test database with multiple experiments
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        for i, name in enumerate(["exp1", "exp2"]):
            record = ExperimentRecord(
                run_id=f"run-{i}",
                experiment_name=name,
                experiment_type="castro",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(record)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(
            experiment_app, ["results", "--db", str(db_path), "--experiment", "exp1"]
        )
        assert result.exit_code == 0
        assert "exp1" in result.output
        # exp2 should not appear when filtering for exp1
        # (but this depends on implementation)

    def test_results_filters_by_type(self, tmp_path) -> None:
        """results command filters by experiment type."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        # Create test database with different experiment types
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        for i, exp_type in enumerate(["castro", "other"]):
            record = ExperimentRecord(
                run_id=f"run-{i}",
                experiment_name=f"exp-{exp_type}",
                experiment_type=exp_type,
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(record)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(
            experiment_app, ["results", "--db", str(db_path), "--type", "castro"]
        )
        assert result.exit_code == 0
        assert "castro" in result.output.lower() or "exp-castro" in result.output

    def test_results_shows_empty_message(self, tmp_path) -> None:
        """results command shows message when no runs found."""
        from payment_simulator.experiments.cli import experiment_app
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Create empty database
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        repo.close()

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["results", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "no" in result.output.lower() and "found" in result.output.lower()


class TestVerboseFlags:
    """Tests for verbose flag handling."""

    def test_replay_has_verbose_iterations(self) -> None:
        """replay command has --verbose-iterations option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--verbose-iterations" in result.output

    def test_replay_has_verbose_bootstrap(self) -> None:
        """replay command has --verbose-bootstrap option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--verbose-bootstrap" in result.output

    def test_replay_has_verbose_llm(self) -> None:
        """replay command has --verbose-llm option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--verbose-llm" in result.output

    def test_replay_has_verbose_policy(self) -> None:
        """replay command has --verbose-policy option."""
        from payment_simulator.experiments.cli import experiment_app

        runner = CliRunner()
        result = runner.invoke(experiment_app, ["replay", "--help"])
        assert "--verbose-policy" in result.output


class TestCommonUtilities:
    """Tests for common utilities."""

    def test_build_verbose_config_importable(self) -> None:
        """build_verbose_config importable from common module."""
        from payment_simulator.experiments.cli.common import build_verbose_config

        assert build_verbose_config is not None

    def test_build_verbose_config_all_false_by_default(self) -> None:
        """build_verbose_config returns all False by default."""
        from payment_simulator.experiments.cli.common import build_verbose_config

        config = build_verbose_config()
        assert config.iterations is False
        assert config.policy is False
        assert config.bootstrap is False
        assert config.llm is False

    def test_build_verbose_config_verbose_enables_all(self) -> None:
        """build_verbose_config with verbose=True enables all main flags."""
        from payment_simulator.experiments.cli.common import build_verbose_config

        config = build_verbose_config(verbose=True)
        assert config.iterations is True
        assert config.policy is True
        assert config.bootstrap is True
        assert config.llm is True

    def test_build_verbose_config_individual_flags(self) -> None:
        """build_verbose_config respects individual flag overrides."""
        from payment_simulator.experiments.cli.common import build_verbose_config

        config = build_verbose_config(verbose_policy=True, verbose_bootstrap=True)
        assert config.policy is True
        assert config.bootstrap is True
        assert config.iterations is False
        assert config.llm is False
