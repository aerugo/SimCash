"""Experiment repository for DuckDB persistence.

Implements the Repository protocol for storing and retrieving
experiment data in DuckDB.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import duckdb

from experiments.castro.castro.core.types import ValidationErrorSummary
from experiments.castro.castro.db.schema import SCHEMA_SQL

if TYPE_CHECKING:
    from experiments.castro.prompts.context import IterationRecord


def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def extract_parameters(policy: dict[str, Any]) -> dict[str, Any]:
    """Extract parameters from policy JSON."""
    return policy.get("parameters", {})


class ExperimentRepository:
    """DuckDB-based repository for experiment tracking.

    Implements the Repository protocol. Provides persistent storage for:
    - Experiment configuration
    - Policy iterations
    - LLM interactions
    - Simulation runs
    - Iteration metrics
    - Validation errors

    Usage:
        repo = ExperimentRepository("results/exp1.db")
        repo.record_experiment_config(...)
        repo.record_policy_iteration(...)
        repo.close()
    """

    def __init__(self, db_path: str) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        for stmt in SCHEMA_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.conn.execute(stmt)

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    # =========================================================================
    # Write Operations
    # =========================================================================

    def record_experiment_config(
        self,
        experiment_id: str,
        experiment_name: str,
        config_yaml: str,
        cost_rates: dict[str, int | float],
        agent_configs: list[dict[str, str | int]],
        model_name: str,
        reasoning_effort: str,
        num_seeds: int,
        max_iterations: int,
        convergence_threshold: float,
        convergence_window: int,
        master_seed: int,
        seed_matrix: dict[int, list[int]],
        notes: str | None = None,
    ) -> None:
        """Record experiment configuration."""
        self.conn.execute(
            """
            INSERT INTO experiment_config VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                experiment_id,
                experiment_name,
                datetime.now(),
                config_yaml,
                compute_hash(config_yaml),
                json.dumps(cost_rates),
                json.dumps(agent_configs),
                model_name,
                reasoning_effort,
                num_seeds,
                max_iterations,
                convergence_threshold,
                convergence_window,
                master_seed,
                json.dumps(seed_matrix),
                notes,
            ],
        )

    def record_policy_iteration(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        policy_json: str,
        created_by: str = "init",
        was_accepted: bool = True,
        is_best: bool = False,
    ) -> str:
        """Record a policy iteration.

        Args:
            experiment_id: Experiment identifier
            iteration_number: Iteration number
            agent_id: Agent identifier (BANK_A or BANK_B)
            policy_json: JSON string of the policy
            created_by: Who created this policy (init, llm, manual)
            was_accepted: Whether this policy was accepted (improved over best)
            is_best: Whether this is the best policy discovered so far

        Returns:
            Generated iteration_id
        """
        iteration_id = str(uuid.uuid4())
        policy_dict = json.loads(policy_json)
        parameters = extract_parameters(policy_dict)

        self.conn.execute(
            """
            INSERT INTO policy_iterations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                iteration_id,
                experiment_id,
                iteration_number,
                agent_id,
                policy_json,
                compute_hash(policy_json),
                json.dumps(parameters),
                datetime.now(),
                created_by,
                was_accepted,
                is_best,
            ],
        )
        return iteration_id

    def record_llm_interaction(
        self,
        experiment_id: str,
        iteration_number: int,
        prompt_text: str,
        response_text: str,
        model_name: str,
        reasoning_effort: str,
        tokens_used: int,
        latency_seconds: float,
        error_message: str | None = None,
    ) -> str:
        """Record an LLM interaction.

        Returns:
            Generated interaction_id
        """
        interaction_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO llm_interactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                interaction_id,
                experiment_id,
                iteration_number,
                prompt_text,
                compute_hash(prompt_text),
                response_text,
                compute_hash(response_text),
                model_name,
                reasoning_effort,
                tokens_used,
                latency_seconds,
                datetime.now(),
                error_message,
            ],
        )
        return interaction_id

    def record_simulation_run(
        self,
        experiment_id: str,
        iteration_number: int,
        seed: int,
        result: dict[str, Any],
    ) -> str:
        """Record a simulation run.

        Returns:
            Generated run_id
        """
        run_id = str(uuid.uuid4())

        cost_breakdown = result.get("cost_breakdown", {})
        raw_output = result.get("raw_output", {})

        self.conn.execute(
            """
            INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                run_id,
                experiment_id,
                iteration_number,
                seed,
                int(result.get("total_cost", 0)),
                int(result.get("bank_a_cost", 0)),
                int(result.get("bank_b_cost", 0)),
                result.get("settlement_rate", 0.0),
                cost_breakdown.get("collateral", 0),
                cost_breakdown.get("delay", 0),
                cost_breakdown.get("overdraft", 0),
                cost_breakdown.get("eod_penalty", 0),
                int(result.get("bank_a_balance_end", 0)),
                int(result.get("bank_b_balance_end", 0)),
                raw_output.get("metrics", {}).get("total_arrivals", 0),
                raw_output.get("metrics", {}).get("total_settlements", 0),
                json.dumps(raw_output),
                result.get("verbose_log"),
                datetime.now(),
            ],
        )
        return run_id

    def record_iteration_metrics(
        self,
        experiment_id: str,
        iteration_number: int,
        metrics: dict[str, float | int],
        converged: bool = False,
        policy_was_accepted: bool = True,
        is_best_iteration: bool = False,
        comparison_to_best: str | None = None,
    ) -> str:
        """Record aggregated iteration metrics.

        Returns:
            Generated metric_id
        """
        metric_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO iteration_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                metric_id,
                experiment_id,
                iteration_number,
                metrics["total_cost_mean"],
                metrics["total_cost_std"],
                metrics["risk_adjusted_cost"],
                metrics["settlement_rate_mean"],
                metrics["failure_rate"],
                metrics["best_seed"],
                metrics["worst_seed"],
                int(metrics["best_seed_cost"]),
                int(metrics["worst_seed_cost"]),
                converged,
                policy_was_accepted,
                is_best_iteration,
                comparison_to_best,
                datetime.now(),
            ],
        )
        return metric_id

    def record_validation_error(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        attempt_number: int,
        policy: dict[str, Any],
        errors: list[str],
        was_fixed: bool,
        fix_attempt_count: int,
    ) -> str:
        """Record a policy validation error for learning purposes.

        Args:
            experiment_id: The experiment ID
            iteration_number: Current iteration
            agent_id: Bank A or Bank B
            attempt_number: 0 for initial, 1-3 for fix attempts
            policy: The invalid policy JSON
            errors: List of error messages from validator
            was_fixed: Whether this error was eventually fixed
            fix_attempt_count: Total number of fix attempts made

        Returns:
            Generated error_id
        """
        error_id = str(uuid.uuid4())
        error_category = self._categorize_error(errors)

        self.conn.execute(
            """
            INSERT INTO validation_errors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                error_id,
                experiment_id,
                iteration_number,
                agent_id,
                attempt_number,
                json.dumps(policy),
                json.dumps(errors),
                error_category,
                was_fixed,
                fix_attempt_count,
                datetime.now(),
            ],
        )
        return error_id

    def _categorize_error(self, errors: list[str]) -> str:
        """Categorize validation errors for analysis."""
        error_text = " ".join(errors).lower()

        # Check for error type prefix (format: [ErrorType] message)
        if "[parseerror]" in error_text:
            if "missing field" in error_text:
                return "MISSING_FIELD"
            elif "node_id" in error_text:
                return "MISSING_NODE_ID"
            else:
                return "PARSE_ERROR"
        elif "[validationerror]" in error_text:
            return "VALIDATION_ERROR"
        elif "[unknown]" in error_text:
            return "UNKNOWN_TYPE"

        # Check for common error patterns (fallback for untyped errors)
        if "custom_param" in error_text or "unknown parameter" in error_text:
            return "CUSTOM_PARAM"
        elif "unknown field" in error_text or "invalid field" in error_text:
            return "UNKNOWN_FIELD"
        elif "missing field" in error_text or "missing" in error_text:
            return "MISSING_FIELD"
        elif "node_id" in error_text:
            return "MISSING_NODE_ID"
        elif "schema" in error_text or "validation" in error_text:
            return "SCHEMA_ERROR"
        elif "operator" in error_text or "op" in error_text:
            return "INVALID_OPERATOR"
        elif "action" in error_text:
            return "INVALID_ACTION"
        elif "type" in error_text or "expected" in error_text:
            return "TYPE_ERROR"
        elif "cli error" in error_text:
            return "CLI_ERROR"
        else:
            return "UNKNOWN"

    # =========================================================================
    # Read Operations
    # =========================================================================

    def get_latest_policies(self, experiment_id: str) -> dict[str, dict[str, Any]]:
        """Get the latest policy for each agent."""
        result = self.conn.execute(
            """
            SELECT agent_id, policy_json
            FROM policy_iterations
            WHERE experiment_id = ?
            AND iteration_number = (
                SELECT MAX(iteration_number) FROM policy_iterations WHERE experiment_id = ?
            )
        """,
            [experiment_id, experiment_id],
        ).fetchall()

        return {row[0]: json.loads(row[1]) for row in result}

    def get_iteration_history(self, experiment_id: str) -> list[IterationRecord]:
        """Get complete iteration history with policies and changes.

        Returns a list of IterationRecord objects with:
        - Metrics for each iteration
        - Policies for each bank
        - Policy changes from previous iteration
        """
        from experiments.castro.prompts.context import IterationRecord, compute_policy_diff

        # Get all metrics
        metrics_rows = self.conn.execute(
            """
            SELECT iteration_number, total_cost_mean, total_cost_std, risk_adjusted_cost,
                   settlement_rate_mean, failure_rate, best_seed, worst_seed,
                   best_seed_cost, worst_seed_cost
            FROM iteration_metrics
            WHERE experiment_id = ?
            ORDER BY iteration_number
        """,
            [experiment_id],
        ).fetchall()

        # Get all policies
        policy_rows = self.conn.execute(
            """
            SELECT iteration_number, agent_id, policy_json
            FROM policy_iterations
            WHERE experiment_id = ?
            ORDER BY iteration_number
        """,
            [experiment_id],
        ).fetchall()

        # Build policy lookup: {iteration: {agent_id: policy}}
        policies_by_iter: dict[int, dict[str, dict[str, Any]]] = {}
        for row in policy_rows:
            iter_num = row[0]
            agent_id = row[1]
            policy = json.loads(row[2])
            if iter_num not in policies_by_iter:
                policies_by_iter[iter_num] = {}
            policies_by_iter[iter_num][agent_id] = policy

        # Build iteration records with diffs
        history: list[IterationRecord] = []
        prev_policy_a: dict[str, Any] | None = None
        prev_policy_b: dict[str, Any] | None = None

        for row in metrics_rows:
            iter_num = row[0]
            metrics = {
                "total_cost_mean": row[1],
                "total_cost_std": row[2],
                "risk_adjusted_cost": row[3],
                "settlement_rate_mean": row[4],
                "failure_rate": row[5],
                "best_seed": row[6],
                "worst_seed": row[7],
                "best_seed_cost": row[8],
                "worst_seed_cost": row[9],
            }

            # Get policies for this iteration
            iter_policies = policies_by_iter.get(iter_num, {})
            policy_a = iter_policies.get("BANK_A", {})
            policy_b = iter_policies.get("BANK_B", {})

            # Compute changes from previous iteration
            changes_a = compute_policy_diff(prev_policy_a, policy_a) if prev_policy_a else []
            changes_b = compute_policy_diff(prev_policy_b, policy_b) if prev_policy_b else []

            record = IterationRecord(
                iteration=iter_num,
                metrics=metrics,
                policy_a=policy_a,
                policy_b=policy_b,
                policy_a_changes=changes_a,
                policy_b_changes=changes_b,
            )
            history.append(record)

            # Update previous policies for next iteration's diff
            prev_policy_a = policy_a
            prev_policy_b = policy_b

        return history

    def get_verbose_output_for_seeds(
        self,
        experiment_id: str,
        iteration_number: int,
        seeds: list[int],
    ) -> dict[int, str]:
        """Get verbose output logs for specific seeds.

        Returns: {seed: verbose_log} for seeds that have verbose output.
        """
        placeholders = ",".join("?" * len(seeds))
        params = [experiment_id, iteration_number, *seeds]

        rows = self.conn.execute(
            f"""
            SELECT seed, verbose_log
            FROM simulation_runs
            WHERE experiment_id = ?
            AND iteration_number = ?
            AND seed IN ({placeholders})
            AND verbose_log IS NOT NULL
        """,
            params,
        ).fetchall()

        return {row[0]: row[1] for row in rows}

    def get_validation_error_summary(
        self,
        experiment_id: str | None = None,
    ) -> ValidationErrorSummary:
        """Get summary statistics for validation errors."""
        where_clause = "WHERE experiment_id = ?" if experiment_id else ""
        params = [experiment_id] if experiment_id else []

        # Total errors by category
        category_counts = self.conn.execute(
            f"""
            SELECT error_category, COUNT(*) as count
            FROM validation_errors
            {where_clause}
            GROUP BY error_category
            ORDER BY count DESC
        """,
            params,
        ).fetchall()

        # Fix success rate
        fix_stats = self.conn.execute(
            f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN was_fixed THEN 1 ELSE 0 END) as fixed,
                AVG(fix_attempt_count) as avg_attempts
            FROM validation_errors
            {where_clause}
            {"AND" if where_clause else "WHERE"} attempt_number = 0
        """,
            params,
        ).fetchone()

        # Errors by agent
        agent_counts = self.conn.execute(
            f"""
            SELECT agent_id, COUNT(*) as count
            FROM validation_errors
            {where_clause}
            GROUP BY agent_id
        """,
            params,
        ).fetchall()

        total = fix_stats[0] if fix_stats else 0
        fixed = fix_stats[1] if fix_stats else 0

        return {
            "by_category": {row[0]: row[1] for row in category_counts},
            "total_errors": total,
            "fixed_count": fixed,
            "fix_rate": (fixed / total * 100) if total > 0 else 0,
            "avg_fix_attempts": fix_stats[2] if fix_stats else 0,
            "by_agent": {row[0]: row[1] for row in agent_counts},
        }

    def export_summary(self) -> dict[str, Any]:
        """Export experiment summary for reproducibility."""
        experiments = self.conn.execute(
            """
            SELECT experiment_id, experiment_name, created_at,
                   model_name, num_seeds, max_iterations
            FROM experiment_config
        """
        ).fetchall()

        summary: dict[str, Any] = {
            "experiments": [],
            "exported_at": datetime.now().isoformat(),
        }

        for exp in experiments:
            exp_id = exp[0]
            iterations = self.conn.execute(
                """
                SELECT iteration_number, total_cost_mean, settlement_rate_mean,
                       failure_rate, converged
                FROM iteration_metrics
                WHERE experiment_id = ?
                ORDER BY iteration_number
            """,
                [exp_id],
            ).fetchall()

            summary["experiments"].append(
                {
                    "experiment_id": exp_id,
                    "experiment_name": exp[1],
                    "created_at": str(exp[2]),
                    "model_name": exp[3],
                    "num_seeds": exp[4],
                    "max_iterations": exp[5],
                    "iterations": [
                        {
                            "iteration": it[0],
                            "mean_cost": it[1],
                            "settlement_rate": it[2],
                            "failure_rate": it[3],
                            "converged": it[4],
                        }
                        for it in iterations
                    ],
                }
            )

        return summary
