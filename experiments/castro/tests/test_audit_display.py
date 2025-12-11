"""TDD tests for audit display functions.

These tests are written BEFORE the implementation following TDD principles.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from typing import Any

import duckdb
import pytest
from rich.console import Console

from payment_simulator.ai_cash_mgmt.events import (
    EVENT_LLM_INTERACTION,
    create_llm_interaction_event,
)

from castro.event_compat import CastroEvent as ExperimentEvent
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord
from castro.state_provider import DatabaseExperimentProvider


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


@pytest.fixture
def console_capture() -> tuple[Console, StringIO]:
    """Create a console that captures output."""
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    return console, output


@pytest.fixture
def db_conn() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection."""
    return duckdb.connect(":memory:")


@pytest.fixture
def provider_with_data(db_conn: duckdb.DuckDBPyConnection) -> DatabaseExperimentProvider:
    """Create a provider with test data for audit display."""
    repo = ExperimentEventRepository(db_conn)
    repo.initialize_schema()

    # Create run record
    run_record = ExperimentRunRecord(
        run_id="test-audit-run",
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

    # Add LLM interaction events for multiple iterations and agents
    for iteration in range(1, 4):
        for agent_id in ["BANK_A", "BANK_B"]:
            event = create_llm_interaction_event(
                run_id="test-audit-run",
                iteration=iteration,
                agent_id=agent_id,
                system_prompt=f"You are a payment optimization expert. Agent: {agent_id}",
                user_prompt=f"Optimize the policy for {agent_id}. Current cost: ${iteration * 1000}",
                raw_response=f'{{"version": "2.0", "policy_id": "policy_{agent_id}_{iteration}"}}',
                parsed_policy={
                    "version": "2.0",
                    "policy_id": f"policy_{agent_id}_{iteration}",
                    "parameters": {"urgency_threshold": 3.0 - iteration * 0.5},
                },
                parsing_error=None,
                model="anthropic:claude-sonnet-4-5",
                prompt_tokens=500 + iteration * 100,
                completion_tokens=200 + iteration * 50,
                latency_seconds=1.5 + iteration * 0.2,
            )
            repo.save_event(event)

    return DatabaseExperimentProvider(conn=db_conn, run_id="test-audit-run")


class TestDisplayAuditOutput:
    """Test the main display_audit_output function."""

    def test_display_audit_output_exists(self) -> None:
        """display_audit_output function should be importable."""
        from castro.audit_display import display_audit_output

        assert display_audit_output is not None

    def test_display_audit_output_runs_without_error(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """display_audit_output should run without raising errors."""
        from castro.audit_display import display_audit_output

        console, _ = console_capture

        # Should not raise
        display_audit_output(
            provider=provider_with_data,
            console=console,
        )

    def test_display_audit_shows_iteration_header(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """Audit output should show iteration headers."""
        from castro.audit_display import display_audit_output

        console, output = console_capture

        display_audit_output(
            provider=provider_with_data,
            console=console,
            start_iteration=1,
            end_iteration=1,
        )

        text = strip_ansi(output.getvalue())
        assert "Iteration 1" in text or "ITERATION 1" in text

    def test_display_audit_shows_agent_sections(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """Audit output should show separate sections for each agent."""
        from castro.audit_display import display_audit_output

        console, output = console_capture

        display_audit_output(
            provider=provider_with_data,
            console=console,
            start_iteration=1,
            end_iteration=1,
        )

        text = strip_ansi(output.getvalue())
        assert "BANK_A" in text
        assert "BANK_B" in text

    def test_display_audit_filters_by_start(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """Audit output should respect --start filter."""
        from castro.audit_display import display_audit_output

        console, output = console_capture

        display_audit_output(
            provider=provider_with_data,
            console=console,
            start_iteration=2,
        )

        text = strip_ansi(output.getvalue())
        # Should contain iteration 2
        assert "Iteration 2" in text or "iteration 2" in text.lower()
        # Should also contain iteration 3 (no end specified)
        assert "Iteration 3" in text or "iteration 3" in text.lower()

    def test_display_audit_filters_by_end(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """Audit output should respect --end filter."""
        from castro.audit_display import display_audit_output

        console, output = console_capture

        display_audit_output(
            provider=provider_with_data,
            console=console,
            end_iteration=2,
        )

        text = strip_ansi(output.getvalue())
        # Should contain iterations 1 and 2
        assert "Iteration 1" in text or "iteration 1" in text.lower()
        assert "Iteration 2" in text or "iteration 2" in text.lower()

    def test_display_audit_filters_by_range(
        self,
        provider_with_data: DatabaseExperimentProvider,
        console_capture: tuple[Console, StringIO],
    ) -> None:
        """Audit output should respect --start and --end range filter."""
        from castro.audit_display import display_audit_output

        console, output = console_capture

        display_audit_output(
            provider=provider_with_data,
            console=console,
            start_iteration=2,
            end_iteration=2,
        )

        text = strip_ansi(output.getvalue())
        # Should only contain iteration 2
        assert "Iteration 2" in text or "iteration 2" in text.lower()


class TestDisplayAgentAudit:
    """Test display_agent_audit function."""

    def test_display_agent_audit_exists(self) -> None:
        """display_agent_audit function should be importable."""
        from castro.audit_display import display_agent_audit

        assert display_agent_audit is not None

    def test_display_agent_audit_shows_agent_header(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_agent_audit should show agent header."""
        from castro.audit_display import display_agent_audit

        console, output = console_capture

        # Create a test event
        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_agent_audit(event, console)

        text = strip_ansi(output.getvalue())
        assert "BANK_A" in text


class TestDisplayLlmInteractionAudit:
    """Test display_llm_interaction_audit function."""

    def test_display_llm_interaction_shows_system_prompt(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_llm_interaction_audit should show system prompt."""
        from castro.audit_display import display_llm_interaction_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="You are a payment optimization expert.",
            user_prompt="Optimize this policy.",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_llm_interaction_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show system prompt header and content
        assert "System Prompt" in text or "system prompt" in text.lower()
        assert "payment optimization expert" in text

    def test_display_llm_interaction_shows_user_prompt(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_llm_interaction_audit should show user prompt."""
        from castro.audit_display import display_llm_interaction_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="Please optimize the policy for BANK_A.",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_llm_interaction_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show user prompt header and content
        assert "User Prompt" in text or "user prompt" in text.lower()
        assert "optimize the policy" in text.lower()

    def test_display_llm_interaction_shows_raw_response(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_llm_interaction_audit should show raw response."""
        from castro.audit_display import display_llm_interaction_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response='{"version": "2.0", "policy_id": "test_policy_123"}',
            parsed_policy={"version": "2.0", "policy_id": "test_policy_123"},
            parsing_error=None,
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_llm_interaction_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show response header and content
        assert "Response" in text or "response" in text.lower()
        assert "test_policy_123" in text

    def test_display_llm_interaction_shows_model_info(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_llm_interaction_audit should show model information."""
        from castro.audit_display import display_llm_interaction_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,
            model="anthropic:claude-sonnet-4-5",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_seconds=2.5,
        )

        display_llm_interaction_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show model info
        assert "claude" in text.lower() or "anthropic" in text.lower()

    def test_display_llm_interaction_shows_token_counts(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_llm_interaction_audit should show token counts."""
        from castro.audit_display import display_llm_interaction_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,
            model="test-model",
            prompt_tokens=1234,
            completion_tokens=567,
            latency_seconds=2.5,
        )

        display_llm_interaction_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show token counts (format may vary)
        assert "1234" in text or "1,234" in text
        assert "567" in text


class TestDisplayValidationAudit:
    """Test display_validation_audit function for parsing errors."""

    def test_display_validation_shows_success(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_validation_audit should show success for valid policies."""
        from castro.audit_display import display_validation_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response='{"version": "2.0"}',
            parsed_policy={"version": "2.0"},
            parsing_error=None,  # No error
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_validation_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should indicate success
        assert "valid" in text.lower() or "success" in text.lower() or "✓" in output.getvalue()

    def test_display_validation_shows_error(
        self, console_capture: tuple[Console, StringIO]
    ) -> None:
        """display_validation_audit should show error for invalid policies."""
        from castro.audit_display import display_validation_audit

        console, output = console_capture

        event = create_llm_interaction_event(
            run_id="test",
            iteration=1,
            agent_id="BANK_A",
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response="invalid json {{{",
            parsed_policy=None,  # Parsing failed
            parsing_error="Failed to parse policy JSON: JSONDecodeError",
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.0,
        )

        display_validation_audit(event, console)

        text = strip_ansi(output.getvalue())
        # Should show error
        assert (
            "error" in text.lower()
            or "invalid" in text.lower()
            or "failed" in text.lower()
        )
        assert "JSONDecodeError" in text or "parse" in text.lower()


class TestAuditDisplayHelpers:
    """Test helper functions in audit_display module."""

    def test_format_iteration_header(self) -> None:
        """format_iteration_header should format iteration numbers nicely."""
        from castro.audit_display import format_iteration_header

        header = format_iteration_header(1)
        assert "1" in header
        assert "Iteration" in header or "ITERATION" in header

    def test_format_agent_section_header(self) -> None:
        """format_agent_section_header should format agent IDs nicely."""
        from castro.audit_display import format_agent_section_header

        header = format_agent_section_header("BANK_A")
        assert "BANK_A" in header
