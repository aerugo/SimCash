"""TDD tests for Castro display using core ExperimentStateProviderProtocol.

Phase 13, Task 13.2: Update display to use core protocol.

Write these tests FIRST, then update display/audit_display to make them pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


def _get_display_source() -> str:
    """Get display.py source without importing (avoids dependency issues)."""
    display_path = Path(__file__).parent.parent / "castro" / "display.py"
    return display_path.read_text()


def _get_audit_display_source() -> str:
    """Get audit_display.py source without importing (avoids dependency issues)."""
    audit_path = Path(__file__).parent.parent / "castro" / "audit_display.py"
    return audit_path.read_text()


class TestDisplayImportsFromCore:
    """Tests verifying display.py imports ExperimentStateProviderProtocol from core."""

    def test_display_imports_state_provider_from_core(self) -> None:
        """display.py should import ExperimentStateProviderProtocol from core."""
        source = _get_display_source()

        # Should import from core
        assert "from payment_simulator.experiments.runner" in source
        assert "ExperimentStateProviderProtocol" in source

    def test_display_does_not_import_castro_state_provider(self) -> None:
        """display.py should NOT import ExperimentStateProvider from castro."""
        source = _get_display_source()

        # Should NOT import from castro.state_provider
        # The TYPE_CHECKING block should not have castro.state_provider
        assert "from castro.state_provider import ExperimentStateProvider" not in source


class TestAuditDisplayImportsFromCore:
    """Tests verifying audit_display.py imports from core."""

    def test_audit_display_imports_state_provider_from_core(self) -> None:
        """audit_display.py should import ExperimentStateProviderProtocol from core."""
        source = _get_audit_display_source()

        # Should import from core
        assert "from payment_simulator.experiments.runner" in source
        assert "ExperimentStateProviderProtocol" in source

    def test_audit_display_does_not_import_castro_state_provider(self) -> None:
        """audit_display.py should NOT import ExperimentStateProvider from castro."""
        source = _get_audit_display_source()

        # Should NOT import from castro.state_provider
        assert "from castro.state_provider import ExperimentStateProvider" not in source


class TestDisplayWorksWithCoreLiveProvider:
    """Tests verifying display works with core LiveStateProvider."""

    def test_display_experiment_output_accepts_core_provider(self) -> None:
        """display_experiment_output should accept core LiveStateProvider."""
        from payment_simulator.experiments.runner import LiveStateProvider
        from rich.console import Console

        # Import display function
        from castro.display import display_experiment_output

        # Create a core LiveStateProvider
        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="castro",
            config={"model": "test-model"},
            run_id="test-run-001",
        )

        # Record some test data
        provider.record_event(
            iteration=0,
            event_type="experiment_start",
            event_data={"experiment_name": "test_exp", "max_iterations": 10},
        )

        provider.set_final_result(
            final_cost=15000,
            best_cost=14000,
            converged=True,
            convergence_reason="stability",
        )

        # Should work without errors (use string capture for output)
        console = Console(file=None, force_terminal=False, record=True)
        display_experiment_output(provider, console)

        # Should have recorded some output
        output = console.export_text()
        assert "test-run-001" in output or "test_exp" in output


class TestAuditDisplayWorksWithCoreDatabaseProvider:
    """Tests verifying audit_display works with core DatabaseStateProvider."""

    def test_audit_display_accepts_core_provider(self, tmp_path: Path) -> None:
        """display_audit_output should accept core DatabaseStateProvider."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner import DatabaseStateProvider
        from rich.console import Console

        # Import audit display function
        from castro.audit_display import display_audit_output

        # Create test database
        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        # Save experiment
        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="test_exp",
            experiment_type="castro",
            config={"model": "anthropic:claude-sonnet-4-5"},
            created_at="2025-12-11T10:00:00",
            completed_at="2025-12-11T10:30:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )
        repo.save_experiment(exp_record)

        # Save LLM interaction event
        event = EventRecord(
            run_id="test-run-001",
            iteration=0,
            event_type="llm_interaction",
            event_data={
                "agent_id": "BANK_A",
                "model": "anthropic:claude-sonnet-4-5",
                "system_prompt": "You are a policy optimizer.",
                "user_prompt": "Current policy: {}",
                "raw_response": '{"policy_id": "new_policy"}',
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "latency_seconds": 2.5,
            },
            timestamp="2025-12-11T10:01:00",
        )
        repo.save_event(event)

        # Create provider
        provider = DatabaseStateProvider(repo, "test-run-001")

        # Should work without errors
        console = Console(file=None, force_terminal=False, record=True)
        display_audit_output(provider, console)

        # Should have recorded some output
        output = console.export_text()
        assert "AUDIT" in output or "BANK_A" in output

        repo.close()


class TestEventsAsDict:
    """Tests verifying display functions can handle dict events from core."""

    def test_display_handles_dict_events(self) -> None:
        """Display should handle events as dicts (not CastroEvent objects)."""
        from payment_simulator.experiments.runner import LiveStateProvider

        provider = LiveStateProvider(
            experiment_name="test_exp",
            experiment_type="castro",
            config={},
            run_id="test-run-001",
        )

        # Record event as dict (this is how core works)
        provider.record_event(
            iteration=0,
            event_type="experiment_start",
            event_data={"experiment_name": "test_exp"},
        )

        # Get events - should be dicts
        events = list(provider.get_all_events())
        assert len(events) == 1
        assert isinstance(events[0], dict)
        assert events[0]["event_type"] == "experiment_start"

    def test_audit_display_handles_dict_events(self, tmp_path: Path) -> None:
        """Audit display should handle events as dicts from core."""
        from payment_simulator.experiments.persistence import (
            EventRecord,
            ExperimentRecord,
            ExperimentRepository,
        )
        from payment_simulator.experiments.runner import DatabaseStateProvider

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)

        exp_record = ExperimentRecord(
            run_id="test-run-001",
            experiment_name="test_exp",
            experiment_type="castro",
            config={},
            created_at="2025-12-11T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(exp_record)

        # Get events from provider - should be dicts
        provider = DatabaseStateProvider(repo, "test-run-001")
        events = list(provider.get_all_events())

        # Events from core are dicts
        for event in events:
            assert isinstance(event, dict)

        repo.close()
