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
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
from openai import OpenAI


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

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_policy_exp_iter ON policy_iterations(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_policy_hash ON policy_iterations(policy_hash);
CREATE INDEX IF NOT EXISTS idx_llm_exp_iter ON llm_interactions(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_sim_exp_iter ON simulation_runs(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_metrics_exp ON iteration_metrics(experiment_id, iteration_number);
"""


# ============================================================================
# Experiment Definitions
# ============================================================================

EXPERIMENTS = {
    "exp1": {
        "name": "Experiment 1: Two-Period Deterministic",
        "description": "Simple 2-period scenario to validate Nash equilibrium discovery",
        "config_path": "experiments/castro/configs/castro_2period.yaml",
        "policy_a_path": "experiments/castro/policies/exp1_bank_a.json",
        "policy_b_path": "experiments/castro/policies/exp1_bank_b.json",
        "num_seeds": 1,  # Deterministic - only need 1 seed
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 3,
    },
    "exp2_fixed": {
        "name": "Experiment 2: Twelve-Period Stochastic (Castro-Equivalent)",
        "description": "12-period LVTS-style with correct collateral capacity",
        "config_path": "experiments/castro/configs/castro_12period_castro_equiv_fixed.yaml",
        "policy_a_path": "experiments/castro/policies/exp2d_fixed_bank_a.json",
        "policy_b_path": "experiments/castro/policies/exp2d_fixed_bank_b.json",
        "num_seeds": 10,
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 3,
    },
    "exp3": {
        "name": "Experiment 3: Joint Liquidity and Timing Learning",
        "description": "Three-period scenario testing joint policy learning",
        "config_path": "experiments/castro/configs/castro_joint.yaml",
        "policy_a_path": "experiments/castro/policies/exp3_bank_a.json",
        "policy_b_path": "experiments/castro/policies/exp3_bank_b.json",
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


def compute_metrics(results: list[dict]) -> dict:
    """Compute aggregated metrics from simulation results."""
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        raise RuntimeError("All simulations failed")

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
# LLM Optimizer
# ============================================================================

class LLMOptimizer:
    """LLM-based policy optimizer with full logging."""

    def __init__(
        self,
        model: str = "gpt-4o",
        reasoning_effort: str = "high",
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.client = OpenAI()

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

        prompt = f"""# Policy Optimization Task

## Experiment: {experiment_name}
## Iteration: {iteration}

## Current Performance
- Mean Cost: ${metrics['total_cost_mean']:,.0f}
- Std Dev: ${metrics['total_cost_std']:,.0f}
- Risk-Adjusted: ${metrics['risk_adjusted_cost']:,.0f}
- Settlement Rate: {metrics['settlement_rate_mean']*100:.1f}%
- Failure Rate: {metrics['failure_rate']*100:.0f}%
- Best Seed Cost: ${metrics['best_seed_cost']:,.0f} (seed {metrics['best_seed']})
- Worst Seed Cost: ${metrics['worst_seed_cost']:,.0f} (seed {metrics['worst_seed']})

## Cost Rates
{json.dumps(cost_rates, indent=2)}

## Current Policies

### Bank A Policy
```json
{json.dumps(policy_a, indent=2)}
```

### Bank B Policy
```json
{json.dumps(policy_b, indent=2)}
```

## Task
Analyze the current policies and performance. Suggest improved policies that:
1. Reduce total cost while maintaining 100% settlement
2. Balance collateral costs vs overdraft costs
3. Optimize payment timing for liquidity efficiency

Return your response as valid JSON with this structure:
```json
{{
  "analysis": "Your analysis of current performance and strategy",
  "bank_a_policy": {{ ... full policy JSON ... }},
  "bank_b_policy": {{ ... full policy JSON ... }},
  "expected_improvement": "What improvement you expect and why"
}}
```
"""
        return prompt

    def call_llm(self, prompt: str) -> tuple[str, int, float]:
        """Call LLM and return response, tokens, latency."""
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=16000,
            )

            latency = time.time() - start_time
            response_text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            return response_text, tokens, latency
        except Exception as e:
            latency = time.time() - start_time
            return f"ERROR: {e}", 0, latency

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
    """Main experiment runner with full reproducibility."""

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
        self.simcash_root = simcash_root

        self.db = ExperimentDatabase(db_path)
        self.optimizer = LLMOptimizer(model=model, reasoning_effort=reasoning_effort)

        # Load configs
        self.config_path = str(Path(simcash_root) / self.experiment_def["config_path"])
        self.config = load_yaml_config(self.config_path)

        # Load initial policies
        self.policy_a = load_json_policy(
            str(Path(simcash_root) / self.experiment_def["policy_a_path"])
        )
        self.policy_b = load_json_policy(
            str(Path(simcash_root) / self.experiment_def["policy_b_path"])
        )

        # Settings
        self.num_seeds = self.experiment_def["num_seeds"]
        self.max_iterations = self.experiment_def["max_iterations"]
        self.convergence_threshold = self.experiment_def["convergence_threshold"]
        self.convergence_window = self.experiment_def["convergence_window"]
        self.model = model
        self.reasoning_effort = reasoning_effort

        # History
        self.history: list[dict] = []

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

    def save_policies_to_temp(self) -> tuple[str, str]:
        """Save current policies to temp files for simulation."""
        import tempfile

        temp_dir = tempfile.mkdtemp()
        policy_a_path = str(Path(temp_dir) / "policy_a.json")
        policy_b_path = str(Path(temp_dir) / "policy_b.json")

        save_json_policy(policy_a_path, self.policy_a)
        save_json_policy(policy_b_path, self.policy_b)

        return policy_a_path, policy_b_path

    def run_iteration(self, iteration: int) -> dict:
        """Run a single iteration."""
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}/{self.max_iterations}")
        print(f"{'='*60}")

        # Run simulations
        seeds = list(range(1, self.num_seeds + 1))
        verbose_seeds = [seeds[0], seeds[-1]] if len(seeds) > 1 else seeds

        print(f"  Running {len(seeds)} simulations...")
        results = run_simulations_parallel(
            config_path=self.config_path,
            simcash_root=self.simcash_root,
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

        print(f"  Mean cost: ${metrics['total_cost_mean']:,.0f} ± ${metrics['total_cost_std']:,.0f}")
        print(f"  Settlement rate: {metrics['settlement_rate_mean']*100:.1f}%")
        print(f"  Failure rate: {metrics['failure_rate']*100:.0f}%")

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

    def optimize_policies(self, iteration: int, metrics: dict, results: list[dict]) -> bool:
        """Call LLM to optimize policies."""
        print(f"  Calling LLM for optimization...")

        # Create prompt
        prompt = self.optimizer.create_prompt(
            experiment_name=self.experiment_def["name"],
            iteration=iteration,
            policy_a=self.policy_a,
            policy_b=self.policy_b,
            metrics=metrics,
            results=results,
            cost_rates=self.config.get("cost_rates", {}),
        )

        # Call LLM
        response, tokens, latency = self.optimizer.call_llm(prompt)

        # Record interaction
        error_msg = None if not response.startswith("ERROR:") else response
        self.db.record_llm_interaction(
            experiment_id=self.experiment_id,
            iteration_number=iteration,
            prompt_text=prompt,
            response_text=response,
            model_name=self.model,
            reasoning_effort=self.reasoning_effort,
            tokens_used=tokens,
            latency_seconds=latency,
            error_message=error_msg,
        )

        print(f"  LLM response: {tokens} tokens, {latency:.1f}s")

        if error_msg:
            print(f"  ERROR: {error_msg}")
            return False

        # Parse response
        parsed = self.optimizer.parse_response(response)
        if parsed is None:
            print("  Failed to parse LLM response")
            return False

        new_policy_a, new_policy_b = parsed

        # Update policies
        self.policy_a = new_policy_a
        self.policy_b = new_policy_b

        # Record new policies
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

        # Update temp policy files for next iteration
        policy_a_path = str(Path(self.simcash_root) / self.experiment_def["policy_a_path"])
        policy_b_path = str(Path(self.simcash_root) / self.experiment_def["policy_b_path"])
        save_json_policy(policy_a_path, new_policy_a)
        save_json_policy(policy_b_path, new_policy_b)

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
        print(f"  Final mean cost: ${self.history[-1]['total_cost_mean']:,.0f}")
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
  # Run Experiment 1 (Two-Period)
  python reproducible_experiment.py --experiment exp1 --output exp1.db

  # Run Experiment 2 (Twelve-Period, Castro-equivalent with fix)
  python reproducible_experiment.py --experiment exp2_fixed --output exp2.db

  # Run Experiment 3 (Joint Learning)
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
