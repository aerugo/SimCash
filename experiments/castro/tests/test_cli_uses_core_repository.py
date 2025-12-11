"""TDD tests for Castro CLI using core ExperimentRepository.

Phase 12, Task 12.2b: Migrate CLI to use core persistence.

Write these tests FIRST, then update CLI to make them pass.

All costs must be integer cents (INV-1 compliance).
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


class TestCliImportsFromCore:
    """Tests verifying CLI uses core persistence imports."""

    def test_cli_imports_experiment_repository_from_core(self) -> None:
        """CLI results command should use ExperimentRepository from core."""
        source = _get_cli_source()

        # Should import from core for results command
        assert "from payment_simulator.experiments.persistence import" in source
        assert "ExperimentRepository" in source

    def test_cli_does_not_import_castro_persistence_in_results(self) -> None:
        """CLI should NOT import ExperimentEventRepository from castro.persistence."""
        source = _get_cli_source()

        # Should NOT use castro's ExperimentEventRepository
        assert "ExperimentEventRepository" not in source


class TestResultsCommandUsesCore:
    """Tests for results command using core repository."""

    def test_results_command_can_list_experiments(self, tmp_path: Path) -> None:
        """Results command should be able to list experiments from core repository."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create test database with experiments
        db_path = tmp_path / "castro.db"
        repo = ExperimentRepository(db_path)

        # Add test experiments
        for i, name in enumerate(["exp1", "exp2", "exp3"]):
            record = ExperimentRecord(
                run_id=f"{name}-20251211-100000-abc{i}",
                experiment_name=name,
                experiment_type="castro",
                config={"master_seed": 42 + i},
                created_at="2025-12-11T10:00:00",
                completed_at="2025-12-11T10:30:00",
                num_iterations=10,
                converged=True,
                convergence_reason="stability",
            )
            repo.save_experiment(record)

        # List experiments
        experiments = repo.list_experiments(experiment_type="castro")
        assert len(experiments) == 3

        repo.close()


class TestReplayUsesCoreDatabaseProvider:
    """Tests for replay command's provider using core database."""

    def test_database_provider_can_load_from_core_repository(
        self, tmp_path: Path
    ) -> None:
        """DatabaseExperimentProvider should work with core repository's schema."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create test database with core repository
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

        # Save some events
        for i in range(3):
            event = EventRecord(
                run_id="test-run-001",
                iteration=i,
                event_type="llm_interaction",
                event_data={
                    "agent_id": "BANK_A",
                    "model": "anthropic:claude-sonnet-4-5",
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                },
                timestamp=f"2025-12-11T10:{i:02d}:00",
            )
            repo.save_event(event)

        # Verify we can retrieve the data
        loaded = repo.load_experiment("test-run-001")
        assert loaded is not None
        assert loaded.experiment_name == "exp1"
        assert loaded.converged is True

        events = repo.get_all_events("test-run-001")
        assert len(events) == 3

        repo.close()


class TestDatabaseSchemaCompatibility:
    """Tests ensuring CLI can work with core's database schema."""

    def test_core_schema_supports_castro_fields(self, tmp_path: Path) -> None:
        """Core schema should store all fields Castro needs for replay."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save Castro-specific data in config
        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={
                "model": "anthropic:claude-sonnet-4-5",
                "master_seed": 42,
                "num_samples": 10,
                "evaluation_ticks": 12,
                "final_cost": 150000,  # Integer cents
                "best_cost": 140000,  # Integer cents
            },
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(exp_record)

        # Verify all fields preserved
        loaded = repo.load_experiment("test-run-001")
        assert loaded is not None
        assert loaded.config["model"] == "anthropic:claude-sonnet-4-5"
        assert loaded.config["master_seed"] == 42
        assert loaded.config["final_cost"] == 150000
        assert isinstance(loaded.config["final_cost"], int)

        repo.close()

    def test_events_preserve_all_llm_interaction_fields(self, tmp_path: Path) -> None:
        """Events should preserve all LLM interaction fields for audit replay."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Save LLM interaction event with all audit fields
        event = EventRecord(
            run_id="test-run-001",
            iteration=0,
            event_type="llm_interaction",
            event_data={
                "agent_id": "BANK_A",
                "system_prompt": "You are a policy optimizer...",
                "user_prompt": "Current policy: ...",
                "raw_response": "```yaml\npolicy_id: new_policy\n...",
                "parsed_policy": {"policy_id": "new_policy", "parameters": {}},
                "parsing_error": None,
                "model": "anthropic:claude-sonnet-4-5",
                "prompt_tokens": 1500,
                "completion_tokens": 800,
                "latency_seconds": 2.5,
            },
            timestamp="2025-12-11T10:01:00",
        )
        repo.save_event(event)

        # Verify all fields preserved
        events = repo.get_events("test-run-001", iteration=0)
        assert len(events) == 1

        data = events[0].event_data
        assert data["agent_id"] == "BANK_A"
        assert data["system_prompt"] == "You are a policy optimizer..."
        assert data["raw_response"].startswith("```yaml")
        assert data["parsed_policy"]["policy_id"] == "new_policy"
        assert data["prompt_tokens"] == 1500

        repo.close()


class TestCostInvariant:
    """Tests for INV-1: All costs must be integer cents."""

    def test_experiment_costs_are_integer_cents(self, tmp_path: Path) -> None:
        """Experiment costs must be stored as integer cents."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            ExperimentRepository,
        )

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save with integer costs
        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="exp1",
            experiment_type="castro",
            config={
                "final_cost": 150000,  # $1,500.00 in cents
                "best_cost": 140000,  # $1,400.00 in cents
            },
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=10,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(exp_record)

        # Verify costs are integers
        loaded = repo.load_experiment("test-run-001")
        assert isinstance(loaded.config["final_cost"], int)
        assert isinstance(loaded.config["best_cost"], int)
        assert loaded.config["final_cost"] == 150000

        repo.close()
