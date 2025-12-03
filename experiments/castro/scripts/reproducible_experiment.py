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
import yaml

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS
from experiments.castro.prompts.context import IterationRecord, compute_policy_diff


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
        "convergence_window": 3,
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
        "convergence_window": 3,
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
        "convergence_window": 3,
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
        notes: str | None = None,
    ) -> None:
        """Record experiment configuration."""
        self.conn.execute("""
            INSERT INTO experiment_config VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            notes,
        ])

    def record_policy_iteration(
        self,
        experiment_id: str,
        iteration_number: int,
        agent_id: str,
        policy_json: str,
        created_by: str = "init",
    ) -> str:
        """Record a policy iteration."""
        iteration_id = str(uuid.uuid4())
        policy_dict = json.loads(policy_json)
        parameters = extract_parameters(policy_dict)

        self.conn.execute("""
            INSERT INTO policy_iterations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    ) -> str:
        """Record aggregated iteration metrics."""
        metric_id = str(uuid.uuid4())

        self.conn.execute("""
            INSERT INTO iteration_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
# Simulation Runner
# ============================================================================

def run_single_simulation(args: tuple) -> dict:
    """Run a single simulation (for parallel execution)."""
    config_path, simcash_root, seed, capture_verbose = args

    try:
        cmd = [
            str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
            "run",
            "--config", str(config_path),
            "--seed", str(seed),
        ]

        if not capture_verbose:
            cmd.append("--quiet")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(simcash_root),
            timeout=60,
        )

        if result.returncode != 0:
            return {"error": f"Simulation failed: {result.stderr}", "seed": seed}

        # Parse output
        if capture_verbose:
            verbose_output = result.stdout
            # Run again quiet for JSON
            quiet_result = subprocess.run(
                cmd + ["--quiet"],
                capture_output=True,
                text=True,
                cwd=str(simcash_root),
                timeout=60,
            )
            output = json.loads(quiet_result.stdout)
        else:
            verbose_output = None
            output = json.loads(result.stdout)

        costs = output.get("costs", {})
        agents = {a["id"]: a for a in output.get("agents", [])}

        total_cost = costs.get("total_cost", 0)

        return {
            "seed": seed,
            "total_cost": total_cost,
            "bank_a_cost": total_cost / 2,
            "bank_b_cost": total_cost / 2,
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
            "verbose_log": verbose_output,
        }
    except Exception as e:
        return {"error": str(e), "seed": seed}


def run_simulations_parallel(
    config_path: str,
    simcash_root: str,
    seeds: list[int],
    capture_verbose_for: list[int] | None = None,
) -> list[dict]:
    """Run simulations in parallel."""
    if capture_verbose_for is None:
        capture_verbose_for = []

    args_list = [
        (config_path, simcash_root, seed, seed in capture_verbose_for)
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
    """
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        return None  # Let caller handle this gracefully

    costs = [r["total_cost"] for r in valid_results]
    settlements = [r["settlement_rate"] for r in valid_results]

    import statistics
    mean_cost = statistics.mean(costs)
    std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

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
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        reasoning_effort: str = "high",
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort

        # Create RobustPolicyAgent with constraints
        # Use "high" reasoning for GPT-5.1, map string to literal
        effort_mapping = {"low": "low", "medium": "medium", "high": "high"}
        effort = effort_mapping.get(reasoning_effort, "high")

        self.agent = RobustPolicyAgent(
            constraints=STANDARD_CONSTRAINTS,
            model=model,
            reasoning_effort=effort,  # type: ignore
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
        other_bank_policy: dict[str, Any] | None = None,
    ) -> tuple[dict | None, int, float]:
        """Generate an optimized policy using PydanticAI with extended context.

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
                # Pass through extended context
                iteration_history=iteration_history,
                best_seed_output=best_seed_output,
                worst_seed_output=worst_seed_output,
                best_seed=best_seed,
                worst_seed=worst_seed,
                best_seed_cost=best_seed_cost,
                worst_seed_cost=worst_seed_cost,
                cost_breakdown=cost_breakdown,
                cost_rates=cost_rates,
                other_bank_policy=other_bank_policy,
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
    """

    # Maximum retries when LLM produces invalid policy
    MAX_VALIDATION_RETRIES = 3

    def __init__(
        self,
        experiment_key: str,
        db_path: str,
        simcash_root: str = "/home/user/SimCash",
        model: str = "gpt-4o",
        reasoning_effort: str = "high",
    ):
        self.experiment_def = EXPERIMENTS[experiment_key]
        self.experiment_id = f"{experiment_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.simcash_root = Path(simcash_root)

        self.db = ExperimentDatabase(db_path)
        self.optimizer = LLMOptimizer(model=model, reasoning_effort=reasoning_effort)

        # Load configs
        self.config_path = self.simcash_root / self.experiment_def["config_path"]
        self.config = load_yaml_config(str(self.config_path))

        # Create output directories for iteration-specific files
        self.output_dir = Path(db_path).parent
        self.policies_dir = self.output_dir / "policies"
        self.configs_dir = self.output_dir / "configs"
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

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

        # Track current iteration config path
        self.current_config_path: Path | None = None

        # History (metrics only - for convergence checking)
        self.history: list[dict] = []

        # Full iteration history with policies and changes (for LLM context)
        self.iteration_records: list[IterationRecord] = []

        # Track policy history for computing diffs
        self.policy_history_a: list[dict] = [self.policy_a.copy()]
        self.policy_history_b: list[dict] = [self.policy_b.copy()]

        # Last iteration's verbose output (best/worst seeds)
        self.last_best_seed_output: str | None = None
        self.last_worst_seed_output: str | None = None
        self.last_best_seed: int = 0
        self.last_worst_seed: int = 0
        self.last_best_cost: int = 0
        self.last_worst_cost: int = 0
        self.last_cost_breakdown: dict[str, int] = {}

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
        """
        is_valid, _, errors = self.validate_policy_with_details(policy, agent_name)
        if is_valid:
            return policy, True

        print(f"  {agent_name} policy invalid, attempting LLM fix...")

        # Track all errors for logging
        all_errors: list[tuple[int, dict, list[str]]] = [(0, policy, errors)]

        for attempt in range(self.MAX_VALIDATION_RETRIES):
            fixed = self.request_policy_fix_from_llm(policy, agent_name, errors)
            if fixed is None:
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
        """Run a single iteration."""
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}/{self.max_iterations}")
        print(f"{'='*60}")

        # Create iteration-specific config with current policies
        config_path = self.create_iteration_config(iteration)

        # Run simulations - capture verbose for ALL seeds so we can get best/worst later
        seeds = list(range(1, self.num_seeds + 1))
        # Capture verbose for first, last, and a sample in between
        if len(seeds) <= 3:
            verbose_seeds = seeds
        else:
            verbose_seeds = [seeds[0], seeds[len(seeds)//2], seeds[-1]]

        print(f"  Running {len(seeds)} simulations...")
        results = run_simulations_parallel(
            config_path=str(config_path),
            simcash_root=str(self.simcash_root),
            seeds=seeds,
            capture_verbose_for=verbose_seeds,
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

        # Compute metrics
        metrics = compute_metrics(results)

        if metrics is None:
            print("  ERROR: All simulations failed, reverting to previous policies")
            # Revert to last known good policies
            if self.history:
                last_good = self.history[-1]
                self.policy_a = last_good.get("policy_a", self.policy_a)
                self.policy_b = last_good.get("policy_b", self.policy_b)
            # Return with failure metrics
            return {
                "iteration": iteration,
                "metrics": {"total_cost_mean": float("inf"), "total_cost_std": 0,
                           "settlement_rate_mean": 0, "failure_rate": 1.0,
                           "best_seed_cost": float("inf"), "worst_seed_cost": float("inf"),
                           "best_seed": 0, "worst_seed": 0, "risk_adjusted_cost": float("inf")},
                "results": results,
                "converged": False,
                "failed": True,
            }

        print(f"  Mean cost: ${metrics['total_cost_mean']:,.0f} ± ${metrics['total_cost_std']:,.0f}")
        print(f"  Settlement rate: {metrics['settlement_rate_mean']*100:.1f}%")
        print(f"  Failure rate: {metrics['failure_rate']*100:.0f}%")

        # Extract best/worst seed verbose output for LLM context
        self._extract_best_worst_context(results, metrics)

        # Build iteration record for history
        self._record_iteration(iteration, metrics)

        # Check convergence
        converged = self.check_convergence(metrics)

        # Record metrics
        self.db.record_iteration_metrics(
            experiment_id=self.experiment_id,
            iteration_number=iteration,
            metrics=metrics,
            converged=converged,
        )

        self.history.append(metrics)

        return {
            "iteration": iteration,
            "metrics": metrics,
            "results": results,
            "converged": converged,
        }

    def _extract_best_worst_context(self, results: list[dict], metrics: dict) -> None:
        """Extract verbose output and cost breakdown from best/worst seeds."""
        valid_results = [r for r in results if "error" not in r]
        if not valid_results:
            return

        # Find best and worst by cost
        best_result = min(valid_results, key=lambda r: r.get("total_cost", float("inf")))
        worst_result = max(valid_results, key=lambda r: r.get("total_cost", 0))

        # Store verbose output
        self.last_best_seed_output = best_result.get("verbose_log")
        self.last_worst_seed_output = worst_result.get("verbose_log")
        self.last_best_seed = best_result.get("seed", 0)
        self.last_worst_seed = worst_result.get("seed", 0)
        self.last_best_cost = int(best_result.get("total_cost", 0))
        self.last_worst_cost = int(worst_result.get("total_cost", 0))

        # Aggregate cost breakdown from worst seed (to show problem areas)
        cost_bd = worst_result.get("cost_breakdown", {})
        self.last_cost_breakdown = {
            "delay": int(cost_bd.get("delay", 0)),
            "collateral": int(cost_bd.get("collateral", 0)),
            "overdraft": int(cost_bd.get("overdraft", 0)),
            "eod_penalty": int(cost_bd.get("eod_penalty", 0)),
        }

        # If best seed has no verbose output but worst does, try to get best from DB
        if self.last_best_seed_output is None and self.last_best_seed != self.last_worst_seed:
            # Run a separate simulation for best seed with verbose
            print(f"  Capturing verbose output for best seed #{self.last_best_seed}...")
            best_results = run_simulations_parallel(
                config_path=str(self.current_config_path) if self.current_config_path else "",
                simcash_root=str(self.simcash_root),
                seeds=[self.last_best_seed],
                capture_verbose_for=[self.last_best_seed],
            )
            if best_results and "error" not in best_results[0]:
                self.last_best_seed_output = best_results[0].get("verbose_log")

    def _record_iteration(self, iteration: int, metrics: dict) -> None:
        """Record this iteration in the history with policy changes."""
        # Compute policy changes from previous iteration
        prev_policy_a = self.policy_history_a[-1] if self.policy_history_a else {}
        prev_policy_b = self.policy_history_b[-1] if self.policy_history_b else {}

        changes_a = compute_policy_diff(prev_policy_a, self.policy_a) if prev_policy_a else []
        changes_b = compute_policy_diff(prev_policy_b, self.policy_b) if prev_policy_b else []

        record = IterationRecord(
            iteration=iteration,
            metrics=metrics,
            policy_a=self.policy_a.copy(),
            policy_b=self.policy_b.copy(),
            policy_a_changes=changes_a,
            policy_b_changes=changes_b,
        )
        self.iteration_records.append(record)

    def optimize_policies(self, iteration: int, metrics: dict, results: list[dict]) -> bool:
        """Call LLM to optimize policies using PydanticAI structured output.

        Passes rich historical context including:
        - Full tick-by-tick output from best and worst seeds
        - Complete iteration history with metrics and policy changes
        - Cost breakdown for optimization guidance
        """
        print(f"  Calling LLM for optimization with extended context...")
        print(f"    - History: {len(self.iteration_records)} previous iterations")
        print(f"    - Best seed #{self.last_best_seed}: ${self.last_best_cost:,}")
        print(f"    - Worst seed #{self.last_worst_seed}: ${self.last_worst_cost:,}")

        # Create instruction prompt
        instruction = f"""Optimize policy for iteration {iteration}.

Current performance: Mean cost ${metrics['total_cost_mean']:,.0f}, Settlement {metrics['settlement_rate_mean']*100:.1f}%
Goal: Reduce cost while maintaining 100% settlement.

IMPORTANT: Review the tick-by-tick simulation output below to understand:
1. What patterns lead to high costs (worst seed)
2. What patterns lead to low costs (best seed)
3. Which cost component dominates (delay vs collateral vs overdraft)

Use this insight to make targeted policy improvements."""

        # Generate policy for Bank A with full context
        policy_a, tokens_a, latency_a = self.optimizer.generate_policy(
            instruction=instruction,
            current_policy=self.policy_a,
            current_cost=metrics['total_cost_mean'] / 2,  # Approximate per-bank cost
            settlement_rate=metrics['settlement_rate_mean'],
            iteration=iteration,
            # Extended context
            iteration_history=self.iteration_records,
            best_seed_output=self.last_best_seed_output,
            worst_seed_output=self.last_worst_seed_output,
            best_seed=self.last_best_seed,
            worst_seed=self.last_worst_seed,
            best_seed_cost=self.last_best_cost,
            worst_seed_cost=self.last_worst_cost,
            cost_breakdown=self.last_cost_breakdown,
            cost_rates=self.config.get("cost_rates", {}),
            other_bank_policy=self.policy_b,
        )

        # Generate policy for Bank B (may be same or different based on scenario)
        policy_b, tokens_b, latency_b = self.optimizer.generate_policy(
            instruction=instruction,
            current_policy=self.policy_b,
            current_cost=metrics['total_cost_mean'] / 2,
            settlement_rate=metrics['settlement_rate_mean'],
            iteration=iteration,
            # Extended context
            iteration_history=self.iteration_records,
            best_seed_output=self.last_best_seed_output,
            worst_seed_output=self.last_worst_seed_output,
            best_seed=self.last_best_seed,
            worst_seed=self.last_worst_seed,
            best_seed_cost=self.last_best_cost,
            worst_seed_cost=self.last_worst_cost,
            cost_breakdown=self.last_cost_breakdown,
            cost_rates=self.config.get("cost_rates", {}),
            other_bank_policy=self.policy_a,
        )

        total_tokens = tokens_a + tokens_b
        total_latency = latency_a + latency_b

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

        if policy_a is None or policy_b is None:
            print("  ERROR: Policy generation failed")
            return False

        # Validate policies with retry logic (NEVER writes to seed files)
        # Log all validation errors to database for analysis
        new_policy_a, was_valid_a = self.validate_and_fix_policy(
            policy_a, "Bank A", self.policy_a, iteration=iteration
        )
        new_policy_b, was_valid_b = self.validate_and_fix_policy(
            policy_b, "Bank B", self.policy_b, iteration=iteration
        )

        # Update current policies (in-memory only, seed files never modified)
        self.policy_a = new_policy_a
        self.policy_b = new_policy_b

        # Track policy history for computing diffs in next iteration
        self.policy_history_a.append(new_policy_a.copy())
        self.policy_history_b.append(new_policy_b.copy())

        # Record new policies to database
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=iteration + 1,
            agent_id="BANK_A",
            policy_json=json.dumps(new_policy_a),
            created_by="llm",
        )
        self.db.record_policy_iteration(
            experiment_id=self.experiment_id,
            iteration_number=iteration + 1,
            agent_id="BANK_B",
            policy_json=json.dumps(new_policy_b),
            created_by="llm",
        )

        # NOTE: Policies are saved to iteration-specific files in run_iteration()
        # via create_iteration_config(). The seed policy files are NEVER modified.

        print(f"  Policies updated for iteration {iteration + 1}")
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
        """Run the full experiment."""
        print(f"\n{'#'*60}")
        print(f"# {self.experiment_def['name']}")
        print(f"# Experiment ID: {self.experiment_id}")
        print(f"{'#'*60}")

        self.setup()

        for iteration in range(1, self.max_iterations + 1):
            result = self.run_iteration(iteration)

            # Handle failed iterations (all simulations crashed)
            if result.get("failed"):
                print(f"  Skipping optimization due to simulation failures")
                continue

            if result["converged"]:
                print(f"\n✓ Converged at iteration {iteration}")
                break

            if iteration < self.max_iterations:
                if not self.optimize_policies(iteration, result["metrics"], result["results"]):
                    print("  Optimization failed, continuing with current policies")

        # Export summary
        summary = self.db.export_summary()

        print(f"\n{'='*60}")
        print("Experiment Complete")
        print(f"{'='*60}")
        if self.history:
            print(f"  Final mean cost: ${self.history[-1]['total_cost_mean']:,.0f}")
        else:
            print("  WARNING: No successful iterations completed")
        print(f"  Database: {self.db.db_path}")

        self.db.close()

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
        default="/home/user/SimCash",
        help="SimCash root directory",
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

    if not args.experiment:
        parser.error("--experiment is required (use --list to see options)")

    # Override max_iter if specified
    if args.max_iter:
        EXPERIMENTS[args.experiment]["max_iterations"] = args.max_iter

    # Run experiment
    experiment = ReproducibleExperiment(
        experiment_key=args.experiment,
        db_path=args.output,
        simcash_root=args.simcash_root,
        model=args.model,
        reasoning_effort=args.reasoning,
    )

    experiment.run()


if __name__ == "__main__":
    main()
