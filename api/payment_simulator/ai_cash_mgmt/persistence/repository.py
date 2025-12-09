"""Database repository for AI Cash Management.

Provides database operations for game sessions and policy iterations.
Integrates with the main SimCash DuckDB database.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb

from payment_simulator.ai_cash_mgmt.persistence.models import (
    GameSessionRecord,
    PolicyIterationRecord,
)


class GameRepository:
    """Repository for AI Cash Management database operations.

    Provides CRUD operations for game sessions and policy iterations.
    Integrates with the main SimCash database connection.

    Example:
        >>> from payment_simulator.persistence.connection import DatabaseManager
        >>> with DatabaseManager("simulation.db") as manager:
        ...     repo = GameRepository(manager.conn)
        ...     repo.initialize_schema()
        ...     sessions = repo.list_game_sessions()
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Initialize repository with database connection.

        Args:
            conn: DuckDB connection from DatabaseManager
        """
        self._conn = conn

    def initialize_schema(self) -> None:
        """Initialize AI Cash Management database tables.

        Creates game_sessions and policy_iterations tables if they don't exist.
        Safe to call multiple times (uses IF NOT EXISTS).
        """
        # Create game_sessions table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS game_sessions (
                game_id VARCHAR PRIMARY KEY,
                scenario_config VARCHAR NOT NULL,
                master_seed BIGINT NOT NULL,
                game_mode VARCHAR NOT NULL,
                config_json VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                status VARCHAR NOT NULL,
                optimized_agents VARCHAR NOT NULL,
                total_iterations INTEGER DEFAULT 0,
                converged BOOLEAN DEFAULT FALSE,
                final_cost DOUBLE
            )
        """)

        # Create policy_iterations table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_iterations (
                game_id VARCHAR NOT NULL,
                agent_id VARCHAR NOT NULL,
                iteration_number INTEGER NOT NULL,
                trigger_tick INTEGER NOT NULL,
                old_policy_json VARCHAR NOT NULL,
                new_policy_json VARCHAR NOT NULL,
                old_cost DOUBLE NOT NULL,
                new_cost DOUBLE NOT NULL,
                cost_improvement DOUBLE NOT NULL,
                was_accepted BOOLEAN NOT NULL,
                validation_errors VARCHAR NOT NULL,
                llm_model VARCHAR NOT NULL,
                llm_latency_seconds DOUBLE NOT NULL,
                tokens_used INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (game_id, agent_id, iteration_number)
            )
        """)

        # Create indexes
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_status ON game_sessions(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_started_at ON game_sessions(started_at)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_iter_game ON policy_iterations(game_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_iter_agent ON policy_iterations(game_id, agent_id)
        """)

    # =========================================================================
    # Game Session Operations
    # =========================================================================

    def save_game_session(self, session: GameSessionRecord) -> None:
        """Save or update a game session.

        Args:
            session: GameSessionRecord to persist
        """
        # Serialize optimized_agents list to JSON
        agents_json = json.dumps(session.optimized_agents)

        self._conn.execute(
            """
            INSERT OR REPLACE INTO game_sessions (
                game_id, scenario_config, master_seed, game_mode,
                config_json, started_at, completed_at, status,
                optimized_agents, total_iterations, converged, final_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session.game_id,
                session.scenario_config,
                session.master_seed,
                session.game_mode,
                session.config_json,
                session.started_at,
                session.completed_at,
                session.status,
                agents_json,
                session.total_iterations,
                session.converged,
                session.final_cost,
            ],
        )

    def get_game_session(self, game_id: str) -> GameSessionRecord | None:
        """Retrieve a game session by ID.

        Args:
            game_id: Game session identifier

        Returns:
            GameSessionRecord if found, None otherwise
        """
        result = self._conn.execute(
            "SELECT * FROM game_sessions WHERE game_id = ?",
            [game_id],
        ).fetchone()

        if result is None:
            return None

        return self._row_to_game_session(result)

    def update_game_session_status(
        self,
        game_id: str,
        status: str,
        completed_at: datetime | None = None,
        total_iterations: int | None = None,
        converged: bool | None = None,
        final_cost: float | None = None,
    ) -> None:
        """Update game session status and completion fields.

        Args:
            game_id: Game session identifier
            status: New status value
            completed_at: Completion timestamp (optional)
            total_iterations: Total iterations count (optional)
            converged: Whether game converged (optional)
            final_cost: Final aggregate cost (optional)
        """
        updates = ["status = ?"]
        params: list[Any] = [status]

        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        if total_iterations is not None:
            updates.append("total_iterations = ?")
            params.append(total_iterations)

        if converged is not None:
            updates.append("converged = ?")
            params.append(converged)

        if final_cost is not None:
            updates.append("final_cost = ?")
            params.append(final_cost)

        params.append(game_id)

        # Field names are hardcoded above, not from user input
        self._conn.execute(
            f"UPDATE game_sessions SET {', '.join(updates)} WHERE game_id = ?",  # noqa: S608
            params,
        )

    def list_game_sessions(
        self,
        status: str | None = None,
        game_mode: str | None = None,
        limit: int = 100,
    ) -> list[GameSessionRecord]:
        """List game sessions with optional filtering.

        Args:
            status: Filter by status (optional)
            game_mode: Filter by game mode (optional)
            limit: Maximum results to return

        Returns:
            List of GameSessionRecord matching filters
        """
        query = "SELECT * FROM game_sessions WHERE 1=1"
        params: list[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status)

        if game_mode is not None:
            query += " AND game_mode = ?"
            params.append(game_mode)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        results = self._conn.execute(query, params).fetchall()
        return [self._row_to_game_session(row) for row in results]

    def _row_to_game_session(self, row: tuple[Any, ...]) -> GameSessionRecord:
        """Convert database row to GameSessionRecord."""
        # Column order matches CREATE TABLE
        return GameSessionRecord(
            game_id=row[0],
            scenario_config=row[1],
            master_seed=row[2],
            game_mode=row[3],
            config_json=row[4],
            started_at=row[5],
            completed_at=row[6],
            status=row[7],
            optimized_agents=json.loads(row[8]),
            total_iterations=row[9],
            converged=row[10],
            final_cost=row[11],
        )

    # =========================================================================
    # Policy Iteration Operations
    # =========================================================================

    def save_policy_iteration(self, iteration: PolicyIterationRecord) -> None:
        """Save a policy iteration record.

        Args:
            iteration: PolicyIterationRecord to persist
        """
        # Serialize validation_errors list to JSON
        errors_json = json.dumps(iteration.validation_errors)

        self._conn.execute(
            """
            INSERT OR REPLACE INTO policy_iterations (
                game_id, agent_id, iteration_number, trigger_tick,
                old_policy_json, new_policy_json, old_cost, new_cost,
                cost_improvement, was_accepted, validation_errors,
                llm_model, llm_latency_seconds, tokens_used, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                iteration.game_id,
                iteration.agent_id,
                iteration.iteration_number,
                iteration.trigger_tick,
                iteration.old_policy_json,
                iteration.new_policy_json,
                iteration.old_cost,
                iteration.new_cost,
                iteration.cost_improvement,
                iteration.was_accepted,
                errors_json,
                iteration.llm_model,
                iteration.llm_latency_seconds,
                iteration.tokens_used,
                iteration.created_at,
            ],
        )

    def get_policy_iterations(
        self,
        game_id: str,
        agent_id: str | None = None,
    ) -> list[PolicyIterationRecord]:
        """Get policy iterations for a game/agent.

        Args:
            game_id: Game session identifier
            agent_id: Agent identifier (optional, filters by agent)

        Returns:
            List of PolicyIterationRecord ordered by iteration_number
        """
        if agent_id is not None:
            query = """
                SELECT * FROM policy_iterations
                WHERE game_id = ? AND agent_id = ?
                ORDER BY iteration_number
            """
            results = self._conn.execute(query, [game_id, agent_id]).fetchall()
        else:
            query = """
                SELECT * FROM policy_iterations
                WHERE game_id = ?
                ORDER BY agent_id, iteration_number
            """
            results = self._conn.execute(query, [game_id]).fetchall()

        return [self._row_to_policy_iteration(row) for row in results]

    def get_best_policy(self, game_id: str, agent_id: str) -> str | None:
        """Get the best (lowest cost) accepted policy for an agent.

        Args:
            game_id: Game session identifier
            agent_id: Agent identifier

        Returns:
            Policy JSON string of the best accepted policy, or None if no accepted policies
        """
        result = self._conn.execute(
            """
            SELECT new_policy_json FROM policy_iterations
            WHERE game_id = ? AND agent_id = ? AND was_accepted = TRUE
            ORDER BY new_cost ASC
            LIMIT 1
            """,
            [game_id, agent_id],
        ).fetchone()

        if result is None:
            return None

        policy_json: str = result[0]
        return policy_json

    def _row_to_policy_iteration(self, row: tuple[Any, ...]) -> PolicyIterationRecord:
        """Convert database row to PolicyIterationRecord."""
        return PolicyIterationRecord(
            game_id=row[0],
            agent_id=row[1],
            iteration_number=row[2],
            trigger_tick=row[3],
            old_policy_json=row[4],
            new_policy_json=row[5],
            old_cost=row[6],
            new_cost=row[7],
            cost_improvement=row[8],
            was_accepted=row[9],
            validation_errors=json.loads(row[10]),
            llm_model=row[11],
            llm_latency_seconds=row[12],
            tokens_used=row[13],
            created_at=row[14],
        )

    # =========================================================================
    # Query Interface
    # =========================================================================

    def get_optimization_summary(self, game_id: str) -> dict[str, Any]:
        """Get summary statistics for a game's optimization.

        Args:
            game_id: Game session identifier

        Returns:
            Dictionary with summary statistics:
            - total_iterations: Total number of iterations
            - accepted_iterations: Number of accepted iterations
            - rejected_iterations: Number of rejected iterations
            - total_cost_improvement: Sum of cost improvements
            - total_tokens_used: Total LLM tokens consumed
            - total_llm_latency: Total LLM call time
        """
        result = self._conn.execute(
            """
            SELECT
                COUNT(*) as total_iterations,
                SUM(CASE WHEN was_accepted THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN NOT was_accepted THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN was_accepted THEN cost_improvement ELSE 0 END) as total_improvement,
                SUM(tokens_used) as total_tokens,
                SUM(llm_latency_seconds) as total_latency
            FROM policy_iterations
            WHERE game_id = ?
            """,
            [game_id],
        ).fetchone()

        if result is None or result[0] == 0:
            return {
                "total_iterations": 0,
                "accepted_iterations": 0,
                "rejected_iterations": 0,
                "total_cost_improvement": 0.0,
                "total_tokens_used": 0,
                "total_llm_latency": 0.0,
            }

        return {
            "total_iterations": result[0],
            "accepted_iterations": result[1],
            "rejected_iterations": result[2],
            "total_cost_improvement": result[3] or 0.0,
            "total_tokens_used": result[4] or 0,
            "total_llm_latency": result[5] or 0.0,
        }
