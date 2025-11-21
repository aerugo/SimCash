#!/usr/bin/env python3
"""
Automated policy comparison experiment runner.

This script runs multiple simulations with different policy configurations,
collects results, and generates comparison data.
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import yaml

# Experiment configuration
BASE_CONFIG_PATH = Path("examples/configs/suboptimal_policies_25day.yaml")
RESULTS_DIR = Path("experiments/results")
SCRATCHPAD_PATH = Path("experiments/policy_comparison_scratchpad.md")

# Policies to test - focused subset for initial analysis
POLICIES_TO_TEST = [
    "cautious_liquidity_preserver",  # Conservative baseline
    "efficient_memory_adaptive",      # Current "optimal" policy
    "efficient_proactive",            # Strategic collateral use
    "aggressive_market_maker",        # High-velocity alternative
]

# Agents in the simulation
AGENTS = ["BIG_BANK_A", "BIG_BANK_B", "SMALL_BANK_A", "SMALL_BANK_B"]


def load_base_config() -> Dict[str, Any]:
    """Load the base 25-day scenario configuration."""
    with open(BASE_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def create_variant_config(
    base_config: Dict[str, Any],
    agent_to_modify: str,
    new_policy: str,
) -> Dict[str, Any]:
    """Create a variant configuration with one agent using a different policy."""
    config = json.loads(json.dumps(base_config))  # Deep copy

    for agent in config["agents"]:
        if agent["id"] == agent_to_modify:
            agent["policy"] = {
                "type": "FromJson",
                "json_path": f"backend/policies/{new_policy}.json"
            }
            break

    return config


def run_simulation(
    config: Dict[str, Any],
    run_id: str,
    output_db: Path,
) -> bool:
    """Run a single simulation with the given configuration."""
    # Save config to temporary file
    config_path = RESULTS_DIR / f"{run_id}_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    print(f"\n{'='*80}")
    print(f"Running: {run_id}")
    print(f"Config: {config_path}")
    print(f"Output: {output_db}")
    print(f"{'='*80}\n")

    # Run simulation via CLI (use absolute path to .venv in api/)
    cmd = [
        "/home/user/SimCash/api/.venv/bin/payment-sim",
        "run",
        "--config", str(config_path),
        "--persist",
        "--db-path", str(output_db),
        "--quiet",  # Suppress verbose output for batch runs
    ]

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        duration = time.time() - start_time
        print(f"✓ Completed in {duration:.1f}s")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False


def extract_results(db_path: Path, sim_id: str = None) -> Dict[str, Any]:
    """Extract key metrics from simulation database."""
    conn = duckdb.connect(str(db_path), read_only=True)

    # Get simulation ID if not provided
    if sim_id is None:
        result = conn.execute("SELECT simulation_id FROM simulations LIMIT 1").fetchone()
        if not result:
            return {}
        sim_id = result[0]

    # Get agent final states
    agent_results = conn.execute("""
        SELECT
            agent_id,
            total_cost,
            cost_delay,
            cost_overdraft,
            cost_collateral,
            cost_deadline_penalty,
            cost_split_friction,
            cost_eod_penalty,
            settlement_rate,
            total_sent,
            total_received,
            final_balance,
            max_posted_collateral,
            max_credit_used
        FROM agent_final_states
        WHERE simulation_id = ?
        ORDER BY agent_id
    """, [sim_id]).fetchall()

    # Get system-wide metrics
    system_metrics = conn.execute("""
        SELECT
            end_tick,
            total_transactions,
            settled_transactions,
            unsettled_transactions
        FROM simulations
        WHERE simulation_id = ?
    """, [sim_id]).fetchone()

    conn.close()

    # Format results
    results = {
        "simulation_id": sim_id,
        "agents": {},
        "system": {
            "total_ticks": system_metrics[0] if system_metrics else 0,
            "total_transactions": system_metrics[1] if system_metrics else 0,
            "settled": system_metrics[2] if system_metrics else 0,
            "unsettled": system_metrics[3] if system_metrics else 0,
        }
    }

    for row in agent_results:
        results["agents"][row[0]] = {
            "total_cost": row[1],
            "cost_delay": row[2],
            "cost_overdraft": row[3],
            "cost_collateral": row[4],
            "cost_deadline_penalty": row[5],
            "cost_split_friction": row[6],
            "cost_eod_penalty": row[7],
            "settlement_rate": row[8],
            "total_sent": row[9],
            "total_received": row[10],
            "final_balance": row[11],
            "max_collateral": row[12],
            "max_credit": row[13],
        }

    return results


def format_cost(cost: float) -> str:
    """Format cost in dollars."""
    return f"${cost/100:,.2f}"


def append_results_to_scratchpad(
    run_id: str,
    test_agent: str,
    policy: str,
    results: Dict[str, Any],
) -> None:
    """Append results to the scratchpad document."""
    with open(SCRATCHPAD_PATH, "a") as f:
        f.write(f"\n### {run_id}\n\n")
        f.write(f"**Test Agent**: {test_agent}\n")
        f.write(f"**Policy**: {policy}\n")
        f.write(f"**Simulation ID**: {results['simulation_id']}\n\n")

        f.write("**Agent Results**:\n\n")
        f.write("| Agent | Total Cost | Delay | Overdraft | Collateral | Settlement Rate |\n")
        f.write("|-------|------------|-------|-----------|------------|----------------|\n")

        for agent_id, metrics in results["agents"].items():
            marker = " 🎯" if agent_id == test_agent else ""
            f.write(f"| {agent_id}{marker} | ")
            f.write(f"{format_cost(metrics['total_cost'])} | ")
            f.write(f"{format_cost(metrics['cost_delay'])} | ")
            f.write(f"{format_cost(metrics['cost_overdraft'])} | ")
            f.write(f"{format_cost(metrics['cost_collateral'])} | ")
            f.write(f"{metrics['settlement_rate']:.2%} |\n")

        f.write(f"\n**System Metrics**:\n")
        f.write(f"- Total transactions: {results['system']['total_transactions']}\n")
        f.write(f"- Settled: {results['system']['settled']}\n")
        f.write(f"- Unsettled: {results['system']['unsettled']}\n")
        f.write(f"- System settlement rate: {results['system']['settled']/max(1, results['system']['total_transactions']):.2%}\n")
        f.write("\n---\n")


def main():
    """Run all policy comparison experiments."""
    # Setup
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                  Policy Comparison Experiment Runner                       ║
╚════════════════════════════════════════════════════════════════════════════╝

Base config: {BASE_CONFIG_PATH}
Results dir: {RESULTS_DIR}
Scratchpad: {SCRATCHPAD_PATH}

Testing {len(AGENTS)} agents × {len(POLICIES_TO_TEST)} policies = {len(AGENTS) * len(POLICIES_TO_TEST)} runs
    """)

    base_config = load_base_config()
    all_results = []

    # Run experiments
    for agent_to_test in AGENTS:
        for policy in POLICIES_TO_TEST:
            run_id = f"{agent_to_test}_{policy}"
            output_db = RESULTS_DIR / f"{run_id}.db"

            # Create variant config
            config = create_variant_config(base_config, agent_to_test, policy)

            # Run simulation
            success = run_simulation(config, run_id, output_db)

            if success and output_db.exists():
                # Extract and save results
                results = extract_results(output_db)
                if results:
                    all_results.append({
                        "run_id": run_id,
                        "agent": agent_to_test,
                        "policy": policy,
                        "results": results,
                    })

                    # Append to scratchpad
                    append_results_to_scratchpad(
                        run_id,
                        agent_to_test,
                        policy,
                        results,
                    )

                    print(f"✓ Results saved for {run_id}")
                else:
                    print(f"⚠ No results extracted for {run_id}")
            else:
                print(f"✗ Simulation failed for {run_id}")

    # Save summary JSON
    summary_path = RESULTS_DIR / "all_results.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                          Experiment Complete                               ║
╚════════════════════════════════════════════════════════════════════════════╝

Completed: {len(all_results)} / {len(AGENTS) * len(POLICIES_TO_TEST)} runs

Results saved to:
  - Individual DBs: {RESULTS_DIR}/*.db
  - Summary JSON: {summary_path}
  - Scratchpad: {SCRATCHPAD_PATH}

Next steps:
  1. Review scratchpad document for initial findings
  2. Run analysis notebook for deeper insights
  3. Generate visualizations
  4. Write final report
    """)


if __name__ == "__main__":
    main()
