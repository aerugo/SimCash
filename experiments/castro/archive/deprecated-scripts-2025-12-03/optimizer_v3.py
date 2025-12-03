#!/usr/bin/env python3
"""
LLM Policy Optimizer V3 - Enhanced with Per-Tick Event Logs

Key improvements over V2:
1. All V2 features (risk-adjusted metrics, failure rate tracking, etc.)
2. Captures verbose simulation logs for best/worst seeds
3. Parses logs into condensed per-tick event summaries
4. Includes causal event logs in LLM prompt for deeper insight

The goal: Help the LLM understand WHY certain seeds fail, not just THAT they fail.

IMPORTANT: This optimizer NEVER modifies the seed policy file.
- Seed policy is read-only (loaded once at startup)
- Each iteration creates temporary policy files in the results directory
- All policy versions are stored in the database
- If LLM produces invalid policies, we retry with feedback
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

        # Use --quiet for JSON output (metrics), but also capture verbose if requested
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
            # Extract JSON from verbose output (last line or search for JSON block)
            verbose_output = result.stdout

            # Run again with --quiet to get clean JSON
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

        # Extract costs from output
        costs = output.get("costs", {})
        agents = {a["id"]: a for a in output.get("agents", [])}

        # Handle different cost output formats
        if isinstance(costs, dict) and "BANK_A" in costs:
            bank_a_cost = costs.get("BANK_A", {}).get("total", 0)
            bank_b_cost = costs.get("BANK_B", {}).get("total", 0)
        else:
            bank_a_cost = costs.get("total_cost", 0) / 2
            bank_b_cost = costs.get("total_cost", 0) / 2

        total_cost = costs.get("total_cost", bank_a_cost + bank_b_cost)

        # Extract detailed cost breakdown
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


def _run_verbose_simulation(args: tuple) -> dict | None:
    """Run a single simulation with verbose output capture."""
    scenario_path, simcash_root, seed = args
    return _run_single_simulation((scenario_path, simcash_root, seed, True))


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
    condensed_log: str | None = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across multiple seeds."""
    total_cost_mean: float
    total_cost_std: float
    risk_adjusted_cost: float  # mean + σ
    bank_a_cost_mean: float
    bank_b_cost_mean: float
    settlement_rate_mean: float
    failure_rate: float  # % of seeds with <100% settlement
    worst_seed_cost: float
    best_seed_cost: float
    individual_results: list


@dataclass
class IterationResult:
    """Results from one optimization iteration."""
    iteration: int
    policy_a: dict
    policy_b: dict
    metrics: AggregatedMetrics
    llm_analysis: str
    tokens_used: int = 0


class VerboseLogParser:
    """Handles verbose simulation logs - now passes through full logs."""

    def parse(self, verbose_log: str, seed: int) -> str:
        """Return the full verbose log with a header. No condensation needed with 200k token limit."""
        if not verbose_log:
            return f"[No verbose log for seed {seed}]"

        # Just add a header and return the full log
        return f"=== Seed {seed} Full Event Log ===\n{verbose_log}"


class CastroPolicyOptimizerV3:
    """LLM-based policy optimizer with per-tick event log feedback.

    IMPORTANT: This optimizer NEVER modifies the seed policy files.
    Instead, it:
    1. Loads seed policies once at initialization (read-only)
    2. Creates iteration-specific policy files in results_dir
    3. Creates iteration-specific YAML configs pointing to those policies
    4. Stores all policy versions for reproducibility
    """

    # Maximum retries when LLM produces invalid policy
    MAX_VALIDATION_RETRIES = 3

    def __init__(
        self,
        scenario_path: str,
        policy_a_path: str,
        policy_b_path: str,
        results_dir: str,
        lab_notes_path: str,
        num_seeds: int = 10,
        max_iterations: int = 40,
        model: str = "gpt-5.1",
        reasoning_effort: str = "high",
        simcash_root: str = "/home/user/SimCash",
        convergence_threshold: float = 0.10,
        convergence_window: int = 5,
        verbose_seeds: int = 2,  # Number of best/worst seeds to capture verbose logs for
    ):
        self.scenario_path = Path(scenario_path)
        self.seed_policy_a_path = Path(policy_a_path)  # Read-only seed path
        self.seed_policy_b_path = Path(policy_b_path)  # Read-only seed path
        self.results_dir = Path(results_dir)
        self.lab_notes_path = Path(lab_notes_path)
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.simcash_root = Path(simcash_root)
        self.convergence_threshold = convergence_threshold
        self.convergence_window = convergence_window
        self.verbose_seeds = verbose_seeds

        # Initialize OpenAI client
        self.client = OpenAI()

        # Log parser
        self.log_parser = VerboseLogParser()

        self.history: list[IterationResult] = []
        self.total_tokens = 0
        self.start_time = None

        # Ensure results directory exists
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Create policies subdirectory for iteration policies
        self.policies_dir = self.results_dir / "policies"
        self.policies_dir.mkdir(parents=True, exist_ok=True)

        # Create configs subdirectory for iteration configs
        self.configs_dir = self.results_dir / "configs"
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        # Load seed policies ONCE (read-only, never modified)
        self.seed_policy_a = self.load_policy(self.seed_policy_a_path)
        self.seed_policy_b = self.load_policy(self.seed_policy_b_path)

        # Current policies (start with seed, updated each iteration)
        self.current_policy_a = self.seed_policy_a.copy()
        self.current_policy_b = self.seed_policy_b.copy()

        # Load base scenario config
        with open(self.scenario_path) as f:
            self.base_scenario_config = yaml.safe_load(f)

        # Track current iteration config path
        self.current_config_path: Path | None = None

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
        """Create iteration-specific policy files and YAML config.

        This method:
        1. Writes current policies to results/policies/iter_XXX_policy_{a,b}.json
        2. Creates a modified YAML config pointing to those policy files
        3. Returns the path to the iteration-specific config

        NEVER modifies the original seed policy files.
        """
        # Write iteration-specific policy files
        policy_a_path = self.policies_dir / f"iter_{iteration:03d}_policy_a.json"
        policy_b_path = self.policies_dir / f"iter_{iteration:03d}_policy_b.json"

        self.save_policy(self.current_policy_a, policy_a_path)
        self.save_policy(self.current_policy_b, policy_b_path)

        # Create modified config with new policy paths
        iter_config = self.base_scenario_config.copy()

        # Deep copy agents to avoid modifying base config
        iter_config["agents"] = []
        for agent in self.base_scenario_config.get("agents", []):
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
        iter_config_path = self.configs_dir / f"iter_{iteration:03d}_config.yaml"
        with open(iter_config_path, 'w') as f:
            yaml.safe_dump(iter_config, f, default_flow_style=False)

        self.current_config_path = iter_config_path
        return iter_config_path

    def validate_policy_with_details(self, policy: dict, agent_name: str) -> tuple[bool, str, list[str]]:
        """Validate a policy and return detailed error messages.

        Returns:
            (is_valid, raw_output, list_of_errors)
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(policy, f)
            f.flush()
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    str(self.simcash_root / "api" / ".venv" / "bin" / "payment-sim"),
                    "validate-policy",
                    temp_path,
                    "--format", "json"
                ],
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root)
            )

            errors = []

            if result.returncode != 0:
                # Try to extract specific error messages
                stderr = result.stderr.strip()
                if stderr:
                    errors.append(f"CLI error: {stderr}")
                return False, result.stderr, errors

            try:
                output = json.loads(result.stdout)
                is_valid = output.get("valid", False)

                if not is_valid:
                    # Extract detailed error messages from validation output
                    if "errors" in output:
                        errors = output["errors"]
                    elif "error" in output:
                        errors = [output["error"]]
                    elif "message" in output:
                        errors = [output["message"]]
                    else:
                        errors = [f"Validation failed for {agent_name}: {result.stdout[:500]}"]

                return is_valid, result.stdout, errors

            except json.JSONDecodeError:
                # If output isn't JSON, treat non-zero return as failure
                return result.returncode == 0, result.stdout, [f"Non-JSON output: {result.stdout[:200]}"]

        finally:
            os.unlink(temp_path)

    def request_policy_fix_from_llm(
        self,
        policy: dict,
        agent_name: str,
        errors: list[str],
        original_prompt: str
    ) -> dict | None:
        """Ask LLM to fix an invalid policy.

        Returns:
            Fixed policy dict, or None if fix failed
        """
        error_list = "\n".join(f"  - {e}" for e in errors)

        fix_prompt = f"""# Policy Validation Error - Fix Required

The {agent_name} policy you generated failed validation with the following errors:

{error_list}

## Invalid Policy
```json
{json.dumps(policy, indent=2)}
```

## Task
Please fix the policy to address these validation errors. Output ONLY the corrected JSON policy, nothing else.

**Common fixes:**
- Ensure all node_id values are unique strings
- Ensure "type" is one of: "condition", "action"
- Ensure "action" is one of: "Release", "Hold", "PostCollateral", "HoldCollateral"
- Ensure all field references use valid field names
- Ensure numeric values are numbers, not strings

## Corrected {agent_name} Policy
```json
"""

        try:
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are fixing a JSON policy. Output ONLY valid JSON."},
                    {"role": "user", "content": fix_prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.3,  # Lower temperature for more deterministic fixes
            }

            response = self.client.chat.completions.create(**request_params)
            response_text = response.choices[0].message.content

            # Parse JSON from response
            # Try to find JSON block
            if "```json" in response_text:
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    return json.loads(json_match.group(1))
            elif "```" in response_text:
                json_match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    return json.loads(json_match.group(1))
            else:
                # Try to parse entire response as JSON
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    return json.loads(response_text[start:end])

            return None

        except Exception as e:
            self.log_to_notes(f"Failed to get policy fix from LLM: {e}")
            return None

    def validate_and_fix_policy(
        self,
        policy: dict,
        agent_name: str,
        fallback_policy: dict
    ) -> tuple[dict, bool]:
        """Validate a policy, attempting to fix it if invalid.

        Returns:
            (final_policy, was_originally_valid)
        """
        is_valid, output, errors = self.validate_policy_with_details(policy, agent_name)

        if is_valid:
            return policy, True

        self.log_to_notes(f"{agent_name} policy invalid. Attempting fix. Errors: {errors[:3]}")
        print(f"  {agent_name} policy invalid, attempting LLM fix...")

        # Try to fix the policy
        for attempt in range(self.MAX_VALIDATION_RETRIES):
            fixed_policy = self.request_policy_fix_from_llm(
                policy, agent_name, errors, ""
            )

            if fixed_policy is None:
                self.log_to_notes(f"  Fix attempt {attempt + 1} failed: LLM returned no valid JSON")
                continue

            # Validate the fixed policy
            is_valid, output, new_errors = self.validate_policy_with_details(fixed_policy, agent_name)

            if is_valid:
                self.log_to_notes(f"  Fix succeeded on attempt {attempt + 1}")
                print(f"  {agent_name} policy fixed on attempt {attempt + 1}")
                return fixed_policy, False

            # Update errors for next attempt
            errors = new_errors
            self.log_to_notes(f"  Fix attempt {attempt + 1} still invalid: {new_errors[:2]}")

        # All fix attempts failed, use fallback
        self.log_to_notes(f"{agent_name} policy could not be fixed after {self.MAX_VALIDATION_RETRIES} attempts. Using fallback.")
        print(f"  {agent_name} policy unfixable, using previous valid policy")
        return fallback_policy, False

    def run_simulations(self, seeds: list[int], iteration: int) -> AggregatedMetrics:
        """Run simulations with multiple seeds in parallel and aggregate results.

        Uses the iteration-specific config created by create_iteration_config().
        """
        import statistics

        # Create iteration-specific config with current policies
        config_path = self.create_iteration_config(iteration)

        # First pass: Run all simulations without verbose output (faster)
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
                        print(f"    Warning: Seed {seed} failed: {error_msg}")
                except Exception as e:
                    failed_seeds.append((seed, str(e)))
                    print(f"    Warning: Seed {seed} exception: {e}")

        if not results:
            raise RuntimeError(f"All simulations failed. Failures: {failed_seeds}")

        # Sort by cost to identify best/worst
        results.sort(key=lambda r: r.total_cost)

        # Identify seeds needing verbose logs (worst N and best N)
        worst_seeds = [r.seed for r in results[-self.verbose_seeds:]]
        best_seeds = [r.seed for r in results[:self.verbose_seeds]]
        verbose_target_seeds = set(worst_seeds + best_seeds)

        print(f"  Capturing verbose logs for seeds: {sorted(verbose_target_seeds)}")

        # Second pass: Run verbose simulations for selected seeds (same config)
        verbose_args = [
            (str(config_path), str(self.simcash_root), seed)
            for seed in verbose_target_seeds
        ]

        with ProcessPoolExecutor(max_workers=min(len(verbose_args), 4)) as executor:
            future_to_seed = {
                executor.submit(_run_verbose_simulation, args): args[2]
                for args in verbose_args
            }

            for future in as_completed(future_to_seed):
                seed = future_to_seed[future]
                try:
                    result_dict = future.result()
                    if result_dict and "error" not in result_dict and result_dict.get("verbose_log"):
                        # Update the result with verbose log
                        for r in results:
                            if r.seed == seed:
                                r.verbose_log = result_dict["verbose_log"]
                                r.condensed_log = self.log_parser.parse(
                                    result_dict["verbose_log"],
                                    seed
                                )
                                break
                except Exception as e:
                    print(f"    Warning: Verbose capture for seed {seed} failed: {e}")

        # Sort by seed for consistent ordering
        results.sort(key=lambda r: r.seed)

        costs = [r.total_cost for r in results]
        a_costs = [r.bank_a_cost for r in results]
        b_costs = [r.bank_b_cost for r in results]
        rates = [r.settlement_rate for r in results]

        mean_cost = statistics.mean(costs)
        std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

        # Calculate failure rate (seeds with <100% settlement)
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

    def build_prompt(
        self,
        policy_a: dict,
        policy_b: dict,
        metrics: AggregatedMetrics
    ) -> str:
        """Build enhanced prompt with per-tick event logs for best/worst seeds."""

        # History table with risk-adjusted costs
        history_rows = []
        for h in self.history[-10:]:
            liq_a = h.policy_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
            liq_b = h.policy_b.get("parameters", {}).get("initial_liquidity_fraction", "?")
            history_rows.append(
                f"| {h.iteration} | A={liq_a}, B={liq_b} | ${h.metrics.total_cost_mean:.0f} ± ${h.metrics.total_cost_std:.0f} | "
                f"${h.metrics.risk_adjusted_cost:.0f} | {h.metrics.failure_rate*100:.0f}% | "
                f"{h.metrics.settlement_rate_mean*100:.0f}% |"
            )
        history_table = "\n".join(history_rows) if history_rows else "| (No history yet) | | | | | |"

        # Per-seed results table with settlement status
        seed_rows = []
        sorted_results = sorted(metrics.individual_results, key=lambda r: r.total_cost, reverse=True)
        for r in sorted_results:
            status = "FAILED" if r.settlement_rate < 1.0 else "OK"
            unsettled = int((1 - r.settlement_rate) * 10)
            has_log = "📋" if r.condensed_log else ""
            seed_rows.append(
                f"| {r.seed} | ${r.total_cost:.0f} | {r.settlement_rate*100:.0f}% | {status} | ~{unsettled} unsettled | {has_log} |"
            )
        seed_table = "\n".join(seed_rows)

        # Identify worst performers for explicit callout
        failed_seeds = [r for r in metrics.individual_results if r.settlement_rate < 1.0]
        if failed_seeds:
            worst = max(failed_seeds, key=lambda r: r.total_cost)
            worst_callout = f"""
### ⚠️ CRITICAL: Settlement Failures Detected

**{len(failed_seeds)} out of {len(metrics.individual_results)} seeds had settlement failures.**

Worst performer: Seed {worst.seed}
- Cost: ${worst.total_cost:.0f}
- Settlement rate: {worst.settlement_rate*100:.0f}%
- Estimated unsettled transactions: ~{int((1-worst.settlement_rate)*10)}

**Each unsettled transaction incurs a $500 EOD penalty.** This dominates other costs.
Your PRIMARY goal should be achieving 100% settlement across all seeds.
"""
        else:
            worst_callout = """
### ✓ All Seeds Achieved 100% Settlement

Focus on reducing collateral and delay costs while maintaining perfect settlement.
"""

        # Cost breakdown from sample results (aggregate)
        if metrics.individual_results:
            sample = metrics.individual_results[0].raw_output
            costs = sample.get("costs", {})
            cost_breakdown = f"""
**Aggregate Cost Components (from seed 1):**
- Collateral cost: ${costs.get('total_collateral_cost', 0):.0f}
- Delay cost: ${costs.get('total_delay_cost', 0):.0f}
- Overdraft cost: ${costs.get('total_overdraft_cost', 0):.0f}
- EOD penalties: ${costs.get('total_eod_penalty', 0):.0f}
"""
        else:
            cost_breakdown = ""

        # ===== NEW: Per-tick event logs for best/worst seeds =====
        event_logs_section = self._build_event_logs_section(metrics)

        return f"""# SimCash Stochastic Scenario Optimization - Iteration {len(self.history)}

## Context
You are optimizing payment policies for a **stochastic** payment system. Unlike deterministic scenarios, payment arrivals are random (Poisson process) with variable amounts (LogNormal distribution).

**Key challenge**: Policies must be ROBUST across different random scenarios. A policy that works for some seeds but fails for others is not acceptable.

## Castro Model (Stochastic Extension)
- Two banks exchange payments over 12 discrete periods
- Payments arrive randomly: ~6-8 per day with $100-120k median amounts
- Each bank chooses:
  1. **Initial liquidity**: Fraction of collateral to allocate (via `strategic_collateral_tree`)
  2. **Payment timing**: When to release each payment (via `payment_tree`)
- Costs:
  - **Collateral cost (r_c)**: ~83 bps/tick for posted liquidity
  - **Delay cost (r_d)**: ~0.017 cents/tick for holding payments
  - **EOD penalty**: **$500 per unsettled transaction** (DOMINANT COST)

## ⚠️ Critical Insight: EOD Penalties Dominate

In stochastic scenarios, **the $500 EOD penalty per unsettled transaction is the largest cost driver.**

Example: If 3 transactions fail to settle → $1,500 penalty
This often exceeds all other costs combined.

**Your optimization priority should be:**
1. **FIRST**: Achieve 100% settlement rate across ALL seeds
2. **THEN**: Minimize collateral and delay costs

{worst_callout}

## Current Policies

### Bank A Policy
```json
{json.dumps(policy_a, indent=2)}
```

### Bank B Policy
```json
{json.dumps(policy_b, indent=2)}
```

## Simulation Results ({self.num_seeds} random seeds)

### Summary Metrics
| Metric | Value | Notes |
|--------|-------|-------|
| **Mean Cost** | ${metrics.total_cost_mean:.0f} | Average across all seeds |
| **Std Deviation** | ±${metrics.total_cost_std:.0f} | Variance measure |
| **Risk-Adjusted Cost** | ${metrics.risk_adjusted_cost:.0f} | mean + σ (OPTIMIZE THIS) |
| **Failure Rate** | {metrics.failure_rate*100:.0f}% | Seeds with <100% settlement |
| **Settlement Rate** | {metrics.settlement_rate_mean*100:.1f}% | Must be 100% for all seeds |
| **Worst Seed Cost** | ${metrics.worst_seed_cost:.0f} | Highest cost scenario |
| **Best Seed Cost** | ${metrics.best_seed_cost:.0f} | Lowest cost scenario |

{cost_breakdown}

### Per-Seed Results (sorted by cost, worst first)
| Seed | Total Cost | Settlement | Status | Notes | Log |
|------|------------|------------|--------|-------|-----|
{seed_table}

{event_logs_section}

## Iteration History
| Iter | Liquidity | Mean ± Std | Risk-Adj | Fail% | Settlement |
|------|-----------|------------|----------|-------|------------|
{history_table}

## Policy Structure

Policies use SimCash JSON DSL:

1. `strategic_collateral_tree`: Called at tick 0, decides initial liquidity
   - Key: `initial_liquidity_fraction` (0.0 to 1.0)

2. `payment_tree`: Called for each payment, decides Release vs Hold
   - Key parameters: `urgency_threshold`, `liquidity_buffer_factor`
   - Available fields: `ticks_to_deadline`, `effective_liquidity`, `remaining_amount`

## Your Task

Analyze the results and propose improved policies. Think step by step:

1. **Event Log Analysis**: Review the per-tick event logs below. What patterns cause failures?
   - Are payments arriving in bursts that overwhelm liquidity?
   - Are there timing mismatches between inflows and outflows?
   - Is liquidity being exhausted at critical moments?

2. **Settlement Analysis**: Are there settlement failures? If so, this is the PRIMARY problem to solve.

3. **Variance Analysis**: Is the cost variance high? What causes the worst seeds to perform poorly?

4. **Policy Changes**: Propose specific changes to parameters or tree structure.

## Output Format

### Analysis
[Your 2-3 paragraph analysis focusing on:
- What patterns in the event logs explain the failures?
- Why are some seeds failing? (if any)
- What specific timing or liquidity issues need to be addressed?]

### Bank A Policy
```json
[Complete valid JSON policy]
```

### Bank B Policy
```json
[Complete valid JSON policy]
```

### Expected Improvement
[What specific metric improvements do you expect?]

**CRITICAL**:
- Output complete, valid JSON policies
- Do NOT use ellipsis (...) or placeholders
- Focus on achieving 100% settlement FIRST, then optimize costs
"""

    def _build_event_logs_section(self, metrics: AggregatedMetrics) -> str:
        """Build the per-tick event logs section for best/worst seeds."""

        # Sort by cost
        sorted_results = sorted(metrics.individual_results, key=lambda r: r.total_cost)

        # Get best and worst seeds with logs
        worst_with_logs = [r for r in sorted_results if r.condensed_log][-self.verbose_seeds:]
        best_with_logs = [r for r in sorted_results if r.condensed_log][:self.verbose_seeds]

        sections = []

        if worst_with_logs:
            sections.append("## 📉 Worst Seed Event Logs (study these for failure patterns)")
            for r in worst_with_logs:
                status = "FAILED" if r.settlement_rate < 1.0 else "OK"
                sections.append(f"\n### Seed {r.seed} - Cost: ${r.total_cost:.0f} ({r.settlement_rate*100:.0f}% settled) - {status}")
                sections.append("```")
                sections.append(r.condensed_log or "[No log available]")
                sections.append("```")

        if best_with_logs:
            sections.append("\n## 📈 Best Seed Event Logs (study these for success patterns)")
            for r in best_with_logs:
                status = "OK" if r.settlement_rate >= 1.0 else "PARTIAL"
                sections.append(f"\n### Seed {r.seed} - Cost: ${r.total_cost:.0f} ({r.settlement_rate*100:.0f}% settled) - {status}")
                sections.append("```")
                sections.append(r.condensed_log or "[No log available]")
                sections.append("```")

        if not sections:
            return "## Event Logs\n[No verbose logs captured for this iteration]"

        return "\n".join(sections)

    def parse_policies(self, response: str) -> tuple[dict, dict]:
        """Parse two policy JSONs from LLM response."""
        import re

        debug_path = self.results_dir / f"llm_response_{len(self.history):03d}.txt"
        with open(debug_path, 'w') as f:
            f.write(response)

        # Strategy 1: Find ```json blocks
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', response)

        # Strategy 2: Find any ``` code blocks
        if len(json_blocks) < 2:
            json_blocks = re.findall(r'```\s*([\s\S]*?)\s*```', response)
            json_blocks = [b for b in json_blocks if b.strip().startswith('{')]

        # Strategy 3: Find JSON objects with policy_id
        if len(json_blocks) < 2:
            json_blocks = []
            in_json = False
            depth = 0
            current = ""
            for char in response:
                if char == '{':
                    in_json = True
                    depth += 1
                if in_json:
                    current += char
                if char == '}':
                    depth -= 1
                    if depth == 0 and in_json:
                        if '"policy_id"' in current or '"version"' in current:
                            json_blocks.append(current)
                        current = ""
                        in_json = False

        if len(json_blocks) < 2:
            self.log_to_notes(f"Parsing failed. Found {len(json_blocks)} JSON blocks. Response saved to {debug_path}")
            raise ValueError(f"Expected 2 JSON blocks, found {len(json_blocks)}")

        try:
            policy_a = json.loads(json_blocks[0])
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Bank A policy: {e}")

        try:
            policy_b = json.loads(json_blocks[1])
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Bank B policy: {e}")

        return policy_a, policy_b

    def validate_policy(self, policy: dict) -> tuple[bool, str]:
        """Validate a policy using SimCash CLI."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(policy, f)
            f.flush()
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    str(self.simcash_root / "api" / ".venv" / "bin" / "payment-sim"),
                    "validate-policy",
                    temp_path,
                    "--format", "json"
                ],
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root)
            )

            if result.returncode != 0:
                return False, result.stderr

            try:
                output = json.loads(result.stdout)
                return output.get("valid", False), result.stdout
            except json.JSONDecodeError:
                return result.returncode == 0, result.stdout

        finally:
            os.unlink(temp_path)

    def iterate(self) -> tuple[dict, dict, AggregatedMetrics]:
        """Run one iteration of the optimization loop.

        Uses current_policy_a/b (never reads from seed files after init).
        Creates iteration-specific configs for simulations.
        """
        iteration_num = len(self.history)

        seeds = list(range(1, self.num_seeds + 1))
        seeds_str = ", ".join(str(s) for s in seeds)

        self.log_to_notes(f"Starting iteration {iteration_num} with seeds: [{seeds_str}]")

        # Use current policies (not loaded from files)
        policy_a = self.current_policy_a
        policy_b = self.current_policy_b

        print(f"  Running {self.num_seeds} simulations in parallel...")
        metrics = self.run_simulations(seeds, iteration_num)

        # Enhanced logging with failure info
        failed_count = sum(1 for r in metrics.individual_results if r.settlement_rate < 1.0)
        verbose_count = sum(1 for r in metrics.individual_results if r.condensed_log)

        self.log_to_notes(
            f"Iteration {iteration_num}: Mean=${metrics.total_cost_mean:.0f} ± ${metrics.total_cost_std:.0f}, "
            f"RiskAdj=${metrics.risk_adjusted_cost:.0f}, "
            f"Failures={failed_count}/{self.num_seeds}, "
            f"Settlement={metrics.settlement_rate_mean*100:.1f}%, "
            f"VerboseLogs={verbose_count}"
        )

        prompt = self.build_prompt(policy_a, policy_b, metrics)

        print(f"  Calling {self.model} (reasoning={self.reasoning_effort})...")
        llm_text = None
        tokens_used = 0
        max_retries = 8
        for attempt in range(max_retries):
            try:
                request_params = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert financial systems researcher optimizing payment system policies for STOCHASTIC scenarios. Focus on ROBUSTNESS - policies must work across all random seeds, not just the average case. Pay special attention to the per-tick event logs to understand causality."
                        },
                        {"role": "user", "content": prompt}
                    ],
                }

                if self.model.startswith("gpt-5"):
                    request_params["max_completion_tokens"] = 128000
                    request_params["reasoning_effort"] = self.reasoning_effort
                elif self.model.startswith("o1") or self.model.startswith("o3"):
                    request_params["max_completion_tokens"] = 8000
                else:
                    request_params["max_tokens"] = 8000
                    request_params["temperature"] = 0.7

                response = self.client.chat.completions.create(**request_params)
                llm_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                self.total_tokens += tokens_used
                break
            except Exception as e:
                wait_time = 2 ** (attempt + 1)
                self.log_to_notes(f"LLM call attempt {attempt+1} failed: {e}. Retrying in {wait_time}s...")
                print(f"  API error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    self.log_to_notes(f"LLM call failed after {max_retries} attempts: {e}")
                    raise

        if llm_text is None:
            raise RuntimeError("LLM returned no response")

        try:
            new_a, new_b = self.parse_policies(llm_text)
            self.log_to_notes(f"Successfully parsed new policies from LLM response")
        except Exception as e:
            self.log_to_notes(f"Failed to parse policies: {e}. Keeping current policies.")
            print(f"  Failed to parse policies: {e}")
            new_a, new_b = policy_a, policy_b

        # Validate policies with retry logic (NEVER writes to seed files)
        new_a, was_valid_a = self.validate_and_fix_policy(new_a, "Bank A", policy_a)
        new_b, was_valid_b = self.validate_and_fix_policy(new_b, "Bank B", policy_b)

        # Update current policies (in-memory, not written to seed files)
        self.current_policy_a = new_a
        self.current_policy_b = new_b

        # Note: Policies are saved to iteration-specific files in run_simulations()
        # via create_iteration_config(). The seed policy files are NEVER modified.

        self.history.append(IterationResult(
            iteration=iteration_num,
            policy_a=new_a,
            policy_b=new_b,
            metrics=metrics,
            llm_analysis=llm_text,
            tokens_used=tokens_used
        ))

        old_liq_a = policy_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
        new_liq_a = new_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
        old_liq_b = policy_b.get("parameters", {}).get("initial_liquidity_fraction", "?")
        new_liq_b = new_b.get("parameters", {}).get("initial_liquidity_fraction", "?")

        self.log_to_notes(
            f"Parameter changes: Bank A liquidity {old_liq_a} -> {new_liq_a}, "
            f"Bank B liquidity {old_liq_b} -> {new_liq_b}"
        )

        return new_a, new_b, metrics

    def has_converged(self) -> bool:
        """Check if optimization has converged using stricter criteria for stochastic."""
        if len(self.history) < self.convergence_window + 1:
            return False

        # Use risk-adjusted cost for convergence check
        recent_costs = [h.metrics.risk_adjusted_cost for h in self.history[-self.convergence_window:]]
        prev_cost = self.history[-(self.convergence_window+1)].metrics.risk_adjusted_cost

        if prev_cost == 0:
            return True

        import statistics

        # Check if all recent failures rates are 0 (perfect settlement)
        recent_failures = [h.metrics.failure_rate for h in self.history[-self.convergence_window:]]

        # If still having failures, don't converge
        if any(f > 0 for f in recent_failures):
            return False

        # Check variance of recent costs
        if len(recent_costs) > 1:
            variance = statistics.stdev(recent_costs) / max(statistics.mean(recent_costs), 1)
            if variance > 0.15:
                return False

        # Check if improvement is minimal
        avg_recent = statistics.mean(recent_costs)
        relative_change = abs(avg_recent - prev_cost) / max(prev_cost, 1)

        return relative_change < self.convergence_threshold

    def run(self) -> dict:
        """Run the full optimization loop."""
        self.start_time = datetime.now()

        print(f"=" * 60)
        print(f"Castro Policy Optimization V3 (Per-Tick Event Logs)")
        print(f"=" * 60)
        print(f"  Scenario: {self.scenario_path}")
        print(f"  Model: {self.model} (reasoning={self.reasoning_effort})")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"  Seeds per iteration: {self.num_seeds}")
        print(f"  Verbose logs for: {self.verbose_seeds} best + {self.verbose_seeds} worst seeds")
        print(f"  Convergence: {self.convergence_threshold*100:.0f}% over {self.convergence_window} iterations")
        print()

        self.log_to_notes(
            f"\n---\n## Experiment 2c Run: {self.scenario_path.name}\n"
            f"**Model**: {self.model}\n"
            f"**Reasoning**: {self.reasoning_effort}\n"
            f"**Max Iterations**: {self.max_iterations}\n"
            f"**Seeds**: {self.num_seeds}\n"
            f"**Verbose Logs**: {self.verbose_seeds} best + {self.verbose_seeds} worst\n"
            f"**Convergence**: {self.convergence_threshold*100:.0f}% over {self.convergence_window} iterations\n"
            f"**Enhanced**: Per-tick event logs for causal understanding\n"
        )

        for i in range(self.max_iterations):
            print(f"\nIteration {i+1}/{self.max_iterations}")
            print("-" * 40)

            policy_a, policy_b, metrics = self.iterate()

            # Enhanced output with risk metrics
            failed_count = sum(1 for r in metrics.individual_results if r.settlement_rate < 1.0)
            print(f"  Mean cost: ${metrics.total_cost_mean:.0f} ± ${metrics.total_cost_std:.0f}")
            print(f"  Risk-adjusted: ${metrics.risk_adjusted_cost:.0f}")
            print(f"  Failures: {failed_count}/{self.num_seeds} seeds")
            print(f"  Settlement rate: {metrics.settlement_rate_mean*100:.1f}%")
            print(f"  Worst/Best seed: ${metrics.worst_seed_cost:.0f} / ${metrics.best_seed_cost:.0f}")
            print(f"  Tokens used: {self.history[-1].tokens_used:,}")

            # Save iteration results
            iteration_path = self.results_dir / f"iteration_{i:03d}.json"
            per_seed_results = [
                {
                    "seed": r.seed,
                    "total_cost": r.total_cost,
                    "bank_a_cost": r.bank_a_cost,
                    "bank_b_cost": r.bank_b_cost,
                    "settlement_rate": r.settlement_rate,
                    "cost_breakdown": r.cost_breakdown,
                    "has_verbose_log": r.condensed_log is not None
                }
                for r in metrics.individual_results
            ]
            with open(iteration_path, 'w') as f:
                json.dump({
                    "iteration": i,
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "total_cost_mean": metrics.total_cost_mean,
                        "total_cost_std": metrics.total_cost_std,
                        "risk_adjusted_cost": metrics.risk_adjusted_cost,
                        "bank_a_cost_mean": metrics.bank_a_cost_mean,
                        "bank_b_cost_mean": metrics.bank_b_cost_mean,
                        "settlement_rate_mean": metrics.settlement_rate_mean,
                        "failure_rate": metrics.failure_rate,
                        "worst_seed_cost": metrics.worst_seed_cost,
                        "best_seed_cost": metrics.best_seed_cost
                    },
                    "per_seed_results": per_seed_results,
                    "policy_a": policy_a,
                    "policy_b": policy_b,
                    "tokens_used": self.history[-1].tokens_used
                }, f, indent=2)

            if self.has_converged():
                print(f"\n✓ Converged at iteration {i+1}")
                self.log_to_notes(f"**CONVERGED** at iteration {i+1}")
                break

        duration = datetime.now() - self.start_time
        duration_str = str(duration).split('.')[0]

        final_results = {
            "experiment": str(self.scenario_path),
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "version": "v3_event_logs",
            "total_iterations": len(self.history),
            "converged": self.has_converged(),
            "duration": duration_str,
            "total_tokens": self.total_tokens,
            "final_metrics": {
                "total_cost_mean": self.history[-1].metrics.total_cost_mean,
                "total_cost_std": self.history[-1].metrics.total_cost_std,
                "risk_adjusted_cost": self.history[-1].metrics.risk_adjusted_cost,
                "bank_a_cost_mean": self.history[-1].metrics.bank_a_cost_mean,
                "bank_b_cost_mean": self.history[-1].metrics.bank_b_cost_mean,
                "settlement_rate_mean": self.history[-1].metrics.settlement_rate_mean,
                "failure_rate": self.history[-1].metrics.failure_rate
            },
            "cost_progression": [h.metrics.total_cost_mean for h in self.history],
            "risk_adjusted_progression": [h.metrics.risk_adjusted_cost for h in self.history],
            "failure_rate_progression": [h.metrics.failure_rate for h in self.history],
            "final_policy_a": self.history[-1].policy_a,
            "final_policy_b": self.history[-1].policy_b
        }

        final_path = self.results_dir / "final_results.json"
        with open(final_path, 'w') as f:
            json.dump(final_results, f, indent=2)

        self.log_to_notes(
            f"\n### Final Results (V3 Event Logs)\n"
            f"- **Iterations**: {len(self.history)}\n"
            f"- **Converged**: {self.has_converged()}\n"
            f"- **Duration**: {duration_str}\n"
            f"- **Total Tokens**: {self.total_tokens:,}\n"
            f"- **Final Mean Cost**: ${self.history[-1].metrics.total_cost_mean:.0f}\n"
            f"- **Final Risk-Adjusted**: ${self.history[-1].metrics.risk_adjusted_cost:.0f}\n"
            f"- **Final Failure Rate**: {self.history[-1].metrics.failure_rate*100:.0f}%\n"
            f"- **Final Settlement Rate**: {self.history[-1].metrics.settlement_rate_mean*100:.1f}%\n"
        )

        print(f"\n{'=' * 60}")
        print(f"Optimization Complete (V3 Event Logs)")
        print(f"{'=' * 60}")
        print(f"  Iterations: {len(self.history)}")
        print(f"  Duration: {duration_str}")
        print(f"  Total tokens: {self.total_tokens:,}")
        print(f"  Final mean cost: ${self.history[-1].metrics.total_cost_mean:.0f}")
        print(f"  Final risk-adjusted: ${self.history[-1].metrics.risk_adjusted_cost:.0f}")
        print(f"  Final failure rate: {self.history[-1].metrics.failure_rate*100:.0f}%")
        print(f"  Results saved to: {self.results_dir}")

        return final_results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Castro Policy Optimizer V3 (Per-Tick Event Logs)")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--policy-a", required=True, help="Path to Bank A policy JSON")
    parser.add_argument("--policy-b", required=True, help="Path to Bank B policy JSON")
    parser.add_argument("--results-dir", required=True, help="Directory for results")
    parser.add_argument("--lab-notes", required=True, help="Path to lab notes file")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds per iteration")
    parser.add_argument("--max-iter", type=int, default=40, help="Max iterations")
    parser.add_argument("--model", default="gpt-5.1", help="OpenAI model")
    parser.add_argument("--reasoning", default="high",
                       choices=["none", "low", "medium", "high"],
                       help="Reasoning effort level")
    parser.add_argument("--verbose-seeds", type=int, default=2,
                       help="Number of best/worst seeds to capture verbose logs for")
    parser.add_argument("--convergence-threshold", type=float, default=0.10,
                       help="Convergence threshold (default 10%)")
    parser.add_argument("--convergence-window", type=int, default=5,
                       help="Consecutive stable iterations for convergence")

    args = parser.parse_args()

    optimizer = CastroPolicyOptimizerV3(
        scenario_path=args.scenario,
        policy_a_path=args.policy_a,
        policy_b_path=args.policy_b,
        results_dir=args.results_dir,
        lab_notes_path=args.lab_notes,
        num_seeds=args.seeds,
        max_iterations=args.max_iter,
        model=args.model,
        reasoning_effort=args.reasoning,
        verbose_seeds=args.verbose_seeds,
        convergence_threshold=args.convergence_threshold,
        convergence_window=args.convergence_window
    )

    optimizer.run()


if __name__ == "__main__":
    main()
