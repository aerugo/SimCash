#!/usr/bin/env python3
"""
LLM Policy Optimizer V4 - Structured Output with Pydantic AI

Key improvements over V3:
1. Uses OpenAI Structured Output for policy generation
2. Pydantic schemas ensure valid JSON structure
3. Dynamic schemas based on feature toggles
4. Reduced parsing failures and invalid policies

The structured output approach constrains the LLM to generate valid
policy JSON that matches our Pydantic schemas, dramatically reducing
the need for retry and fix loops.

IMPORTANT: This optimizer NEVER modifies the seed policy file.
"""

import json
import shutil
import subprocess
import tempfile
import os
import sys
import time
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from datetime import datetime

import yaml

# OpenAI API
from openai import OpenAI

# Structured output imports
from experiments.castro.schemas.generator import PolicySchemaGenerator
from experiments.castro.schemas.toggles import PolicyFeatureToggles
from experiments.castro.prompts.builder import PolicyPromptBuilder
from experiments.castro.prompts.templates import SYSTEM_PROMPT
from experiments.castro.generator.validation import validate_policy_structure
from experiments.castro.generator.client import PolicyContext


def _run_single_simulation(args: tuple) -> dict | None:
    """Standalone function for parallel simulation execution."""
    scenario_path, simcash_root, seed, capture_verbose = args
    try:
        cmd = [
            str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
            "run",
            "--config", str(scenario_path),
            "--seed", str(seed),
        ]

        if not capture_verbose:
            cmd.append("--quiet")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(simcash_root)
        )

        if result.returncode != 0:
            return {"error": f"Simulation failed (seed {seed}): {result.stderr}", "seed": seed}

        if capture_verbose:
            verbose_output = result.stdout

            quiet_result = subprocess.run(
                [
                    str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
                    "run",
                    "--config", str(scenario_path),
                    "--seed", str(seed),
                    "--quiet"
                ],
                capture_output=True,
                text=True,
                cwd=str(simcash_root)
            )

            if quiet_result.returncode != 0:
                return {"error": f"Simulation failed (seed {seed}): {quiet_result.stderr}", "seed": seed}

            try:
                output = json.loads(quiet_result.stdout)
            except json.JSONDecodeError as e:
                return {"error": f"Failed to parse output: {e}", "seed": seed}
        else:
            verbose_output = None
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return {"error": f"Failed to parse output: {e}", "seed": seed}

        costs = output.get("costs", {})
        agents = {a["id"]: a for a in output.get("agents", [])}

        if isinstance(costs, dict) and "BANK_A" in costs:
            bank_a_cost = costs.get("BANK_A", {}).get("total", 0)
            bank_b_cost = costs.get("BANK_B", {}).get("total", 0)
        else:
            bank_a_cost = costs.get("total_cost", 0) / 2
            bank_b_cost = costs.get("total_cost", 0) / 2

        total_cost = costs.get("total_cost", bank_a_cost + bank_b_cost)

        cost_breakdown = {
            "collateral": costs.get("total_collateral_cost", 0),
            "delay": costs.get("total_delay_cost", 0),
            "overdraft": costs.get("total_overdraft_cost", 0),
            "eod_penalty": costs.get("total_eod_penalty", 0),
        }

        return {
            "seed": seed,
            "bank_a_cost": bank_a_cost,
            "bank_b_cost": bank_b_cost,
            "total_cost": total_cost,
            "settlement_rate": output.get("metrics", {}).get("settlement_rate", 0),
            "bank_a_balance_end": agents.get("BANK_A", {}).get("final_balance", 0),
            "bank_b_balance_end": agents.get("BANK_B", {}).get("final_balance", 0),
            "cost_breakdown": cost_breakdown,
            "raw_output": output,
            "verbose_log": verbose_output
        }
    except Exception as e:
        return {"error": str(e), "seed": seed}


@dataclass
class SimulationResult:
    """Results from a single simulation run."""
    seed: int
    bank_a_cost: float
    bank_b_cost: float
    total_cost: float
    settlement_rate: float
    bank_a_balance_end: float
    bank_b_balance_end: float
    cost_breakdown: dict
    raw_output: dict
    verbose_log: str | None = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across multiple seeds."""
    total_cost_mean: float
    total_cost_std: float
    risk_adjusted_cost: float
    bank_a_cost_mean: float
    bank_b_cost_mean: float
    settlement_rate_mean: float
    failure_rate: float
    worst_seed_cost: float
    best_seed_cost: float
    individual_results: list


class StructuredPolicyOptimizerV4:
    """LLM-based policy optimizer using OpenAI Structured Output.

    This version uses Pydantic schemas to constrain the LLM output,
    ensuring valid JSON structure and reducing parse/validation failures.
    """

    def __init__(
        self,
        scenario_path: str,
        policy_path: str,
        results_dir: str,
        lab_notes_path: str,
        num_seeds: int = 10,
        max_iterations: int = 40,
        model: str = "gpt-4o-2024-08-06",
        simcash_root: str = "/home/user/SimCash",
        convergence_threshold: float = 0.10,
        convergence_window: int = 5,
        max_depth: int = 3,
    ):
        self.scenario_path = Path(scenario_path)
        self.seed_policy_path = Path(policy_path)
        self.results_dir = Path(results_dir)
        self.lab_notes_path = Path(lab_notes_path)
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.model = model
        self.simcash_root = Path(simcash_root)
        self.convergence_threshold = convergence_threshold
        self.convergence_window = convergence_window
        self.max_depth = max_depth

        # Initialize OpenAI client
        self.client = OpenAI()

        # Feature toggles (can be loaded from scenario config)
        self.feature_toggles = PolicyFeatureToggles()

        self.history: list = []
        self.total_tokens = 0
        self.start_time = None

        # Setup directories
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.policies_dir = self.results_dir / "policies"
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        self.configs_dir = self.results_dir / "configs"
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        # Load seed policy (read-only)
        self.seed_policy = self.load_policy(self.seed_policy_path)
        self.current_policy = self.seed_policy.copy()

        # Load base scenario config
        with open(self.scenario_path) as f:
            self.base_scenario_config = yaml.safe_load(f)

    def log_to_notes(self, message: str) -> None:
        """Append a message to the lab notes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.lab_notes_path, 'a') as f:
            f.write(f"\n**[{timestamp}]** {message}\n")

    def load_policy(self, path: Path) -> dict:
        """Load a policy JSON file."""
        with open(path) as f:
            return json.load(f)

    def save_policy(self, policy: dict, path: Path) -> None:
        """Save a policy to JSON file."""
        with open(path, 'w') as f:
            json.dump(policy, f, indent=2)

    def create_iteration_config(self, iteration: int) -> Path:
        """Create iteration-specific policy file and YAML config."""
        policy_path = self.policies_dir / f"iter_{iteration:03d}_policy.json"
        self.save_policy(self.current_policy, policy_path)

        iter_config = self.base_scenario_config.copy()

        # Update all agents to use the new policy path
        iter_config["agents"] = []
        for agent in self.base_scenario_config.get("agents", []):
            agent_copy = agent.copy()
            agent_copy["policy"] = {
                "type": "FromJson",
                "json_path": str(policy_path.absolute())
            }
            iter_config["agents"].append(agent_copy)

        iter_config_path = self.configs_dir / f"iter_{iteration:03d}_config.yaml"
        with open(iter_config_path, 'w') as f:
            yaml.safe_dump(iter_config, f, default_flow_style=False)

        return iter_config_path

    def run_simulations(self, seeds: list[int], iteration: int) -> AggregatedMetrics:
        """Run simulations with multiple seeds in parallel."""
        import statistics

        config_path = self.create_iteration_config(iteration)

        args_list = [
            (str(config_path), str(self.simcash_root), seed, False)
            for seed in seeds
        ]

        results = []
        failed_seeds = []

        with ProcessPoolExecutor(max_workers=min(len(seeds), 8)) as executor:
            future_to_seed = {
                executor.submit(_run_single_simulation, args): args[2]
                for args in args_list
            }

            for future in as_completed(future_to_seed):
                seed = future_to_seed[future]
                try:
                    result_dict = future.result()
                    if result_dict and "error" not in result_dict:
                        results.append(SimulationResult(
                            seed=result_dict["seed"],
                            bank_a_cost=result_dict["bank_a_cost"],
                            bank_b_cost=result_dict["bank_b_cost"],
                            total_cost=result_dict["total_cost"],
                            settlement_rate=result_dict["settlement_rate"],
                            bank_a_balance_end=result_dict["bank_a_balance_end"],
                            bank_b_balance_end=result_dict["bank_b_balance_end"],
                            cost_breakdown=result_dict.get("cost_breakdown", {}),
                            raw_output=result_dict["raw_output"],
                            verbose_log=None
                        ))
                    else:
                        error_msg = result_dict.get("error", "Unknown error") if result_dict else "No result"
                        failed_seeds.append((seed, error_msg))
                except Exception as e:
                    failed_seeds.append((seed, str(e)))

        if not results:
            raise RuntimeError(f"All simulations failed. Failures: {failed_seeds}")

        results.sort(key=lambda r: r.seed)

        costs = [r.total_cost for r in results]
        a_costs = [r.bank_a_cost for r in results]
        b_costs = [r.bank_b_cost for r in results]
        rates = [r.settlement_rate for r in results]

        mean_cost = statistics.mean(costs)
        std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

        failures = sum(1 for r in rates if r < 1.0)
        failure_rate = failures / len(rates)

        return AggregatedMetrics(
            total_cost_mean=mean_cost,
            total_cost_std=std_cost,
            risk_adjusted_cost=mean_cost + std_cost,
            bank_a_cost_mean=statistics.mean(a_costs),
            bank_b_cost_mean=statistics.mean(b_costs),
            settlement_rate_mean=statistics.mean(rates),
            failure_rate=failure_rate,
            worst_seed_cost=max(costs),
            best_seed_cost=min(costs),
            individual_results=results
        )

    def generate_policy_structured(
        self,
        tree_type: str,
        context: PolicyContext,
        current_tree: dict | None = None,
    ) -> dict:
        """Generate a policy tree using structured output."""

        # Build schema generator
        schema_gen = PolicySchemaGenerator(
            tree_type=tree_type,
            feature_toggles=self.feature_toggles,
            max_depth=self.max_depth,
        )

        # Build prompt
        prompt_builder = PolicyPromptBuilder.from_generator(schema_gen)
        if current_tree:
            prompt_builder.set_current_policy(current_tree)
        prompt_builder.set_performance(
            total_cost=context.total_cost,
            settlement_rate=context.settlement_rate,
            per_bank_costs=context.current_costs,
        )
        user_prompt = prompt_builder.build()

        # Get JSON schema
        from pydantic import TypeAdapter
        TreeType = schema_gen.build_tree_model()
        adapter = TypeAdapter(TreeType)
        json_schema = adapter.json_schema()

        # Call API with structured output
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": f"{tree_type}_schema",
                    "strict": True,
                    "schema": json_schema,
                },
            },
            max_tokens=4000,
        )

        content = response.choices[0].message.content
        self.total_tokens += response.usage.total_tokens if response.usage else 0

        if not content:
            raise ValueError("Empty response from API")

        tree = json.loads(content)

        # Validate
        validation = validate_policy_structure(tree, tree_type, self.max_depth)
        if not validation.is_valid:
            self.log_to_notes(f"Structured output validation failed: {validation.errors}")
            raise ValueError(f"Validation failed: {validation.errors}")

        return tree

    def iterate(self) -> tuple[dict, AggregatedMetrics]:
        """Run one iteration of the optimization loop."""
        iteration_num = len(self.history)

        seeds = list(range(1, self.num_seeds + 1))
        self.log_to_notes(f"Starting iteration {iteration_num}")

        print(f"  Running {self.num_seeds} simulations in parallel...")
        metrics = self.run_simulations(seeds, iteration_num)

        failed_count = sum(1 for r in metrics.individual_results if r.settlement_rate < 1.0)
        self.log_to_notes(
            f"Iteration {iteration_num}: Mean=${metrics.total_cost_mean:.0f}, "
            f"Failures={failed_count}/{self.num_seeds}"
        )

        # Build context for LLM
        context = PolicyContext(
            current_costs={
                "BANK_A": metrics.bank_a_cost_mean,
                "BANK_B": metrics.bank_b_cost_mean,
            },
            settlement_rate=metrics.settlement_rate_mean,
        )

        # Generate new trees using structured output
        print(f"  Generating new policy with structured output ({self.model})...")

        new_policy = self.current_policy.copy()

        for tree_type in ["payment_tree", "strategic_collateral_tree"]:
            if tree_type in self.current_policy:
                try:
                    current_tree = self.current_policy.get(tree_type)
                    new_tree = self.generate_policy_structured(
                        tree_type=tree_type,
                        context=context,
                        current_tree=current_tree,
                    )
                    new_policy[tree_type] = new_tree
                    print(f"    Generated {tree_type}")
                except Exception as e:
                    self.log_to_notes(f"Failed to generate {tree_type}: {e}")
                    print(f"    Failed {tree_type}: {e}")

        self.current_policy = new_policy

        self.history.append({
            "iteration": iteration_num,
            "policy": new_policy,
            "metrics": metrics,
        })

        return new_policy, metrics

    def has_converged(self) -> bool:
        """Check if optimization has converged."""
        if len(self.history) < self.convergence_window + 1:
            return False

        recent_costs = [h["metrics"].risk_adjusted_cost for h in self.history[-self.convergence_window:]]
        prev_cost = self.history[-(self.convergence_window+1)]["metrics"].risk_adjusted_cost

        if prev_cost == 0:
            return True

        import statistics

        recent_failures = [h["metrics"].failure_rate for h in self.history[-self.convergence_window:]]
        if any(f > 0 for f in recent_failures):
            return False

        avg_recent = statistics.mean(recent_costs)
        relative_change = abs(avg_recent - prev_cost) / max(prev_cost, 1)

        return relative_change < self.convergence_threshold

    def run(self) -> dict:
        """Run the full optimization loop."""
        self.start_time = datetime.now()

        print(f"=" * 60)
        print(f"Castro Policy Optimization V4 (Structured Output)")
        print(f"=" * 60)
        print(f"  Scenario: {self.scenario_path}")
        print(f"  Model: {self.model}")
        print(f"  Max depth: {self.max_depth}")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"  Seeds per iteration: {self.num_seeds}")
        print()

        self.log_to_notes(
            f"\n---\n## Optimizer V4 Run (Structured Output)\n"
            f"**Model**: {self.model}\n"
            f"**Max Depth**: {self.max_depth}\n"
            f"**Max Iterations**: {self.max_iterations}\n"
            f"**Seeds**: {self.num_seeds}\n"
        )

        for i in range(self.max_iterations):
            print(f"\nIteration {i+1}/{self.max_iterations}")
            print("-" * 40)

            policy, metrics = self.iterate()

            print(f"  Mean cost: ${metrics.total_cost_mean:.0f} ± ${metrics.total_cost_std:.0f}")
            print(f"  Risk-adjusted: ${metrics.risk_adjusted_cost:.0f}")
            print(f"  Settlement rate: {metrics.settlement_rate_mean*100:.1f}%")

            if self.has_converged():
                print(f"\n✓ Converged at iteration {i+1}")
                self.log_to_notes(f"**CONVERGED** at iteration {i+1}")
                break

        duration = datetime.now() - self.start_time

        final_results = {
            "experiment": str(self.scenario_path),
            "model": self.model,
            "version": "v4_structured_output",
            "total_iterations": len(self.history),
            "converged": self.has_converged(),
            "duration": str(duration).split('.')[0],
            "total_tokens": self.total_tokens,
            "final_policy": self.current_policy,
        }

        final_path = self.results_dir / "final_results.json"
        with open(final_path, 'w') as f:
            json.dump(final_results, f, indent=2, default=str)

        print(f"\n{'=' * 60}")
        print(f"Optimization Complete (V4 Structured Output)")
        print(f"{'=' * 60}")
        print(f"  Iterations: {len(self.history)}")
        print(f"  Total tokens: {self.total_tokens:,}")
        print(f"  Results saved to: {self.results_dir}")

        return final_results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Castro Policy Optimizer V4 (Structured Output)")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--policy", required=True, help="Path to policy JSON")
    parser.add_argument("--results-dir", required=True, help="Directory for results")
    parser.add_argument("--lab-notes", required=True, help="Path to lab notes file")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds per iteration")
    parser.add_argument("--max-iter", type=int, default=40, help="Max iterations")
    parser.add_argument("--model", default="gpt-4o-2024-08-06", help="OpenAI model")
    parser.add_argument("--max-depth", type=int, default=3, help="Max tree depth for schemas")

    args = parser.parse_args()

    optimizer = StructuredPolicyOptimizerV4(
        scenario_path=args.scenario,
        policy_path=args.policy,
        results_dir=args.results_dir,
        lab_notes_path=args.lab_notes,
        num_seeds=args.seeds,
        max_iterations=args.max_iter,
        model=args.model,
        max_depth=args.max_depth,
    )

    optimizer.run()


if __name__ == "__main__":
    main()
