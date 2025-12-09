"""Integration tests for AI Cash Management database persistence.

TDD: These tests are written BEFORE the implementation.
Tests database integration for game sessions, policy iterations, and diffs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import duckdb


class TestGameSessionPersistence:
    """Test game session persistence to database."""

    def test_game_session_persisted_to_database(self, tmp_path: Path) -> None:
        """Should persist game session metadata to database."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create a game session record
            session = GameSessionRecord(
                game_id="test_game_001",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A", "BANK_B"],
                config_json=json.dumps({"key": "value"}),
            )

            # Persist
            repo.save_game_session(session)

            # Retrieve
            retrieved = repo.get_game_session("test_game_001")

            assert retrieved is not None
            assert retrieved.game_id == "test_game_001"
            assert retrieved.master_seed == 42
            assert retrieved.game_mode == "rl_optimization"
            assert retrieved.optimized_agents == ["BANK_A", "BANK_B"]

    def test_game_session_update_status(self, tmp_path: Path) -> None:
        """Should update game session status."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create and save
            session = GameSessionRecord(
                game_id="test_game_002",
                scenario_config="scenarios/test.yaml",
                master_seed=123,
                game_mode="campaign_learning",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Update status
            repo.update_game_session_status(
                game_id="test_game_002",
                status="completed",
                completed_at=datetime.now(),
            )

            # Verify
            retrieved = repo.get_game_session("test_game_002")
            assert retrieved is not None
            assert retrieved.status == "completed"
            assert retrieved.completed_at is not None


class TestPolicyIterationTracking:
    """Test policy iteration tracking in database."""

    def test_policy_iterations_tracked_correctly(self, tmp_path: Path) -> None:
        """Should track policy iterations with metrics."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session first
            session = GameSessionRecord(
                game_id="test_game_003",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Create policy iteration
            iteration = PolicyIterationRecord(
                game_id="test_game_003",
                agent_id="BANK_A",
                iteration_number=1,
                trigger_tick=50,
                old_policy_json=json.dumps({"version": "1.0"}),
                new_policy_json=json.dumps({"version": "2.0"}),
                old_cost=1000.0,
                new_cost=800.0,
                cost_improvement=200.0,
                was_accepted=True,
                validation_errors=[],
                llm_model="openai/gpt-5.1",
                llm_latency_seconds=1.5,
                tokens_used=500,
                created_at=datetime.now(),
            )
            repo.save_policy_iteration(iteration)

            # Retrieve
            iterations = repo.get_policy_iterations("test_game_003", "BANK_A")

            assert len(iterations) == 1
            assert iterations[0].iteration_number == 1
            assert iterations[0].old_cost == 1000.0
            assert iterations[0].new_cost == 800.0
            assert iterations[0].was_accepted is True

    def test_policy_iterations_track_llm_model_used(self, tmp_path: Path) -> None:
        """Should track which LLM model was used for each iteration."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_004",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A", "BANK_B"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Save iterations with different LLM models (different agents)
            repo.save_policy_iteration(
                PolicyIterationRecord(
                    game_id="test_game_004",
                    agent_id="BANK_A",
                    iteration_number=1,
                    trigger_tick=50,
                    old_policy_json="{}",
                    new_policy_json="{}",
                    old_cost=1000.0,
                    new_cost=900.0,
                    cost_improvement=100.0,
                    was_accepted=True,
                    validation_errors=[],
                    llm_model="openai/gpt-5.1",
                    llm_latency_seconds=1.2,
                    tokens_used=400,
                    created_at=datetime.now(),
                )
            )

            repo.save_policy_iteration(
                PolicyIterationRecord(
                    game_id="test_game_004",
                    agent_id="BANK_B",
                    iteration_number=1,
                    trigger_tick=50,
                    old_policy_json="{}",
                    new_policy_json="{}",
                    old_cost=1200.0,
                    new_cost=1100.0,
                    cost_improvement=100.0,
                    was_accepted=True,
                    validation_errors=[],
                    llm_model="anthropic/claude-3-opus",
                    llm_latency_seconds=2.0,
                    tokens_used=600,
                    created_at=datetime.now(),
                )
            )

            # Retrieve and verify models tracked
            bank_a_iters = repo.get_policy_iterations("test_game_004", "BANK_A")
            bank_b_iters = repo.get_policy_iterations("test_game_004", "BANK_B")

            assert bank_a_iters[0].llm_model == "openai/gpt-5.1"
            assert bank_b_iters[0].llm_model == "anthropic/claude-3-opus"

    def test_multiple_iterations_for_same_agent(self, tmp_path: Path) -> None:
        """Should track multiple iterations per agent."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_005",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Save multiple iterations
            for i in range(5):
                repo.save_policy_iteration(
                    PolicyIterationRecord(
                        game_id="test_game_005",
                        agent_id="BANK_A",
                        iteration_number=i + 1,
                        trigger_tick=50 * (i + 1),
                        old_policy_json="{}",
                        new_policy_json="{}",
                        old_cost=1000.0 - (i * 50),
                        new_cost=950.0 - (i * 50),
                        cost_improvement=50.0,
                        was_accepted=True,
                        validation_errors=[],
                        llm_model="openai/gpt-5.1",
                        llm_latency_seconds=1.0,
                        tokens_used=400,
                        created_at=datetime.now(),
                    )
                )

            # Retrieve all iterations
            iterations = repo.get_policy_iterations("test_game_005", "BANK_A")

            assert len(iterations) == 5
            assert iterations[0].iteration_number == 1
            assert iterations[4].iteration_number == 5


class TestPolicyDiffTracking:
    """Test policy diff computation and storage."""

    def test_policy_diffs_computed_and_stored(self, tmp_path: Path) -> None:
        """Should compute and store diffs between policy versions."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_006",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Policies with diffs
            old_policy = {
                "version": "1.0",
                "parameters": {"urgency_threshold": 5.0, "liquidity_buffer": 1.0},
            }
            new_policy = {
                "version": "2.0",
                "parameters": {"urgency_threshold": 4.0, "liquidity_buffer": 1.2},
            }

            iteration = PolicyIterationRecord(
                game_id="test_game_006",
                agent_id="BANK_A",
                iteration_number=1,
                trigger_tick=50,
                old_policy_json=json.dumps(old_policy),
                new_policy_json=json.dumps(new_policy),
                old_cost=1000.0,
                new_cost=850.0,
                cost_improvement=150.0,
                was_accepted=True,
                validation_errors=[],
                llm_model="openai/gpt-5.1",
                llm_latency_seconds=1.5,
                tokens_used=500,
                created_at=datetime.now(),
            )
            repo.save_policy_iteration(iteration)

            # Retrieve and verify policies stored correctly
            iterations = repo.get_policy_iterations("test_game_006", "BANK_A")
            assert len(iterations) == 1

            # Parse stored JSON
            stored_old = json.loads(iterations[0].old_policy_json)
            stored_new = json.loads(iterations[0].new_policy_json)

            assert stored_old["parameters"]["urgency_threshold"] == 5.0
            assert stored_new["parameters"]["urgency_threshold"] == 4.0
            assert stored_new["parameters"]["liquidity_buffer"] == 1.2


class TestDatabaseSharing:
    """Test that ai_cash_mgmt shares database with main SimCash."""

    def test_game_shares_database_with_simcash(self, tmp_path: Path) -> None:
        """Game tables should coexist with SimCash tables in same database."""
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "shared.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()

            # Main SimCash tables should exist
            result = manager.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone()
            # Note: DuckDB uses different introspection
            tables = manager.conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]

            assert "transactions" in table_names
            assert "simulation_runs" in table_names

            # Initialize game repository (creates game tables)
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Now game tables should also exist
            tables_after = manager.conn.execute("SHOW TABLES").fetchall()
            table_names_after = [t[0] for t in tables_after]

            assert "game_sessions" in table_names_after
            assert "policy_iterations" in table_names_after

            # Original tables still exist
            assert "transactions" in table_names_after


class TestMonteCarloNonPersistence:
    """Test that Monte Carlo evaluation results are NOT persisted."""

    def test_monte_carlo_results_not_persisted(self, tmp_path: Path) -> None:
        """Monte Carlo evaluation runs should not be saved to database."""
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Check there is no monte_carlo_runs or evaluation_runs table
            tables = manager.conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]

            # These tables should NOT exist (Monte Carlo is ephemeral)
            assert "monte_carlo_runs" not in table_names
            assert "evaluation_runs" not in table_names
            assert "mc_samples" not in table_names

            # The repository should not have methods for persisting MC results
            assert not hasattr(repo, "save_monte_carlo_run")
            assert not hasattr(repo, "save_evaluation_run")


class TestValidationErrorTracking:
    """Test tracking of validation errors in policy iterations."""

    def test_validation_errors_stored_as_json(self, tmp_path: Path) -> None:
        """Validation errors should be stored and retrievable."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_007",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="running",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Iteration with validation errors (rejected)
            errors = [
                "Invalid parameter: urgency_threshold must be >= 0",
                "Unknown action: 'invalid_action' not allowed",
            ]
            iteration = PolicyIterationRecord(
                game_id="test_game_007",
                agent_id="BANK_A",
                iteration_number=1,
                trigger_tick=50,
                old_policy_json="{}",
                new_policy_json="{}",
                old_cost=1000.0,
                new_cost=1000.0,  # Same cost since rejected
                cost_improvement=0.0,
                was_accepted=False,
                validation_errors=errors,
                llm_model="openai/gpt-5.1",
                llm_latency_seconds=1.0,
                tokens_used=300,
                created_at=datetime.now(),
            )
            repo.save_policy_iteration(iteration)

            # Retrieve and verify errors stored
            iterations = repo.get_policy_iterations("test_game_007", "BANK_A")
            assert len(iterations) == 1
            assert iterations[0].was_accepted is False
            assert len(iterations[0].validation_errors) == 2
            assert "Invalid parameter" in iterations[0].validation_errors[0]


class TestQueryInterface:
    """Test query interface for game results."""

    def test_list_game_sessions(self, tmp_path: Path) -> None:
        """Should list all game sessions."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create multiple sessions
            for i in range(3):
                session = GameSessionRecord(
                    game_id=f"game_{i:03d}",
                    scenario_config="scenarios/test.yaml",
                    master_seed=42 + i,
                    game_mode="rl_optimization",
                    started_at=datetime.now(),
                    status="completed" if i < 2 else "running",
                    optimized_agents=["BANK_A"],
                    config_json="{}",
                )
                repo.save_game_session(session)

            # List all
            sessions = repo.list_game_sessions()
            assert len(sessions) == 3

            # List by status
            completed = repo.list_game_sessions(status="completed")
            assert len(completed) == 2

            running = repo.list_game_sessions(status="running")
            assert len(running) == 1

    def test_get_best_policy_for_agent(self, tmp_path: Path) -> None:
        """Should retrieve the best policy for an agent."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_008",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="completed",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Save iterations with decreasing costs
            best_policy = {"version": "3.0", "optimal": True}
            for i in range(3):
                repo.save_policy_iteration(
                    PolicyIterationRecord(
                        game_id="test_game_008",
                        agent_id="BANK_A",
                        iteration_number=i + 1,
                        trigger_tick=50 * (i + 1),
                        old_policy_json="{}",
                        new_policy_json=json.dumps({"version": f"{i + 1}.0"})
                        if i < 2
                        else json.dumps(best_policy),
                        old_cost=1000.0 - (i * 100),
                        new_cost=900.0 - (i * 100),
                        cost_improvement=100.0,
                        was_accepted=True,
                        validation_errors=[],
                        llm_model="openai/gpt-5.1",
                        llm_latency_seconds=1.0,
                        tokens_used=400,
                        created_at=datetime.now(),
                    )
                )

            # Get best policy (lowest cost)
            best = repo.get_best_policy("test_game_008", "BANK_A")
            assert best is not None
            best_json = json.loads(best)
            assert best_json["version"] == "3.0"
            assert best_json["optimal"] is True

    def test_get_optimization_summary(self, tmp_path: Path) -> None:
        """Should get summary statistics for a game."""
        from payment_simulator.ai_cash_mgmt.persistence.models import (
            GameSessionRecord,
            PolicyIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.persistence.repository import (
            GameRepository,
        )
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        with DatabaseManager(db_path) as manager:
            manager.setup()
            repo = GameRepository(manager.conn)
            repo.initialize_schema()

            # Create game session
            session = GameSessionRecord(
                game_id="test_game_009",
                scenario_config="scenarios/test.yaml",
                master_seed=42,
                game_mode="rl_optimization",
                started_at=datetime.now(),
                status="completed",
                optimized_agents=["BANK_A"],
                config_json="{}",
            )
            repo.save_game_session(session)

            # Save iterations
            for i in range(5):
                repo.save_policy_iteration(
                    PolicyIterationRecord(
                        game_id="test_game_009",
                        agent_id="BANK_A",
                        iteration_number=i + 1,
                        trigger_tick=50 * (i + 1),
                        old_policy_json="{}",
                        new_policy_json="{}",
                        old_cost=1000.0 - (i * 50),
                        new_cost=950.0 - (i * 50),
                        cost_improvement=50.0,
                        was_accepted=True,
                        validation_errors=[],
                        llm_model="openai/gpt-5.1",
                        llm_latency_seconds=1.0 + (i * 0.1),
                        tokens_used=400 + (i * 10),
                        created_at=datetime.now(),
                    )
                )

            # Get summary
            summary = repo.get_optimization_summary("test_game_009")

            assert summary["total_iterations"] == 5
            assert summary["total_cost_improvement"] == 250.0  # 50 * 5
            assert summary["accepted_iterations"] == 5
            assert summary["rejected_iterations"] == 0
            assert "total_tokens_used" in summary
            assert "total_llm_latency" in summary
