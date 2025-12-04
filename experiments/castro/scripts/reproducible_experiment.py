#!/usr/bin/env python3
"""
Reproducible Experiment Runner for Castro et al. Replication

This script provides a fully reproducible experiment framework that:
1. Stores ALL policy iterations in a DuckDB database
2. Logs ALL LLM interactions (prompts and responses)
3. Records complete simulation results for each seed
4. Exports everything needed for third-party validation

Usage:
    python reproducible_experiment.py --experiment exp1 --output results.db
    python reproducible_experiment.py --experiment exp2_fixed --output results.db --max-iter 20
    python reproducible_experiment.py --replay results.db  # Reproduce from database

The resulting database contains:
- experiment_config: Full experiment configuration
- policy_iterations: Every policy version with hash
- llm_interactions: All prompts and responses
- simulation_runs: Results for every seed at every iteration
- iteration_metrics: Aggregated metrics per iteration

IMPORTANT: This runner NEVER modifies the seed policy files.
- Seed policies are read-only (loaded once at startup)
- Each iteration creates temporary policy files in the output directory
- All policy versions are stored in the database
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import matplotlib.pyplot as plt
import yaml
from dotenv import load_dotenv

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from experiments/castro/.env if it exists
CASTRO_ENV_PATH = Path(__file__).parent.parent / ".env"
if CASTRO_ENV_PATH.exists():
    load_dotenv(CASTRO_ENV_PATH)

from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS
from experiments.castro.prompts.context import (
    IterationRecord,
    SingleAgentIterationRecord,
    compute_policy_diff,
)


# ============================================================================
# Database Schema
# ============================================================================

SCHEMA_SQL = """
-- Experiment configuration
CREATE TABLE IF NOT EXISTS experiment_config (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    config_yaml TEXT NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    cost_rates JSON NOT NULL,
    agent_configs JSON NOT NULL,
    model_name VARCHAR NOT NULL,
    reasoning_effort VARCHAR NOT NULL,
    num_seeds INTEGER NOT NULL,
    max_iterations INTEGER NOT NULL,
    convergence_threshold DOUBLE NOT NULL,
    convergence_window INTEGER NOT NULL,
    master_seed INTEGER NOT NULL,
    seed_matrix JSON NOT NULL,
    notes TEXT
);

-- Policy iterations (every version of every policy)
CREATE TABLE IF NOT EXISTS policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    parameters JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR NOT NULL,  -- 'init', 'llm', 'manual'
    was_accepted BOOLEAN DEFAULT TRUE,  -- Was this policy kept (improved) or rejected?
    is_best BOOLEAN DEFAULT FALSE,  -- Is this the best policy discovered so far?
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- LLM interactions (prompts and responses)
CREATE TABLE IF NOT EXISTS llm_interactions (
    interaction_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    response_text TEXT NOT NULL,
    response_hash VARCHAR(64) NOT NULL,
    model_name VARCHAR NOT NULL,
    reasoning_effort VARCHAR NOT NULL,
    tokens_used INTEGER NOT NULL,
    latency_seconds DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    error_message TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Individual simulation runs
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    total_cost BIGINT NOT NULL,
    bank_a_cost BIGINT NOT NULL,
    bank_b_cost BIGINT NOT NULL,
    settlement_rate DOUBLE NOT NULL,
    collateral_cost BIGINT,
    delay_cost BIGINT,
    overdraft_cost BIGINT,
    eod_penalty BIGINT,
    bank_a_final_balance BIGINT,
    bank_b_final_balance BIGINT,
    total_arrivals INTEGER,
    total_settlements INTEGER,
    raw_output JSON NOT NULL,
    verbose_log TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Aggregated iteration metrics
CREATE TABLE IF NOT EXISTS iteration_metrics (
    metric_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    total_cost_mean DOUBLE NOT NULL,
    total_cost_std DOUBLE NOT NULL,
    risk_adjusted_cost DOUBLE NOT NULL,
    settlement_rate_mean DOUBLE NOT NULL,
    failure_rate DOUBLE NOT NULL,
    best_seed INTEGER NOT NULL,
    worst_seed INTEGER NOT NULL,
    best_seed_cost BIGINT NOT NULL,
    worst_seed_cost BIGINT NOT NULL,
    converged BOOLEAN NOT NULL DEFAULT FALSE,
    policy_was_accepted BOOLEAN DEFAULT TRUE,  -- Was this iteration's policy accepted?
    is_best_iteration BOOLEAN DEFAULT FALSE,  -- Is this the best iteration so far?
    comparison_to_best VARCHAR,  -- Human-readable comparison
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Policy validation errors (track all failures for learning)
CREATE TABLE IF NOT EXISTS validation_errors (
    error_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    attempt_number INTEGER NOT NULL,  -- 0 = initial, 1-3 = fix attempts
    policy_json TEXT NOT NULL,
    error_messages JSON NOT NULL,
    error_category VARCHAR,           -- Categorized error type
    was_fixed BOOLEAN NOT NULL,
    fix_attempt_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_policy_exp_iter ON policy_iterations(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_policy_hash ON policy_iterations(policy_hash);
CREATE INDEX IF NOT EXISTS idx_llm_exp_iter ON llm_interactions(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_sim_exp_iter ON simulation_runs(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_metrics_exp ON iteration_metrics(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_validation_errors_exp ON validation_errors(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_validation_errors_category ON validation_errors(error_category);
"""


# ============================================================================
# Experiment Definitions
# ============================================================================

EXPERIMENTS = {
    # Castro-aligned experiments (with deferred_crediting and deadline_cap_at_eod)
    "exp1": {
        "name": "Experiment 1: Two-Period Deterministic (Castro-Aligned)",
        "description": "2-period Nash equilibrium validation with deferred crediting",
        "config_path": "experiments/castro/configs/castro_2period_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 1,  # Deterministic - only need 1 seed
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
    },
    "exp2": {
        "name": "Experiment 2: Twelve-Period Stochastic (Castro-Aligned)",
        "description": "12-period LVTS-style with deferred crediting and EOD deadline cap",
        "config_path": "experiments/castro/configs/castro_12period_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 10,
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
    },
    "exp3": {
        "name": "Experiment 3: Joint Liquidity and Timing (Castro-Aligned)",
        "description": "3-period joint learning with deferred crediting",
        "config_path": "experiments/castro/configs/castro_joint_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 10,
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
    },
}


# ============================================================================
# Helper Functions
# ============================================================================

def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def load_yaml_config(path: str) -> dict:
    """Load YAML config file."""
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def load_json_policy(path: str) -> dict:
    """Load JSON policy file."""
    with open(path) as f:
        return json.load(f)


def save_json_policy(path: str, policy: dict) -> None:
    """Save JSON policy file."""
    with open(path, 'w') as f:
        json.dump(policy, f, indent=2)


def extract_parameters(policy: dict) -> dict:
    """Extract parameters from policy JSON."""
    return policy.get("parameters", {})


# ============================================================================
# Database Operations
# ============================================================================

class ExperimentDatabase:
    """Database wrapper for experiment tracking."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        # Execute each statement individually
        for stmt in SCHEMA_SQL.split(';'):
            stmt = stmt.strip()
            if stmt:
                self.conn.execute(stmt)

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def record_experiment_config(
        self,
        experiment_id: str,
        experiment_name: str,
        config_yaml: str,
        cost_rates: dict,
        agent_configs: list,
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
        self.conn.execute("""
            INSERT INTO experiment_config VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])

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
        """
        iteration_id = str(uuid.uuid4())
        policy_dict = json.loads(policy_json)
        parameters = extract_parameters(policy_dict)

        self.conn.execute("""
            INSERT INTO policy_iterations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])
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
        """Record an LLM interaction."""
        interaction_id = str(uuid.uuid4())

        self.conn.execute("""
            INSERT INTO llm_interactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])
        return interaction_id

    def record_simulation_run(
        self,
        experiment_id: str,
        iteration_number: int,
        seed: int,
        result: dict,
    ) -> str:
        """Record a simulation run."""
        run_id = str(uuid.uuid4())

        cost_breakdown = result.get("cost_breakdown", {})
        raw_output = result.get("raw_output", {})

        self.conn.execute("""
            INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])
        return run_id

    def record_iteration_metrics(
        self,
        experiment_id: str,
        iteration_number: int,
        metrics: dict,
        converged: bool = False,
        policy_was_accepted: bool = True,
        is_best_iteration: bool = False,
        comparison_to_best: str | None = None,
    ) -> str:
        """Record aggregated iteration metrics.

        Args:
            experiment_id: Experiment identifier
            iteration_number: Iteration number
            metrics: Dictionary of metrics
            converged: Whether the experiment has converged
            policy_was_accepted: Whether this iteration's policy was accepted
            is_best_iteration: Whether this is the best iteration so far
            comparison_to_best: Human-readable comparison to best policy
        """
        metric_id = str(uuid.uuid4())

        self.conn.execute("""
            INSERT INTO iteration_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])
        return metric_id

    def record_validation_error(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        attempt_number: int,
        policy: dict,
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
        """
        error_id = str(uuid.uuid4())

        # Categorize the error based on common patterns
        error_category = self._categorize_error(errors)

        self.conn.execute("""
            INSERT INTO validation_errors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])
        return error_id

    def _categorize_error(self, errors: list[str]) -> str:
        """Categorize validation errors for analysis."""
        error_text = " ".join(errors).lower()

        # Check for error type prefix (format: [ErrorType] message)
        if "[parseerror]" in error_text:
            # Parse errors are often about missing/invalid JSON structure
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

    def get_validation_error_summary(self, experiment_id: str | None = None) -> dict:
        """Get summary statistics for validation errors."""
        where_clause = "WHERE experiment_id = ?" if experiment_id else ""
        params = [experiment_id] if experiment_id else []

        # Total errors by category
        category_counts = self.conn.execute(f"""
            SELECT error_category, COUNT(*) as count
            FROM validation_errors
            {where_clause}
            GROUP BY error_category
            ORDER BY count DESC
        """, params).fetchall()

        # Fix success rate
        fix_stats = self.conn.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN was_fixed THEN 1 ELSE 0 END) as fixed,
                AVG(fix_attempt_count) as avg_attempts
            FROM validation_errors
            {where_clause}
            AND attempt_number = 0
        """, params).fetchone()

        # Errors by agent
        agent_counts = self.conn.execute(f"""
            SELECT agent_id, COUNT(*) as count
            FROM validation_errors
            {where_clause}
            GROUP BY agent_id
        """, params).fetchall()

        return {
            "by_category": {row[0]: row[1] for row in category_counts},
            "total_errors": fix_stats[0] if fix_stats else 0,
            "fixed_count": fix_stats[1] if fix_stats else 0,
            "fix_rate": (fix_stats[1] / fix_stats[0] * 100) if fix_stats and fix_stats[0] > 0 else 0,
            "avg_fix_attempts": fix_stats[2] if fix_stats else 0,
            "by_agent": {row[0]: row[1] for row in agent_counts},
        }

    def get_latest_policies(self, experiment_id: str) -> dict[str, dict]:
        """Get the latest policy for each agent."""
        result = self.conn.execute("""
            SELECT agent_id, policy_json
            FROM policy_iterations
            WHERE experiment_id = ?
            AND iteration_number = (
                SELECT MAX(iteration_number) FROM policy_iterations WHERE experiment_id = ?
            )
        """, [experiment_id, experiment_id]).fetchall()

        return {row[0]: json.loads(row[1]) for row in result}

    def get_iteration_history(self, experiment_id: str) -> list[IterationRecord]:
        """Get complete iteration history with policies and changes.

        Returns a list of IterationRecord objects with:
        - Metrics for each iteration
        - Policies for each bank
        - Policy changes from previous iteration
        """
        # Get all metrics
        metrics_rows = self.conn.execute("""
            SELECT iteration_number, total_cost_mean, total_cost_std, risk_adjusted_cost,
                   settlement_rate_mean, failure_rate, best_seed, worst_seed,
                   best_seed_cost, worst_seed_cost
            FROM iteration_metrics
            WHERE experiment_id = ?
            ORDER BY iteration_number
        """, [experiment_id]).fetchall()

        # Get all policies
        policy_rows = self.conn.execute("""
            SELECT iteration_number, agent_id, policy_json
            FROM policy_iterations
            WHERE experiment_id = ?
            ORDER BY iteration_number
        """, [experiment_id]).fetchall()

        # Build policy lookup: {iteration: {agent_id: policy}}
        policies_by_iter: dict[int, dict[str, dict]] = {}
        for row in policy_rows:
            iter_num = row[0]
            agent_id = row[1]
            policy = json.loads(row[2])
            if iter_num not in policies_by_iter:
                policies_by_iter[iter_num] = {}
            policies_by_iter[iter_num][agent_id] = policy

        # Build iteration records with diffs
        history: list[IterationRecord] = []
        prev_policy_a: dict | None = None
        prev_policy_b: dict | None = None

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
        params = [experiment_id, iteration_number] + seeds

        rows = self.conn.execute(f"""
            SELECT seed, verbose_log
            FROM simulation_runs
            WHERE experiment_id = ?
            AND iteration_number = ?
            AND seed IN ({placeholders})
            AND verbose_log IS NOT NULL
        """, params).fetchall()

        return {row[0]: row[1] for row in rows}

    def export_summary(self) -> dict:
        """Export experiment summary for reproducibility."""
        experiments = self.conn.execute("""
            SELECT experiment_id, experiment_name, created_at,
                   model_name, num_seeds, max_iterations
            FROM experiment_config
        """).fetchall()

        summary = {
            "experiments": [],
            "exported_at": datetime.now().isoformat(),
        }

        for exp in experiments:
            exp_id = exp[0]
            iterations = self.conn.execute("""
                SELECT iteration_number, total_cost_mean, settlement_rate_mean,
                       failure_rate, converged
                FROM iteration_metrics
                WHERE experiment_id = ?
                ORDER BY iteration_number
            """, [exp_id]).fetchall()

            summary["experiments"].append({
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
            })

        return summary


# ============================================================================
# Chart Generation
# ============================================================================

def generate_cost_ribbon_chart(db_path: str, output_path: Path, experiment_name: str) -> None:
    """Generate a ribbon plot showing cost evolution over iterations.

    Creates a chart with:
    - Mean cost line (center)
    - Best cost line (lower bound)
    - Worst cost line (upper bound)
    - Filled ribbon between best and worst

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    conn = duckdb.connect(db_path, read_only=True)

    # Query iteration metrics
    data = conn.execute("""
        SELECT
            iteration_number,
            total_cost_mean,
            best_seed_cost,
            worst_seed_cost
        FROM iteration_metrics
        ORDER BY iteration_number
    """).fetchall()
    conn.close()

    if not data:
        print("  No iteration data found for chart generation")
        return

    # Extract data - deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, int, int]] = {}
    for row in data:
        iter_num, mean_cost, best_cost, worst_cost = row
        seen[iter_num] = (mean_cost, best_cost, worst_cost)

    iterations = sorted(seen.keys())
    mean_costs = [seen[i][0] for i in iterations]
    best_costs = [seen[i][1] for i in iterations]
    worst_costs = [seen[i][2] for i in iterations]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot the ribbon (filled area between best and worst)
    ax.fill_between(
        iterations,
        best_costs,
        worst_costs,
        alpha=0.3,
        color='steelblue',
        label='Best-Worst Range'
    )

    # Plot the lines
    ax.plot(
        iterations,
        worst_costs,
        'o-',
        color='indianred',
        linewidth=1.5,
        markersize=5,
        label='Worst Cost',
        alpha=0.8
    )
    ax.plot(
        iterations,
        mean_costs,
        'o-',
        color='steelblue',
        linewidth=2.5,
        markersize=7,
        label='Average Cost'
    )
    ax.plot(
        iterations,
        best_costs,
        'o-',
        color='seagreen',
        linewidth=1.5,
        markersize=5,
        label='Best Cost',
        alpha=0.8
    )

    # Find and annotate the best iteration
    min_mean_cost = min(mean_costs)
    best_iter_idx = mean_costs.index(min_mean_cost)
    best_iter = iterations[best_iter_idx]

    ax.annotate(
        f'Best Avg: ${min_mean_cost:,.0f}',
        xy=(best_iter, min_mean_cost),
        xytext=(best_iter + 1, min_mean_cost * 1.15),
        arrowprops=dict(arrowstyle='->', color='steelblue', lw=1.5),
        fontsize=11,
        fontweight='bold',
        color='steelblue'
    )

    # Formatting
    ax.set_xlabel('Iteration', fontsize=13)
    ax.set_ylabel('Total Cost ($)', fontsize=13)
    ax.set_title(f'Cost Over Iterations - {experiment_name}', fontsize=14, fontweight='bold')

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Legend
    ax.legend(loc='upper right', fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Set axis limits with some padding
    ax.set_xlim(min(iterations) - 0.5, max(iterations) + 0.5)
    y_min = min(best_costs) * 0.9
    y_max = max(worst_costs) * 1.1
    ax.set_ylim(y_min, y_max)

    # Add summary statistics as text box
    final_mean = mean_costs[-1]
    final_best = best_costs[-1]
    final_worst = worst_costs[-1]
    improvement = ((mean_costs[0] - min_mean_cost) / mean_costs[0] * 100) if mean_costs[0] > 0 else 0

    stats_text = (
        f"Final (Iter {iterations[-1]}):\n"
        f"  Avg: ${final_mean:,.0f}\n"
        f"  Best: ${final_best:,.0f}\n"
        f"  Worst: ${final_worst:,.0f}\n"
        f"Improvement: {improvement:.1f}%"
    )
    ax.text(
        0.02, 0.98, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Cost ribbon chart saved to: {output_path}")


def generate_settlement_rate_chart(db_path: str, output_path: Path, experiment_name: str) -> None:
    """Generate a chart showing settlement rate over iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    conn = duckdb.connect(db_path, read_only=True)

    # Query iteration metrics
    data = conn.execute("""
        SELECT
            iteration_number,
            settlement_rate_mean,
            failure_rate
        FROM iteration_metrics
        ORDER BY iteration_number
    """).fetchall()
    conn.close()

    if not data:
        print("  No iteration data found for settlement rate chart")
        return

    # Deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, float]] = {}
    for row in data:
        iter_num, settlement_rate, failure_rate = row
        seen[iter_num] = (settlement_rate, failure_rate)

    iterations = sorted(seen.keys())
    settlement_rates = [seen[i][0] * 100 for i in iterations]  # Convert to percentage
    failure_rates = [seen[i][1] * 100 for i in iterations]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot settlement rate
    ax.plot(
        iterations,
        settlement_rates,
        'o-',
        color='seagreen',
        linewidth=2.5,
        markersize=7,
        label='Settlement Rate'
    )

    # Plot failure rate if any failures exist
    if any(f > 0 for f in failure_rates):
        ax.plot(
            iterations,
            failure_rates,
            's--',
            color='indianred',
            linewidth=1.5,
            markersize=5,
            label='Failure Rate',
            alpha=0.8
        )

    # Formatting
    ax.set_xlabel('Iteration', fontsize=13)
    ax.set_ylabel('Rate (%)', fontsize=13)
    ax.set_title(f'Settlement Rate Over Iterations - {experiment_name}', fontsize=14, fontweight='bold')

    # Legend
    ax.legend(loc='lower right', fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Set axis limits
    ax.set_xlim(min(iterations) - 0.5, max(iterations) + 0.5)
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Settlement rate chart saved to: {output_path}")


def generate_per_agent_cost_chart(db_path: str, output_path: Path, experiment_name: str) -> None:
    """Generate a chart showing per-agent cost breakdown over iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    conn = duckdb.connect(db_path, read_only=True)

    # Query per-agent costs from simulation_runs
    data = conn.execute("""
        SELECT
            iteration_number,
            AVG(bank_a_cost) as avg_bank_a_cost,
            AVG(bank_b_cost) as avg_bank_b_cost,
            AVG(total_cost) as avg_total_cost
        FROM simulation_runs
        GROUP BY iteration_number
        ORDER BY iteration_number
    """).fetchall()
    conn.close()

    if not data:
        print("  No simulation run data found for per-agent cost chart")
        return

    iterations = [row[0] for row in data]
    bank_a_costs = [row[1] for row in data]
    bank_b_costs = [row[2] for row in data]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot stacked area chart
    ax.stackplot(
        iterations,
        bank_a_costs,
        bank_b_costs,
        labels=['BANK_A', 'BANK_B'],
        colors=['steelblue', 'coral'],
        alpha=0.7
    )

    # Formatting
    ax.set_xlabel('Iteration', fontsize=13)
    ax.set_ylabel('Cost ($)', fontsize=13)
    ax.set_title(f'Per-Agent Cost Breakdown - {experiment_name}', fontsize=14, fontweight='bold')

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Legend
    ax.legend(loc='upper right', fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Set axis limits
    ax.set_xlim(min(iterations), max(iterations))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Per-agent cost chart saved to: {output_path}")


def generate_acceptance_chart(db_path: str, output_path: Path, experiment_name: str) -> None:
    """Generate a chart showing accepted vs rejected iterations.

    Args:
        db_path: Path to the experiment database
        output_path: Path where the chart should be saved
        experiment_name: Name of the experiment for the chart title
    """
    conn = duckdb.connect(db_path, read_only=True)

    # Query iteration acceptance status
    data = conn.execute("""
        SELECT
            iteration_number,
            total_cost_mean,
            policy_was_accepted,
            is_best_iteration
        FROM iteration_metrics
        ORDER BY iteration_number
    """).fetchall()
    conn.close()

    if not data:
        print("  No iteration data found for acceptance chart")
        return

    # Deduplicate by taking last entry per iteration
    seen: dict[int, tuple[float, bool, bool]] = {}
    for row in data:
        iter_num, mean_cost, accepted, is_best = row
        seen[iter_num] = (mean_cost, accepted, is_best)

    iterations = sorted(seen.keys())
    mean_costs = [seen[i][0] for i in iterations]
    accepted = [seen[i][1] for i in iterations]
    is_best = [seen[i][2] for i in iterations]

    # Create the figure
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot all points
    for i, iter_num in enumerate(iterations):
        color = 'seagreen' if accepted[i] else 'indianred'
        marker = '*' if is_best[i] else 'o'
        size = 200 if is_best[i] else 80
        ax.scatter(iter_num, mean_costs[i], c=color, marker=marker, s=size, zorder=3)

    # Connect with line
    ax.plot(iterations, mean_costs, '-', color='gray', linewidth=1, alpha=0.5, zorder=1)

    # Add legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='seagreen', markersize=10, label='Accepted'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='indianred', markersize=10, label='Rejected'),
        Line2D([0], [0], marker='*', color='w', markerfacecolor='gold', markersize=15, label='Best'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=11)

    # Formatting
    ax.set_xlabel('Iteration', fontsize=13)
    ax.set_ylabel('Mean Cost ($)', fontsize=13)
    ax.set_title(f'Iteration Acceptance - {experiment_name}', fontsize=14, fontweight='bold')

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Count statistics
    num_accepted = sum(1 for a in accepted if a)
    num_rejected = sum(1 for a in accepted if not a)
    stats_text = f"Accepted: {num_accepted}\nRejected: {num_rejected}"
    ax.text(
        0.02, 0.98, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Acceptance chart saved to: {output_path}")


def generate_all_charts(db_path: str, output_dir: Path | None = None) -> None:
    """Generate all charts from an existing experiment database.

    Args:
        db_path: Path to the experiment database
        output_dir: Directory to save charts (default: same directory as database)
    """
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        print(f"Error: Database not found: {db_path}")
        return

    # Determine output directory
    if output_dir is None:
        output_dir = db_path_obj.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get experiment name from database
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        result = conn.execute("SELECT experiment_name FROM experiment_config LIMIT 1").fetchone()
        experiment_name = result[0] if result else "Unknown Experiment"
    except Exception:
        experiment_name = "Unknown Experiment"
    finally:
        conn.close()

    print(f"\nGenerating charts for: {experiment_name}")
    print(f"Output directory: {output_dir}")
    print("-" * 60)

    # Generate all charts
    generate_cost_ribbon_chart(
        db_path=str(db_path),
        output_path=output_dir / "cost_over_iterations.png",
        experiment_name=experiment_name,
    )

    generate_settlement_rate_chart(
        db_path=str(db_path),
        output_path=output_dir / "settlement_rate.png",
        experiment_name=experiment_name,
    )

    generate_per_agent_cost_chart(
        db_path=str(db_path),
        output_path=output_dir / "per_agent_costs.png",
        experiment_name=experiment_name,
    )

    generate_acceptance_chart(
        db_path=str(db_path),
        output_path=output_dir / "iteration_acceptance.png",
        experiment_name=experiment_name,
    )

    print("-" * 60)
    print(f"All charts generated in: {output_dir}")


# ============================================================================
# Simulation Runner
# ============================================================================


def get_per_agent_costs_from_db(db_path: str, simulation_id: str) -> dict[str, int]:
    """Query per-agent total costs from the simulation database.

    Each bank is selfish and only cares about their own costs, so we need
    to extract per-agent costs from the daily_agent_metrics table.

    Args:
        db_path: Path to simulation database file
        simulation_id: Simulation ID to query

    Returns:
        Dict mapping agent_id to their total_cost (in cents)
    """
    try:
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT agent_id, SUM(total_cost) as total_cost
            FROM daily_agent_metrics
            WHERE simulation_id = ?
            GROUP BY agent_id
        """
        result = conn.execute(query, [simulation_id]).fetchall()
        conn.close()
        return {row[0]: int(row[1]) for row in result}
    except Exception:
        # If database query fails, return empty dict
        return {}


def run_single_simulation(args: tuple) -> dict:
    """Run a single simulation with persistence for filtered replay.

    The simulation is run with --persist --full-replay to enable filtered
    replay of events per agent. This allows the LLM optimizer to see only
    events relevant to the bank whose policy it is optimizing.

    Args:
        args: Tuple of (config_path, simcash_root, seed, work_dir)
            - config_path: Path to simulation config YAML
            - simcash_root: Path to SimCash root directory
            - seed: Random seed for this simulation
            - work_dir: Directory for simulation database files

    Returns:
        Dict with simulation results including db_path and simulation_id
        for filtered replay.
    """
    config_path, simcash_root, seed, work_dir = args

    try:
        # Generate unique simulation ID for this run
        sim_id = f"castro_seed{seed}_{uuid.uuid4().hex[:8]}"
        db_path = Path(work_dir) / f"sim_{seed}.db"

        cmd = [
            str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
            "run",
            "--config", str(config_path),
            "--seed", str(seed),
            "--quiet",  # No verbose during run (we'll get it via replay)
            "--persist",  # Enable persistence for replay
            "--full-replay",  # Capture all data for filtered replay
            "--db-path", str(db_path),
            "--simulation-id", sim_id,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(simcash_root),
            timeout=120,  # Increased timeout for persistence overhead
        )

        if result.returncode != 0:
            return {"error": f"Simulation failed: {result.stderr}", "seed": seed}

        # Parse JSON output - extract JSON line from output
        # (persistence messages may precede the JSON on stdout)
        stdout_lines = result.stdout.strip().split('\n')
        json_line = None
        for line in stdout_lines:
            if line.strip().startswith('{'):
                json_line = line.strip()
                break
        if json_line is None:
            return {"error": f"No JSON output found in: {result.stdout[:200]}", "seed": seed}
        output = json.loads(json_line)

        costs = output.get("costs", {})
        agents = {a["id"]: a for a in output.get("agents", [])}

        total_cost = costs.get("total_cost", 0)

        # Get actual per-agent costs from database
        # Each bank is selfish and only cares about their own costs!
        per_agent_costs = get_per_agent_costs_from_db(str(db_path), sim_id)
        bank_a_cost = per_agent_costs.get("BANK_A", total_cost // 2)
        bank_b_cost = per_agent_costs.get("BANK_B", total_cost // 2)

        return {
            "seed": seed,
            "total_cost": total_cost,
            "bank_a_cost": bank_a_cost,
            "bank_b_cost": bank_b_cost,
            "settlement_rate": output.get("metrics", {}).get("settlement_rate", 0),
            "bank_a_balance_end": agents.get("BANK_A", {}).get("final_balance", 0),
            "bank_b_balance_end": agents.get("BANK_B", {}).get("final_balance", 0),
            "cost_breakdown": {
                "collateral": costs.get("total_collateral_cost", 0),
                "delay": costs.get("total_delay_cost", 0),
                "overdraft": costs.get("total_overdraft_cost", 0),
                "eod_penalty": costs.get("total_eod_penalty", 0),
            },
            "raw_output": output,
            # Include db_path and simulation_id for filtered replay
            "db_path": str(db_path),
            "simulation_id": sim_id,
        }
    except Exception as e:
        return {"error": str(e), "seed": seed}


def get_filtered_replay_output(
    simcash_root: str,
    db_path: str,
    simulation_id: str,
    agent_id: str,
) -> str:
    """Get filtered verbose output for a specific agent via replay.

    Uses the payment-sim replay command with --filter-agent to produce
    verbose output showing only events relevant to the specified agent.
    This ensures the LLM optimizer only sees events for the bank whose
    policy it is optimizing.

    Args:
        simcash_root: Path to SimCash root directory
        db_path: Path to simulation database file
        simulation_id: Simulation ID to replay
        agent_id: Agent ID to filter for (e.g., "BANK_A")

    Returns:
        Filtered verbose output string showing only events for the specified agent

    Raises:
        RuntimeError: If replay command fails
    """
    cmd = [
        str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
        "replay",
        "--simulation-id", simulation_id,
        "--db-path", db_path,
        "--verbose",
        "--filter-agent", agent_id,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(simcash_root),
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Replay failed for {agent_id}: {result.stderr}")

    return result.stdout


def run_simulations_parallel(
    config_path: str,
    simcash_root: str,
    seeds: list[int],
    work_dir: str | Path,
) -> list[dict]:
    """Run simulations in parallel with persistence.

    Simulations are run with --persist --full-replay to enable filtered
    replay per agent. Results include db_path and simulation_id for
    subsequent filtered replay.

    Args:
        config_path: Path to simulation config YAML
        simcash_root: Path to SimCash root directory
        seeds: List of random seeds to run
        work_dir: Directory for simulation database files

    Returns:
        List of result dicts sorted by seed
    """
    # Ensure work_dir exists
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    args_list = [
        (config_path, simcash_root, seed, str(work_dir))
        for seed in seeds
    ]

    results = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_single_simulation, args): args[2] for args in args_list}
        for future in as_completed(futures):
            results.append(future.result())

    return sorted(results, key=lambda x: x.get("seed", 0))


def compute_metrics(results: list[dict]) -> dict | None:
    """Compute aggregated metrics from simulation results.

    Returns None if all simulations failed, allowing caller to handle gracefully.

    IMPORTANT: Each bank is selfish and only cares about their own costs!
    This function computes per-bank cost metrics for independent policy evaluation.
    """
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        return None  # Let caller handle this gracefully

    costs = [r["total_cost"] for r in valid_results]
    settlements = [r["settlement_rate"] for r in valid_results]

    # Per-bank costs for selfish evaluation
    bank_a_costs = [r["bank_a_cost"] for r in valid_results]
    bank_b_costs = [r["bank_b_cost"] for r in valid_results]

    import statistics
    mean_cost = statistics.mean(costs)
    std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

    # Per-bank cost statistics
    bank_a_mean = statistics.mean(bank_a_costs)
    bank_a_std = statistics.stdev(bank_a_costs) if len(bank_a_costs) > 1 else 0
    bank_b_mean = statistics.mean(bank_b_costs)
    bank_b_std = statistics.stdev(bank_b_costs) if len(bank_b_costs) > 1 else 0

    best_idx = costs.index(min(costs))
    worst_idx = costs.index(max(costs))

    failures = sum(1 for r in valid_results if r["settlement_rate"] < 1.0)

    return {
        "total_cost_mean": mean_cost,
        "total_cost_std": std_cost,
        "risk_adjusted_cost": mean_cost + std_cost,
        "settlement_rate_mean": statistics.mean(settlements),
        "failure_rate": failures / len(valid_results),
        "best_seed": valid_results[best_idx]["seed"],
        "worst_seed": valid_results[worst_idx]["seed"],
        "best_seed_cost": min(costs),
        "worst_seed_cost": max(costs),
        # Per-bank metrics for selfish policy evaluation
        "bank_a_cost_mean": bank_a_mean,
        "bank_a_cost_std": bank_a_std,
        "bank_b_cost_mean": bank_b_mean,
        "bank_b_cost_std": bank_b_std,
    }


# ============================================================================
# LLM Optimizer (using PydanticAI via RobustPolicyAgent)
# ============================================================================

class LLMOptimizer:
    """LLM-based policy optimizer using PydanticAI structured output.

    This class wraps RobustPolicyAgent to generate validated policies
    using PydanticAI's structured output capabilities. This ensures:
    - Correct API usage for reasoning models (GPT-5.1, o1, etc.)
    - Structured JSON output with validation
    - Proper retry logic on validation failures
    - Extended thinking support for Anthropic Claude models
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        reasoning_effort: str = "high",
        thinking_budget: int | None = None,
        verbose: bool = False,
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.thinking_budget = thinking_budget
        self.verbose = verbose

        # Create RobustPolicyAgent with constraints
        # Use "high" reasoning for GPT-5.1, map string to literal
        effort_mapping = {"low": "low", "medium": "medium", "high": "high"}
        effort = effort_mapping.get(reasoning_effort, "high")

        self.agent = RobustPolicyAgent(
            constraints=STANDARD_CONSTRAINTS,
            model=model,
            reasoning_effort=effort,  # type: ignore
            thinking_budget=thinking_budget,
            verbose=verbose,
        )

        # Track last prompt for logging
        self._last_prompt: str = ""

    def create_prompt(
        self,
        experiment_name: str,
        iteration: int,
        policy_a: dict,
        policy_b: dict,
        metrics: dict,
        results: list[dict],
        cost_rates: dict,
    ) -> str:
        """Create optimization prompt for LLM."""
        prompt = f"""# Policy Optimization - {experiment_name} - Iteration {iteration}

## Current Performance
- Mean Cost: ${metrics['total_cost_mean']:,.0f} ± ${metrics['total_cost_std']:,.0f}
- Settlement Rate: {metrics['settlement_rate_mean']*100:.1f}%
- Best/Worst: ${metrics['best_seed_cost']:,.0f} / ${metrics['worst_seed_cost']:,.0f}

## Cost Rates
{json.dumps(cost_rates, indent=2)}

## Task
Generate an improved policy that reduces total cost while maintaining 100% settlement.
Focus on optimizing the trade-off between collateral costs and delay costs.
"""
        self._last_prompt = prompt
        return prompt

    def generate_policy(
        self,
        instruction: str,
        current_policy: dict | None = None,
        current_cost: float = 0,
        settlement_rate: float = 1.0,
        iteration: int = 0,
        # Extended context parameters
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> tuple[dict | None, int, float]:
        """Generate an optimized policy using PydanticAI with extended context.

        CRITICAL ISOLATION: This method receives ONLY the specified agent's data.
        The iteration_history must be pre-filtered to contain only this agent's
        policy history. No cross-agent information should be passed.

        Args:
            instruction: Natural language instruction for optimization
            current_policy: This agent's current policy
            current_cost: Approximate cost for this agent
            settlement_rate: Current settlement rate
            iteration: Current iteration number
            iteration_history: MUST be filtered for this agent only
            best_seed_output: Simulation output filtered for this agent
            worst_seed_output: Simulation output filtered for this agent
            best_seed: Best performing seed number
            worst_seed: Worst performing seed number
            best_seed_cost: Cost from best seed
            worst_seed_cost: Cost from worst seed
            cost_breakdown: Cost breakdown by type
            cost_rates: Cost rate configuration
            agent_id: Identifier of the agent being optimized (e.g., "BANK_A")

        Returns:
            tuple of (policy_dict or None, tokens_used, latency_seconds)
        """
        start_time = time.time()

        try:
            policy = self.agent.generate_policy(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
                # Pass through extended context - MUST be filtered for single agent
                iteration_history=iteration_history,
                best_seed_output=best_seed_output,
                worst_seed_output=worst_seed_output,
                best_seed=best_seed,
                worst_seed=worst_seed,
                best_seed_cost=best_seed_cost,
                worst_seed_cost=worst_seed_cost,
                cost_breakdown=cost_breakdown,
                cost_rates=cost_rates,
                agent_id=agent_id,
            )

            latency = time.time() - start_time
            # PydanticAI doesn't expose token counts directly in sync mode
            # We'll estimate based on typical response sizes
            tokens = 2000  # Rough estimate

            return policy, tokens, latency

        except Exception as e:
            latency = time.time() - start_time
            print(f"  Policy generation error: {e}")
            return None, 0, latency

    async def generate_policy_async(
        self,
        instruction: str,
        current_policy: dict | None = None,
        current_cost: float = 0,
        settlement_rate: float = 1.0,
        iteration: int = 0,
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
        stagger_delay: float = 0.0,
    ) -> tuple[dict | None, int, float]:
        """Async version of generate_policy for parallel execution.

        CRITICAL ISOLATION: Each agent's call is completely independent.
        No shared state between parallel calls.

        Args:
            stagger_delay: Initial delay before starting (for rate limit avoidance)
            ... (other args same as generate_policy)

        Returns:
            tuple of (policy_dict or None, tokens_used, latency_seconds)
        """
        # Apply staggered delay to avoid rate limits
        if stagger_delay > 0:
            await asyncio.sleep(stagger_delay)

        start_time = time.time()

        try:
            # Use the native async method from RobustPolicyAgent
            # This avoids nested asyncio.run() calls which cause "Event loop is closed" errors
            policy = await self.agent.generate_policy_async(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
                iteration_history=iteration_history,
                best_seed_output=best_seed_output,
                worst_seed_output=worst_seed_output,
                best_seed=best_seed,
                worst_seed=worst_seed,
                best_seed_cost=best_seed_cost,
                worst_seed_cost=worst_seed_cost,
                cost_breakdown=cost_breakdown,
                cost_rates=cost_rates,
                agent_id=agent_id,
            )

            latency = time.time() - start_time
            tokens = 2000  # Rough estimate

            return policy, tokens, latency

        except Exception as e:
            latency = time.time() - start_time
            print(f"  Policy generation error for {agent_id}: {e}")
            return None, 0, latency

    async def generate_policies_parallel(
        self,
        agent_configs: list[dict[str, Any]],
        stagger_interval: float = 0.5,
    ) -> list[tuple[str, dict | None, int, float]]:
        """Generate policies for multiple agents in parallel with staggered starts.

        CRITICAL ISOLATION: Each agent runs in complete isolation.
        - Separate coroutines with no shared state
        - Staggered starts to avoid rate limits
        - Independent error handling per agent

        Args:
            agent_configs: List of dicts, each containing:
                - agent_id: str (e.g., "BANK_A")
                - instruction: str
                - current_policy: dict
                - ... (all other generate_policy args)
            stagger_interval: Delay between starting each agent's call (seconds)

        Returns:
            List of (agent_id, policy, tokens, latency) tuples
        """
        tasks = []

        for i, config in enumerate(agent_configs):
            agent_id = config.pop("agent_id")
            stagger_delay = i * stagger_interval

            # Create task with staggered start
            task = asyncio.create_task(
                self._generate_with_retry(
                    agent_id=agent_id,
                    stagger_delay=stagger_delay,
                    **config,
                )
            )
            tasks.append((agent_id, task))

        # Wait for all tasks to complete
        results = []
        for agent_id, task in tasks:
            try:
                policy, tokens, latency = await task
                results.append((agent_id, policy, tokens, latency))
            except Exception as e:
                print(f"  Failed to generate policy for {agent_id}: {e}")
                results.append((agent_id, None, 0, 0.0))

        return results

    async def _generate_with_retry(
        self,
        agent_id: str,
        stagger_delay: float,
        max_retries: int = 3,
        base_backoff: float = 2.0,
        **kwargs: Any,
    ) -> tuple[dict | None, int, float]:
        """Generate policy with exponential backoff retry on rate limits.

        Args:
            agent_id: Agent identifier
            stagger_delay: Initial delay before first attempt
            max_retries: Maximum retry attempts
            base_backoff: Base delay for exponential backoff
            **kwargs: Arguments for generate_policy_async

        Returns:
            tuple of (policy, tokens, latency)
        """
        last_exception: Exception | None = None
        total_latency = 0.0

        for attempt in range(max_retries):
            try:
                # Add exponential backoff delay for retries
                if attempt > 0:
                    backoff_delay = base_backoff * (2 ** (attempt - 1))
                    print(f"    [{agent_id}] Retry {attempt}/{max_retries}, "
                          f"waiting {backoff_delay:.1f}s...")
                    await asyncio.sleep(backoff_delay)

                policy, tokens, latency = await self.generate_policy_async(
                    agent_id=agent_id,
                    stagger_delay=stagger_delay if attempt == 0 else 0,
                    **kwargs,
                )
                total_latency += latency

                if policy is not None:
                    return policy, tokens, total_latency

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if "rate" in error_str or "429" in error_str or "limit" in error_str:
                    print(f"    [{agent_id}] Rate limit hit, will retry...")
                    continue
                else:
                    # Non-rate-limit error, don't retry
                    raise

        # All retries exhausted
        if last_exception:
            print(f"    [{agent_id}] All retries exhausted: {last_exception}")

        return None, 0, total_latency

    def call_llm(self, prompt: str) -> tuple[str, int, float]:
        """Legacy interface for backward compatibility.

        Note: This method is kept for logging purposes but actual
        policy generation should use generate_policy() which returns
        structured output directly.
        """
        # Generate a policy and serialize it
        result, tokens, latency = self.generate_policy(
            instruction=prompt,
            iteration=0,
        )

        if result is None:
            return "ERROR: Policy generation failed", 0, latency

        # Wrap in expected response format
        response = json.dumps({
            "analysis": "Generated via PydanticAI structured output",
            "bank_a_policy": result,
            "bank_b_policy": result,  # Same policy for both in this mode
            "expected_improvement": "Optimized based on cost structure"
        }, indent=2)

        return response, tokens, latency

    def parse_response(self, response: str) -> tuple[dict, dict] | None:
        """Parse LLM response to extract new policies."""
        try:
            # Find JSON block
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                return None

            json_str = response[start:end]
            data = json.loads(json_str)

            policy_a = data.get("bank_a_policy")
            policy_b = data.get("bank_b_policy")

            if policy_a and policy_b:
                return policy_a, policy_b
            return None
        except (json.JSONDecodeError, KeyError):
            return None


# ============================================================================
# Main Experiment Runner
# ============================================================================

class ReproducibleExperiment:
    """Main experiment runner with full reproducibility.

    IMPORTANT: This runner NEVER modifies the seed policy files.
    Instead, it:
    1. Loads seed policies once at initialization (read-only)
    2. Creates iteration-specific policy files in output directory
    3. Creates iteration-specific YAML configs pointing to those policies
    4. Stores all policy versions in the database

    CRITICAL ISOLATION: Each agent's LLM optimization call receives ONLY
    that agent's data. No cross-agent information leakage occurs.
    """

    # Maximum retries when LLM produces invalid policy
    MAX_VALIDATION_RETRIES = 3

    @staticmethod
    def _filter_iteration_history_for_agent(
        records: list[IterationRecord],
        agent_id: str,
    ) -> list[SingleAgentIterationRecord]:
        """Filter iteration history to contain ONLY the specified agent's data.

        CRITICAL ISOLATION: This function ensures the LLM optimizing one agent
        never sees any information about other agents.

        Args:
            records: Full iteration records containing both agents' data
            agent_id: The agent to filter for ("BANK_A" or "BANK_B")

        Returns:
            List of SingleAgentIterationRecord containing only this agent's data
        """
        filtered: list[SingleAgentIterationRecord] = []
        for record in records:
            # Extract only this agent's policy and changes
            if agent_id == "BANK_A":
                policy = record.policy_a
                changes = record.policy_a_changes
            elif agent_id == "BANK_B":
                policy = record.policy_b
                changes = record.policy_b_changes
            else:
                # Unknown agent - use Bank A by default
                policy = record.policy_a
                changes = record.policy_a_changes

            filtered.append(SingleAgentIterationRecord(
                iteration=record.iteration,
                metrics=record.metrics,
                policy=policy,
                policy_changes=changes,
                was_accepted=record.was_accepted,
                is_best_so_far=record.is_best_so_far,
                comparison_to_best=record.comparison_to_best,
            ))
        return filtered

    def __init__(
        self,
        experiment_key: str,
        db_path: str,
        simcash_root: str | None = None,
        model: str = "gpt-4o",
        reasoning_effort: str = "high",
        master_seed: int | None = None,
        verbose: bool = False,
        thinking_budget: int | None = None,
    ):
        self.verbose = verbose
        self.thinking_budget = thinking_budget
        self.experiment_def = EXPERIMENTS[experiment_key]
        # Generate unique experiment ID with timestamp: exp1_2025-12-04-143022
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        self.experiment_id = f"{experiment_key}_{timestamp}"
        self.simcash_root = Path(simcash_root) if simcash_root else PROJECT_ROOT

        # Create experiment-specific output directories using the unique experiment ID
        # This ensures parallel experiments never share config/policy directories
        # All experiment outputs go into results/ folder for organization
        script_dir = Path(__file__).parent.parent  # experiments/castro/
        self.results_dir = script_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_work_dir = self.results_dir / self.experiment_id
        self.output_dir = self.experiment_work_dir
        self.policies_dir = self.experiment_work_dir / "policies"
        self.configs_dir = self.experiment_work_dir / "configs"
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        # Put database inside the experiment work directory
        db_filename = Path(db_path).name
        db_path = str(self.experiment_work_dir / db_filename)

        self.db = ExperimentDatabase(db_path)
        self.optimizer = LLMOptimizer(
            model=model,
            reasoning_effort=reasoning_effort,
            thinking_budget=thinking_budget,
            verbose=self.verbose,
        )

        # Master seed for reproducibility - if not provided, use timestamp-based seed
        # This ensures different experiments get different seeds by default
        if master_seed is None:
            # Use current time as a seed generator (reproducible if timestamp matches)
            import random
            master_seed = int(datetime.now().timestamp() * 1000) % (2**31)
        self.master_seed = master_seed

        # Load configs
        self.config_path = self.simcash_root / self.experiment_def["config_path"]
        self.config = load_yaml_config(str(self.config_path))

        # Load seed policies ONCE (read-only, never modified)
        self.seed_policy_a = load_json_policy(
            str(self.simcash_root / self.experiment_def["policy_a_path"])
        )
        self.seed_policy_b = load_json_policy(
            str(self.simcash_root / self.experiment_def["policy_b_path"])
        )

        # Current policies (start with seed, updated each iteration)
        self.policy_a = self.seed_policy_a.copy()
        self.policy_b = self.seed_policy_b.copy()

        # Settings
        self.num_seeds = self.experiment_def["num_seeds"]
        self.max_iterations = self.experiment_def["max_iterations"]
        self.convergence_threshold = self.experiment_def["convergence_threshold"]
        self.convergence_window = self.experiment_def["convergence_window"]
        self.model = model
        self.reasoning_effort = reasoning_effort

        # Pre-generate all seeds for all iterations using master seed
        # This ensures each iteration uses different seeds, maintaining determinism
        # while avoiding identical results when a policy is rejected and re-run
        self.seed_matrix = self._generate_seed_matrix()

        # Save experiment configuration to work directory root for reproducibility
        # (must be after seed_matrix is generated so it can be included)
        self._save_experiment_metadata(experiment_key, model, reasoning_effort)

        # Track current iteration config path
        self.current_config_path: Path | None = None

        # History (metrics only - for convergence checking)
        self.history: list[dict] = []

        # Full iteration history with policies and changes (for LLM context)
        self.iteration_records: list[IterationRecord] = []

        # Track policy history for computing diffs
        self.policy_history_a: list[dict] = [self.policy_a.copy()]
        self.policy_history_b: list[dict] = [self.policy_b.copy()]

        # Directory for simulation database files (for filtered replay)
        self.sim_db_dir = self.experiment_work_dir / "sim_databases"
        self.sim_db_dir.mkdir(parents=True, exist_ok=True)

        # Last iteration's verbose output (per-agent filtered output)
        # Each agent sees only events relevant to their bank
        self.last_best_seed_output_bank_a: str | None = None
        self.last_best_seed_output_bank_b: str | None = None
        self.last_worst_seed_output_bank_a: str | None = None
        self.last_worst_seed_output_bank_b: str | None = None
        self.last_best_seed: int = 0
        self.last_worst_seed: int = 0
        self.last_best_cost: int = 0
        self.last_worst_cost: int = 0
        self.last_cost_breakdown: dict[str, int] = {}
        # Store best/worst result dicts for replay access
        self.last_best_result: dict | None = None
        self.last_worst_result: dict | None = None

        # Best policy tracking - keeps the best discovered policy so far
        # This is separate from current policy (which may be a candidate being tested)
        self.best_policy_a: dict = self.seed_policy_a.copy()
        self.best_policy_b: dict = self.seed_policy_b.copy()
        self.best_metrics: dict | None = None  # Set after first iteration
        self.best_iteration: int = 0  # Iteration number where best was found

    def _save_experiment_metadata(
        self,
        experiment_key: str,
        model: str,
        reasoning_effort: str,
    ) -> None:
        """Save experiment configuration and parameters to the work directory root.

        Creates the following files in experiment_work_dir:
        - scenario.yaml: Copy of the simulation scenario config
        - parameters.json: Experiment parameters (model, seeds, iterations, etc.)
        - seed_policy_a.json: Initial policy for Bank A
        - seed_policy_b.json: Initial policy for Bank B
        """
        import shutil

        # 1. Copy scenario config
        scenario_dest = self.experiment_work_dir / "scenario.yaml"
        shutil.copy(self.config_path, scenario_dest)

        # 2. Save experiment parameters
        # Convert seed_matrix keys to strings for JSON serialization
        seed_matrix_serializable = {str(k): v for k, v in self.seed_matrix.items()}
        parameters = {
            "experiment_id": self.experiment_id,
            "experiment_key": experiment_key,
            "experiment_name": self.experiment_def["name"],
            "description": self.experiment_def.get("description", ""),
            "model": model,
            "reasoning_effort": reasoning_effort,
            "num_seeds": self.experiment_def["num_seeds"],
            "max_iterations": self.experiment_def["max_iterations"],
            "convergence_threshold": self.experiment_def["convergence_threshold"],
            "convergence_window": self.experiment_def["convergence_window"],
            "master_seed": self.master_seed,
            "seed_matrix": seed_matrix_serializable,
            "config_path": str(self.config_path),
            "simcash_root": str(self.simcash_root),
            "created_at": datetime.now().isoformat(),
        }
        params_dest = self.experiment_work_dir / "parameters.json"
        with open(params_dest, "w") as f:
            json.dump(parameters, f, indent=2)

        # 3. Copy seed policies
        seed_policy_a_src = self.simcash_root / self.experiment_def["policy_a_path"]
        seed_policy_b_src = self.simcash_root / self.experiment_def["policy_b_path"]
        shutil.copy(seed_policy_a_src, self.experiment_work_dir / "seed_policy_a.json")
        shutil.copy(seed_policy_b_src, self.experiment_work_dir / "seed_policy_b.json")

    def _generate_seed_matrix(self) -> dict[int, list[int]]:
        """Generate a matrix of unique seeds for all iterations.

        Pre-generates N x Y unique random seeds where:
        - N = max_iterations
        - Y = num_seeds (seeds per iteration)

        This ensures:
        1. Determinism: Same master_seed always produces same seed_matrix
        2. Uniqueness: Each iteration uses different seeds
        3. No overlap: When a policy is rejected and we revert, we still use
           new seeds to get fresh results rather than identical replays

        Returns:
            Dict mapping iteration number (1-based) to list of seeds for that iteration.
            Example: {1: [12345, 67890, ...], 2: [11111, 22222, ...], ...}
        """
        import random

        # Use master_seed to initialize the RNG for reproducibility
        rng = random.Random(self.master_seed)

        # Generate unique seeds for all iterations
        # Use large range to minimize collision probability
        seed_matrix: dict[int, list[int]] = {}

        # Track all generated seeds to ensure uniqueness
        all_seeds: set[int] = set()

        for iteration in range(1, self.max_iterations + 1):
            iteration_seeds: list[int] = []
            for _ in range(self.num_seeds):
                # Generate unique seed
                while True:
                    seed = rng.randint(1, 2**31 - 1)
                    if seed not in all_seeds:
                        all_seeds.add(seed)
                        iteration_seeds.append(seed)
                        break
            seed_matrix[iteration] = iteration_seeds

        return seed_matrix

    def setup(self) -> None:
        """Initialize experiment in database."""
        with open(self.config_path) as f:
            config_yaml = f.read()

        self.db.record_experiment_config(
            experiment_id=self.experiment_id,
            experiment_name=self.experiment_def["name"],
            config_yaml=config_yaml,
            cost_rates=self.config.get("cost_rates", {}),
            agent_configs=self.config.get("agents", []),
            model_name=self.model,
            reasoning_effort=self.reasoning_effort,
            num_seeds=self.num_seeds,
            max_iterations=self.max_iterations,
            convergence_threshold=self.convergence_threshold,
            convergence_window=self.convergence_window,
            master_seed=self.master_seed,
            seed_matrix=self.seed_matrix,
            notes=self.experiment_def.get("description"),
        )

        # Record initial policies
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=0,
            agent_id="BANK_A",
            policy_json=json.dumps(self.policy_a),
            created_by="init",
        )
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=0,
            agent_id="BANK_B",
            policy_json=json.dumps(self.policy_b),
            created_by="init",
        )

    def is_better_for_agent(
        self, agent_id: str, candidate_metrics: dict
    ) -> tuple[bool, str]:
        """Compare candidate metrics for a specific agent (selfish evaluation).

        IMPORTANT: Each bank is selfish and only cares about their own costs!
        A policy is considered better for an agent if:
        1. It has 100% settlement rate (required for system stability)
        2. It has lower mean cost FOR THAT AGENT than the current best

        Args:
            agent_id: The agent to evaluate ("BANK_A" or "BANK_B")
            candidate_metrics: Metrics from the candidate policy run

        Returns:
            Tuple of (is_better, comparison_description)
        """
        if self.best_metrics is None:
            # First iteration - automatically becomes best
            return True, f"{agent_id}: First iteration - establishing baseline"

        # Get per-agent cost metrics
        if agent_id == "BANK_A":
            candidate_cost = candidate_metrics["bank_a_cost_mean"]
            best_cost = self.best_metrics["bank_a_cost_mean"]
        else:  # BANK_B
            candidate_cost = candidate_metrics["bank_b_cost_mean"]
            best_cost = self.best_metrics["bank_b_cost_mean"]

        candidate_settlement = candidate_metrics["settlement_rate_mean"]

        # Settlement rate must be 100% (or very close) for system stability
        if candidate_settlement < 0.999:
            return False, (
                f"{agent_id}: Settlement rate {candidate_settlement*100:.1f}% < 100%. "
                f"Cost ${candidate_cost:,.0f} vs best ${best_cost:,.0f}"
            )

        # Compare agent's own costs (selfish evaluation)
        cost_delta = candidate_cost - best_cost
        cost_pct = (cost_delta / best_cost) * 100 if best_cost > 0 else 0

        if candidate_cost < best_cost:
            return True, (
                f"{agent_id}: Improved by ${-cost_delta:,.0f} ({-cost_pct:.1f}%). "
                f"New: ${candidate_cost:,.0f}, Previous best: ${best_cost:,.0f}"
            )
        elif candidate_cost == best_cost:
            return False, (
                f"{agent_id}: No improvement. "
                f"Cost ${candidate_cost:,.0f} equals best ${best_cost:,.0f}"
            )
        else:
            return False, (
                f"{agent_id}: Worse by ${cost_delta:,.0f} (+{cost_pct:.1f}%). "
                f"Candidate: ${candidate_cost:,.0f}, Best: ${best_cost:,.0f}"
            )

    def is_better_than_best(self, candidate_metrics: dict) -> tuple[bool, str]:
        """Compare candidate metrics to the current best (LEGACY - uses total cost).

        NOTE: This method is deprecated for policy acceptance decisions.
        Use is_better_for_agent() instead for selfish per-bank evaluation.

        A policy is considered better if:
        1. It has 100% settlement rate (required)
        2. It has lower mean cost than the current best

        Args:
            candidate_metrics: Metrics from the candidate policy run

        Returns:
            Tuple of (is_better, comparison_description)
        """
        if self.best_metrics is None:
            # First iteration - automatically becomes best
            return True, "First iteration - establishing baseline"

        candidate_cost = candidate_metrics["total_cost_mean"]
        best_cost = self.best_metrics["total_cost_mean"]
        candidate_settlement = candidate_metrics["settlement_rate_mean"]

        # Settlement rate must be 100% (or very close)
        if candidate_settlement < 0.999:
            return False, (
                f"Settlement rate {candidate_settlement*100:.1f}% < 100%. "
                f"Cost ${candidate_cost:,.0f} vs best ${best_cost:,.0f}"
            )

        # Compare costs
        cost_delta = candidate_cost - best_cost
        cost_pct = (cost_delta / best_cost) * 100 if best_cost > 0 else 0

        if candidate_cost < best_cost:
            return True, (
                f"Improved by ${-cost_delta:,.0f} ({-cost_pct:.1f}%). "
                f"New: ${candidate_cost:,.0f}, Previous best: ${best_cost:,.0f}"
            )
        elif candidate_cost == best_cost:
            return False, (
                f"No improvement. Cost ${candidate_cost:,.0f} equals best ${best_cost:,.0f}"
            )
        else:
            return False, (
                f"Worse by ${cost_delta:,.0f} (+{cost_pct:.1f}%). "
                f"Candidate: ${candidate_cost:,.0f}, Best: ${best_cost:,.0f}"
            )

    def create_iteration_config(self, iteration: int) -> Path:
        """Create iteration-specific policy files and YAML config.

        This method:
        1. Writes current policies to policies/iter_XXX_policy_{a,b}.json
        2. Creates a modified YAML config pointing to those policy files
        3. Returns the path to the iteration-specific config

        NEVER modifies the original seed policy files.
        """
        # Write iteration-specific policy files
        policy_a_path = self.policies_dir / f"iter_{iteration:03d}_policy_a.json"
        policy_b_path = self.policies_dir / f"iter_{iteration:03d}_policy_b.json"

        save_json_policy(str(policy_a_path), self.policy_a)
        save_json_policy(str(policy_b_path), self.policy_b)

        # Create modified config with new policy paths
        iter_config = self.config.copy()

        # Deep copy agents to avoid modifying base config
        iter_config["agents"] = []
        for agent in self.config.get("agents", []):
            agent_copy = agent.copy()
            if agent_copy.get("id") == "BANK_A":
                agent_copy["policy"] = {
                    "type": "FromJson",
                    "json_path": str(policy_a_path.absolute())
                }
            elif agent_copy.get("id") == "BANK_B":
                agent_copy["policy"] = {
                    "type": "FromJson",
                    "json_path": str(policy_b_path.absolute())
                }
            iter_config["agents"].append(agent_copy)

        # Write iteration config
        iter_config_path = (self.configs_dir / f"iter_{iteration:03d}_config.yaml").absolute()
        with open(iter_config_path, 'w') as f:
            yaml.safe_dump(iter_config, f, default_flow_style=False)

        self.current_config_path = iter_config_path
        return iter_config_path

    def validate_policy_with_details(self, policy: dict, agent_name: str) -> tuple[bool, str, list[str]]:
        """Validate a policy and return detailed error messages.

        Uses both:
        - --scenario: Validates against scenario's feature toggles
        - --functional-tests: Catches runtime errors (e.g., wrong action types
          in collateral trees) that schema validation alone would miss.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(policy, f)
            f.flush()
            temp_path = f.name

        try:
            cmd = [
                str(self.simcash_root / "api" / ".venv" / "bin" / "payment-sim"),
                "validate-policy",
                temp_path,
                "--format", "json",
                "--functional-tests",  # Catches runtime errors like wrong action types
            ]
            # Add scenario validation if we have a config path
            if hasattr(self, 'current_config_path') and self.current_config_path:
                cmd.extend(["--scenario", str(self.current_config_path)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root)
            )

            errors = []

            # Note: validator returns JSON even on error (return code != 0)
            # so we should parse stdout in both cases
            try:
                output = json.loads(result.stdout)
                is_valid = output.get("valid", False)

                # Check functional tests - these catch runtime errors
                functional_tests = output.get("functional_tests", {})
                if functional_tests and not functional_tests.get("passed", True):
                    is_valid = False
                    # Extract functional test error messages
                    for test_result in functional_tests.get("results", []):
                        if not test_result.get("passed", True):
                            errors.append(f"[FunctionalTest] {test_result.get('message', 'Test failed')}")

                # Check scenario validation - forbidden categories/elements
                forbidden_cats = output.get("forbidden_categories", [])
                if forbidden_cats:
                    is_valid = False
                    errors.append(f"[Scenario] Forbidden categories used: {', '.join(forbidden_cats)}")

                forbidden_elems = output.get("forbidden_elements", [])
                if forbidden_elems:
                    is_valid = False
                    errors.append(f"[Scenario] Forbidden elements used: {', '.join(forbidden_elems)}")

                if not is_valid and not errors:
                    if "errors" in output:
                        # Errors are objects with 'message' and 'type' fields
                        raw_errors = output["errors"]
                        for err in raw_errors:
                            if isinstance(err, dict):
                                msg = err.get("message", str(err))
                                err_type = err.get("type", "Unknown")
                                errors.append(f"[{err_type}] {msg}")
                            else:
                                errors.append(str(err))
                    elif "error" in output:
                        errors = [output["error"]]
                    elif "message" in output:
                        errors = [output["message"]]
                    else:
                        errors = [f"Validation failed for {agent_name}: {result.stdout[:500]}"]
                return is_valid, result.stdout, errors
            except json.JSONDecodeError:
                return result.returncode == 0, result.stdout, [f"Non-JSON output: {result.stdout[:200]}"]
        finally:
            os.unlink(temp_path)

    def request_policy_fix_from_llm(self, policy: dict, agent_name: str, errors: list[str]) -> dict | None:
        """Ask LLM to fix an invalid policy using PydanticAI.

        Since RobustPolicyAgent uses structured output, invalid policies are rare.
        When they do occur, we regenerate with explicit error context.
        """
        error_list = "\n".join(f"  - {e}" for e in errors)

        fix_instruction = f"""Fix the policy for {agent_name}.

Previous policy had validation errors:
{error_list}

Generate a corrected policy that avoids these errors.
"""
        try:
            fixed_policy, _, _ = self.optimizer.generate_policy(
                instruction=fix_instruction,
                current_policy=policy,
                iteration=0,
            )
            return fixed_policy
        except Exception:
            return None

    def validate_and_fix_policy(
        self,
        policy: dict,
        agent_name: str,
        fallback: dict,
        iteration: int = 0,
    ) -> tuple[dict, bool]:
        """Validate a policy, attempting to fix it if invalid.

        Logs all validation errors to the database for analysis.
        When verbose mode is enabled, prints all validation errors.
        """
        is_valid, _, errors = self.validate_policy_with_details(policy, agent_name)
        if is_valid:
            if self.verbose:
                print(f"  [VERBOSE] {agent_name} policy validated successfully")
            return policy, True

        print(f"  {agent_name} policy invalid, attempting LLM fix...")
        # Always print validation errors (not just in verbose mode) so user can see what's wrong
        print(f"    Validation errors:")
        for err in errors:
            print(f"      - {err}")

        # Track all errors for logging
        all_errors: list[tuple[int, dict, list[str]]] = [(0, policy, errors)]

        for attempt in range(self.MAX_VALIDATION_RETRIES):
            if self.verbose:
                print(f"    [VERBOSE] Fix attempt {attempt + 1}/{self.MAX_VALIDATION_RETRIES}...")
            fixed = self.request_policy_fix_from_llm(policy, agent_name, errors)
            if fixed is None:
                print(f"    Fix attempt {attempt + 1} failed: LLM returned no policy")
                continue

            is_valid, _, new_errors = self.validate_policy_with_details(fixed, agent_name)
            if is_valid:
                print(f"  {agent_name} policy fixed on attempt {attempt + 1}")
                # Log all errors with was_fixed=True for the initial, False for fix attempts
                for err_attempt, err_policy, err_msgs in all_errors:
                    self.db.record_validation_error(
                        experiment_id=self.experiment_id,
                        iteration_number=iteration,
                        agent_id=agent_name,
                        attempt_number=err_attempt,
                        policy=err_policy,
                        errors=err_msgs,
                        was_fixed=True,
                        fix_attempt_count=attempt + 1,
                    )
                return fixed, False

            # Print errors for this fix attempt
            print(f"    Fix attempt {attempt + 1} still invalid:")
            for err in new_errors:
                print(f"      - {err}")

            # Track this fix attempt's error
            all_errors.append((attempt + 1, fixed, new_errors))
            errors = new_errors
            policy = fixed  # Use fixed policy for next attempt

        # Log all errors with was_fixed=False
        for err_attempt, err_policy, err_msgs in all_errors:
            self.db.record_validation_error(
                experiment_id=self.experiment_id,
                iteration_number=iteration,
                agent_id=agent_name,
                attempt_number=err_attempt,
                policy=err_policy,
                errors=err_msgs,
                was_fixed=False,
                fix_attempt_count=self.MAX_VALIDATION_RETRIES,
            )

        print(f"  {agent_name} policy unfixable, using previous valid policy")
        return fallback, False

    def run_iteration(self, iteration: int) -> dict:
        """Run a single iteration and evaluate whether to accept the policy.

        This method:
        1. Runs simulations with current (candidate) policies
        2. Compares results to best known policy
        3. Accepts if better, rejects if worse
        4. Records full history including rejected attempts
        """
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}/{self.max_iterations}")
        print(f"{'='*60}")

        # Create iteration-specific config with current policies
        config_path = self.create_iteration_config(iteration)

        # Use pre-generated seeds for this iteration
        # This ensures each iteration uses unique seeds, even if policies are reverted
        seeds = self.seed_matrix[iteration]

        print(f"  Running {len(seeds)} simulations with persistence...")
        if self.verbose:
            print(f"    [VERBOSE] Seeds for this iteration: {seeds}")
            print(f"    [VERBOSE] Config path: {config_path}")
        results = run_simulations_parallel(
            config_path=str(config_path),
            simcash_root=str(self.simcash_root),
            seeds=seeds,
            work_dir=str(self.sim_db_dir.absolute()),  # Must be absolute for subprocess cwd
        )

        # Record all runs
        for result in results:
            if "error" not in result:
                self.db.record_simulation_run(
                    experiment_id=self.experiment_id,
                    iteration_number=iteration,
                    seed=result["seed"],
                    result=result,
                )
                if self.verbose:
                    print(f"    [VERBOSE] Seed {result['seed']}: cost=${result['total_cost']:,.0f}, settlement={result['settlement_rate']*100:.1f}%")
            else:
                print(f"    [ERROR] Seed {result.get('seed', '?')}: {result['error']}")

        # Compute metrics
        metrics = compute_metrics(results)

        if metrics is None:
            print("  ERROR: All simulations failed")
            # Revert to best known policies for next iteration
            self.policy_a = self.best_policy_a.copy()
            self.policy_b = self.best_policy_b.copy()
            # Return with failure metrics (including per-bank costs)
            return {
                "iteration": iteration,
                "metrics": {
                    "total_cost_mean": float("inf"), "total_cost_std": 0,
                    "settlement_rate_mean": 0, "failure_rate": 1.0,
                    "best_seed_cost": float("inf"), "worst_seed_cost": float("inf"),
                    "best_seed": 0, "worst_seed": 0, "risk_adjusted_cost": float("inf"),
                    # Per-bank metrics for selfish evaluation
                    "bank_a_cost_mean": float("inf"), "bank_a_cost_std": 0,
                    "bank_b_cost_mean": float("inf"), "bank_b_cost_std": 0,
                },
                "results": results,
                "converged": False,
                "failed": True,
                "was_accepted": False,
                "is_best": False,
                "comparison": "Simulation failed",
            }

        print(f"  Mean cost: ${metrics['total_cost_mean']:,.0f} ± ${metrics['total_cost_std']:,.0f}")
        print(f"  Settlement rate: {metrics['settlement_rate_mean']*100:.1f}%")
        print(f"  Failure rate: {metrics['failure_rate']*100:.0f}%")

        if self.verbose:
            # Aggregate cost breakdown from all successful runs
            valid_results = [r for r in results if "error" not in r]
            if valid_results:
                total_delay = sum(r.get("cost_breakdown", {}).get("delay", 0) for r in valid_results)
                total_collateral = sum(r.get("cost_breakdown", {}).get("collateral", 0) for r in valid_results)
                total_overdraft = sum(r.get("cost_breakdown", {}).get("overdraft", 0) for r in valid_results)
                total_eod = sum(r.get("cost_breakdown", {}).get("eod_penalty", 0) for r in valid_results)
                n = len(valid_results)
                print(f"    [VERBOSE] Avg cost breakdown:")
                print(f"      - Delay: ${total_delay/n:,.0f}")
                print(f"      - Collateral: ${total_collateral/n:,.0f}")
                print(f"      - Overdraft: ${total_overdraft/n:,.0f}")
                print(f"      - EOD penalty: ${total_eod/n:,.0f}")

        # Extract best/worst seed verbose output for LLM context
        self._extract_best_worst_context(results, metrics)

        # SELFISH EVALUATION: Each bank only cares about their own costs!
        # Evaluate each bank's policy independently
        is_better_a, comparison_a = self.is_better_for_agent("BANK_A", metrics)
        is_better_b, comparison_b = self.is_better_for_agent("BANK_B", metrics)

        # Print per-bank cost breakdown
        print(f"  Per-bank costs:")
        print(f"    BANK_A: ${metrics['bank_a_cost_mean']:,.0f} ± ${metrics['bank_a_cost_std']:,.0f}")
        print(f"    BANK_B: ${metrics['bank_b_cost_mean']:,.0f} ± ${metrics['bank_b_cost_std']:,.0f}")

        # Handle Bank A's policy independently
        if is_better_a:
            print(f"  ✅ BANK_A ACCEPTED: {comparison_a}")
            self.best_policy_a = self.policy_a.copy()
            if self.verbose:
                print(f"    [VERBOSE] Updated BANK_A best policy to iteration {iteration}")
                print(f"    [VERBOSE] Best Bank A parameters: {self.best_policy_a.get('parameters', {})}")
        else:
            print(f"  ❌ BANK_A REJECTED: {comparison_a}")
            # Revert Bank A policy to its best
            self.policy_a = self.best_policy_a.copy()
            if self.verbose:
                print(f"    [VERBOSE] BANK_A reverted to best policy")

        # Handle Bank B's policy independently
        if is_better_b:
            print(f"  ✅ BANK_B ACCEPTED: {comparison_b}")
            self.best_policy_b = self.policy_b.copy()
            if self.verbose:
                print(f"    [VERBOSE] Updated BANK_B best policy to iteration {iteration}")
                print(f"    [VERBOSE] Best Bank B parameters: {self.best_policy_b.get('parameters', {})}")
        else:
            print(f"  ❌ BANK_B REJECTED: {comparison_b}")
            # Revert Bank B policy to its best
            self.policy_b = self.best_policy_b.copy()
            if self.verbose:
                print(f"    [VERBOSE] BANK_B reverted to best policy")

        # Update best metrics if any bank improved (for tracking purposes)
        # Note: best_metrics tracks the overall state, not per-bank
        was_accepted = is_better_a or is_better_b
        is_best = is_better_a and is_better_b

        if was_accepted:
            self.best_metrics = metrics.copy()
            self.best_iteration = iteration

        # Build combined comparison string for logging
        comparison = f"A: {comparison_a} | B: {comparison_b}"

        # Record iteration in history (including rejected attempts)
        self._record_iteration(
            iteration=iteration,
            metrics=metrics,
            was_accepted=was_accepted,
            is_best_so_far=is_best,
            comparison_to_best=comparison,
        )

        # Check convergence (based on best policy stability)
        converged = self.check_convergence(metrics)

        # Record metrics to database
        self.db.record_iteration_metrics(
            experiment_id=self.experiment_id,
            iteration_number=iteration,
            metrics=metrics,
            converged=converged,
            policy_was_accepted=was_accepted,
            is_best_iteration=is_best,
            comparison_to_best=comparison,
        )

        self.history.append(metrics)

        # Track policy history for diffs
        self.policy_history_a.append(self.policy_a.copy())
        self.policy_history_b.append(self.policy_b.copy())

        return {
            "iteration": iteration,
            "metrics": metrics,
            "results": results,
            "converged": converged,
            "was_accepted": was_accepted,
            "is_best": is_best,
            "comparison": comparison,
        }

    def _extract_best_worst_context(self, results: list[dict], metrics: dict) -> None:
        """Extract filtered verbose output per agent from best/worst seeds.

        Uses filtered replay to ensure each LLM optimizer only sees events
        relevant to the bank whose policy it is optimizing. This provides
        information isolation between competing banks.
        """
        valid_results = [r for r in results if "error" not in r]
        if not valid_results:
            return

        # Find best and worst by cost
        best_result = min(valid_results, key=lambda r: r.get("total_cost", float("inf")))
        worst_result = max(valid_results, key=lambda r: r.get("total_cost", 0))

        # Store seed info
        self.last_best_seed = best_result.get("seed", 0)
        self.last_worst_seed = worst_result.get("seed", 0)
        self.last_best_cost = int(best_result.get("total_cost", 0))
        self.last_worst_cost = int(worst_result.get("total_cost", 0))
        self.last_best_result = best_result
        self.last_worst_result = worst_result

        # Aggregate cost breakdown from worst seed (to show problem areas)
        cost_bd = worst_result.get("cost_breakdown", {})
        self.last_cost_breakdown = {
            "delay": int(cost_bd.get("delay", 0)),
            "collateral": int(cost_bd.get("collateral", 0)),
            "overdraft": int(cost_bd.get("overdraft", 0)),
            "eod_penalty": int(cost_bd.get("eod_penalty", 0)),
        }

        # Extract filtered verbose output per agent via replay
        # This ensures each LLM only sees events for its own bank
        print(f"  Extracting filtered outputs for BANK_A and BANK_B...")

        try:
            # Get filtered output for BANK_A from best seed
            self.last_best_seed_output_bank_a = get_filtered_replay_output(
                simcash_root=str(self.simcash_root),
                db_path=best_result["db_path"],
                simulation_id=best_result["simulation_id"],
                agent_id="BANK_A",
            )
            # Get filtered output for BANK_B from best seed
            self.last_best_seed_output_bank_b = get_filtered_replay_output(
                simcash_root=str(self.simcash_root),
                db_path=best_result["db_path"],
                simulation_id=best_result["simulation_id"],
                agent_id="BANK_B",
            )
            # Get filtered output for BANK_A from worst seed
            self.last_worst_seed_output_bank_a = get_filtered_replay_output(
                simcash_root=str(self.simcash_root),
                db_path=worst_result["db_path"],
                simulation_id=worst_result["simulation_id"],
                agent_id="BANK_A",
            )
            # Get filtered output for BANK_B from worst seed
            self.last_worst_seed_output_bank_b = get_filtered_replay_output(
                simcash_root=str(self.simcash_root),
                db_path=worst_result["db_path"],
                simulation_id=worst_result["simulation_id"],
                agent_id="BANK_B",
            )
            print(f"    ✓ Filtered outputs extracted successfully")
        except Exception as e:
            print(f"    WARNING: Failed to extract filtered outputs: {e}")
            # Clear outputs to indicate failure
            self.last_best_seed_output_bank_a = None
            self.last_best_seed_output_bank_b = None
            self.last_worst_seed_output_bank_a = None
            self.last_worst_seed_output_bank_b = None

    def _record_iteration(
        self,
        iteration: int,
        metrics: dict,
        was_accepted: bool = True,
        is_best_so_far: bool = False,
        comparison_to_best: str = "",
    ) -> None:
        """Record this iteration in the history with policy changes.

        Args:
            iteration: Iteration number
            metrics: Metrics from this iteration
            was_accepted: Whether this policy was accepted (improved over best)
            is_best_so_far: Whether this is the best policy discovered so far
            comparison_to_best: Human-readable comparison to best
        """
        # Compute policy changes from previous best policy (not just previous iteration)
        # This is more useful for the LLM to understand what changed
        changes_a = compute_policy_diff(self.best_policy_a, self.policy_a)
        changes_b = compute_policy_diff(self.best_policy_b, self.policy_b)

        record = IterationRecord(
            iteration=iteration,
            metrics=metrics,
            policy_a=self.policy_a.copy(),
            policy_b=self.policy_b.copy(),
            policy_a_changes=changes_a,
            policy_b_changes=changes_b,
            was_accepted=was_accepted,
            is_best_so_far=is_best_so_far,
            comparison_to_best=comparison_to_best,
        )
        self.iteration_records.append(record)

    def optimize_policies(self, iteration: int, metrics: dict, results: list[dict]) -> bool:
        """Generate candidate policies using LLM, starting from BEST policy.

        IMPORTANT: Always optimizes from the best known policy, not the current
        (potentially rejected) policy. This ensures the LLM always has the best
        starting point for generating improvements.

        Passes rich historical context including:
        - Full tick-by-tick output from best and worst seeds
        - Complete iteration history with metrics and policy changes
        - Both accepted AND rejected policies (so LLM learns what didn't work)
        - Cost breakdown for optimization guidance
        """
        # Count rejected policies to inform the LLM
        rejected_count = sum(1 for r in self.iteration_records if not r.was_accepted)

        print(f"  Calling LLM for optimization with extended context...")
        print(f"    - History: {len(self.iteration_records)} iterations ({rejected_count} rejected)")
        print(f"    - Starting from best policy (iteration {self.best_iteration})")
        print(f"    - Best seed #{self.last_best_seed}: ${self.last_best_cost:,}")
        print(f"    - Worst seed #{self.last_worst_seed}: ${self.last_worst_cost:,}")

        # Use BEST metrics for optimization, not current (which may be from rejected policy)
        best_metrics = self.best_metrics or metrics

        # Create instruction prompt
        instruction = f"""Optimize policy for iteration {iteration}.

CURRENT BEST (iteration {self.best_iteration}): Mean cost ${best_metrics['total_cost_mean']:,.0f}
Your goal: Generate a policy that BEATS this cost while maintaining 100% settlement.

{f"WARNING: {rejected_count} previous attempts were REJECTED for being worse. Learn from them!" if rejected_count > 0 else ""}

IMPORTANT: Review the tick-by-tick simulation output below to understand:
1. What patterns lead to high costs (worst seed)
2. What patterns lead to low costs (best seed)
3. Which cost component dominates (delay vs collateral vs overdraft)

Use this insight to make targeted policy improvements."""

        # CRITICAL ISOLATION: Filter iteration history for each agent SEPARATELY
        # Each agent's LLM call sees ONLY its own policy history - no cross-agent data
        bank_a_history = self._filter_iteration_history_for_agent(
            self.iteration_records, "BANK_A"
        )
        bank_b_history = self._filter_iteration_history_for_agent(
            self.iteration_records, "BANK_B"
        )

        # Build isolated agent configurations for parallel execution
        # CRITICAL: Each config contains ONLY that agent's data
        # Each bank is selfish - use their actual per-bank cost!
        agent_configs = [
            {
                "agent_id": "BANK_A",
                "instruction": instruction,
                "current_policy": self.best_policy_a,
                "current_cost": best_metrics['bank_a_cost_mean'],  # Use actual BANK_A cost
                "settlement_rate": best_metrics['settlement_rate_mean'],
                "iteration": iteration,
                "iteration_history": bank_a_history,
                "best_seed_output": self.last_best_seed_output_bank_a,
                "worst_seed_output": self.last_worst_seed_output_bank_a,
                "best_seed": self.last_best_seed,
                "worst_seed": self.last_worst_seed,
                "best_seed_cost": self.last_best_cost,
                "worst_seed_cost": self.last_worst_cost,
                "cost_breakdown": self.last_cost_breakdown,
                "cost_rates": self.config.get("cost_rates", {}),
            },
            {
                "agent_id": "BANK_B",
                "instruction": instruction,
                "current_policy": self.best_policy_b,
                "current_cost": best_metrics['bank_b_cost_mean'],  # Use actual BANK_B cost
                "settlement_rate": best_metrics['settlement_rate_mean'],
                "iteration": iteration,
                "iteration_history": bank_b_history,
                "best_seed_output": self.last_best_seed_output_bank_b,
                "worst_seed_output": self.last_worst_seed_output_bank_b,
                "best_seed": self.last_best_seed,
                "worst_seed": self.last_worst_seed,
                "best_seed_cost": self.last_best_cost,
                "worst_seed_cost": self.last_worst_cost,
                "cost_breakdown": self.last_cost_breakdown,
                "cost_rates": self.config.get("cost_rates", {}),
            },
        ]

        # PARALLEL EXECUTION: Run all agent LLM calls simultaneously
        # - Staggered starts (0.5s apart) to avoid rate limits
        # - Exponential backoff retry on rate limit errors
        # - Complete isolation - no shared state between agents
        print(f"    Running {len(agent_configs)} agent optimizations in parallel...")

        results = asyncio.run(
            self.optimizer.generate_policies_parallel(
                agent_configs=agent_configs,
                stagger_interval=0.5,  # 0.5s between starts to avoid rate limits
            )
        )

        # Extract results by agent_id
        policy_a, tokens_a, latency_a = None, 0, 0.0
        policy_b, tokens_b, latency_b = None, 0, 0.0

        for agent_id, policy, tokens, latency in results:
            if agent_id == "BANK_A":
                policy_a, tokens_a, latency_a = policy, tokens, latency
            elif agent_id == "BANK_B":
                policy_b, tokens_b, latency_b = policy, tokens, latency

        total_tokens = tokens_a + tokens_b
        # For parallel execution, total latency is the max (not sum)
        total_latency = max(latency_a, latency_b)

        # Record interaction for logging
        prompt_text = instruction
        if policy_a is not None and policy_b is not None:
            response_text = json.dumps({
                "bank_a_policy": policy_a,
                "bank_b_policy": policy_b,
            }, indent=2)
            error_msg = None
        else:
            response_text = "ERROR: Policy generation failed"
            error_msg = response_text

        self.db.record_llm_interaction(
            experiment_id=self.experiment_id,
            iteration_number=iteration,
            prompt_text=prompt_text,
            response_text=response_text,
            model_name=self.model,
            reasoning_effort=self.reasoning_effort,
            tokens_used=total_tokens,
            latency_seconds=total_latency,
            error_message=error_msg,
        )

        print(f"  LLM response: ~{total_tokens} tokens, {total_latency:.1f}s")

        if self.verbose and policy_a is not None:
            print(f"    [VERBOSE] Bank A policy parameters: {policy_a.get('parameters', {})}")
        if self.verbose and policy_b is not None:
            print(f"    [VERBOSE] Bank B policy parameters: {policy_b.get('parameters', {})}")

        if policy_a is None or policy_b is None:
            print("  ERROR: Policy generation failed")
            return False

        # Validate policies with retry logic (NEVER writes to seed files)
        # Log all validation errors to database for analysis
        # Fallback to BEST policy if validation fails
        if self.verbose:
            print(f"  [VERBOSE] Validating Bank A policy...")
        new_policy_a, was_valid_a = self.validate_and_fix_policy(
            policy_a, "Bank A", self.best_policy_a, iteration=iteration
        )
        if self.verbose:
            print(f"  [VERBOSE] Validating Bank B policy...")
        new_policy_b, was_valid_b = self.validate_and_fix_policy(
            policy_b, "Bank B", self.best_policy_b, iteration=iteration
        )

        # Update current policies to CANDIDATE (will be evaluated in next iteration)
        # Note: These may be rejected if they don't improve over best
        self.policy_a = new_policy_a
        self.policy_b = new_policy_b

        # Check if policies were actually changed or fell back to best
        a_changed = new_policy_a != self.best_policy_a
        b_changed = new_policy_b != self.best_policy_b
        if not a_changed and not b_changed:
            # This is a serious issue - both policies failed validation and reverted
            # Always print this warning since it explains stalls
            print(f"  ⚠️  WARNING: Both policies fell back to previous best (validation failed)")
            print(f"      Next iteration will likely produce identical results (stall)")
        elif self.verbose:
            if not a_changed:
                print(f"  [VERBOSE] Bank A policy unchanged (validation fallback), Bank B changed")
            elif not b_changed:
                print(f"  [VERBOSE] Bank A changed, Bank B policy unchanged (validation fallback)")
            else:
                print(f"  [VERBOSE] Both policies successfully changed")

        # Record new candidate policies to database (will be marked accepted/rejected after evaluation)
        # Note: was_accepted and is_best will be updated after run_iteration evaluates
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=iteration + 1,
            agent_id="BANK_A",
            policy_json=json.dumps(new_policy_a),
            created_by="llm",
            was_accepted=True,  # Will be updated if rejected
            is_best=False,  # Will be updated if this becomes best
        )
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=iteration + 1,
            agent_id="BANK_B",
            policy_json=json.dumps(new_policy_b),
            created_by="llm",
            was_accepted=True,  # Will be updated if rejected
            is_best=False,  # Will be updated if this becomes best
        )

        # NOTE: Policies are saved to iteration-specific files in run_iteration()
        # via create_iteration_config(). The seed policy files are NEVER modified.

        print(f"  Candidate policies generated for iteration {iteration + 1}")
        return True

    def check_convergence(self, current_metrics: dict) -> bool:
        """Check if optimization has converged."""
        if len(self.history) < self.convergence_window:
            return False

        recent = self.history[-self.convergence_window:]
        costs = [m["total_cost_mean"] for m in recent]

        # Check if all recent costs are within threshold of each other
        min_cost = min(costs)
        max_cost = max(costs)

        if min_cost == 0:
            return False

        variation = (max_cost - min_cost) / min_cost
        return variation < self.convergence_threshold

    def run(self) -> dict:
        """Run the full experiment with best-policy continuation.

        The optimization loop:
        1. Run iteration with current (candidate) policies
        2. Compare results to best known policy
        3. If better: Accept candidate as new best
        4. If worse: Reject candidate, continue from best
        5. Generate new candidate from best policy
        6. Repeat until convergence or max iterations

        This ensures we never regress - we always continue from the best
        discovered policy, not the most recent (potentially worse) one.
        """
        print(f"\n{'#'*60}")
        print(f"# {self.experiment_def['name']}")
        print(f"# Experiment ID: {self.experiment_id}")
        print(f"# Master seed: {self.master_seed}")
        print(f"# Best-policy continuation: ENABLED")
        if self.verbose:
            print(f"# Verbose mode: ENABLED")
        print(f"{'#'*60}")

        if self.verbose:
            print(f"\n[VERBOSE] Configuration:")
            print(f"  Model: {self.model}")
            print(f"  Reasoning effort: {self.reasoning_effort}")
            print(f"  Max iterations: {self.max_iterations}")
            print(f"  Seeds per iteration: {self.num_seeds}")
            print(f"  Convergence threshold: {self.convergence_threshold}")
            print(f"  Convergence window: {self.convergence_window}")
            print(f"  Output dir: {self.output_dir}")
            print(f"  Config path: {self.config_path}")
            print(f"\n[VERBOSE] Cost rates:")
            for key, value in self.config.get("cost_rates", {}).items():
                print(f"    {key}: {value}")
            print(f"\n[VERBOSE] Initial policies loaded from:")
            print(f"    Bank A: {self.experiment_def['policy_a_path']}")
            print(f"    Bank B: {self.experiment_def['policy_b_path']}")

        self.setup()

        accepted_count = 0
        rejected_count = 0

        for iteration in range(1, self.max_iterations + 1):
            result = self.run_iteration(iteration)

            # Track acceptance statistics
            if result.get("was_accepted"):
                accepted_count += 1
            else:
                rejected_count += 1

            # Handle failed iterations (all simulations crashed)
            if result.get("failed"):
                print(f"  Skipping optimization due to simulation failures")
                continue

            if result["converged"]:
                print(f"\n✓ Converged at iteration {iteration}")
                break

            if iteration < self.max_iterations:
                # Generate new candidate from BEST policy (not current)
                if not self.optimize_policies(iteration, result["metrics"], result["results"]):
                    print("  Optimization failed, continuing with best policy")
                    # Ensure we're using best policy for next iteration
                    self.policy_a = self.best_policy_a.copy()
                    self.policy_b = self.best_policy_b.copy()

        # Export summary
        summary = self.db.export_summary()

        print(f"\n{'='*60}")
        print("Experiment Complete")
        print(f"{'='*60}")
        print(f"  Iterations: {len(self.history)}")
        print(f"  Accepted: {accepted_count} | Rejected: {rejected_count}")
        if self.best_metrics:
            print(f"  Best cost: ${self.best_metrics['total_cost_mean']:,.0f} (iteration {self.best_iteration})")
        else:
            print("  WARNING: No successful iterations completed")
        print(f"  Database: {self.db.db_path}")

        # Close DB connection before chart generation (DuckDB doesn't allow
        # multiple connections with different configurations)
        db_path = self.db.db_path
        self.db.close()

        # Generate all charts
        print(f"\nGenerating charts...")
        generate_all_charts(db_path=db_path, output_dir=self.output_dir)

        return summary


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Reproducible Experiment Runner for Castro et al. Replication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run Experiment 1 (Two-Period, Castro-Aligned)
  python reproducible_experiment.py --experiment exp1 --output exp1.db

  # Run Experiment 2 (Twelve-Period, Castro-Aligned)
  python reproducible_experiment.py --experiment exp2 --output exp2.db

  # Run Experiment 3 (Joint Learning, Castro-Aligned)
  python reproducible_experiment.py --experiment exp3 --output exp3.db

  # Run with Claude Sonnet 4.5 and extended thinking (32K token budget)
  python reproducible_experiment.py --experiment exp2 \\
      --model anthropic:claude-sonnet-4-5-20250929 \\
      --thinking-budget 32000

  # Run with Claude without thinking (standard mode)
  python reproducible_experiment.py --experiment exp2 \\
      --model anthropic:claude-sonnet-4-5-20250929

  # Generate charts from an existing database
  python reproducible_experiment.py --charts experiment.db

  # Generate charts to a specific directory
  python reproducible_experiment.py --charts experiment.db --chart-output ./charts

  # List available experiments
  python reproducible_experiment.py --list
""",
    )

    parser.add_argument(
        "--experiment", "-e",
        choices=list(EXPERIMENTS.keys()),
        help="Experiment to run",
    )
    parser.add_argument(
        "--output", "-o",
        default="experiment.db",
        help="Output database path (default: experiment.db)",
    )
    parser.add_argument(
        "--model", "-m",
        default="gpt-4o",
        help="LLM model to use (default: gpt-4o)",
    )
    parser.add_argument(
        "--reasoning",
        default="high",
        choices=["none", "low", "medium", "high"],
        help="Reasoning effort level (default: high)",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Token budget for Anthropic Claude extended thinking mode. "
             "Enables deep reasoning when using anthropic: models. "
             "Minimum 1024, recommended 10000-32000. "
             "Example: --thinking-budget 32000",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        help="Override max iterations",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available experiments",
    )
    parser.add_argument(
        "--simcash-root",
        default=str(PROJECT_ROOT),
        help="SimCash root directory",
    )
    parser.add_argument(
        "--master-seed",
        type=int,
        default=None,
        help="Master seed for reproducibility (pre-generates all iteration seeds)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose mode: output detailed progress and all validation errors",
    )
    parser.add_argument(
        "--charts",
        metavar="DB_PATH",
        help="Generate charts from an existing experiment database",
    )
    parser.add_argument(
        "--chart-output",
        metavar="DIR",
        help="Output directory for charts (default: same as database directory)",
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable Experiments:")
        print("=" * 60)
        for key, exp in EXPERIMENTS.items():
            print(f"\n{key}:")
            print(f"  Name: {exp['name']}")
            print(f"  Description: {exp['description']}")
            print(f"  Config: {exp['config_path']}")
            print(f"  Seeds: {exp['num_seeds']}")
            print(f"  Max iterations: {exp['max_iterations']}")
        return

    if args.charts:
        # Generate charts from existing database
        output_dir = Path(args.chart_output) if args.chart_output else None
        generate_all_charts(db_path=args.charts, output_dir=output_dir)
        return

    if not args.experiment:
        parser.error("--experiment is required (use --list to see options)")

    # Override max_iter if specified
    if args.max_iter:
        EXPERIMENTS[args.experiment]["max_iterations"] = args.max_iter

    # Validate thinking_budget with model
    if args.thinking_budget is not None and not args.model.startswith("anthropic:"):
        print(
            f"Warning: --thinking-budget is only supported for Anthropic models "
            f"(anthropic:*). Current model: {args.model}"
        )
        print("Ignoring --thinking-budget.")
        args.thinking_budget = None

    # Run experiment
    experiment = ReproducibleExperiment(
        experiment_key=args.experiment,
        db_path=args.output,
        simcash_root=args.simcash_root,
        model=args.model,
        reasoning_effort=args.reasoning,
        master_seed=args.master_seed,
        verbose=args.verbose,
        thinking_budget=args.thinking_budget,
    )

    experiment.run()


if __name__ == "__main__":
    main()
