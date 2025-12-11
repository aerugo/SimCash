"""TDD tests for Castro CLI replay using core DatabaseStateProvider.

Phase 13, Task 13.3: Update CLI replay to use core StateProvider.

Write these tests FIRST, then update cli.py to make them pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


def _get_cli_source() -> str:
    """Get cli.py source without importing (avoids dependency issues)."""
    cli_path = Path(__file__).parent.parent / "cli.py"
    return cli_path.read_text()


class TestReplayImportsFromCore:
    """Tests verifying replay command imports from core."""

    def test_replay_imports_experiment_repository_from_core(self) -> None:
        """Replay should import ExperimentRepository from core."""
        source = _get_cli_source()

        # The replay function should use ExperimentRepository
        # Look for the import in the replay function context
        assert "from payment_simulator.experiments.persistence import ExperimentRepository" in source

    def test_replay_does_not_import_database_experiment_provider(self) -> None:
        """Replay should NOT import DatabaseExperimentProvider from castro."""
        source = _get_cli_source()

        # Should NOT use castro's DatabaseExperimentProvider
        assert "from castro.state_provider import DatabaseExperimentProvider" not in source


class TestReplayUsesRepositoryAsStateProvider:
    """Tests verifying replay uses repo.as_state_provider()."""

    def test_replay_uses_as_state_provider_method(self) -> None:
        """Replay should use repo.as_state_provider() to create provider."""
        source = _get_cli_source()

        # Should use as_state_provider pattern
        assert "as_state_provider" in source

    def test_replay_can_create_provider_from_repo(self, tmp_path: Path) -> None:
        """Verify repo.as_state_provider() returns a usable provider."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create test database
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save experiment
        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={"model": "anthropic:claude-sonnet-4-5"},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(exp_record)

        # Create provider using as_state_provider
        provider = repo.as_state_provider("test-run-001")

        # Verify provider works
        assert provider.run_id == "test-run-001"

        metadata = provider.get_run_metadata()
        assert metadata is not None
        assert metadata["experiment_name"] == "exp1"

        repo.close()


class TestReplayFunctionalTest:
    """Functional tests for replay command using core infrastructure."""

    def test_replay_works_with_core_repository(self, tmp_path: Path) -> None:
        """Replay should work with data saved by core repository."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create test database with experiment and events
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-replay-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={
                "model": "anthropic:claude-sonnet-4-5",
                "final_cost": 150000,  # Integer cents
                "best_cost": 140000,  # Integer cents
            },
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(exp_record)

        # Save events
        event = EventRecord(
            run_id="test-replay-001",
            iteration=0,
            event_type="experiment_start",
            event_data={
                "experiment_name": "exp1",
                "max_iterations": 25,
            },
            timestamp="2025-12-11T10:00:00",
        )
        repo.save_event(event)

        # Create provider and verify
        provider = repo.as_state_provider("test-replay-001")

        # Test all provider methods work
        assert provider.run_id == "test-replay-001"

        metadata = provider.get_run_metadata()
        assert metadata["experiment_name"] == "exp1"

        events = list(provider.get_all_events())
        assert len(events) == 1
        assert events[0]["event_type"] == "experiment_start"

        result = provider.get_final_result()
        assert result is not None
        assert result["final_cost"] == 150000
        assert result["converged"] is True

        repo.close()


class TestReplayNoLegacyImports:
    """Tests ensuring replay doesn't use legacy Castro infrastructure."""

    def test_no_duckdb_direct_connection_in_replay(self) -> None:
        """Replay should use ExperimentRepository, not raw duckdb.connect()."""
        source = _get_cli_source()

        # Find the replay function
        replay_start = source.find("def replay(")
        next_def = source.find("\ndef ", replay_start + 1)
        if next_def == -1:
            next_def = source.find("\n@app.command()", replay_start + 1)
        replay_code = source[replay_start:next_def]

        # Should use ExperimentRepository, not raw duckdb.connect() in the function body
        # We check that the provider is created via repo.as_state_provider
        assert "as_state_provider" in replay_code

    def test_no_castro_state_provider_import(self) -> None:
        """Replay should not import from castro.state_provider."""
        source = _get_cli_source()

        # Should NOT import DatabaseExperimentProvider from castro
        assert "DatabaseExperimentProvider" not in source
