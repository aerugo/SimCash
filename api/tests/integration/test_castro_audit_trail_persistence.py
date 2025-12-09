"""
TDD Cycle 2: Castro Audit Trail Repository Integration Tests

These tests define the requirements for saving and querying audit trail records.
Following the RED phase: these tests will fail until we implement the repository methods.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest

from payment_simulator.ai_cash_mgmt.persistence.models import (
    GameSessionRecord,
    IterationContextRecord,
    LLMInteractionRecord,
    PolicyDiffRecord,
    PolicyIterationRecord,
)
from payment_simulator.ai_cash_mgmt.persistence.repository import GameRepository
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def test_db(tmp_path: Path) -> Generator[DatabaseManager, None, None]:
    """Create temporary database with schema."""
    db_path = tmp_path / "test_castro_audit.db"
    manager = DatabaseManager(db_path)
    manager.setup()
    yield manager
    manager.close()


@pytest.fixture
def repository(test_db: DatabaseManager) -> GameRepository:
    """Create repository with initialized schema."""
    repo = GameRepository(test_db.conn)
    repo.initialize_schema()
    return repo


@pytest.fixture
def sample_game_session() -> GameSessionRecord:
    """Create a sample game session for foreign key reference."""
    return GameSessionRecord(
        game_id="test_game_001",
        scenario_config="test_scenario.yaml",
        master_seed=12345,
        game_mode="rl_optimization",
        config_json='{"agents": ["A", "B"]}',
        started_at=datetime.now(),
        status="running",
        optimized_agents=["A", "B"],
    )


@pytest.fixture
def sample_policy_iteration() -> PolicyIterationRecord:
    """Create a sample policy iteration for foreign key reference."""
    return PolicyIterationRecord(
        game_id="test_game_001",
        agent_id="A",
        iteration_number=1,
        trigger_tick=100,
        old_policy_json='{"version": 1}',
        new_policy_json='{"version": 2}',
        old_cost=1000.0,
        new_cost=800.0,
        cost_improvement=200.0,
        was_accepted=True,
        validation_errors=[],
        llm_model="anthropic/claude-3",
        llm_latency_seconds=2.5,
        tokens_used=1500,
        created_at=datetime.now(),
    )


class TestLLMInteractionSaveAndRetrieve:
    """Test save and retrieve operations for LLM interaction records."""

    def test_save_llm_interaction(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify LLM interaction can be saved."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        now = datetime.now()
        record = LLMInteractionRecord(
            interaction_id="test_game_001_A_1",
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            system_prompt="You are a policy optimizer.",
            user_prompt="Optimize this policy...",
            raw_response='{"policy": {...}}',
            parsed_policy_json='{"policy": {...}}',
            parsing_error=None,
            llm_reasoning="I optimized X because Y.",
            request_timestamp=now,
            response_timestamp=now,
        )

        # This should not raise
        repository.save_llm_interaction(record)

    def test_get_llm_interactions_by_game(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify LLM interactions can be retrieved by game_id."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        now = datetime.now()
        record = LLMInteractionRecord(
            interaction_id="test_game_001_A_1",
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response="Raw response",
            parsed_policy_json='{"policy": {}}',
            parsing_error=None,
            llm_reasoning=None,
            request_timestamp=now,
            response_timestamp=now,
        )
        repository.save_llm_interaction(record)

        results = repository.get_llm_interactions("test_game_001")
        assert len(results) == 1
        assert results[0].interaction_id == "test_game_001_A_1"
        assert results[0].system_prompt == "System prompt"

    def test_get_llm_interactions_by_agent(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
    ) -> None:
        """Verify LLM interactions can be filtered by agent_id."""
        repository.save_game_session(sample_game_session)

        # Create policy iterations for two agents
        for agent_id, iteration in [("A", 1), ("B", 1)]:
            iter_record = PolicyIterationRecord(
                game_id="test_game_001",
                agent_id=agent_id,
                iteration_number=iteration,
                trigger_tick=100,
                old_policy_json='{"version": 1}',
                new_policy_json='{"version": 2}',
                old_cost=1000.0,
                new_cost=800.0,
                cost_improvement=200.0,
                was_accepted=True,
                validation_errors=[],
                llm_model="anthropic/claude-3",
                llm_latency_seconds=2.5,
                tokens_used=1500,
                created_at=datetime.now(),
            )
            repository.save_policy_iteration(iter_record)

        now = datetime.now()
        for agent_id in ["A", "B"]:
            record = LLMInteractionRecord(
                interaction_id=f"test_game_001_{agent_id}_1",
                game_id="test_game_001",
                agent_id=agent_id,
                iteration_number=1,
                system_prompt=f"Prompt for {agent_id}",
                user_prompt=f"User prompt for {agent_id}",
                raw_response="Response",
                parsed_policy_json=None,
                parsing_error=None,
                llm_reasoning=None,
                request_timestamp=now,
                response_timestamp=now,
            )
            repository.save_llm_interaction(record)

        # Filter by agent A only
        results = repository.get_llm_interactions("test_game_001", agent_id="A")
        assert len(results) == 1
        assert results[0].agent_id == "A"

    def test_get_failed_parsing_attempts(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify failed parsing attempts can be queried."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        now = datetime.now()
        # One successful, one failed
        success_record = LLMInteractionRecord(
            interaction_id="test_game_001_A_1_success",
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            system_prompt="System",
            user_prompt="User",
            raw_response='{"valid": "json"}',
            parsed_policy_json='{"valid": "json"}',
            parsing_error=None,
            llm_reasoning=None,
            request_timestamp=now,
            response_timestamp=now,
        )
        failed_record = LLMInteractionRecord(
            interaction_id="test_game_001_A_1_failed",
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            system_prompt="System",
            user_prompt="User",
            raw_response="Invalid JSON response",
            parsed_policy_json=None,
            parsing_error="JSONDecodeError: Expecting value",
            llm_reasoning=None,
            request_timestamp=now,
            response_timestamp=now,
        )
        repository.save_llm_interaction(success_record)
        repository.save_llm_interaction(failed_record)

        results = repository.get_failed_parsing_attempts("test_game_001")
        assert len(results) == 1
        assert results[0].interaction_id == "test_game_001_A_1_failed"
        assert results[0].parsing_error is not None


class TestPolicyDiffSaveAndRetrieve:
    """Test save and retrieve operations for policy diff records."""

    def test_save_policy_diff(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify policy diff can be saved."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        record = PolicyDiffRecord(
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            diff_summary="Changed 'threshold': 5.0 → 3.0 (↓2.00)",
            parameter_changes_json='[{"param": "threshold", "old": 5.0, "new": 3.0}]',
            payment_tree_changed=False,
            collateral_tree_changed=True,
            parameters_snapshot_json='{"threshold": 3.0}',
        )

        # This should not raise
        repository.save_policy_diff(record)

    def test_get_policy_diffs_by_game(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify policy diffs can be retrieved by game_id."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        record = PolicyDiffRecord(
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            diff_summary="Test diff summary",
            parameter_changes_json='[]',
            payment_tree_changed=True,
            collateral_tree_changed=False,
            parameters_snapshot_json='{"x": 1}',
        )
        repository.save_policy_diff(record)

        results = repository.get_policy_diffs("test_game_001")
        assert len(results) == 1
        assert results[0].diff_summary == "Test diff summary"
        assert results[0].payment_tree_changed is True

    def test_get_parameter_trajectory(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
    ) -> None:
        """Verify parameter values can be extracted across iterations."""
        repository.save_game_session(sample_game_session)

        # Create multiple iterations with evolving parameter
        for iteration in range(1, 4):
            iter_record = PolicyIterationRecord(
                game_id="test_game_001",
                agent_id="A",
                iteration_number=iteration,
                trigger_tick=100 * iteration,
                old_policy_json='{}',
                new_policy_json='{}',
                old_cost=1000.0,
                new_cost=800.0,
                cost_improvement=200.0,
                was_accepted=True,
                validation_errors=[],
                llm_model="anthropic/claude-3",
                llm_latency_seconds=2.5,
                tokens_used=1500,
                created_at=datetime.now(),
            )
            repository.save_policy_iteration(iter_record)

            # Parameter value evolves: 5.0 -> 4.0 -> 3.0
            param_value = 6.0 - iteration
            diff_record = PolicyDiffRecord(
                game_id="test_game_001",
                agent_id="A",
                iteration_number=iteration,
                diff_summary=f"Iteration {iteration}",
                parameter_changes_json=None,
                payment_tree_changed=False,
                collateral_tree_changed=False,
                parameters_snapshot_json=json.dumps({
                    "threshold": param_value,
                    "buffer": 0.5,
                }),
            )
            repository.save_policy_diff(diff_record)

        trajectory = repository.get_parameter_trajectory(
            "test_game_001", "A", "threshold"
        )
        assert trajectory == [(1, 5.0), (2, 4.0), (3, 3.0)]


class TestIterationContextSaveAndRetrieve:
    """Test save and retrieve operations for iteration context records."""

    def test_save_iteration_context(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify iteration context can be saved."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        record = IterationContextRecord(
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            monte_carlo_seeds="[123, 456, 789]",
            num_samples=3,
            best_seed=123,
            worst_seed=789,
            best_seed_cost=100.5,
            worst_seed_cost=500.0,
            best_seed_verbose_output="Best seed output...",
            worst_seed_verbose_output="Worst seed output...",
            cost_mean=250.0,
            cost_std=150.0,
            settlement_rate_mean=0.95,
        )

        # This should not raise
        repository.save_iteration_context(record)

    def test_get_iteration_contexts_by_game(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify iteration contexts can be retrieved by game_id."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        record = IterationContextRecord(
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            monte_carlo_seeds="[123, 456]",
            num_samples=2,
            best_seed=123,
            worst_seed=456,
            best_seed_cost=100.0,
            worst_seed_cost=200.0,
            best_seed_verbose_output=None,
            worst_seed_verbose_output=None,
            cost_mean=150.0,
            cost_std=50.0,
            settlement_rate_mean=0.90,
        )
        repository.save_iteration_context(record)

        results = repository.get_iteration_contexts("test_game_001")
        assert len(results) == 1
        assert results[0].num_samples == 2
        assert results[0].best_seed == 123
        assert results[0].cost_mean == 150.0

    def test_iteration_context_with_large_verbose_output(
        self,
        repository: GameRepository,
        sample_game_session: GameSessionRecord,
        sample_policy_iteration: PolicyIterationRecord,
    ) -> None:
        """Verify large verbose outputs are stored correctly."""
        repository.save_game_session(sample_game_session)
        repository.save_policy_iteration(sample_policy_iteration)

        # Simulate large verbose output (10KB+)
        large_output = "=" * 50000

        record = IterationContextRecord(
            game_id="test_game_001",
            agent_id="A",
            iteration_number=1,
            monte_carlo_seeds="[123]",
            num_samples=1,
            best_seed=123,
            worst_seed=123,
            best_seed_cost=100.0,
            worst_seed_cost=100.0,
            best_seed_verbose_output=large_output,
            worst_seed_verbose_output=large_output,
            cost_mean=100.0,
            cost_std=0.0,
            settlement_rate_mean=1.0,
        )
        repository.save_iteration_context(record)

        results = repository.get_iteration_contexts("test_game_001")
        assert len(results) == 1
        assert len(results[0].best_seed_verbose_output or "") == 50000


class TestAuditTableSchema:
    """Test that audit tables are created with initialize_schema."""

    def test_initialize_schema_creates_audit_tables(
        self, repository: GameRepository
    ) -> None:
        """Verify initialize_schema creates all audit tables."""
        # Query DuckDB to check tables exist
        conn = repository._conn

        tables_result = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
        table_names = [row[0] for row in tables_result]

        assert "llm_interaction_log" in table_names
        assert "policy_diffs" in table_names
        assert "iteration_context" in table_names

    def test_audit_tables_have_correct_columns(
        self, repository: GameRepository
    ) -> None:
        """Verify audit tables have expected columns."""
        conn = repository._conn

        # Check llm_interaction_log columns
        llm_cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'llm_interaction_log'"
        ).fetchall()
        llm_col_names = [row[0] for row in llm_cols]

        expected_llm_cols = [
            "interaction_id", "game_id", "agent_id", "iteration_number",
            "system_prompt", "user_prompt", "raw_response",
            "parsed_policy_json", "parsing_error", "llm_reasoning",
            "request_timestamp", "response_timestamp",
        ]
        for col in expected_llm_cols:
            assert col in llm_col_names, f"Missing column: {col}"

        # Check policy_diffs columns
        diff_cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'policy_diffs'"
        ).fetchall()
        diff_col_names = [row[0] for row in diff_cols]

        expected_diff_cols = [
            "game_id", "agent_id", "iteration_number",
            "diff_summary", "parameter_changes_json",
            "payment_tree_changed", "collateral_tree_changed",
            "parameters_snapshot_json",
        ]
        for col in expected_diff_cols:
            assert col in diff_col_names, f"Missing column: {col}"

        # Check iteration_context columns
        ctx_cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'iteration_context'"
        ).fetchall()
        ctx_col_names = [row[0] for row in ctx_cols]

        expected_ctx_cols = [
            "game_id", "agent_id", "iteration_number",
            "monte_carlo_seeds", "num_samples",
            "best_seed", "worst_seed",
            "best_seed_cost", "worst_seed_cost",
            "best_seed_verbose_output", "worst_seed_verbose_output",
            "cost_mean", "cost_std", "settlement_rate_mean",
        ]
        for col in expected_ctx_cols:
            assert col in ctx_col_names, f"Missing column: {col}"
