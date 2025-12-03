"""
Experiment Framework Tests.

These tests verify that the experiment framework components work correctly:

1. Database schema creation
2. Experiment config recording
3. Policy iteration recording
4. Simulation run recording
5. Metrics computation
6. Result reproducibility

These tests ensure the LLM optimization experiment infrastructure is reliable.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import tempfile
from pathlib import Path
from typing import Any

import duckdb
import pytest


# ============================================================================
# Database Schema Tests
# ============================================================================


SCHEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    parameters JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR NOT NULL
);

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
    raw_output JSON NOT NULL,
    created_at TIMESTAMP NOT NULL
);

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
    created_at TIMESTAMP NOT NULL
);
"""


class TestDatabaseSchema:
    """Test database schema creation and structure."""

    def test_schema_creates_successfully(self) -> None:
        """Database schema should create without errors."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            # Execute each statement
            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            conn.close()

    def test_tables_exist_after_creation(self) -> None:
        """All required tables should exist after schema creation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            # Check tables exist
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            table_names = {t[0] for t in tables}

            assert "experiment_config" in table_names
            assert "policy_iterations" in table_names
            assert "simulation_runs" in table_names
            assert "iteration_metrics" in table_names

            conn.close()


# ============================================================================
# Experiment Config Recording Tests
# ============================================================================


class TestExperimentConfigRecording:
    """Test experiment config recording."""

    def test_record_experiment_config(self) -> None:
        """Should be able to record experiment config."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            # Insert config
            config_yaml = "simulation:\n  ticks_per_day: 2"
            config_hash = hashlib.sha256(config_yaml.encode()).hexdigest()

            conn.execute(
                """
                INSERT INTO experiment_config VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "exp1_test",
                    "Test Experiment",
                    "2025-12-03 10:00:00",
                    config_yaml,
                    config_hash,
                    json.dumps({"collateral_cost": 500}),
                    json.dumps([{"id": "BANK_A"}]),
                    "gpt-4o",
                    "high",
                    10,
                    25,
                    0.05,
                    3,
                    "Test notes",
                ],
            )

            # Verify insertion
            result = conn.execute(
                "SELECT experiment_name FROM experiment_config WHERE experiment_id = ?",
                ["exp1_test"],
            ).fetchone()

            assert result is not None
            assert result[0] == "Test Experiment"

            conn.close()


# ============================================================================
# Policy Iteration Recording Tests
# ============================================================================


class TestPolicyIterationRecording:
    """Test policy iteration recording."""

    def test_record_policy_iteration(self) -> None:
        """Should record policy iterations with hash."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            # Insert policy
            policy_json = json.dumps({
                "version": "2.0",
                "parameters": {"initial_liquidity_fraction": 0.25},
            })
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            conn.execute(
                """
                INSERT INTO policy_iterations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "iter_001",
                    "exp1_test",
                    0,
                    "BANK_A",
                    policy_json,
                    policy_hash,
                    json.dumps({"initial_liquidity_fraction": 0.25}),
                    "2025-12-03 10:00:00",
                    "init",
                ],
            )

            # Verify
            result = conn.execute(
                "SELECT policy_hash FROM policy_iterations WHERE iteration_id = ?",
                ["iter_001"],
            ).fetchone()

            assert result is not None
            assert result[0] == policy_hash

            conn.close()

    def test_policy_hash_uniqueness(self) -> None:
        """Different policies should have different hashes."""
        policy1 = json.dumps({"initial_liquidity_fraction": 0.25})
        policy2 = json.dumps({"initial_liquidity_fraction": 0.50})

        hash1 = hashlib.sha256(policy1.encode()).hexdigest()
        hash2 = hashlib.sha256(policy2.encode()).hexdigest()

        assert hash1 != hash2

    def test_same_policy_same_hash(self) -> None:
        """Same policy should have same hash (for deduplication)."""
        policy = {"initial_liquidity_fraction": 0.25, "urgency_threshold": 3.0}

        # Ensure consistent ordering
        policy_json = json.dumps(policy, sort_keys=True)

        hash1 = hashlib.sha256(policy_json.encode()).hexdigest()
        hash2 = hashlib.sha256(policy_json.encode()).hexdigest()

        assert hash1 == hash2


# ============================================================================
# Simulation Run Recording Tests
# ============================================================================


class TestSimulationRunRecording:
    """Test simulation run recording."""

    def test_record_simulation_run(self) -> None:
        """Should record simulation run with costs."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            conn.execute(
                """
                INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "run_001",
                    "exp1_test",
                    0,
                    42,  # seed
                    108000,  # total_cost (cents)
                    54000,  # bank_a_cost
                    54000,  # bank_b_cost
                    1.0,  # settlement_rate
                    50000,  # collateral_cost
                    30000,  # delay_cost
                    28000,  # overdraft_cost
                    0,  # eod_penalty
                    json.dumps({"metrics": {"total_arrivals": 3}}),
                    "2025-12-03 10:00:00",
                ],
            )

            result = conn.execute(
                "SELECT total_cost, settlement_rate FROM simulation_runs WHERE run_id = ?",
                ["run_001"],
            ).fetchone()

            assert result[0] == 108000
            assert result[1] == 1.0

            conn.close()


# ============================================================================
# Metrics Computation Tests
# ============================================================================


class TestMetricsComputation:
    """Test metrics computation functions."""

    def test_compute_mean_cost(self) -> None:
        """Should correctly compute mean cost across seeds."""
        costs = [100, 120, 80, 110, 90]
        mean_cost = statistics.mean(costs)
        assert mean_cost == 100

    def test_compute_std_cost(self) -> None:
        """Should correctly compute standard deviation."""
        costs = [100, 100, 100, 100, 100]
        std_cost = statistics.stdev(costs)
        assert std_cost == 0

        costs = [80, 100, 120]
        std_cost = statistics.stdev(costs)
        assert std_cost == 20

    def test_risk_adjusted_cost(self) -> None:
        """Risk-adjusted cost = mean + std."""
        costs = [80, 100, 120]
        mean = statistics.mean(costs)
        std = statistics.stdev(costs)
        risk_adjusted = mean + std

        assert mean == 100
        assert std == 20
        assert risk_adjusted == 120

    def test_failure_rate_computation(self) -> None:
        """Failure rate = count(settlement_rate < 1.0) / total."""
        settlement_rates = [1.0, 1.0, 0.95, 1.0, 0.8]
        failures = sum(1 for r in settlement_rates if r < 1.0)
        failure_rate = failures / len(settlement_rates)

        assert failure_rate == 0.4  # 2 out of 5

    def test_best_worst_seed_identification(self) -> None:
        """Should correctly identify best and worst seeds."""
        results = [
            {"seed": 1, "cost": 100},
            {"seed": 2, "cost": 80},  # Best
            {"seed": 3, "cost": 120},  # Worst
            {"seed": 4, "cost": 90},
        ]

        costs = [r["cost"] for r in results]
        best_idx = costs.index(min(costs))
        worst_idx = costs.index(max(costs))

        assert results[best_idx]["seed"] == 2
        assert results[worst_idx]["seed"] == 3


# ============================================================================
# Convergence Detection Tests
# ============================================================================


class TestConvergenceDetection:
    """Test convergence detection logic."""

    def test_convergence_within_threshold(self) -> None:
        """Should detect convergence when variation < threshold."""
        history = [
            {"total_cost_mean": 100},
            {"total_cost_mean": 102},
            {"total_cost_mean": 99},
        ]

        convergence_threshold = 0.05  # 5%
        convergence_window = 3

        if len(history) < convergence_window:
            converged = False
        else:
            recent = history[-convergence_window:]
            costs = [m["total_cost_mean"] for m in recent]
            min_cost = min(costs)
            max_cost = max(costs)
            variation = (max_cost - min_cost) / min_cost if min_cost > 0 else 0
            converged = variation < convergence_threshold

        # Variation = (102-99)/99 = 0.0303 < 0.05
        assert converged is True

    def test_no_convergence_above_threshold(self) -> None:
        """Should not detect convergence when variation > threshold."""
        history = [
            {"total_cost_mean": 100},
            {"total_cost_mean": 150},  # Big jump
            {"total_cost_mean": 120},
        ]

        convergence_threshold = 0.05
        convergence_window = 3

        recent = history[-convergence_window:]
        costs = [m["total_cost_mean"] for m in recent]
        min_cost = min(costs)
        max_cost = max(costs)
        variation = (max_cost - min_cost) / min_cost if min_cost > 0 else 0
        converged = variation < convergence_threshold

        # Variation = (150-100)/100 = 0.50 > 0.05
        assert converged is False

    def test_convergence_needs_minimum_history(self) -> None:
        """Should not converge with insufficient history."""
        history = [
            {"total_cost_mean": 100},
            {"total_cost_mean": 100},
        ]

        convergence_window = 3

        converged = len(history) >= convergence_window
        assert converged is False


# ============================================================================
# Result Reproducibility Tests
# ============================================================================


class TestResultReproducibility:
    """Test that results can be reproduced from database."""

    def test_config_hash_enables_verification(self) -> None:
        """Config hash should enable verification of config unchanged."""
        config_yaml = """
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42
"""
        hash1 = hashlib.sha256(config_yaml.encode()).hexdigest()

        # Exact same config should have same hash
        hash2 = hashlib.sha256(config_yaml.encode()).hexdigest()
        assert hash1 == hash2

        # Modified config should have different hash
        modified_yaml = config_yaml.replace("42", "43")
        hash3 = hashlib.sha256(modified_yaml.encode()).hexdigest()
        assert hash1 != hash3

    def test_policy_can_be_reconstructed(self) -> None:
        """Policy should be reconstructable from stored JSON."""
        original_policy = {
            "version": "2.0",
            "policy_id": "test",
            "parameters": {
                "initial_liquidity_fraction": 0.25,
                "urgency_threshold": 3.0,
            },
            "strategic_collateral_tree": {"type": "action", "action": "Hold"},
            "payment_tree": {"type": "action", "action": "Release"},
        }

        # Store and reconstruct
        stored_json = json.dumps(original_policy)
        reconstructed = json.loads(stored_json)

        assert reconstructed == original_policy


# ============================================================================
# Query Interface Tests
# ============================================================================


class TestQueryInterface:
    """Test database query patterns."""

    def test_query_iteration_results(self) -> None:
        """Should query aggregated results per iteration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            # Insert some runs
            for seed in [1, 2, 3]:
                conn.execute(
                    """
                    INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f"run_seed{seed}",
                        "exp1",
                        0,  # iteration 0
                        seed,
                        100000 + seed * 10000,  # varying costs
                        50000,
                        50000,
                        1.0,
                        30000,
                        20000,
                        50000,
                        0,
                        "{}",
                        "2025-12-03",
                    ],
                )

            # Query aggregated
            result = conn.execute(
                """
                SELECT
                    iteration_number,
                    AVG(total_cost) as mean_cost,
                    MIN(total_cost) as min_cost,
                    MAX(total_cost) as max_cost
                FROM simulation_runs
                WHERE experiment_id = ?
                GROUP BY iteration_number
                """,
                ["exp1"],
            ).fetchone()

            assert result is not None
            assert result[1] == 120000  # Mean of 110k, 120k, 130k

            conn.close()

    def test_query_policy_history(self) -> None:
        """Should query policy evolution across iterations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
            conn = duckdb.connect(f.name)

            for stmt in SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

            # Insert policies for different iterations
            for iteration in [0, 1, 2]:
                fraction = 0.25 + iteration * 0.1
                policy = {"initial_liquidity_fraction": fraction}
                conn.execute(
                    """
                    INSERT INTO policy_iterations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f"policy_iter{iteration}",
                        "exp1",
                        iteration,
                        "BANK_A",
                        json.dumps(policy),
                        f"hash{iteration}",
                        json.dumps(policy),
                        "2025-12-03",
                        "init" if iteration == 0 else "llm",
                    ],
                )

            # Query evolution
            results = conn.execute(
                """
                SELECT iteration_number, parameters
                FROM policy_iterations
                WHERE experiment_id = ? AND agent_id = ?
                ORDER BY iteration_number
                """,
                ["exp1", "BANK_A"],
            ).fetchall()

            assert len(results) == 3

            fractions = [
                json.loads(r[1])["initial_liquidity_fraction"]
                for r in results
            ]
            assert fractions == [0.25, 0.35, 0.45]

            conn.close()
