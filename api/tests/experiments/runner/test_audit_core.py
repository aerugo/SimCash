"""Tests for core audit display functions.

Task 14.3: TDD tests for display_audit_output and related functions.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from io import StringIO
from rich.console import Console


class TestAuditImport:
    """Tests for audit display importability."""

    def test_import_from_experiments_runner(self) -> None:
        """display_audit_output importable from experiments.runner."""
        from payment_simulator.experiments.runner import display_audit_output
        assert display_audit_output is not None

    def test_import_from_audit_module(self) -> None:
        """display_audit_output importable from audit module."""
        from payment_simulator.experiments.runner.audit import display_audit_output
        assert display_audit_output is not None


class TestDisplayAuditOutput:
    """Tests for display_audit_output function."""

    def test_displays_audit_header(self, tmp_path) -> None:
        """Audit display shows audit header."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output
        from payment_simulator.experiments.persistence import ExperimentRecord

        # Create test database with experiment
        repo = ExperimentRepository(tmp_path / "test.db")

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

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_audit_output(provider, console)

        result = output.getvalue()
        assert "AUDIT" in result or "test-run-123" in result

    def test_filters_to_llm_interaction_events(self, tmp_path) -> None:
        """Audit display filters to llm_interaction events."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output
        from payment_simulator.experiments.persistence import ExperimentRecord, EventRecord

        repo = ExperimentRepository(tmp_path / "test.db")

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

        # Save an LLM interaction event
        event = EventRecord(
            run_id="test-run-123",
            iteration=1,
            event_type="llm_interaction",
            event_data={
                "agent_id": "BANK_A",
                "system_prompt": "You are an expert...",
                "user_prompt": "Optimize this policy...",
                "raw_response": '{"parameters": {}}',
            },
            timestamp=datetime.now().isoformat(),
        )
        repo.save_event(event)

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        display_audit_output(provider, console)

        result = output.getvalue()
        assert "BANK_A" in result

    def test_respects_iteration_range(self, tmp_path) -> None:
        """Audit display respects start_iteration and end_iteration."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import display_audit_output
        from payment_simulator.experiments.persistence import ExperimentRecord, EventRecord

        repo = ExperimentRepository(tmp_path / "test.db")

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

        # Save events for multiple iterations
        for i in [1, 2, 3]:
            event = EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_interaction",
                event_data={"agent_id": f"BANK_{i}", "iteration": i},
                timestamp=datetime.now().isoformat(),
            )
            repo.save_event(event)

        provider = repo.as_state_provider("test-run-123")
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        # Only show iteration 2
        display_audit_output(provider, console, start_iteration=2, end_iteration=2)

        result = output.getvalue()
        # Should show iteration 2, but not 1 or 3
        assert "BANK_2" in result or "Iteration 2" in result


class TestFormatIterationHeader:
    """Tests for format_iteration_header function."""

    def test_format_iteration_header(self) -> None:
        """format_iteration_header returns formatted string."""
        from payment_simulator.experiments.runner.audit import format_iteration_header

        result = format_iteration_header(5)
        assert "5" in result
        assert "AUDIT" in result or "Iteration" in result


class TestFormatAgentSectionHeader:
    """Tests for format_agent_section_header function."""

    def test_format_agent_section_header(self) -> None:
        """format_agent_section_header returns formatted string."""
        from payment_simulator.experiments.runner.audit import format_agent_section_header

        result = format_agent_section_header("BANK_A")
        assert "BANK_A" in result


class TestDisplayLLMInteractionAudit:
    """Tests for display_llm_interaction_audit function."""

    def test_displays_model_info(self) -> None:
        """display_llm_interaction_audit shows model info."""
        from payment_simulator.experiments.runner.audit import display_llm_interaction_audit

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        event = {
            "event_type": "llm_interaction",
            "model": "anthropic:claude-sonnet-4-5",
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "latency_seconds": 2.5,
            "system_prompt": "You are an expert...",
            "user_prompt": "Optimize this...",
            "raw_response": '{"test": true}',
        }

        display_llm_interaction_audit(event, console)

        result = output.getvalue()
        assert "anthropic:claude-sonnet-4-5" in result


class TestDisplayValidationAudit:
    """Tests for display_validation_audit function."""

    def test_displays_validation_success(self) -> None:
        """display_validation_audit shows success for valid policy."""
        from payment_simulator.experiments.runner.audit import display_validation_audit

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        event = {
            "event_type": "llm_interaction",
            "parsed_policy": {"parameters": {}},
            "parsing_error": None,
        }

        display_validation_audit(event, console)

        result = output.getvalue()
        assert "valid" in result.lower() or "success" in result.lower() or "Validation" in result

    def test_displays_validation_error(self) -> None:
        """display_validation_audit shows error when parsing failed."""
        from payment_simulator.experiments.runner.audit import display_validation_audit

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True)

        event = {
            "event_type": "llm_interaction",
            "parsed_policy": None,
            "parsing_error": "Invalid JSON",
        }

        display_validation_audit(event, console)

        result = output.getvalue()
        assert "Invalid JSON" in result or "Error" in result
