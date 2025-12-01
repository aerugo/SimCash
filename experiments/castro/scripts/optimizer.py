#!/usr/bin/env python3
"""
LLM Policy Optimizer for Castro et al. Replication
Using OpenAI GPT-5.1 with high reasoning effort

This script implements the LLM-in-the-loop policy optimization
described in llm-castro-simcash.md research proposal.
"""

import json
import subprocess
import tempfile
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from datetime import datetime

# OpenAI API
from openai import OpenAI


def _run_single_simulation(args: tuple) -> dict | None:
    """Standalone function for parallel simulation execution.

    Args:
        args: Tuple of (scenario_path, simcash_root, seed)

    Returns:
        Dict with simulation results or None on failure
    """
    scenario_path, simcash_root, seed = args
    try:
        result = subprocess.run(
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

        if result.returncode != 0:
            return {"error": f"Simulation failed (seed {seed}): {result.stderr}", "seed": seed}

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

        return {
            "seed": seed,
            "bank_a_cost": bank_a_cost,
            "bank_b_cost": bank_b_cost,
            "total_cost": total_cost,
            "settlement_rate": output.get("metrics", {}).get("settlement_rate", 0),
            "bank_a_balance_end": agents.get("BANK_A", {}).get("final_balance", 0),
            "bank_b_balance_end": agents.get("BANK_B", {}).get("final_balance", 0),
            "raw_output": output
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
    raw_output: dict


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across multiple seeds."""
    total_cost_mean: float
    total_cost_std: float
    bank_a_cost_mean: float
    bank_b_cost_mean: float
    settlement_rate_mean: float
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


class CastroPolicyOptimizer:
    """LLM-based policy optimizer for Castro et al. replication using GPT-5.1."""

    def __init__(
        self,
        scenario_path: str,
        policy_a_path: str,
        policy_b_path: str,
        results_dir: str,
        lab_notes_path: str,
        num_seeds: int = 10,
        max_iterations: int = 25,
        model: str = "gpt-5.1",
        reasoning_effort: str = "high",
        simcash_root: str = "/home/user/SimCash"
    ):
        self.scenario_path = Path(scenario_path)
        self.policy_a_path = Path(policy_a_path)
        self.policy_b_path = Path(policy_b_path)
        self.results_dir = Path(results_dir)
        self.lab_notes_path = Path(lab_notes_path)
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.simcash_root = Path(simcash_root)

        # Initialize OpenAI client
        self.client = OpenAI()

        self.history: list[IterationResult] = []
        self.total_tokens = 0
        self.start_time = None

        # Ensure results directory exists
        self.results_dir.mkdir(parents=True, exist_ok=True)

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

    def run_simulation(self, seed: int) -> SimulationResult:
        """Run a single simulation with the given seed."""
        result = subprocess.run(
            [
                str(self.simcash_root / "api" / ".venv" / "bin" / "payment-sim"),
                "run",
                "--config", str(self.scenario_path),
                "--seed", str(seed),
                "--quiet"
            ],
            capture_output=True,
            text=True,
            cwd=str(self.simcash_root)
        )

        if result.returncode != 0:
            raise RuntimeError(f"Simulation failed (seed {seed}): {result.stderr}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse simulation output: {e}\nOutput: {result.stdout[:500]}")

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

        return SimulationResult(
            seed=seed,
            bank_a_cost=bank_a_cost,
            bank_b_cost=bank_b_cost,
            total_cost=total_cost,
            settlement_rate=output.get("metrics", {}).get("settlement_rate", 0),
            bank_a_balance_end=agents.get("BANK_A", {}).get("final_balance", 0),
            bank_b_balance_end=agents.get("BANK_B", {}).get("final_balance", 0),
            raw_output=output
        )

    def run_simulations(self, seeds: list[int]) -> AggregatedMetrics:
        """Run simulations with multiple seeds in parallel and aggregate results."""
        import statistics

        # Prepare arguments for parallel execution
        args_list = [
            (str(self.scenario_path), str(self.simcash_root), seed)
            for seed in seeds
        ]

        results = []
        failed_seeds = []

        # Run simulations in parallel using ProcessPoolExecutor
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
                            raw_output=result_dict["raw_output"]
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

        # Sort results by seed for consistent ordering
        results.sort(key=lambda r: r.seed)

        costs = [r.total_cost for r in results]
        a_costs = [r.bank_a_cost for r in results]
        b_costs = [r.bank_b_cost for r in results]
        rates = [r.settlement_rate for r in results]

        return AggregatedMetrics(
            total_cost_mean=statistics.mean(costs),
            total_cost_std=statistics.stdev(costs) if len(costs) > 1 else 0,
            bank_a_cost_mean=statistics.mean(a_costs),
            bank_b_cost_mean=statistics.mean(b_costs),
            settlement_rate_mean=statistics.mean(rates),
            individual_results=results
        )

    def build_prompt(
        self,
        policy_a: dict,
        policy_b: dict,
        metrics: AggregatedMetrics
    ) -> str:
        """Build the LLM prompt for policy optimization."""

        history_rows = []
        for h in self.history[-10:]:  # Last 10 iterations for better learning
            # Extract key parameters from policies
            liq_a = h.policy_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
            liq_b = h.policy_b.get("parameters", {}).get("initial_liquidity_fraction", "?")
            history_rows.append(
                f"| {h.iteration} | A={liq_a}, B={liq_b} | ${h.metrics.total_cost_mean:.0f} | "
                f"${h.metrics.bank_a_cost_mean:.0f} / ${h.metrics.bank_b_cost_mean:.0f} | "
                f"{h.metrics.settlement_rate_mean*100:.0f}% |"
            )
        history_table = "\n".join(history_rows) if history_rows else "| (No history yet) | | | | |"

        # Cost breakdown from individual results
        if metrics.individual_results:
            sample = metrics.individual_results[0].raw_output
            cost_breakdown = json.dumps(sample.get("costs", {}), indent=2)
        else:
            cost_breakdown = "{}"

        return f"""# SimCash Castro Replication - Iteration {len(self.history)}

## Context
You are replicating Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning." Instead of gradient-based RL, you reason about cost trade-offs and propose improved policies.

## Castro Model Summary
- Two banks exchange payments over discrete periods
- Each bank chooses:
  1. **Initial liquidity**: Fraction of collateral to allocate at start (via `strategic_collateral_tree`)
  2. **Payment timing**: When to release each payment (via `payment_tree`)
- Costs:
  - **Collateral cost (r_c=0.1)**: Opportunity cost of posting capital
  - **Delay cost (r_d=0.2)**: Penalty for holding payments in Queue 1
  - **EOD/Overdraft cost (r_b=0.4)**: Cost for unsettled payments or borrowing

## Key Trade-off (from Castro et al.)
- Waiting for incoming payments can provide "free" liquidity
- But delay costs accumulate while waiting
- Optimal strategy balances these costs
- Nash equilibrium: Each bank's choice is best response to other's

## Policy Structure

Policies use SimCash JSON DSL with two trees:

1. `strategic_collateral_tree`: Called at tick 0, decides initial liquidity
   - Key parameter: `initial_liquidity_fraction` (0.0 to 1.0)
   - Action: `PostCollateral` with calculated amount

2. `payment_tree`: Called for each payment, decides Release vs Hold
   - Key parameters: `urgency_threshold`, `liquidity_buffer_factor`
   - Actions: `Release` or `Hold`

## Available Fields
- `system_tick_in_day`: Current tick (0, 1, 2, ...)
- `ticks_to_deadline`: Ticks until payment deadline
- `effective_liquidity`: Current balance + credit headroom
- `remaining_amount`: Payment amount
- `max_collateral_capacity`: Maximum collateral available

## Current Policies

### Bank A Policy
```json
{json.dumps(policy_a, indent=2)}
```

### Bank B Policy
```json
{json.dumps(policy_b, indent=2)}
```

## Simulation Results ({self.num_seeds} seeds)

| Metric | Value |
|--------|-------|
| **Total System Cost** | ${metrics.total_cost_mean:.2f} ± ${metrics.total_cost_std:.2f} |
| **Bank A Cost** | ${metrics.bank_a_cost_mean:.2f} |
| **Bank B Cost** | ${metrics.bank_b_cost_mean:.2f} |
| **Settlement Rate** | {metrics.settlement_rate_mean*100:.1f}% |

### Raw Cost Breakdown (Sample)
```json
{cost_breakdown}
```

## Iteration History (CRITICAL: Learn from this data!)
| Iter | Liquidity Params | Total Cost | A Cost / B Cost | Settlement |
|------|------------------|------------|-----------------|------------|
{history_table}

**Key Insight**: Lower initial_liquidity_fraction = Lower collateral cost. Observe how costs change with different liquidity values above.

## Your Task

Think step by step:

1. **Analyze Current State**: What are the dominant cost drivers? Is collateral cost, delay cost, or EOD penalty the main contributor?

2. **Evaluate Initial Liquidity**: Are banks posting too much (high collateral cost) or too little (high delay/EOD cost)?

3. **Evaluate Payment Timing**: Are payments being released too early (overdraft risk) or too late (delay cost)?

4. **Consider Strategic Interaction**: How does one bank's behavior affect the other? If Bank B sends early, Bank A can wait for incoming liquidity.

5. **Propose Improvements**: Adjust `parameters` values and/or tree structure to reduce total costs.

## Output Format

Provide your response in this exact format:

### Analysis
[Your 2-3 paragraph analysis]

### Bank A Policy
```json
[Complete valid JSON policy for Bank A]
```

### Bank B Policy
```json
[Complete valid JSON policy for Bank B]
```

### Expected Improvement
[One paragraph explaining expected cost reduction]

**CRITICAL**: Output complete, valid JSON policies. Do not use ellipsis (...) or placeholders. Every policy must have `version`, `policy_id`, `parameters`, and at least a `payment_tree`.
"""

    def parse_policies(self, response: str) -> tuple[dict, dict]:
        """Parse two policy JSONs from LLM response."""
        import re

        # Save response for debugging
        debug_path = self.results_dir / f"llm_response_{len(self.history):03d}.txt"
        with open(debug_path, 'w') as f:
            f.write(response)

        # Try multiple parsing strategies

        # Strategy 1: Find ```json blocks
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', response)

        # Strategy 2: Find any ``` code blocks
        if len(json_blocks) < 2:
            json_blocks = re.findall(r'```\s*([\s\S]*?)\s*```', response)
            # Filter to only those that look like JSON
            json_blocks = [b for b in json_blocks if b.strip().startswith('{')]

        # Strategy 3: Find JSON objects with policy_id
        if len(json_blocks) < 2:
            # Match complete JSON objects by balanced braces
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

        # Strategy 4: Look for Bank A / Bank B section headers and extract JSON
        if len(json_blocks) < 2:
            bank_a_match = re.search(r'Bank A[^\{]*(\{[\s\S]*?"payment_tree"[\s\S]*?\})\s*(?:###|Bank B|$)', response)
            bank_b_match = re.search(r'Bank B[^\{]*(\{[\s\S]*?"payment_tree"[\s\S]*?\})\s*(?:###|Expected|$)', response)
            if bank_a_match and bank_b_match:
                json_blocks = [bank_a_match.group(1), bank_b_match.group(1)]

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
        """Run one iteration of the optimization loop."""
        iteration_num = len(self.history)

        # Generate seeds for this iteration
        seeds = list(range(1, self.num_seeds + 1))
        seeds_str = ", ".join(str(s) for s in seeds)

        self.log_to_notes(f"Starting iteration {iteration_num} with seeds: [{seeds_str}]")

        # Load current policies
        policy_a = self.load_policy(self.policy_a_path)
        policy_b = self.load_policy(self.policy_b_path)

        # Run simulations in parallel
        print(f"  Running {self.num_seeds} simulations in parallel (seeds: {seeds_str})...")
        metrics = self.run_simulations(seeds)

        # Log detailed per-seed results
        per_seed_costs = [f"S{r.seed}=${r.total_cost:.0f}" for r in metrics.individual_results]
        per_seed_summary = ", ".join(per_seed_costs)

        self.log_to_notes(
            f"Iteration {iteration_num} results: Mean=${metrics.total_cost_mean:.2f} ± ${metrics.total_cost_std:.2f}, "
            f"Settlement={metrics.settlement_rate_mean*100:.1f}%, "
            f"Per-seed: [{per_seed_summary}]"
        )

        # Build prompt
        prompt = self.build_prompt(policy_a, policy_b, metrics)

        # Call LLM with appropriate settings (with retry logic)
        print(f"  Calling {self.model} (reasoning={self.reasoning_effort})...")
        llm_text = None
        tokens_used = 0
        max_retries = 8  # More retries for intermittent TLS errors
        for attempt in range(max_retries):
            try:
                # Build request parameters
                request_params = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert financial systems researcher optimizing payment system policies. Think carefully and provide detailed analysis."
                        },
                        {"role": "user", "content": prompt}
                    ],
                }

                # Model-specific parameters
                if self.model.startswith("gpt-5"):
                    # GPT-5.x uses max_completion_tokens and reasoning_effort
                    # High reasoning effort needs large token budget for reasoning + output
                    request_params["max_completion_tokens"] = 200000
                    request_params["reasoning_effort"] = self.reasoning_effort
                elif self.model.startswith("o1") or self.model.startswith("o3"):
                    # o1/o3 models use max_completion_tokens
                    request_params["max_completion_tokens"] = 8000
                else:
                    # Standard models use max_tokens and temperature
                    request_params["max_tokens"] = 8000
                    request_params["temperature"] = 0.7

                response = self.client.chat.completions.create(**request_params)
                llm_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                self.total_tokens += tokens_used
                break
            except Exception as e:
                wait_time = 2 ** (attempt + 1)  # 2, 4, 8, 16 seconds
                self.log_to_notes(f"LLM call attempt {attempt+1} failed: {e}. Retrying in {wait_time}s...")
                print(f"  API error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    self.log_to_notes(f"LLM call failed after {max_retries} attempts: {e}")
                    raise

        if llm_text is None:
            raise RuntimeError("LLM returned no response")

        # Parse new policies
        try:
            new_a, new_b = self.parse_policies(llm_text)
            self.log_to_notes(f"Successfully parsed new policies from LLM response")
        except Exception as e:
            self.log_to_notes(f"Failed to parse policies: {e}. Keeping current policies.")
            print(f"  Failed to parse policies: {e}")
            new_a, new_b = policy_a, policy_b

        # Validate policies
        valid_a, msg_a = self.validate_policy(new_a)
        if not valid_a:
            self.log_to_notes(f"Bank A policy invalid: {msg_a[:200]}")
            print(f"  Bank A policy invalid, keeping previous")
            new_a = policy_a

        valid_b, msg_b = self.validate_policy(new_b)
        if not valid_b:
            self.log_to_notes(f"Bank B policy invalid: {msg_b[:200]}")
            print(f"  Bank B policy invalid, keeping previous")
            new_b = policy_b

        # Save new policies
        self.save_policy(new_a, self.policy_a_path)
        self.save_policy(new_b, self.policy_b_path)

        # Record history
        self.history.append(IterationResult(
            iteration=iteration_num,
            policy_a=new_a,
            policy_b=new_b,
            metrics=metrics,
            llm_analysis=llm_text,
            tokens_used=tokens_used
        ))

        # Log key parameter changes
        old_liq_a = policy_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
        new_liq_a = new_a.get("parameters", {}).get("initial_liquidity_fraction", "?")
        old_liq_b = policy_b.get("parameters", {}).get("initial_liquidity_fraction", "?")
        new_liq_b = new_b.get("parameters", {}).get("initial_liquidity_fraction", "?")

        self.log_to_notes(
            f"Parameter changes: Bank A liquidity {old_liq_a} -> {new_liq_a}, "
            f"Bank B liquidity {old_liq_b} -> {new_liq_b}"
        )

        return new_a, new_b, metrics

    def has_converged(self, window: int = 3, threshold: float = 0.05) -> bool:
        """Check if optimization has converged."""
        if len(self.history) < window + 1:
            return False

        recent_costs = [h.metrics.total_cost_mean for h in self.history[-window:]]
        prev_cost = self.history[-(window+1)].metrics.total_cost_mean

        if prev_cost == 0:
            return True

        # Check if variance is low
        import statistics
        if len(recent_costs) > 1:
            variance = statistics.stdev(recent_costs) / statistics.mean(recent_costs)
            if variance > 0.1:  # High variance means not converged
                return False

        # Check if improvement is minimal
        avg_recent = statistics.mean(recent_costs)
        relative_change = abs(avg_recent - prev_cost) / max(prev_cost, 1)

        return relative_change < threshold

    def run(self) -> dict:
        """Run the full optimization loop."""
        self.start_time = datetime.now()

        print(f"=" * 60)
        print(f"Castro Policy Optimization using GPT-5.1")
        print(f"=" * 60)
        print(f"  Scenario: {self.scenario_path}")
        print(f"  Model: {self.model} (reasoning={self.reasoning_effort})")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"  Seeds per iteration: {self.num_seeds}")
        print()

        self.log_to_notes(
            f"\n---\n## Experiment Run: {self.scenario_path.name}\n"
            f"**Model**: {self.model}\n"
            f"**Reasoning**: {self.reasoning_effort}\n"
            f"**Max Iterations**: {self.max_iterations}\n"
            f"**Seeds**: {self.num_seeds}\n"
        )

        for i in range(self.max_iterations):
            print(f"\nIteration {i+1}/{self.max_iterations}")
            print("-" * 40)

            policy_a, policy_b, metrics = self.iterate()

            print(f"  Total cost: ${metrics.total_cost_mean:.2f} ± ${metrics.total_cost_std:.2f}")
            print(f"  Bank A: ${metrics.bank_a_cost_mean:.2f}, Bank B: ${metrics.bank_b_cost_mean:.2f}")
            print(f"  Settlement rate: {metrics.settlement_rate_mean*100:.1f}%")
            print(f"  Tokens used this iteration: {self.history[-1].tokens_used:,}")

            # Save iteration results with per-seed data
            iteration_path = self.results_dir / f"iteration_{i:03d}.json"
            seeds_used = [r.seed for r in metrics.individual_results]
            per_seed_results = [
                {
                    "seed": r.seed,
                    "total_cost": r.total_cost,
                    "bank_a_cost": r.bank_a_cost,
                    "bank_b_cost": r.bank_b_cost,
                    "settlement_rate": r.settlement_rate
                }
                for r in metrics.individual_results
            ]
            with open(iteration_path, 'w') as f:
                json.dump({
                    "iteration": i,
                    "timestamp": datetime.now().isoformat(),
                    "seeds_used": seeds_used,
                    "metrics": {
                        "total_cost_mean": metrics.total_cost_mean,
                        "total_cost_std": metrics.total_cost_std,
                        "bank_a_cost_mean": metrics.bank_a_cost_mean,
                        "bank_b_cost_mean": metrics.bank_b_cost_mean,
                        "settlement_rate_mean": metrics.settlement_rate_mean
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

        # Calculate duration
        duration = datetime.now() - self.start_time
        duration_str = str(duration).split('.')[0]

        # Save final results
        final_results = {
            "experiment": str(self.scenario_path),
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "total_iterations": len(self.history),
            "converged": self.has_converged(),
            "duration": duration_str,
            "total_tokens": self.total_tokens,
            "final_metrics": {
                "total_cost_mean": self.history[-1].metrics.total_cost_mean,
                "total_cost_std": self.history[-1].metrics.total_cost_std,
                "bank_a_cost_mean": self.history[-1].metrics.bank_a_cost_mean,
                "bank_b_cost_mean": self.history[-1].metrics.bank_b_cost_mean,
                "settlement_rate_mean": self.history[-1].metrics.settlement_rate_mean
            },
            "cost_progression": [
                h.metrics.total_cost_mean for h in self.history
            ],
            "final_policy_a": self.history[-1].policy_a,
            "final_policy_b": self.history[-1].policy_b
        }

        final_path = self.results_dir / "final_results.json"
        with open(final_path, 'w') as f:
            json.dump(final_results, f, indent=2)

        # Log final summary
        self.log_to_notes(
            f"\n### Final Results\n"
            f"- **Iterations**: {len(self.history)}\n"
            f"- **Converged**: {self.has_converged()}\n"
            f"- **Duration**: {duration_str}\n"
            f"- **Total Tokens**: {self.total_tokens:,}\n"
            f"- **Final Cost**: ${self.history[-1].metrics.total_cost_mean:.2f}\n"
            f"- **Settlement Rate**: {self.history[-1].metrics.settlement_rate_mean*100:.1f}%\n"
        )

        print(f"\n{'=' * 60}")
        print(f"Optimization Complete")
        print(f"{'=' * 60}")
        print(f"  Iterations: {len(self.history)}")
        print(f"  Duration: {duration_str}")
        print(f"  Total tokens: {self.total_tokens:,}")
        print(f"  Final cost: ${self.history[-1].metrics.total_cost_mean:.2f}")
        print(f"  Results saved to: {self.results_dir}")

        return final_results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Castro Policy Optimizer using GPT-5.1")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--policy-a", required=True, help="Path to Bank A policy JSON")
    parser.add_argument("--policy-b", required=True, help="Path to Bank B policy JSON")
    parser.add_argument("--results-dir", required=True, help="Directory for results")
    parser.add_argument("--lab-notes", required=True, help="Path to lab notes file")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds per iteration")
    parser.add_argument("--max-iter", type=int, default=25, help="Max iterations")
    parser.add_argument("--model", default="gpt-5.1", help="OpenAI model")
    parser.add_argument("--reasoning", default="high",
                       choices=["none", "low", "medium", "high"],
                       help="Reasoning effort level")

    args = parser.parse_args()

    optimizer = CastroPolicyOptimizer(
        scenario_path=args.scenario,
        policy_a_path=args.policy_a,
        policy_b_path=args.policy_b,
        results_dir=args.results_dir,
        lab_notes_path=args.lab_notes,
        num_seeds=args.seeds,
        max_iterations=args.max_iter,
        model=args.model,
        reasoning_effort=args.reasoning
    )

    optimizer.run()


if __name__ == "__main__":
    main()
