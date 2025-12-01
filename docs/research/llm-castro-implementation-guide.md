# Implementation Guide: Running Castro et al. Replication Experiments

**Version**: 1.0
**Date**: 2025-11-30
**Companion to**: `llm-castro-simcash.md`

---

## Overview

This guide provides step-by-step instructions for running the LLM-based policy optimization experiments that replicate Castro et al. (2025). By the end, you will have:

1. Three configured experiments matching Castro's setup
2. Baseline policies for comparison
3. An LLM optimization harness
4. Results comparing LLM iteration vs. baselines

---

## Prerequisites

### System Requirements

- Python 3.11+
- Rust (for building SimCash backend)
- API key for an LLM provider (Anthropic/OpenAI)
- ~4GB disk space for results

### Verify SimCash Installation

```bash
# Navigate to SimCash directory
cd /home/user/SimCash

# Build and install
cd api
uv sync --extra dev

# Verify CLI works
.venv/bin/payment-sim --help

# Run a quick test
.venv/bin/payment-sim run --config ../examples/configs/bis_liquidity_delay_tradeoff.yaml --quiet
```

Expected output: JSON with simulation results.

---

## Step 1: Create Directory Structure

```bash
# Create experiment directories
mkdir -p experiments/castro/configs
mkdir -p experiments/castro/policies
mkdir -p experiments/castro/results
mkdir -p experiments/castro/scripts
```

---

## Step 2: Create Scenario Configuration Files

### Experiment 1: Two-Period Validation

Create `experiments/castro/configs/castro_2period.yaml`:

```yaml
# Castro et al. (2025) - 2-Period Fixed Payment Scenario
# Replicates Section 6.3 for analytical validation
#
# Expected Nash Equilibrium:
#   Bank A: ℓ₀ = 0 (wait for incoming from B)
#   Bank B: ℓ₀ = 20000 (cover both periods)
#   Costs: R_A = 0, R_B = 2000

simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42

# Castro cost structure: r_c = 0.1, r_d = 0.2, r_b = 0.4
# Scaled to SimCash per-tick rates
cost_rates:
  # Collateral opportunity cost: 10% per tick of balance
  # Using liquidity_cost_per_tick_bps for posted collateral
  liquidity_cost_per_tick_bps: 1000    # 10% = 1000 bps / 10

  # Delay cost: 20% of held value per tick
  delay_cost_per_tick_per_cent: 0.002  # 0.2% per cent per tick

  # EOD penalty: 40% of unsettled amount
  eod_penalty_per_transaction: 0       # Use custom calc
  overdraft_bps_per_tick: 4000         # 40% EOD borrowing rate proxy

  # Disable non-Castro features
  collateral_cost_per_tick_bps: 0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0

# Disable LSM (not in Castro model)
lsm_config:
  enable_bilateral: false
  enable_cycles: false
  max_cycle_length: 2
  max_cycles_per_tick: 1

agents:
  # BANK_A: Payment profile P^A = [0, 15000] cents
  # Period 1: No outgoing, Period 2: $150
  - id: BANK_A
    opening_balance: 0                 # To be set by collateral policy
    unsecured_cap: 0                   # No credit (force collateral use)
    max_collateral_capacity: 10000000  # $100k max

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/bank_a.json"

  # BANK_B: Payment profile P^B = [15000, 5000] cents
  # Period 1: $150, Period 2: $50
  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 0
    max_collateral_capacity: 10000000

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/bank_b.json"

# Deterministic payment injections matching Castro's fixed profile
scenario_events:
  # Bank A: $150 outgoing in period 2 (tick 1)
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 15000                      # $150 in cents
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 1

  # Bank B: $150 outgoing in period 1 (tick 0)
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 15000
    priority: 5
    deadline: 1
    schedule:
      type: OneTime
      tick: 0

  # Bank B: $50 outgoing in period 2 (tick 1)
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 5000                       # $50 in cents
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 1
```

### Experiment 2: Twelve-Period Stochastic

Create `experiments/castro/configs/castro_12period.yaml`:

```yaml
# Castro et al. (2025) - 12-Period LVTS-Style Scenario
# Replicates Section 6.4 with stochastic arrivals

simulation:
  ticks_per_day: 12
  num_days: 1
  rng_seed: 42

cost_rates:
  # Per-tick rates (Castro daily rates / 12)
  liquidity_cost_per_tick_bps: 83      # r_c ≈ 0.1/12
  delay_cost_per_tick_per_cent: 0.00017  # r_d ≈ 0.2/12
  overdraft_bps_per_tick: 333          # r_b ≈ 0.4/12

  collateral_cost_per_tick_bps: 0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0
  eod_penalty_per_transaction: 50000   # Strong EOD pressure

lsm_config:
  enable_bilateral: false
  enable_cycles: false
  max_cycle_length: 2
  max_cycles_per_tick: 1

agents:
  # BANK_A: Lower volume, symmetric to LVTS participant
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0
    max_collateral_capacity: 50000000  # $500k

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/bank_a.json"

    # Stochastic arrivals
    arrival_config:
      rate_per_tick: 0.5               # ~6 transactions/day
      amount_distribution:
        type: LogNormal
        mean: 11.51                    # ~$100k median
        std_dev: 0.9
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [3, 8]
      priority: 5
      divisible: false

  # BANK_B: Higher volume (asymmetric)
  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 0
    max_collateral_capacity: 50000000

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/bank_b.json"

    arrival_config:
      rate_per_tick: 0.65              # Higher than A
      amount_distribution:
        type: LogNormal
        mean: 11.8                     # ~$120k median
        std_dev: 1.0
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [2, 6]           # Tighter deadlines
      priority: 5
      divisible: false
```

### Experiment 3: Joint Learning (3-Period)

Create `experiments/castro/configs/castro_joint.yaml`:

```yaml
# Castro et al. (2025) - 3-Period Joint Learning
# Replicates Section 7: Learn both initial liquidity AND intraday timing

simulation:
  ticks_per_day: 3
  num_days: 1
  rng_seed: 42

cost_rates:
  # Per-tick rates (Castro daily rates / 3)
  liquidity_cost_per_tick_bps: 333     # r_c ≈ 0.1/3
  delay_cost_per_tick_per_cent: 0.00067  # r_d ≈ 0.2/3
  overdraft_bps_per_tick: 1333         # r_b ≈ 0.4/3

  collateral_cost_per_tick_bps: 0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0
  eod_penalty_per_transaction: 100000

lsm_config:
  enable_bilateral: false
  enable_cycles: false
  max_cycle_length: 2
  max_cycles_per_tick: 1

agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0
    max_collateral_capacity: 10000000

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/joint_policy.json"

  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 0
    max_collateral_capacity: 10000000

    policy:
      type: FromJson
      json_path: "experiments/castro/policies/joint_policy.json"

# Symmetric payment profile: P = [20000, 20000, 0]
scenario_events:
  # Bank A outgoing
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 20000
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 0

  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 20000
    priority: 5
    deadline: 3
    schedule:
      type: OneTime
      tick: 1

  # Bank B outgoing (symmetric)
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 20000
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 0

  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 20000
    priority: 5
    deadline: 3
    schedule:
      type: OneTime
      tick: 1
```

---

## Step 3: Create Initial Policy Templates

### Baseline: FIFO Policy

Create `experiments/castro/policies/fifo_baseline.json`:

```json
{
  "version": "1.0",
  "policy_id": "fifo_baseline",
  "description": "Baseline: Release all payments immediately (no strategic delay)",
  "parameters": {},
  "payment_tree": {
    "type": "action",
    "node_id": "release_all",
    "action": "Release"
  }
}
```

### Seed Policy: Simple Urgency-Based

Create `experiments/castro/policies/bank_a.json` and `bank_b.json`:

```json
{
  "version": "1.0",
  "policy_id": "castro_seed_policy",
  "description": "Seed policy for LLM optimization - simple urgency-based release",
  "parameters": {
    "urgency_threshold": 5.0,
    "initial_liquidity_fraction": 0.5
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_tick_zero",
    "description": "Allocate initial liquidity at start of day",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_post_initial",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        },
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_hold",
      "action": "HoldCollateral"
    }
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "P1_check_urgent",
    "description": "Release if close to deadline",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "P2_release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3_check_liquidity",
      "description": "Release if we have excess liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {"value": 1.5}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "P4_release_liquid",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "P5_hold",
        "action": "Hold"
      }
    }
  }
}
```

### Joint Learning Policy

Create `experiments/castro/policies/joint_policy.json`:

```json
{
  "version": "1.0",
  "policy_id": "castro_joint_policy",
  "description": "Policy for joint initial liquidity and intraday timing optimization",
  "parameters": {
    "initial_liquidity_fraction": 0.5,
    "urgency_threshold": 2.0,
    "liquidity_buffer_factor": 1.2
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_tick_zero",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_post",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        },
        "reason": {"value": "InitialLiquidity"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_hold",
      "action": "HoldCollateral"
    }
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "P1_urgent",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "P2_release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3_liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {"param": "liquidity_buffer_factor"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "P4_release",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "P5_hold",
        "action": "Hold"
      }
    }
  }
}
```

---

## Step 4: Validate Configurations

```bash
cd /home/user/SimCash

# Validate scenario configs
.venv/bin/payment-sim run --config experiments/castro/configs/castro_2period.yaml --quiet

# Validate policies
.venv/bin/payment-sim validate-policy experiments/castro/policies/bank_a.json --verbose
.venv/bin/payment-sim validate-policy experiments/castro/policies/joint_policy.json --verbose

# Validate policy against scenario
.venv/bin/payment-sim validate-policy experiments/castro/policies/bank_a.json \
  --scenario experiments/castro/configs/castro_2period.yaml
```

---

## Step 5: Create LLM Optimization Harness

Create `experiments/castro/scripts/optimizer.py`:

```python
#!/usr/bin/env python3
"""
LLM Policy Optimizer for Castro et al. Replication

This script implements the LLM-in-the-loop policy optimization
described in llm-castro-simcash.md.
"""

import json
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import anthropic  # pip install anthropic


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
    individual_results: list[SimulationResult]


@dataclass
class IterationResult:
    """Results from one optimization iteration."""
    iteration: int
    policy_a: dict
    policy_b: dict
    metrics: AggregatedMetrics
    llm_analysis: str


class CastroPolicyOptimizer:
    """LLM-based policy optimizer for Castro et al. replication."""

    def __init__(
        self,
        scenario_path: str,
        policy_a_path: str,
        policy_b_path: str,
        results_dir: str,
        num_seeds: int = 10,
        max_iterations: int = 25,
        model: str = "claude-sonnet-4-20250514"
    ):
        self.scenario_path = Path(scenario_path)
        self.policy_a_path = Path(policy_a_path)
        self.policy_b_path = Path(policy_b_path)
        self.results_dir = Path(results_dir)
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.model = model

        self.client = anthropic.Anthropic()
        self.history: list[IterationResult] = []

        # Ensure results directory exists
        self.results_dir.mkdir(parents=True, exist_ok=True)

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
                ".venv/bin/payment-sim", "run",
                "--config", str(self.scenario_path),
                "--seed", str(seed),
                "--quiet"
            ],
            capture_output=True,
            text=True,
            cwd="/home/user/SimCash"
        )

        if result.returncode != 0:
            raise RuntimeError(f"Simulation failed: {result.stderr}")

        output = json.loads(result.stdout)

        # Extract costs from output
        costs = output.get("costs", {})
        agents = {a["id"]: a for a in output.get("agents", [])}

        return SimulationResult(
            seed=seed,
            bank_a_cost=costs.get("BANK_A", {}).get("total", 0),
            bank_b_cost=costs.get("BANK_B", {}).get("total", 0),
            total_cost=costs.get("total_cost", 0),
            settlement_rate=output.get("metrics", {}).get("settlement_rate", 0),
            bank_a_balance_end=agents.get("BANK_A", {}).get("final_balance", 0),
            bank_b_balance_end=agents.get("BANK_B", {}).get("final_balance", 0),
            raw_output=output
        )

    def run_simulations(self, seeds: list[int]) -> AggregatedMetrics:
        """Run simulations with multiple seeds and aggregate results."""
        results = []
        for seed in seeds:
            try:
                result = self.run_simulation(seed)
                results.append(result)
            except Exception as e:
                print(f"Warning: Seed {seed} failed: {e}")

        if not results:
            raise RuntimeError("All simulations failed")

        import statistics

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
        for h in self.history[-5:]:  # Last 5 iterations
            history_rows.append(
                f"| {h.iteration} | ${h.metrics.total_cost_mean:.2f} | "
                f"${h.metrics.bank_a_cost_mean:.2f} | ${h.metrics.bank_b_cost_mean:.2f} |"
            )
        history_table = "\n".join(history_rows) if history_rows else "| (No history yet) |"

        return f"""# SimCash Castro Replication - Iteration {len(self.history)}

## Context
You are replicating Castro et al. (2025) "Estimating Policy Functions in Payment
Systems Using Reinforcement Learning." Instead of gradient-based RL, you reason
about cost trade-offs and propose improved policies.

## Castro Model Summary
- Two banks exchange payments over discrete periods
- Each bank chooses:
  1. Initial liquidity (fraction of collateral to allocate at start)
  2. Payment timing (when to release each payment)
- Costs:
  - Collateral/liquidity cost: Opportunity cost of posting capital
  - Delay cost: Penalty for holding payments in queue
  - EOD penalty: Cost for unsettled payments at end of day
- Key trade-off: Waiting for incoming payments saves liquidity but incurs delay

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
| Total System Cost | ${metrics.total_cost_mean:.2f} ± ${metrics.total_cost_std:.2f} |
| Bank A Cost | ${metrics.bank_a_cost_mean:.2f} |
| Bank B Cost | ${metrics.bank_b_cost_mean:.2f} |
| Settlement Rate | {metrics.settlement_rate_mean*100:.1f}% |

## Iteration History
| Iter | System Cost | Bank A | Bank B |
|------|-------------|--------|--------|
{history_table}

## Your Task

1. **Analyze**: What cost component dominates? Are banks over/under-allocating liquidity?
2. **Identify**: What's causing unnecessary costs?
3. **Propose**: Modify parameters and/or tree structure to reduce costs
4. **Explain**: Why will this change improve performance?

## Output Format

Respond with:
1. Your analysis (2-3 paragraphs)
2. The complete updated Bank A policy JSON (wrapped in ```json blocks)
3. The complete updated Bank B policy JSON (wrapped in ```json blocks)
4. Expected cost improvement

IMPORTANT: Output complete, valid JSON policies. Do not use placeholders or ellipsis.
"""

    def parse_policies(self, response: str) -> tuple[dict, dict]:
        """Parse two policy JSONs from LLM response."""
        import re

        # Find all JSON blocks
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', response, re.DOTALL)

        if len(json_blocks) < 2:
            raise ValueError(f"Expected 2 JSON blocks, found {len(json_blocks)}")

        policy_a = json.loads(json_blocks[0])
        policy_b = json.loads(json_blocks[1])

        return policy_a, policy_b

    def validate_policy(self, policy: dict) -> bool:
        """Validate a policy using SimCash CLI."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json.dump(policy, f)
            f.flush()

            result = subprocess.run(
                [
                    ".venv/bin/payment-sim", "validate-policy",
                    f.name, "--format", "json"
                ],
                capture_output=True,
                text=True,
                cwd="/home/user/SimCash"
            )

            os.unlink(f.name)

            if result.returncode != 0:
                print(f"Validation failed: {result.stderr}")
                return False

            output = json.loads(result.stdout)
            return output.get("valid", False)

    def iterate(self) -> tuple[dict, dict, AggregatedMetrics]:
        """Run one iteration of the optimization loop."""
        # Load current policies
        policy_a = self.load_policy(self.policy_a_path)
        policy_b = self.load_policy(self.policy_b_path)

        # Run simulations
        seeds = list(range(1, self.num_seeds + 1))
        metrics = self.run_simulations(seeds)

        # Build prompt
        prompt = self.build_prompt(policy_a, policy_b, metrics)

        # Call LLM
        print(f"  Calling LLM ({self.model})...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        llm_text = response.content[0].text

        # Parse new policies
        try:
            new_a, new_b = self.parse_policies(llm_text)
        except Exception as e:
            print(f"  Failed to parse policies: {e}")
            print("  Keeping current policies...")
            new_a, new_b = policy_a, policy_b

        # Validate policies
        if not self.validate_policy(new_a):
            print("  Bank A policy invalid, keeping previous")
            new_a = policy_a

        if not self.validate_policy(new_b):
            print("  Bank B policy invalid, keeping previous")
            new_b = policy_b

        # Save new policies
        self.save_policy(new_a, self.policy_a_path)
        self.save_policy(new_b, self.policy_b_path)

        # Record history
        self.history.append(IterationResult(
            iteration=len(self.history),
            policy_a=new_a,
            policy_b=new_b,
            metrics=metrics,
            llm_analysis=llm_text
        ))

        return new_a, new_b, metrics

    def has_converged(self, window: int = 3, threshold: float = 0.01) -> bool:
        """Check if optimization has converged."""
        if len(self.history) < window + 1:
            return False

        recent_costs = [h.metrics.total_cost_mean for h in self.history[-window:]]
        prev_cost = self.history[-(window+1)].metrics.total_cost_mean

        # Check if variance is low and improvement is minimal
        import statistics
        if prev_cost == 0:
            return True

        avg_recent = statistics.mean(recent_costs)
        relative_change = abs(avg_recent - prev_cost) / prev_cost

        return relative_change < threshold

    def run(self) -> dict:
        """Run the full optimization loop."""
        print(f"Starting Castro Policy Optimization")
        print(f"  Scenario: {self.scenario_path}")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"  Seeds per iteration: {self.num_seeds}")
        print()

        for i in range(self.max_iterations):
            print(f"Iteration {i+1}/{self.max_iterations}")

            policy_a, policy_b, metrics = self.iterate()

            print(f"  Total cost: ${metrics.total_cost_mean:.2f} ± ${metrics.total_cost_std:.2f}")
            print(f"  Settlement rate: {metrics.settlement_rate_mean*100:.1f}%")

            # Save iteration results
            iteration_path = self.results_dir / f"iteration_{i:03d}.json"
            with open(iteration_path, 'w') as f:
                json.dump({
                    "iteration": i,
                    "metrics": {
                        "total_cost_mean": metrics.total_cost_mean,
                        "total_cost_std": metrics.total_cost_std,
                        "bank_a_cost_mean": metrics.bank_a_cost_mean,
                        "bank_b_cost_mean": metrics.bank_b_cost_mean,
                        "settlement_rate_mean": metrics.settlement_rate_mean
                    },
                    "policy_a": policy_a,
                    "policy_b": policy_b
                }, f, indent=2)

            if self.has_converged():
                print(f"\nConverged at iteration {i+1}")
                break

            print()

        # Save final results
        final_path = self.results_dir / "final_results.json"
        with open(final_path, 'w') as f:
            json.dump({
                "total_iterations": len(self.history),
                "converged": self.has_converged(),
                "final_metrics": {
                    "total_cost_mean": self.history[-1].metrics.total_cost_mean,
                    "total_cost_std": self.history[-1].metrics.total_cost_std,
                    "settlement_rate_mean": self.history[-1].metrics.settlement_rate_mean
                },
                "cost_progression": [
                    h.metrics.total_cost_mean for h in self.history
                ],
                "final_policy_a": self.history[-1].policy_a,
                "final_policy_b": self.history[-1].policy_b
            }, f, indent=2)

        print(f"\nOptimization complete. Results saved to {self.results_dir}")
        return self.history[-1].metrics.__dict__


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Castro Policy Optimizer")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--policy-a", required=True, help="Path to Bank A policy JSON")
    parser.add_argument("--policy-b", required=True, help="Path to Bank B policy JSON")
    parser.add_argument("--results-dir", required=True, help="Directory for results")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds per iteration")
    parser.add_argument("--max-iter", type=int, default=25, help="Max iterations")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="LLM model")

    args = parser.parse_args()

    optimizer = CastroPolicyOptimizer(
        scenario_path=args.scenario,
        policy_a_path=args.policy_a,
        policy_b_path=args.policy_b,
        results_dir=args.results_dir,
        num_seeds=args.seeds,
        max_iterations=args.max_iter,
        model=args.model
    )

    optimizer.run()
```

Make it executable:

```bash
chmod +x experiments/castro/scripts/optimizer.py
```

---

## Step 6: Run Baseline Experiments

Create `experiments/castro/scripts/run_baselines.sh`:

```bash
#!/bin/bash
# Run baseline experiments for comparison

set -e

cd /home/user/SimCash

RESULTS_DIR="experiments/castro/results/baselines"
mkdir -p "$RESULTS_DIR"

echo "=== Running Baselines ==="

# Function to run multiple seeds and aggregate
run_baseline() {
    local name=$1
    local config=$2
    local output_file="$RESULTS_DIR/${name}.json"

    echo "Running baseline: $name"

    # Run 10 seeds
    results="["
    for seed in {1..10}; do
        result=$(.venv/bin/payment-sim run \
            --config "$config" \
            --seed "$seed" \
            --quiet 2>/dev/null)
        if [ "$seed" -gt 1 ]; then
            results+=","
        fi
        results+="$result"
    done
    results+="]"

    echo "$results" > "$output_file"
    echo "  Saved to $output_file"
}

# Run 2-period baselines
echo ""
echo "--- 2-Period Experiment ---"
run_baseline "2period_seed" "experiments/castro/configs/castro_2period.yaml"

# Run 12-period baselines
echo ""
echo "--- 12-Period Experiment ---"
run_baseline "12period_seed" "experiments/castro/configs/castro_12period.yaml"

# Run joint learning baselines
echo ""
echo "--- Joint Learning Experiment ---"
run_baseline "joint_seed" "experiments/castro/configs/castro_joint.yaml"

echo ""
echo "=== Baselines Complete ==="
echo "Results saved to: $RESULTS_DIR"
```

Make it executable and run:

```bash
chmod +x experiments/castro/scripts/run_baselines.sh
./experiments/castro/scripts/run_baselines.sh
```

---

## Step 7: Run LLM Optimization Experiments

### Install Dependencies

```bash
cd /home/user/SimCash/api
pip install anthropic  # or openai if using GPT-4
```

### Set API Key

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Run Experiment 1: Two-Period Validation

```bash
cd /home/user/SimCash

# Copy seed policies
cp experiments/castro/policies/bank_a.json experiments/castro/policies/exp1_bank_a.json
cp experiments/castro/policies/bank_a.json experiments/castro/policies/exp1_bank_b.json

# Run optimizer
python experiments/castro/scripts/optimizer.py \
    --scenario experiments/castro/configs/castro_2period.yaml \
    --policy-a experiments/castro/policies/exp1_bank_a.json \
    --policy-b experiments/castro/policies/exp1_bank_b.json \
    --results-dir experiments/castro/results/exp1_2period \
    --seeds 10 \
    --max-iter 15 \
    --model claude-sonnet-4-20250514
```

### Run Experiment 2: Twelve-Period Stochastic

```bash
# Copy seed policies
cp experiments/castro/policies/bank_a.json experiments/castro/policies/exp2_bank_a.json
cp experiments/castro/policies/bank_a.json experiments/castro/policies/exp2_bank_b.json

# Run optimizer
python experiments/castro/scripts/optimizer.py \
    --scenario experiments/castro/configs/castro_12period.yaml \
    --policy-a experiments/castro/policies/exp2_bank_a.json \
    --policy-b experiments/castro/policies/exp2_bank_b.json \
    --results-dir experiments/castro/results/exp2_12period \
    --seeds 10 \
    --max-iter 25 \
    --model claude-sonnet-4-20250514
```

### Run Experiment 3: Joint Learning

```bash
# Copy seed policies
cp experiments/castro/policies/joint_policy.json experiments/castro/policies/exp3_joint.json

# For joint learning, both banks use the same policy
python experiments/castro/scripts/optimizer.py \
    --scenario experiments/castro/configs/castro_joint.yaml \
    --policy-a experiments/castro/policies/exp3_joint.json \
    --policy-b experiments/castro/policies/exp3_joint.json \
    --results-dir experiments/castro/results/exp3_joint \
    --seeds 10 \
    --max-iter 25 \
    --model claude-sonnet-4-20250514
```

---

## Step 8: Analyze Results

Create `experiments/castro/scripts/analyze_results.py`:

```python
#!/usr/bin/env python3
"""Analyze Castro experiment results."""

import json
from pathlib import Path
import matplotlib.pyplot as plt


def load_results(results_dir: Path) -> dict:
    """Load final results from an experiment."""
    final_path = results_dir / "final_results.json"
    with open(final_path) as f:
        return json.load(f)


def plot_convergence(results_dir: Path, title: str):
    """Plot cost convergence over iterations."""
    results = load_results(results_dir)
    costs = results["cost_progression"]

    plt.figure(figsize=(10, 6))
    plt.plot(range(len(costs)), costs, 'b-o', linewidth=2, markersize=6)
    plt.xlabel('Iteration', fontsize=12)
    plt.ylabel('Total System Cost ($)', fontsize=12)
    plt.title(f'Cost Convergence: {title}', fontsize=14)
    plt.grid(True, alpha=0.3)

    # Add convergence line
    if results.get("converged"):
        plt.axhline(y=costs[-1], color='g', linestyle='--', alpha=0.7,
                   label=f'Final: ${costs[-1]:.2f}')
        plt.legend()

    plt.tight_layout()
    plt.savefig(results_dir / "convergence.png", dpi=150)
    plt.close()


def compare_experiments():
    """Compare results across all experiments."""
    base_dir = Path("experiments/castro/results")

    experiments = {
        "2-Period": base_dir / "exp1_2period",
        "12-Period": base_dir / "exp2_12period",
        "Joint": base_dir / "exp3_joint"
    }

    print("=" * 60)
    print("Castro Replication Experiment Results")
    print("=" * 60)

    for name, path in experiments.items():
        if not path.exists():
            print(f"\n{name}: Not run yet")
            continue

        results = load_results(path)

        print(f"\n{name} Experiment:")
        print(f"  Iterations: {results['total_iterations']}")
        print(f"  Converged: {results['converged']}")
        print(f"  Final cost: ${results['final_metrics']['total_cost_mean']:.2f} "
              f"± ${results['final_metrics']['total_cost_std']:.2f}")
        print(f"  Settlement rate: {results['final_metrics']['settlement_rate_mean']*100:.1f}%")

        # Generate convergence plot
        plot_convergence(path, name)
        print(f"  Convergence plot saved to {path}/convergence.png")


if __name__ == "__main__":
    compare_experiments()
```

Run analysis:

```bash
python experiments/castro/scripts/analyze_results.py
```

---

## Step 9: Compare with Castro et al. Results

### Expected Results (from paper)

| Experiment | Castro RL Result | Target for LLM |
|------------|------------------|----------------|
| 2-Period Nash | $R_A=0$, $R_B=2000$ | Within 10% |
| 12-Period | Convergence ~50 episodes | <25 iterations |
| Joint | Adapts to delay cost | Qualitatively similar |

### Validation Checklist

For **Experiment 1 (2-Period)**:
- [ ] Bank A converges to near-zero initial liquidity
- [ ] Bank B converges to ~$200 initial liquidity (covers $150+$50)
- [ ] Final costs match Nash equilibrium

For **Experiment 2 (12-Period)**:
- [ ] Both banks reduce costs from baseline
- [ ] Policies stabilize (low variance in final iterations)
- [ ] Settlement rate remains >95%

For **Experiment 3 (Joint)**:
- [ ] When delay cheap: Lower initial liquidity, more holding
- [ ] When delay expensive: Higher initial liquidity, faster release

---

## Step 10: Extend Experiments

### Ablation: Different LLM Models

```bash
# Run with Haiku (faster, cheaper)
python experiments/castro/scripts/optimizer.py \
    --scenario experiments/castro/configs/castro_2period.yaml \
    --policy-a experiments/castro/policies/ablation_a.json \
    --policy-b experiments/castro/policies/ablation_b.json \
    --results-dir experiments/castro/results/ablation_haiku \
    --model claude-3-5-haiku-20241022

# Run with Opus (highest capability)
python experiments/castro/scripts/optimizer.py \
    --scenario experiments/castro/configs/castro_2period.yaml \
    --policy-a experiments/castro/policies/ablation_a.json \
    --policy-b experiments/castro/policies/ablation_b.json \
    --results-dir experiments/castro/results/ablation_opus \
    --model claude-opus-4-20250514
```

### Ablation: Delay Cost Sensitivity

Modify `castro_joint.yaml` to test different delay costs:

```bash
# Create variants
for rd in 0.05 0.1 0.15 0.2 0.3; do
    sed "s/delay_cost_per_tick_per_cent: 0.00067/delay_cost_per_tick_per_cent: $rd/" \
        experiments/castro/configs/castro_joint.yaml > \
        experiments/castro/configs/castro_joint_rd_${rd}.yaml
done

# Run each variant
for rd in 0.05 0.1 0.15 0.2 0.3; do
    python experiments/castro/scripts/optimizer.py \
        --scenario experiments/castro/configs/castro_joint_rd_${rd}.yaml \
        --policy-a experiments/castro/policies/rd_${rd}_a.json \
        --policy-b experiments/castro/policies/rd_${rd}_b.json \
        --results-dir experiments/castro/results/delay_sensitivity_${rd} \
        --max-iter 15
done
```

---

## Troubleshooting

### Common Issues

1. **"Simulation failed" errors**
   ```bash
   # Check if policies are valid
   .venv/bin/payment-sim validate-policy path/to/policy.json --verbose
   ```

2. **LLM generates invalid JSON**
   - The optimizer retries with previous policy
   - Check `experiments/castro/results/*/iteration_*.json` for history

3. **Costs not decreasing**
   - Try different seed policies
   - Increase `--max-iter`
   - Use more capable model (Opus)

4. **Out of API credits**
   - Use `claude-3-5-haiku-20241022` for development
   - Switch to `claude-sonnet-4-20250514` for final runs

### Debug Mode

Add verbose output to optimizer:

```python
# In optimizer.py, add after LLM call:
print(f"LLM Response:\n{llm_text[:500]}...")
```

---

## Summary

This guide covers:

1. **Environment setup** - SimCash installation and validation
2. **Scenario creation** - Three experiments matching Castro et al.
3. **Policy templates** - Seed policies for LLM optimization
4. **LLM harness** - Python script for iterative optimization
5. **Baseline runs** - Reference points for comparison
6. **Experiment execution** - Step-by-step commands
7. **Analysis** - Scripts to compare results
8. **Extensions** - Ablation studies for deeper analysis

Expected time to run all experiments: ~2-4 hours (depending on LLM API latency)
Expected API cost: ~$10-30 (using Sonnet model)

---

*Last updated: 2025-11-30*
