#!/usr/bin/env python3
"""
LLM Policy Optimizer V5 - Clean PydanticAI Integration

Uses PydanticAI directly for policy generation. No extra abstraction layers.
PydanticAI handles all provider switching via model strings.

Usage:
    # OpenAI (default)
    python optimizer_v5.py --scenario scenario.yaml --policy policy.json --results-dir ./results --lab-notes notes.md

    # Anthropic
    python optimizer_v5.py --model anthropic:claude-3-5-sonnet-20241022 ...

    # Ollama (local)
    python optimizer_v5.py --model ollama:llama3.1:8b ...
"""

import json
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from datetime import datetime

import yaml

from experiments.castro.generator import PolicyAgent, validate_policy_structure


def _run_simulation(args: tuple[str, str, int]) -> dict[str, Any] | None:
    """Run a single simulation."""
    config_path, simcash_root, seed = args
    try:
        result = subprocess.run(
            [
                str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
                "run", "--config", config_path, "--seed", str(seed), "--quiet"
            ],
            capture_output=True, text=True, cwd=simcash_root
        )
        if result.returncode != 0:
            return {"error": result.stderr, "seed": seed}

        output = json.loads(result.stdout)
        costs = output.get("costs", {})

        return {
            "seed": seed,
            "total_cost": costs.get("total_cost", 0),
            "bank_a_cost": costs.get("BANK_A", {}).get("total", 0),
            "bank_b_cost": costs.get("BANK_B", {}).get("total", 0),
            "settlement_rate": output.get("metrics", {}).get("settlement_rate", 0),
        }
    except Exception as e:
        return {"error": str(e), "seed": seed}


@dataclass
class Metrics:
    """Aggregated metrics from simulation runs."""
    mean_cost: float
    std_cost: float
    settlement_rate: float
    bank_a_cost: float
    bank_b_cost: float


class PolicyOptimizer:
    """LLM-based policy optimizer using PydanticAI."""

    def __init__(
        self,
        scenario_path: str,
        policy_path: str,
        results_dir: str,
        lab_notes_path: str,
        model: str = "openai:gpt-4o",
        num_seeds: int = 10,
        max_iterations: int = 40,
        max_depth: int = 3,
        simcash_root: str = "/home/user/SimCash",
    ):
        self.scenario_path = Path(scenario_path)
        self.policy_path = Path(policy_path)
        self.results_dir = Path(results_dir)
        self.lab_notes_path = Path(lab_notes_path)
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.simcash_root = Path(simcash_root)

        # PydanticAI agent - handles all provider abstraction
        self.agent = PolicyAgent(model=model, max_depth=max_depth)

        # Setup
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.results_dir / "policies").mkdir(exist_ok=True)
        (self.results_dir / "configs").mkdir(exist_ok=True)

        # Load initial state
        with open(self.policy_path) as f:
            self.current_policy = json.load(f)
        with open(self.scenario_path) as f:
            self.base_config = yaml.safe_load(f)

        self.history: list[dict] = []

    def log(self, msg: str) -> None:
        """Log to lab notes."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.lab_notes_path, "a") as f:
            f.write(f"\n**[{ts}]** {msg}\n")

    def run_simulations(self, iteration: int) -> Metrics:
        """Run simulations with current policy."""
        import statistics

        # Save policy for this iteration
        policy_path = self.results_dir / "policies" / f"iter_{iteration:03d}.json"
        with open(policy_path, "w") as f:
            json.dump(self.current_policy, f, indent=2)

        # Create config pointing to this policy
        config = self.base_config.copy()
        config["agents"] = [
            {**a, "policy": {"type": "FromJson", "json_path": str(policy_path.absolute())}}
            for a in self.base_config.get("agents", [])
        ]
        config_path = self.results_dir / "configs" / f"iter_{iteration:03d}.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f)

        # Run in parallel
        args = [(str(config_path), str(self.simcash_root), s) for s in range(1, self.num_seeds + 1)]
        results = []

        with ProcessPoolExecutor(max_workers=min(8, self.num_seeds)) as ex:
            for r in ex.map(_run_simulation, args):
                if r and "error" not in r:
                    results.append(r)

        if not results:
            raise RuntimeError("All simulations failed")

        costs = [r["total_cost"] for r in results]
        return Metrics(
            mean_cost=statistics.mean(costs),
            std_cost=statistics.stdev(costs) if len(costs) > 1 else 0,
            settlement_rate=statistics.mean(r["settlement_rate"] for r in results),
            bank_a_cost=statistics.mean(r["bank_a_cost"] for r in results),
            bank_b_cost=statistics.mean(r["bank_b_cost"] for r in results),
        )

    def iterate(self) -> Metrics:
        """Run one optimization iteration."""
        iteration = len(self.history)
        print(f"\nIteration {iteration + 1}/{self.max_iterations}")

        # Evaluate current policy
        print("  Running simulations...")
        metrics = self.run_simulations(iteration)
        print(f"  Cost: ${metrics.mean_cost:.0f} ± ${metrics.std_cost:.0f}, Settlement: {metrics.settlement_rate*100:.1f}%")

        # Generate improved policy using PydanticAI
        print(f"  Generating new policy with {self.agent.model}...")

        for tree_type in ["payment_tree", "strategic_collateral_tree"]:
            if tree_type in self.current_policy:
                try:
                    new_tree = self.agent.generate(
                        tree_type,
                        f"Improve {tree_type} to reduce costs while maintaining settlement rate",
                        current_policy=self.current_policy.get(tree_type),
                        total_cost=metrics.mean_cost,
                        settlement_rate=metrics.settlement_rate,
                        per_bank_costs={"BANK_A": metrics.bank_a_cost, "BANK_B": metrics.bank_b_cost},
                    )
                    self.current_policy[tree_type] = new_tree
                    print(f"    Updated {tree_type}")
                except Exception as e:
                    self.log(f"Failed to generate {tree_type}: {e}")
                    print(f"    Failed {tree_type}: {e}")

        self.history.append({"iteration": iteration, "metrics": metrics})
        return metrics

    def has_converged(self, window: int = 5, threshold: float = 0.1) -> bool:
        """Check if optimization has converged."""
        if len(self.history) < window + 1:
            return False

        recent = [h["metrics"].mean_cost for h in self.history[-window:]]
        prev = self.history[-(window + 1)]["metrics"].mean_cost

        if prev == 0:
            return True

        import statistics
        return abs(statistics.mean(recent) - prev) / prev < threshold

    def run(self) -> dict:
        """Run the full optimization."""
        start = datetime.now()

        print(f"{'='*60}")
        print(f"Policy Optimizer (PydanticAI)")
        print(f"{'='*60}")
        print(f"  Model: {self.agent.model}")
        print(f"  Scenario: {self.scenario_path}")
        print(f"  Seeds: {self.num_seeds}, Max iterations: {self.max_iterations}")

        self.log(f"Started optimization with {self.agent.model}")

        for _ in range(self.max_iterations):
            self.iterate()
            if self.has_converged():
                print("\n✓ Converged!")
                self.log("Converged")
                break

        duration = datetime.now() - start

        # Save final results
        final = {
            "model": self.agent.model,
            "iterations": len(self.history),
            "duration": str(duration).split(".")[0],
            "final_policy": self.current_policy,
            "final_metrics": {
                "mean_cost": self.history[-1]["metrics"].mean_cost,
                "settlement_rate": self.history[-1]["metrics"].settlement_rate,
            } if self.history else None,
        }

        with open(self.results_dir / "final_results.json", "w") as f:
            json.dump(final, f, indent=2, default=str)

        print(f"\n{'='*60}")
        print(f"Complete: {len(self.history)} iterations, {duration}")
        print(f"Results: {self.results_dir}")

        return final


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Policy Optimizer (PydanticAI)")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--policy", required=True, help="Path to initial policy JSON")
    parser.add_argument("--results-dir", required=True, help="Output directory")
    parser.add_argument("--lab-notes", required=True, help="Lab notes file")
    parser.add_argument("--model", default="openai:gpt-4o", help="PydanticAI model (e.g., openai:gpt-4o, anthropic:claude-3-5-sonnet-20241022)")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds per iteration")
    parser.add_argument("--max-iter", type=int, default=40, help="Max iterations")
    parser.add_argument("--max-depth", type=int, default=3, help="Max tree depth")

    args = parser.parse_args()

    optimizer = PolicyOptimizer(
        scenario_path=args.scenario,
        policy_path=args.policy,
        results_dir=args.results_dir,
        lab_notes_path=args.lab_notes,
        model=args.model,
        num_seeds=args.seeds,
        max_iterations=args.max_iter,
        max_depth=args.max_depth,
    )

    optimizer.run()


if __name__ == "__main__":
    main()
