"""Tests for ai-game show-reasoning CLI command.

Tests the CLI command for querying and displaying LLM reasoning
from the database.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from payment_simulator.ai_cash_mgmt.persistence.models import (
    GameSessionRecord,
    LLMInteractionRecord,
    PolicyIterationRecord,
)
from payment_simulator.ai_cash_mgmt.persistence.repository import GameRepository
from payment_simulator.cli.commands.ai_game import ai_game_app
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_db_with_reasoning(tmp_path: Path) -> Path:
    """Create database with sample LLM interactions including reasoning."""
    db_path = tmp_path / "test_reasoning.db"
    manager = DatabaseManager(db_path)
    manager.setup()

    try:
        repo = GameRepository(manager.conn)
        repo.initialize_schema()

        # Create game session
        session = GameSessionRecord(
            game_id="test_game",
            scenario_config="test.yaml",
            master_seed=12345,
            game_mode="rl_optimization",
            config_json="{}",
            started_at=datetime.now(),
            status="completed",
            optimized_agents=["BANK_A", "BANK_B"],
        )
        repo.save_game_session(session)

        # Create policy iterations
        for agent in ["BANK_A", "BANK_B"]:
            for i in range(1, 3):
                iter_record = PolicyIterationRecord(
                    game_id="test_game",
                    agent_id=agent,
                    iteration_number=i,
                    trigger_tick=100 * i,
                    old_policy_json='{"version": ' + str(i - 1) + "}",
                    new_policy_json='{"version": ' + str(i) + "}",
                    old_cost=1000.0,
                    new_cost=900.0,
                    cost_improvement=100.0,
                    was_accepted=True,
                    validation_errors=[],
                    llm_model="openai:o1",
                    llm_latency_seconds=2.0,
                    tokens_used=1000,
                    created_at=datetime.now(),
                )
                repo.save_policy_iteration(iter_record)

        # Create LLM interactions with reasoning
        now = datetime.now()

        # BANK_A iteration 1 - with reasoning
        repo.save_llm_interaction(
            LLMInteractionRecord(
                interaction_id="test_game_BANK_A_1",
                game_id="test_game",
                agent_id="BANK_A",
                iteration_number=1,
                system_prompt="System prompt",
                user_prompt="User prompt",
                raw_response='{"threshold": 3.0}',
                parsed_policy_json='{"threshold": 3.0}',
                parsing_error=None,
                llm_reasoning="I analyzed the payment queue and decided to lower the threshold.",
                request_timestamp=now,
                response_timestamp=now,
            )
        )

        # BANK_A iteration 2 - with longer reasoning
        repo.save_llm_interaction(
            LLMInteractionRecord(
                interaction_id="test_game_BANK_A_2",
                game_id="test_game",
                agent_id="BANK_A",
                iteration_number=2,
                system_prompt="System prompt",
                user_prompt="User prompt",
                raw_response='{"threshold": 2.5}',
                parsed_policy_json='{"threshold": 2.5}',
                parsing_error=None,
                llm_reasoning="After seeing the results, I refined the threshold further.",
                request_timestamp=now,
                response_timestamp=now,
            )
        )

        # BANK_B iteration 1 - no reasoning (model doesn't support it)
        repo.save_llm_interaction(
            LLMInteractionRecord(
                interaction_id="test_game_BANK_B_1",
                game_id="test_game",
                agent_id="BANK_B",
                iteration_number=1,
                system_prompt="System prompt",
                user_prompt="User prompt",
                raw_response='{"buffer": 0.2}',
                parsed_policy_json='{"buffer": 0.2}',
                parsing_error=None,
                llm_reasoning=None,
                request_timestamp=now,
                response_timestamp=now,
            )
        )

        # BANK_B iteration 2 - with parsing error but reasoning captured
        repo.save_llm_interaction(
            LLMInteractionRecord(
                interaction_id="test_game_BANK_B_2",
                game_id="test_game",
                agent_id="BANK_B",
                iteration_number=2,
                system_prompt="System prompt",
                user_prompt="User prompt",
                raw_response="Invalid JSON {broken",
                parsed_policy_json=None,
                parsing_error="JSONDecodeError",
                llm_reasoning="I tried to generate a policy but the output was malformed.",
                request_timestamp=now,
                response_timestamp=now,
            )
        )

    finally:
        manager.close()

    return db_path


class TestShowReasoningCommand:
    """Tests for show-reasoning command."""

    def test_show_all_reasoning_for_game(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Show all reasoning for a game."""
        result = runner.invoke(
            ai_game_app,
            ["show-reasoning", str(test_db_with_reasoning), "test_game"],
        )

        assert result.exit_code == 0
        assert "BANK_A" in result.output
        assert "BANK_B" in result.output
        assert "lower the threshold" in result.output
        assert "refined the threshold" in result.output

    def test_filter_by_agent(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Filter reasoning by agent ID."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "test_game",
                "-a",
                "BANK_A",
            ],
        )

        assert result.exit_code == 0
        assert "BANK_A" in result.output
        assert "BANK_B" not in result.output
        assert "lower the threshold" in result.output

    def test_filter_by_iteration(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Filter reasoning by iteration number."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "test_game",
                "-i",
                "1",
            ],
        )

        assert result.exit_code == 0
        assert "Iteration: 1" in result.output
        assert "Iteration: 2" not in result.output
        assert "lower the threshold" in result.output
        # Iteration 2 reasoning should not appear
        assert "refined the threshold" not in result.output

    def test_json_output_format(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Output reasoning as JSON."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "test_game",
                "-f",
                "json",
            ],
        )

        assert result.exit_code == 0

        # Extract JSON from output (may include database setup messages)
        # Find the JSON array in the output
        output_lines = result.output.strip().split("\n")
        json_start = None
        json_end = None
        for i, line in enumerate(output_lines):
            if line.strip().startswith("["):
                json_start = i
            if line.strip() == "]" and json_start is not None:
                json_end = i
                break

        assert json_start is not None, "No JSON array found in output"
        assert json_end is not None, "No JSON array end found in output"
        json_content = "\n".join(output_lines[json_start : json_end + 1])
        data = json.loads(json_content)

        assert len(data) == 4  # 4 interactions total
        assert data[0]["agent_id"] == "BANK_A"
        assert data[0]["llm_reasoning"] is not None

    def test_no_reasoning_message(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Show message when reasoning is None."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "test_game",
                "-a",
                "BANK_B",
                "-i",
                "1",
            ],
        )

        assert result.exit_code == 0
        assert "No reasoning captured" in result.output

    def test_show_parsing_error(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Show parsing errors alongside reasoning."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "test_game",
                "-a",
                "BANK_B",
                "-i",
                "2",
            ],
        )

        assert result.exit_code == 0
        assert "Parsing Error: JSONDecodeError" in result.output
        assert "malformed" in result.output

    def test_no_matches_message(
        self, runner: CliRunner, test_db_with_reasoning: Path
    ) -> None:
        """Show message when no interactions match criteria."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(test_db_with_reasoning),
                "nonexistent_game",
            ],
        )

        assert result.exit_code == 0
        assert "No LLM interactions found" in result.output

    def test_nonexistent_database(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Error when database doesn't exist."""
        result = runner.invoke(
            ai_game_app,
            [
                "show-reasoning",
                str(tmp_path / "nonexistent.db"),
                "test_game",
            ],
        )

        # Typer shows error for missing file (exists=True constraint)
        assert result.exit_code != 0
