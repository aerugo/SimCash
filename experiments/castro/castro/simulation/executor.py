"""Simulation execution for castro experiments.

Provides parallel simulation execution with persistence for filtered replay.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from experiments.castro.castro.core.types import SimulationResult


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


def _run_single_simulation(args: tuple[str, str, int, str]) -> SimulationResult:
    """Run a single simulation with persistence for filtered replay.

    The simulation is run with --persist --full-replay to enable filtered
    replay of events per agent. This allows the LLM optimizer to see only
    events relevant to the bank whose policy it is optimizing.

    Args:
        args: Tuple of (config_path, simcash_root, seed, work_dir)

    Returns:
        SimulationResult dict with results or error
    """
    config_path, simcash_root, seed, work_dir = args

    try:
        # Generate unique simulation ID for this run
        sim_id = f"castro_seed{seed}_{uuid.uuid4().hex[:8]}"
        db_path = Path(work_dir) / f"sim_{seed}.db"

        cmd = [
            str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
            "run",
            "--config",
            str(config_path),
            "--seed",
            str(seed),
            "--quiet",  # No verbose during run (we'll get it via replay)
            "--persist",  # Enable persistence for replay
            "--full-replay",  # Capture all data for filtered replay
            "--db-path",
            str(db_path),
            "--simulation-id",
            sim_id,
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
        stdout_lines = result.stdout.strip().split("\n")
        json_line = None
        for line in stdout_lines:
            if line.strip().startswith("{"):
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
        # CRITICAL: Never fall back to total_cost // 2 - that violates the experiment!
        per_agent_costs = get_per_agent_costs_from_db(str(db_path), sim_id)
        if "BANK_A" not in per_agent_costs or "BANK_B" not in per_agent_costs:
            return {
                "error": f"Failed to get per-agent costs from database: {per_agent_costs}",
                "seed": seed,
            }
        bank_a_cost = per_agent_costs["BANK_A"]
        bank_b_cost = per_agent_costs["BANK_B"]

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


class ParallelSimulationExecutor:
    """Executes simulations in parallel with persistence support.

    Implements the SimulationExecutor protocol for running payment-sim
    simulations with full persistence for filtered replay.

    Usage:
        executor = ParallelSimulationExecutor(
            simcash_root="/path/to/SimCash",
            max_workers=8,
        )
        results = executor.run_simulations(
            config_path="config.yaml",
            seeds=[1, 2, 3, 4, 5],
            work_dir="results/",
        )
    """

    def __init__(
        self,
        simcash_root: str | Path,
        max_workers: int = 8,
    ) -> None:
        """Initialize executor.

        Args:
            simcash_root: Path to SimCash root directory
            max_workers: Maximum parallel workers (default 8)
        """
        self.simcash_root = str(simcash_root)
        self.max_workers = max_workers

    def run_simulations(
        self,
        config_path: str | Path,
        seeds: list[int],
        work_dir: str | Path,
    ) -> list[SimulationResult]:
        """Run simulations in parallel for all seeds.

        Simulations are run with --persist --full-replay to enable filtered
        replay per agent. Results include db_path and simulation_id for
        subsequent filtered replay.

        Args:
            config_path: Path to simulation config YAML
            seeds: List of random seeds to run
            work_dir: Directory for simulation database files

        Returns:
            List of SimulationResult dicts sorted by seed
        """
        # Ensure work_dir exists
        work_dir_path = Path(work_dir)
        work_dir_path.mkdir(parents=True, exist_ok=True)

        args_list = [
            (str(config_path), self.simcash_root, seed, str(work_dir_path))
            for seed in seeds
        ]

        results: list[SimulationResult] = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_run_single_simulation, args): args[2] for args in args_list}
            for future in as_completed(futures):
                results.append(future.result())

        return sorted(results, key=lambda x: x.get("seed", 0))

    def get_filtered_replay_output(
        self,
        db_path: str | Path,
        simulation_id: str,
        agent_id: str,
    ) -> str:
        """Get filtered verbose output for a specific agent via replay.

        Uses the payment-sim replay command with --filter-agent to produce
        verbose output showing only events relevant to the specified agent.
        This ensures the LLM optimizer only sees events for the bank whose
        policy it is optimizing.

        Args:
            db_path: Path to simulation database file
            simulation_id: Simulation ID to replay
            agent_id: Agent ID to filter for (e.g., "BANK_A")

        Returns:
            Filtered verbose output string showing only events for the specified agent

        Raises:
            RuntimeError: If replay command fails
        """
        cmd = [
            str(Path(self.simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
            "replay",
            "--simulation-id",
            simulation_id,
            "--db-path",
            str(db_path),
            "--verbose",
            "--filter-agent",
            agent_id,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.simcash_root),
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Replay failed for {agent_id}: {result.stderr}")

        return result.stdout
